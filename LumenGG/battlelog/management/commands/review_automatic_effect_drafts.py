import copy
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from battlelog.game.catalog import _card_snapshot, effect_source_digest
from battlelog.game.drafts import build_effect_draft
from battlelog.game.review import review_automatic_definition
from battlelog.game.schema import validate_effect_definition
from battlelog.management.console import console_safe_json
from card.models import Card
from qna.models import QNARelation


def _review_evidence_issues(definition, *, card_has_text):
    """Return publication-blocking evidence gaps before a draft is stored."""
    return [
        issue for issue in validate_effect_definition(
            definition,
            require_coverage=True,
            card_has_text=card_has_text,
        )
        if issue.path.startswith('$.review_evidence')
        or issue.code == 'missing_ability_review'
    ]


class Command(BaseCommand):
    help = (
        'Build every unreviewed draft and run three deterministic situations '
        'for each simple or bounded card-choice effect. Uncertain cards remain pending.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument(
            '--card-code', action='append', default=[],
            help='Review only this exact card code. May be repeated.',
        )
        parser.add_argument(
            '--verbose', action='store_true',
            help='Include every pending card and reason in the JSON output.',
        )
        parser.add_argument(
            '--recheck-reviewed', action='store_true',
            help=(
                'Re-run current reviewed definitions against the latest '
                'scenario reviewer. Failed definitions return to draft state.'
            ),
        )
        parser.add_argument(
            '--rebuild-reviewed', action='store_true',
            help=(
                'Rebuild selected reviewed definitions from the current '
                'compiler, then review the rebuilt result. Use this after a '
                'card-specific compiler correction.'
            ),
        )

    def handle(self, *args, **options):
        if options['recheck_reviewed'] and options['rebuild_reviewed']:
            raise CommandError(
                '--recheck-reviewed and --rebuild-reviewed cannot be used together.'
            )
        cards = list(Card.objects.prefetch_related('qna').order_by('id'))
        requested_codes = {
            str(code or '').strip() for code in options['card_code']
            if str(code or '').strip()
        }
        if requested_codes:
            existing_codes = {str(card.code or '') for card in cards}
            unknown_codes = sorted(requested_codes - existing_codes)
            if unknown_codes:
                raise CommandError(
                    f'Unknown card code(s): {", ".join(unknown_codes)}'
                )
            cards = [card for card in cards if card.code in requested_codes]
        qna_ids_by_card = {card.id: [] for card in cards}
        for card_id, qna_id in QNARelation.objects.filter(
            card_id__in=qna_ids_by_card,
        ).values_list('card_id', 'qna_id'):
            qna_ids_by_card.setdefault(card_id, []).append(qna_id)

        counts = Counter()
        reviewed_codes = []
        rechecked_reviewed_codes = []
        recheck_failed_codes = []
        rebuilt_reviewed_codes = []
        pending = []
        updates = []
        for card in cards:
            current = card.effect_definition or {}
            was_reviewed = current.get('reviewed') is True
            if was_reviewed and not options['rebuild_reviewed']:
                if options['recheck_reviewed']:
                    normalized = copy.deepcopy(current)
                    result = review_automatic_definition(
                        normalized,
                        card_has_text=bool((card.text or '').strip()),
                        card_snapshot=_card_snapshot(card),
                    )
                    normalized['review_evidence'] = result.as_dict()
                    evidence_issues = (
                        _review_evidence_issues(
                            normalized,
                            card_has_text=bool((card.text or '').strip()),
                        )
                        if result.passed else []
                    )
                    if result.passed and not evidence_issues:
                        counts['rechecked_reviewed'] += 1
                        rechecked_reviewed_codes.append(card.code)
                        normalized['draft'] = False
                        for ability in normalized.get('abilities') or []:
                            ability['draft'] = False
                    else:
                        if evidence_issues:
                            counts['invalid_review_evidence'] += 1
                        counts['recheck_failed'] += 1
                        recheck_failed_codes.append(card.code)
                        counts['pending_manual_review'] += 1
                        normalized['reviewed'] = False
                        normalized['draft'] = True
                        for ability in normalized.get('abilities') or []:
                            ability['draft'] = True
                        pending.append({
                            'code': card.code,
                            'reason': result.reason or (
                                '능력별 자동 검토 증거가 게시 기준을 충족하지 않습니다.'
                            ),
                        })
                    if normalized != current and options['apply']:
                        card.effect_definition = normalized
                        card.effect_revision = int(card.effect_revision or 0) + 1
                        card.effect_updated_at = timezone.now()
                        updates.append(card)
                    continue
                evidence_issues = _review_evidence_issues(
                    current,
                    card_has_text=bool((card.text or '').strip()),
                )
                if evidence_issues:
                    counts['invalid_review_evidence'] += 1
                    counts['pending_manual_review'] += 1
                    reason = (
                        '저장된 검토 증거가 능력별 3개 결정적 상황 '
                        '기준을 충족하지 않습니다.'
                    )
                    pending.append({'code': card.code, 'reason': reason})
                    if options['apply']:
                        normalized = copy.deepcopy(current)
                        normalized['reviewed'] = False
                        normalized['draft'] = True
                        for ability in normalized.get('abilities') or []:
                            ability['draft'] = True
                        card.effect_definition = normalized
                        card.effect_revision = int(card.effect_revision or 0) + 1
                        card.effect_updated_at = timezone.now()
                        updates.append(card)
                    continue
                counts['preserved_reviewed'] += 1
                normalized = copy.deepcopy(current)
                normalized['draft'] = False
                for ability in normalized.get('abilities') or []:
                    ability['draft'] = False
                if normalized != current:
                    counts['normalized_reviewed'] += 1
                    if options['apply']:
                        card.effect_definition = normalized
                        card.effect_revision = int(card.effect_revision or 0) + 1
                        card.effect_updated_at = timezone.now()
                        updates.append(card)
                continue
            definition = build_effect_draft(
                card.code, card.text or '', detail_text=card.detail_text or '',
                qna_ids=qna_ids_by_card.get(card.id) or [],
            )
            result = review_automatic_definition(
                definition, card_has_text=bool((card.text or '').strip()),
                card_snapshot=_card_snapshot(card),
            )
            definition['review_evidence'] = result.as_dict()
            definition['reviewed'] = bool(result.passed)
            evidence_issues = (
                _review_evidence_issues(
                    definition,
                    card_has_text=bool((card.text or '').strip()),
                )
                if result.passed else []
            )
            if result.passed and not evidence_issues:
                definition['draft'] = False
                definition['source_digest'] = effect_source_digest(card)
                for ability in definition.get('abilities') or []:
                    ability['draft'] = False
                if was_reviewed:
                    rebuilt_reviewed_codes.append(card.code)
                    counts['rebuilt_reviewed'] += 1
                else:
                    reviewed_codes.append(card.code)
                    counts['automatic_reviewed'] += 1
            else:
                if evidence_issues:
                    counts['invalid_review_evidence'] += 1
                definition['reviewed'] = False
                definition['draft'] = True
                pending.append({
                    'code': card.code,
                    'reason': result.reason or (
                        '능력별 자동 검토 증거가 게시 기준을 충족하지 않습니다.'
                    ),
                })
                counts['pending_manual_review'] += 1
            if options['apply']:
                card.effect_definition = copy.deepcopy(definition)
                card.effect_revision = int(card.effect_revision or 0) + 1
                card.effect_updated_at = timezone.now()
                updates.append(card)

        if options['apply'] and updates:
            with transaction.atomic():
                Card.objects.bulk_update(
                    updates,
                    ['effect_definition', 'effect_revision', 'effect_updated_at'],
                    batch_size=100,
                )

        report = {
            'applied': bool(options['apply']),
            'card_count': len(cards),
            **dict(counts),
            'automatic_reviewed_codes': reviewed_codes,
            **(
                {'rechecked_reviewed_codes': rechecked_reviewed_codes}
                if options['recheck_reviewed'] else {}
            ),
            **(
                {'recheck_failed_codes': recheck_failed_codes}
                if options['recheck_reviewed'] else {}
            ),
            **(
                {'rebuilt_reviewed_codes': rebuilt_reviewed_codes}
                if options['rebuild_reviewed'] else {}
            ),
            'pending_reason_counts': dict(Counter(
                item['reason'] for item in pending
            )),
        }
        if options['verbose']:
            report['pending'] = pending
        self.stdout.write(console_safe_json(report, self.stdout))
