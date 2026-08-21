import json
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from battlelog.game.catalog import EXPECTED_CARD_COUNT
from battlelog.game.drafts import build_effect_draft
from card.models import Card
from qna.models import QNARelation


def _effect_nodes(value):
    if isinstance(value, dict):
        if value.get('op'):
            yield value
        for nested in value.values():
            yield from _effect_nodes(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _effect_nodes(nested)


class Command(BaseCommand):
    help = 'Read-only audit of generated DSL coverage against every catalog card.'

    def add_arguments(self, parser):
        parser.add_argument('--allow-incomplete-catalog', action='store_true')

    def handle(self, *args, **options):
        rows = list(Card.objects.order_by('id').values('id', 'code', 'text', 'detail_text'))
        qna_ids_by_card = {row['id']: [] for row in rows}
        for card_id, qna_id in QNARelation.objects.filter(
            card_id__in=qna_ids_by_card,
        ).order_by('card_id', 'qna_id').values_list('card_id', 'qna_id'):
            qna_ids_by_card.setdefault(card_id, []).append(qna_id)
        operation_counts = Counter()
        static_rule_counts = Counter()
        uncompiled = []
        unresolved = []
        ability_count = 0
        ability_card_count = 0
        static_only_count = 0

        for row in rows:
            definition = build_effect_draft(
                row['code'], row['text'],
                detail_text=row['detail_text'],
                qna_ids=qna_ids_by_card.get(row['id']) or [],
            )
            abilities = definition.get('abilities') or []
            ability_count += len(abilities)
            ability_card_count += bool(abilities)
            for ability in abilities:
                if not ability.get('draft_compiled'):
                    uncompiled.append({
                        'card_id': row['id'], 'card_code': row['code'],
                        'ability_id': ability.get('id'),
                    })
                nodes = list(_effect_nodes(ability.get('effects') or []))
                operations = {node.get('op') for node in nodes}
                operation_counts.update(node.get('op') for node in nodes)
                for node in nodes:
                    if node.get('op') == 'static_rule':
                        static_rule_counts.update(node.get('rules') or [])
                    if (
                        node.get('op') == 'log'
                        and (node.get('draft') or '[미구현' in str(node.get('text') or ''))
                    ):
                        unresolved.append({
                            'card_id': row['id'], 'card_code': row['code'],
                            'ability_id': ability.get('id'),
                            'text': str(node.get('text') or '')[:300],
                        })
                if operations == {'static_rule'}:
                    static_only_count += 1

        catalog_complete = len(rows) == EXPECTED_CARD_COUNT
        report = {
            'is_complete': (
                (catalog_complete or options['allow_incomplete_catalog'])
                and not uncompiled and not unresolved
            ),
            'card_count': len(rows),
            'expected_card_count': EXPECTED_CARD_COUNT,
            'cards_with_text': sum(bool((row['text'] or '').strip()) for row in rows),
            'cards_with_detail_text': sum(bool((row['detail_text'] or '').strip()) for row in rows),
            'cards_with_qna': sum(bool(qna_ids_by_card.get(row['id'])) for row in rows),
            'source_review_card_count': sum(bool(
                (row['text'] or '').strip()
                or (row['detail_text'] or '').strip()
                or qna_ids_by_card.get(row['id'])
            ) for row in rows),
            'ability_card_count': ability_card_count,
            'ability_count': ability_count,
            'static_only_ability_count': static_only_count,
            'operation_counts': dict(sorted(operation_counts.items())),
            'static_rule_counts': dict(sorted(static_rule_counts.items())),
            'uncompiled_count': len(uncompiled),
            'unresolved_count': len(unresolved),
            'uncompiled': uncompiled,
            'unresolved': unresolved,
        }
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        if not report['is_complete']:
            raise CommandError(
                '효과 초안 감사 실패: '
                f'cards={len(rows)}/{EXPECTED_CARD_COUNT}, '
                f'uncompiled={len(uncompiled)}, unresolved={len(unresolved)}'
            )
