"""Validation and immutable publication of automatic-game rulesets."""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from card.models import Card, Character

from ..models import RulesetRelease
from .card_identity import PASSIVE_CARD_TYPE, is_passive_card_code
from .handlers import handler_has_deterministic_tests, registered_handler_names, run_handler_deterministic_tests
from .deck_rules import deck_rules_from_card_snapshots, merge_deck_rules
from .rules_v1 import CORE_RULES_V1
from .schema import validate_effect_definition
from .spec import (
    CORE_RULE_SOURCES,
    EFFECT_SCHEMA_VERSION,
    ENGINE_SCHEMA_VERSION,
    RULEBOOK_FILENAME,
    RULEBOOK_PAGE_COUNT,
    RULEBOOK_SHA256,
)


CARD_RUNTIME_FIELDS = (
    'id', 'code', 'name', 'type', 'text', 'detail_text', 'frame', 'damage', 'pos', 'body',
    'special', 'hit', 'guard', 'counter', 'g_top', 'g_mid', 'g_bot',
    'ultimate', 'character_id', 'keyword', 'hiddenKeyword', 'search',
)
EXPECTED_CARD_COUNT = 453


@dataclass
class CatalogValidationReport:
    card_count: int = 0
    ability_count: int = 0
    reviewed_card_count: int = 0
    ability_card_count: int = 0
    no_effect_card_count: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def is_valid(self):
        return not self.errors

    def as_dict(self):
        denominator = self.card_count or EXPECTED_CARD_COUNT
        return {
            'is_valid': self.is_valid,
            'card_count': self.card_count,
            'ability_count': self.ability_count,
            'reviewed_card_count': self.reviewed_card_count,
            'remaining_card_count': max(0, denominator - self.reviewed_card_count),
            'review_progress_percent': round(
                self.reviewed_card_count * 100 / max(1, denominator), 1,
            ),
            'ability_card_count': self.ability_card_count,
            'no_effect_card_count': self.no_effect_card_count,
            'errors': self.errors,
            'warnings': self.warnings,
        }


class RulesetPublicationError(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__('전체 카드 효과 검증을 통과하지 못했습니다.')


def verify_rulebook_source(path=None):
    source_path = Path(path) if path else Path(settings.BASE_DIR) / '.temp' / RULEBOOK_FILENAME
    if not source_path.is_file():
        raise ValueError(f'기준 룰북 파일을 찾을 수 없습니다: {source_path}')
    digest = hashlib.sha256()
    with source_path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    actual = digest.hexdigest().upper()
    if actual != RULEBOOK_SHA256:
        raise ValueError(f'기준 룰북 SHA-256이 다릅니다: {actual}')
    try:
        from pypdf import PdfReader
        actual_pages = len(PdfReader(source_path).pages)
    except Exception as exc:
        raise ValueError(f'기준 룰북 페이지 수를 확인할 수 없습니다: {exc}') from exc
    if actual_pages != RULEBOOK_PAGE_COUNT:
        raise ValueError(
            f'기준 룰북 페이지 수가 다릅니다: {actual_pages} '
            f'(예상 {RULEBOOK_PAGE_COUNT})'
        )
    return {'path': str(source_path), 'sha256': actual, 'pages': actual_pages}


def _json_hash(value):
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def effect_source_digest_values(*, code='', text='', detail_text='', qnas=None):
    """Hash every mutable source that can change a reviewed card ruling."""
    qna_payload = []
    for item in qnas or []:
        getter = item.get if isinstance(item, dict) else lambda key, default=None: getattr(item, key, default)
        created_at = getter('created_at')
        qna_payload.append({
            'id': getter('id'),
            'title': getter('title', '') or '',
            'question': getter('question', '') or '',
            'answer': getter('answer', '') or '',
            'created_at': created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at or ''),
        })
    qna_payload.sort(key=lambda item: (int(item.get('id') or 0), item.get('created_at') or ''))
    return _json_hash({
        'code': str(code or ''),
        'text': str(text or ''),
        'detail_text': str(detail_text or ''),
        'qnas': qna_payload,
    })


def general_qna_ids_from_definition(definition):
    if not isinstance(definition, dict):
        return set()
    source_groups = [definition.get('source_refs') or {}]
    source_groups.extend(
        ability.get('source_refs') or {}
        for ability in definition.get('abilities') or []
        if isinstance(ability, dict)
    )
    return {
        int(qna_id)
        for sources in source_groups
        for qna_id in sources.get('general_qna_ids') or []
        if isinstance(qna_id, int) and qna_id > 0
    }


def effect_source_qnas(card, *, definition=None, linked_qnas=None):
    from qna.models import QNA

    definition = definition if isinstance(definition, dict) else (card.effect_definition or {})
    linked = list(linked_qnas) if linked_qnas is not None else list(
        card.qna.all().order_by('id')
    )
    linked_ids = {item.id for item in linked}
    general_ids = general_qna_ids_from_definition(definition) - linked_ids
    general = list(QNA.objects.filter(id__in=general_ids).order_by('id'))
    return linked + general


def effect_source_digest(card, qnas=None):
    if qnas is None:
        qnas = effect_source_qnas(card)
    return effect_source_digest_values(
        code=card.code,
        text=card.text,
        detail_text=card.detail_text,
        qnas=qnas,
    )


def _card_snapshot(card):
    payload = {field: getattr(card, field) for field in CARD_RUNTIME_FIELDS}
    if is_passive_card_code(payload.get('code')):
        payload['type'] = PASSIVE_CARD_TYPE
    payload['effect_revision'] = int(card.effect_revision or 1)
    payload['effect_updated_at'] = card.effect_updated_at.isoformat() if card.effect_updated_at else None
    payload['effect_definition'] = card.effect_definition or {}
    return payload


def _character_snapshot(character):
    return {
        'id': character.id,
        'key': character.localization_key,
        'name': character.name,
        'datas': character.datas or {},
        'img': character.img,
        'sd_img': character.sd_img,
        'icon_img': character.icon_img,
        'body_img': character.body_img,
        'color': character.color,
    }


def validate_catalog(cards=None, *, require_coverage=True):
    cards = list(cards if cards is not None else Card.objects.select_related('character').order_by('id'))
    report = CatalogValidationReport(card_count=len(cards))
    qna_sources_by_card = {card.id: [] for card in cards}
    general_qna_ids_by_card = {
        card.id: general_qna_ids_from_definition(card.effect_definition or {})
        for card in cards
    }
    general_qna_by_id = {}
    if require_coverage and cards:
        from qna.models import QNARelation
        from qna.models import QNA

        source_relations = QNARelation.objects.filter(
            card_id__in=qna_sources_by_card,
        ).select_related('qna').order_by('card_id', 'qna_id')
        for relation in source_relations:
            qna_sources_by_card.setdefault(relation.card_id, []).append(relation.qna)
        requested_general_ids = set().union(*general_qna_ids_by_card.values())
        general_qna_by_id = {
            item.id: item for item in QNA.objects.filter(id__in=requested_general_ids)
        }
    if require_coverage and report.card_count != EXPECTED_CARD_COUNT:
        report.errors.append({
            'path': '$.cards',
            'message': f'전체 {EXPECTED_CARD_COUNT}장이 필요합니다. (현재 {report.card_count}장)',
            'code': 'incomplete_catalog',
        })
    codes = set()
    qna_references = []
    handler_names = registered_handler_names()
    for handler_name in handler_names:
        for failure in run_handler_deterministic_tests(handler_name):
            report.errors.append({
                'path': '$.handlers', 'message': f'{handler_name}: {failure}',
                'code': 'handler_test_failed',
            })
    for card in cards:
        code = str(card.code or '').strip()
        if not code:
            report.errors.append({'card_id': card.id, 'card': card.name, 'path': '$.code', 'message': '자동 규칙 릴리스에는 카드 코드가 필요합니다.', 'code': 'missing_code'})
        elif code in codes:
            report.errors.append({'card_id': card.id, 'card': card.name, 'path': '$.code', 'message': f'카드 코드가 중복되었습니다: {code}', 'code': 'duplicate_code'})
        codes.add(code)
        definition = card.effect_definition or {}
        qna_sources = qna_sources_by_card.get(card.id) or []
        digest_qna_sources = list(qna_sources)
        linked_qna_ids = {item.id for item in qna_sources}
        digest_qna_sources.extend(
            general_qna_by_id[qna_id]
            for qna_id in sorted(general_qna_ids_by_card.get(card.id) or [])
            if qna_id in general_qna_by_id and qna_id not in linked_qna_ids
        )
        has_mutable_sources = bool(
            (card.text or '').strip()
            or (card.detail_text or '').strip()
            or digest_qna_sources
        )
        if require_coverage and has_mutable_sources:
            source_digest = str(definition.get('source_digest') or '')
            expected_source_digest = effect_source_digest(card, digest_qna_sources)
            if not source_digest:
                report.errors.append({
                    'card_id': card.id, 'card_code': card.code, 'card': card.name,
                    'path': '$.source_digest',
                    'message': '검토한 카드 원문·보충 설명·Q&A의 출처 해시가 필요합니다.',
                    'code': 'missing_source_digest',
                })
            elif source_digest != expected_source_digest:
                report.errors.append({
                    'card_id': card.id, 'card_code': card.code, 'card': card.name,
                    'path': '$.source_digest',
                    'message': '카드 원문·보충 설명 또는 Q&A가 검토 후 변경되었습니다.',
                    'code': 'stale_source_digest',
                })
        if definition.get('reviewed') is True:
            report.reviewed_card_count += 1
        if definition.get('no_effect') is True:
            report.no_effect_card_count += 1
        if definition.get('abilities'):
            report.ability_card_count += 1
        source_groups = [definition.get('source_refs') or {}]
        source_groups.extend(
            ability.get('source_refs') or {}
            for ability in definition.get('abilities') or []
            if isinstance(ability, dict)
        )
        referenced_qna_ids = set()
        for sources in source_groups:
            for qna_id in sources.get('qna_ids') or []:
                qna_references.append((card, qna_id, True))
                referenced_qna_ids.add(qna_id)
            for qna_id in sources.get('general_qna_ids') or []:
                qna_references.append((card, qna_id, False))
                # A general ruling may also remain linked from the card page
                # for reviewer discoverability.  Either source bucket counts
                # as an explicit reference; only ``qna_ids`` requires the
                # relation to exist.
                referenced_qna_ids.add(qna_id)
        if require_coverage and (card.text or '').strip() and not any(
            sources.get('card_text') is True for sources in source_groups
        ):
            report.errors.append({
                'card_id': card.id, 'card_code': card.code, 'card': card.name,
                'path': '$.source_refs.card_text',
                'message': '카드 원문이 출처에 포함되어야 합니다.',
                'code': 'missing_card_text_reference',
            })
        if require_coverage and (card.detail_text or '').strip() and not any(
            sources.get('detail_text') is True for sources in source_groups
        ):
            report.errors.append({
                'card_id': card.id, 'card_code': card.code, 'card': card.name,
                'path': '$.source_refs.detail_text',
                'message': '보충 설명이 출처에 포함되어야 합니다.',
                'code': 'missing_detail_text_reference',
            })
        related_qna_ids = {item.id for item in qna_sources}
        missing_qna_ids = sorted(related_qna_ids - referenced_qna_ids)
        if require_coverage and missing_qna_ids:
            report.errors.append({
                'card_id': card.id, 'card_code': card.code, 'card': card.name,
                'path': '$.source_refs.qna_ids',
                'message': f'연결된 Q&A가 출처에서 누락되었습니다: {missing_qna_ids}',
                'code': 'missing_linked_qna_reference',
            })
        for ability in definition.get('abilities') or []:
            if isinstance(ability, dict) and ability.get('handler') and not handler_has_deterministic_tests(ability['handler']):
                report.errors.append({
                    'card_id': card.id, 'card_code': card.code, 'card': card.name,
                    'path': '$.abilities.handler', 'message': f'{ability["handler"]}: 결정적 테스트가 등록되지 않았습니다.',
                    'code': 'handler_tests_missing',
                })
        report.ability_count += len(definition.get('abilities') or []) if isinstance(definition, dict) else 0
        issues = validate_effect_definition(
            definition,
            require_coverage=require_coverage,
            card_has_text=bool((card.text or '').strip()),
            handler_names=handler_names,
        )
        for issue in issues:
            report.errors.append({
                'card_id': card.id,
                'card_code': card.code,
                'card': card.name,
                **issue.as_dict(),
            })
    if qna_references:
        from qna.models import QNA, QNARelation

        requested_ids = {qna_id for _card, qna_id, _linked in qna_references}
        existing_ids = set(QNA.objects.filter(id__in=requested_ids).values_list('id', flat=True))
        related_pairs = set(QNARelation.objects.filter(qna_id__in=requested_ids).values_list('card_id', 'qna_id'))
        for card, qna_id, requires_relation in qna_references:
            if qna_id not in existing_ids:
                report.errors.append({
                    'card_id': card.id, 'card_code': card.code, 'card': card.name,
                    'path': (
                        '$.source_refs.qna_ids' if requires_relation
                        else '$.source_refs.general_qna_ids'
                    ),
                    'message': f'존재하지 않는 Q&A입니다: {qna_id}',
                    'code': 'missing_qna',
                })
            elif requires_relation and (card.id, qna_id) not in related_pairs:
                report.errors.append({
                    'card_id': card.id, 'card_code': card.code, 'card': card.name,
                    'path': '$.source_refs.qna_ids', 'message': f'카드와 연결되지 않은 Q&A입니다: {qna_id}',
                    'code': 'unrelated_qna',
                })
    return report


def build_ruleset_snapshot(cards=None, characters=None):
    cards = list(cards if cards is not None else Card.objects.select_related('character').order_by('id'))
    characters = list(characters if characters is not None else Character.objects.order_by('id'))
    card_snapshots = {str(card.code): _card_snapshot(card) for card in cards}
    character_snapshots = {}
    for character in characters:
        payload = _character_snapshot(character)
        configured = ((character.datas or {}).get('automatic_deck_rules') or {})
        deck_rules = merge_deck_rules(
            configured,
            deck_rules_from_card_snapshots(card_snapshots, character.id),
        )
        if deck_rules:
            payload['deck_rules'] = deck_rules
        character_snapshots[str(character.id)] = payload
    return {
        'engine_schema_version': ENGINE_SCHEMA_VERSION,
        'effect_schema_version': EFFECT_SCHEMA_VERSION,
        'rulebook': {
            'filename': RULEBOOK_FILENAME,
            'sha256': RULEBOOK_SHA256,
            'pages': RULEBOOK_PAGE_COUNT,
        },
        'core_rule_sources': CORE_RULE_SOURCES,
        'core_rules': CORE_RULES_V1,
        'characters': character_snapshots,
        'cards': card_snapshots,
    }


def active_ruleset_release():
    return RulesetRelease.objects.filter(is_active=True).order_by('-published_at', '-id').first()


@transaction.atomic
def publish_ruleset_release(version, *, user=None, activate=True):
    rulebook = verify_rulebook_source()
    cards = list(Card.objects.select_related('character').prefetch_related('qna').order_by('id'))
    report = validate_catalog(cards, require_coverage=True)
    if not report.is_valid:
        raise RulesetPublicationError(report)
    snapshot = build_ruleset_snapshot(cards)
    content_hash = _json_hash(snapshot)
    source_manifest = {
        'precedence': [
            'errata_or_detail_text', 'card_specific_qna', 'card_text',
            'master_rulebook', 'general_qna',
        ],
        'rulebook_sha256': RULEBOOK_SHA256,
        'rulebook_verified': {'sha256': rulebook['sha256'], 'pages': rulebook['pages']},
        'published_at': timezone.now().isoformat(),
        'validation': report.as_dict(),
    }
    list(RulesetRelease.objects.select_for_update().values_list('id', flat=True))
    release, created = RulesetRelease.objects.get_or_create(
        content_hash=content_hash,
        defaults={
            'version': str(version).strip(),
            'schema_version': EFFECT_SCHEMA_VERSION,
            'source_manifest': source_manifest,
            'snapshot': snapshot,
            'created_by': user if getattr(user, 'is_authenticated', False) else None,
            'is_active': False,
        },
    )
    if not created and release.version != str(version).strip():
        raise ValueError(f'동일한 내용이 이미 {release.version} 버전으로 게시되었습니다.')
    if activate:
        RulesetRelease.objects.filter(is_active=True).exclude(id=release.id).update(is_active=False)
        if not release.is_active:
            release.is_active = True
            release.save(update_fields=['is_active'])
    return release, report
