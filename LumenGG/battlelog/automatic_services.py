"""Database boundary for the deterministic automatic simulator engine."""

import copy
import hashlib
import json
import re
import secrets
import traceback
from dataclasses import dataclass, field
from datetime import timedelta
from functools import lru_cache
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from card.models import Card
from deck.models import CardInDeck

from .game.catalog import EXPECTED_CARD_COUNT, _json_hash, active_ruleset_release
from .game.card_identity import is_passive_card
from .game.ai import DEFAULT_POLICY_VERSION, DEFAULT_POLICY_WEIGHTS, choose_action
from .game.deck_rules import (
    allocate_supplement_counts,
    deck_rules_from_card_snapshots,
    main_size_range,
    merge_deck_rules,
)
from .game.effects import card_matches
from .game.spec import EFFECT_SCHEMA_VERSION, RULEBOOK_SHA256
from .game.engine import AutomaticGameEngine, EngineError, IllegalAction, StaleState
from .models import (
    AutomaticIssueComment,
    AutomaticIssueReport,
    LumenSimulatorSession,
    RulesetRelease,
    SimulatorAIPolicy,
)
from .services import (
    character_hand_table,
    hand_limit_for_hp,
    initial_hp_for_character,
    initial_passive_state_for_character,
)


AUTOMATIC_COMMAND_HISTORY_LIMIT = 3
AUTOMATIC_COMMAND_RESULT_LIMIT = 2000
AUTOMATIC_EVENT_LIMIT = 800
AUTOMATIC_EVENT_KEEP = 500
AUTOMATIC_COMMAND_LOG_LIMIT = 2000
AUTOMATIC_COMMAND_LOG_KEEP = 1000
AUTOMATIC_REWIND_ENABLED = False
DEFAULT_AUTOMATIC_READY_SECONDS = 30
DEFAULT_AUTOMATIC_EFFECT_SECONDS = 60
AUTOMATIC_TIMER_CHOICES = {None, 15, 30, 45, 60, 90, 120}
NEUTRAL_CHARACTER_ID = 1
CHARACTER_MAIN_DECK_EXCEPTIONS = {5: 24, 15: 33, 16: 26, 17: 25}
MIN_AI_POLICY_TRAINING_GAMES = 40
MIN_AI_POLICY_EVALUATION_GAMES = 20
CLIENT_ERROR_DEDUP_SECONDS = 300
CLIENT_ERROR_MAX_DISTINCT_PER_WINDOW = 20
CLIENT_ERROR_MAX_STACK = 4000


class AutomaticModeUnavailable(ValueError):
    pass


class AutomaticRuntimeFailure(EngineError):
    """An engine/DSL fault caused an atomic fallback to manual mode."""


class CommandValidationError(ValueError):
    pass


class ImmutableRulesetSnapshot(dict):
    """Marker for a cached published ruleset that engine code only reads."""

    _automatic_immutable_ruleset = True


@dataclass
class DeckValidationReport:
    side: str
    errors: list = field(default_factory=list)

    @property
    def is_valid(self):
        return not self.errors

    def as_dict(self):
        return {'side': self.side, 'is_valid': self.is_valid, 'errors': self.errors}


def _is_special(card):
    return not is_passive_card(card) and '특수' in str(card.type or '')


def _is_attack(card):
    return not is_passive_card(card) and '공격' in str(card.type or '')


def _is_defense(card):
    return not is_passive_card(card) and '수비' in str(card.type or '')


def _card_definition(card, ruleset=None):
    if ruleset:
        released = ((ruleset.get('cards') or {}).get(str(card.code or '')) or {})
        return released.get('effect_definition') or {}
    return card.effect_definition or {}


def _card_rule_payload(card, ruleset=None):
    definition = _card_definition(card, ruleset)
    code = getattr(card, 'code', '') or ''
    character_id = getattr(card, 'character_id', None)
    released = ((ruleset or {}).get('cards') or {}).get(str(code)) or {}
    character = ((ruleset or {}).get('characters') or {}).get(str(character_id)) or {}
    return {
        'code': code,
        'name': getattr(card, 'name', ''),
        'type': getattr(card, 'type', ''),
        'ultimate': bool(getattr(card, 'ultimate', False)),
        'character_id': character_id,
        'character_key': character.get('key'),
        'token_key': definition.get('token_key'),
        **{key: value for key, value in released.items() if key in {
            'code', 'name', 'type', 'ultimate', 'character_id', 'character_key',
        }},
    }


def _card_same_name_limit(card, default, *, ruleset=None, supplements=None):
    definition = _card_definition(card, ruleset)
    configured = definition.get('deck_limit')
    if isinstance(configured, int) and not isinstance(configured, bool) and configured >= 1:
        default = configured
    payload = _card_rule_payload(card, ruleset)
    for supplement in supplements or []:
        if card_matches(payload, supplement.get('where')):
            configured = supplement.get('same_name_limit')
            if isinstance(configured, int) and not isinstance(configured, bool) and configured >= 1:
                default = max(default, configured)
    text = re.sub(r'\s+', ' ', str(card.text or ''))
    match = re.search(
        r'이 (?:기술|카드)은\s*(?:(\d+)장까지\s*덱에|덱에\s*(\d+)장까지)\s*넣을 수 있다',
        text,
    )
    if match:
        return max(default, int(next(value for value in match.groups() if value)))
    return default


def _character_deck_rules(deck, ruleset=None):
    if ruleset:
        released = ((ruleset.get('characters') or {}).get(str(deck.character_id)) or {})
        return merge_deck_rules(released.get('deck_rules') or {})
    configured = ((deck.character.datas or {}).get('automatic_deck_rules') or {})
    characteristic_cards = Card.objects.filter(
        Q(character_id=deck.character_id),
        Q(type='특성') | Q(code__icontains='PS'),
    ).values('character_id', 'code', 'type', 'effect_definition')
    return merge_deck_rules(
        configured,
        deck_rules_from_card_snapshots(characteristic_cards, deck.character_id),
    )


def validate_automatic_deck(deck, *, side='', ruleset=None):
    """Validate the rulebook setup constraints before automatic play."""
    entries = list(CardInDeck.objects.filter(deck=deck).select_related('card', 'card__character'))
    report = DeckValidationReport(side=side)
    rules = merge_deck_rules(
        _character_deck_rules(deck, ruleset),
        *(
            (_card_definition(entry.card, ruleset) or {}).get(
                'deck_rules_when_included',
            ) or {}
            for entry in entries
            if int(entry.count or 0) > 0
        ),
    )
    has_structured_size = isinstance(rules.get('main_size'), (dict, int))
    if has_structured_size:
        minimum_main_size, maximum_main_size = main_size_range(rules)
    else:
        legacy_size = int(CHARACTER_MAIN_DECK_EXCEPTIONS.get(deck.character_id, 20))
        minimum_main_size = maximum_main_size = legacy_size
    same_name_limit = int(rules.get('same_name_limit', 1))
    character_minimum = int(rules.get('character_card_minimum', 10))
    hand_size = int(rules.get('opening_hand_size', 5))
    list_size = int(rules.get('opening_list_size', 9))

    technique_count = 0
    character_count = 0
    ultimate_count = 0
    hand_count = 0
    list_count = 0
    names = {}
    name_limits = {}
    invalid_marks = []
    supplements = rules.get('supplements') or []
    supplement_counts = [0 for _item in supplements]
    supplement_character_counts = [0 for _item in supplements]
    imported_counts = {}
    imported_rule = rules.get('other_character_cards') or {}
    for entry in entries:
        card = entry.card
        count = max(0, int(entry.count or 0))
        card_payload = _card_rule_payload(card, ruleset)
        matching_supplements = [
            index for index, supplement in enumerate(supplements)
            if card_matches(card_payload, supplement.get('where'))
        ]
        supplement = supplements[matching_supplements[0]] if matching_supplements else {}
        for index in matching_supplements:
            supplement_counts[index] += count
            if card.character_id == deck.character_id:
                supplement_character_counts[index] += count
        allowed_character_ids = set(rules.get('allowed_character_ids') or [deck.character_id, NEUTRAL_CHARACTER_ID])
        imported = (
            card.character_id not in allowed_character_ids
            and card.character_id not in set(imported_rule.get('exclude_character_ids') or [])
            and card.type in set(imported_rule.get('allowed_types') or [])
            and (not imported_rule.get('exclude_ultimate') or not card.ultimate)
        )
        supplement_allows_mark = bool(supplement.get('allow_foreign_mark'))
        if card.character_id not in allowed_character_ids and not imported and not supplement_allows_mark:
            invalid_marks.append(card.name)
        if imported:
            imported_counts[card.character_id] = imported_counts.get(card.character_id, 0) + count
        if card.ultimate:
            ultimate_count += count
            continue
        is_technique = _is_attack(card) or _is_defense(card) or _is_special(card)
        if not is_technique and not supplement.get('allow_non_technique'):
            report.errors.append(f'{card.name}: 기술 덱에는 공격·수비·특수 기술만 넣을 수 있습니다.')
        technique_count += count
        names[card.name] = names.get(card.name, 0) + count
        name_limits[card.name] = max(
            name_limits.get(card.name, same_name_limit),
            _card_same_name_limit(
                card, same_name_limit, ruleset=ruleset, supplements=supplements,
            ),
        )
        if card.character_id == deck.character_id:
            character_count += count
        if _is_special(card):
            special_character_ids = rules.get('special_allowed_character_ids')
            if (
                isinstance(special_character_ids, list)
                and card.character_id not in set(special_character_ids)
            ):
                report.errors.append(
                    f'{card.name}: 이 덱에는 허용된 캐릭터의 특수 기술만 넣을 수 있습니다.'
                )
            # Special techniques count toward the 20-card technique deck, but
            # setup always places them in the side deck (rulebook p20/p37).
            if int(entry.hand or 0) or int(entry.side or 0) != count:
                report.errors.append(f'{card.name}: 특수 기술은 전부 사이드 덱에 있어야 합니다.')
            continue
        raw_hand = max(0, int(entry.hand or 0))
        raw_side = max(0, int(entry.side or 0))
        if raw_hand + raw_side > count:
            report.errors.append(f'{card.name}: 패와 사이드 배치 수가 보유 수량을 초과합니다.')
        allocated_hand = min(count, raw_hand)
        allocated_side = min(count - allocated_hand, raw_side)
        hand_count += allocated_hand
        list_count += count - allocated_hand - allocated_side

    if technique_count < minimum_main_size or technique_count > maximum_main_size:
        expected = (
            f'정확히 {minimum_main_size}장'
            if minimum_main_size == maximum_main_size
            else f'{minimum_main_size}~{maximum_main_size}장'
        )
        report.errors.append(f'기술 카드는 {expected}이어야 합니다. (현재 {technique_count}장)')
    main_size_rule = rules.get('main_size') or {}
    supplement_allocations = [0 for _item in supplements]
    if isinstance(main_size_rule, dict) and main_size_rule.get('base_excludes_supplements'):
        base_size = int(main_size_rule.get('min', 20))
        supplement_allocations = allocate_supplement_counts(
            technique_count, base_size, supplements, supplement_counts,
        )
        supplemental_total = sum(supplement_allocations)
        if technique_count - supplemental_total != int(main_size_rule.get('min', 20)):
            report.errors.append(
                '기본 기술 덱은 보충 카드를 제외하고 '
                f'{int(main_size_rule.get("min", 20))}장이어야 합니다. '
                f'(현재 {technique_count - supplemental_total}장)'
            )
    for index, count in enumerate(supplement_counts):
        maximum = int((supplements[index] or {}).get('max_count') or 0)
        if not (supplements[index] or {}).get('allow_base_copies') and count > maximum:
            report.errors.append(f'보충 카드 제한을 초과했습니다: {count}/{maximum}장')
    imported_maximum = imported_rule.get('max_per_character')
    if isinstance(imported_maximum, int) and not isinstance(imported_maximum, bool):
        exceeded = sorted(
            character_id for character_id, count in imported_counts.items()
            if count > imported_maximum
        )
        if exceeded:
            report.errors.append(
                '타 캐릭터 마크별 카드 제한을 초과했습니다: '
                + ', '.join(
                    f'{character_id}({imported_counts[character_id]}/{imported_maximum}장)'
                    for character_id in exceeded
                )
            )
    duplicates = sorted(name for name, count in names.items() if count > name_limits.get(name, same_name_limit))
    if duplicates:
        details = ', '.join(f'{name}({name_limits.get(name, same_name_limit)}장)' for name in duplicates)
        report.errors.append(f'동일 이름 카드 제한을 초과했습니다: {details}')
    base_character_count = character_count - sum(
        min(supplement_allocations[index], supplement_character_counts[index])
        for index in range(len(supplements))
    )
    if base_character_count < character_minimum:
        report.errors.append(f'캐릭터 마크 기술은 최소 {character_minimum}장이어야 합니다. (현재 {base_character_count}장)')
    if invalid_marks:
        report.errors.append(f'사용할 수 없는 캐릭터 마크가 포함되어 있습니다: {", ".join(sorted(set(invalid_marks)))}')
    if ultimate_count > int(rules.get('ultimate_maximum', 1)):
        report.errors.append('얼티밋 카드는 1장까지만 허용됩니다.')
    if hand_count != hand_size:
        report.errors.append(f'공개할 시작 패는 정확히 {hand_size}장이어야 합니다. (현재 {hand_count}장)')
    if list_count != list_size:
        report.errors.append(f'시작 리스트는 정확히 {list_size}장이어야 합니다. (현재 {list_count}장)')
    return report


def automatic_mode_release():
    """Only a fully validated, active release can expose automatic mode."""
    release = active_ruleset_release()
    validation = ((release.source_manifest or {}).get('validation') or {}) if release else {}
    if not release or not validation.get('is_valid'):
        return None
    snapshot = release.snapshot or {}
    if validation.get('card_count') != EXPECTED_CARD_COUNT:
        return None
    if len(snapshot.get('cards') or {}) != EXPECTED_CARD_COUNT:
        return None
    if release.schema_version != EFFECT_SCHEMA_VERSION:
        return None
    if ((snapshot.get('rulebook') or {}).get('sha256') or '').upper() != RULEBOOK_SHA256:
        return None
    if release.content_hash != _json_hash(snapshot):
        return None
    return release


def _metric_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _metric_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def ai_policy_activation_issues(policy):
    if policy is None:
        return ['AI 정책이 없습니다.']
    issues = []
    if not isinstance(policy.weights, dict) or not policy.weights:
        issues.append('정책 가중치가 없습니다.')
    if _metric_int(policy.training_games) < MIN_AI_POLICY_TRAINING_GAMES:
        issues.append(f'훈련 경기는 최소 {MIN_AI_POLICY_TRAINING_GAMES}회여야 합니다.')
    metrics = policy.metrics if isinstance(policy.metrics, dict) else {}
    evaluation = metrics.get('evaluation') if isinstance(metrics.get('evaluation'), dict) else {}
    evaluated_games = _metric_int(metrics.get('evaluation_games'))
    if not evaluated_games:
        evaluated_games = sum(
            _metric_int(evaluation.get(key))
            for key in ('wins', 'losses', 'draws', 'incomplete')
        )
    if evaluated_games < MIN_AI_POLICY_EVALUATION_GAMES:
        issues.append(f'최종 평가는 최소 {MIN_AI_POLICY_EVALUATION_GAMES}경기여야 합니다.')
    if _metric_int(evaluation.get('incomplete')) != 0:
        issues.append('최종 평가에 미완료 경기가 있습니다.')

    evaluation_promoted = (
        metrics.get('selected') == 'evolved'
        and _metric_float(evaluation.get('score')) > 0.5
    )
    benchmark = metrics.get('baseline_benchmark') if isinstance(metrics.get('baseline_benchmark'), dict) else {}
    benchmark_promoted = (
        _metric_int(benchmark.get('games')) >= MIN_AI_POLICY_EVALUATION_GAMES
        and _metric_int(benchmark.get('incomplete')) == 0
        and _metric_float(benchmark.get('score')) > 0.5
    )
    if not evaluation_promoted and not benchmark_promoted:
        issues.append('기준 정책을 상회한 좌석 교대 평가 증거가 없습니다.')
    return issues


def active_ai_policy():
    policies = SimulatorAIPolicy.objects.filter(is_active=True).order_by('-created_at', '-id')
    return next((policy for policy in policies if not ai_policy_activation_issues(policy)), None)


def ai_policy_payload(policy=None):
    if policy:
        return {
            'id': policy.id,
            'name': policy.name,
            'version': policy.version,
            'weights': copy.deepcopy(policy.weights or DEFAULT_POLICY_WEIGHTS),
            'training_games': policy.training_games,
            'metrics': copy.deepcopy(policy.metrics or {}),
        }
    return {
        'id': None,
        'name': 'Lumen AI',
        'version': DEFAULT_POLICY_VERSION,
        'weights': copy.deepcopy(DEFAULT_POLICY_WEIGHTS),
        'training_games': 0,
        'metrics': {'stage': 'bootstrap'},
    }


def _pin_release_card_data(state, snapshot):
    cards = snapshot.get('cards') or {}
    characters = snapshot.get('characters') or {}
    runtime_fields = (
        'name', 'type', 'text', 'detail_text', 'frame', 'damage', 'pos', 'body', 'special', 'hit',
        'guard', 'counter', 'g_top', 'g_mid', 'g_bot', 'ultimate', 'character_id',
        'keyword', 'hiddenKeyword', 'search',
    )
    for player in (state.get('players') or {}).values():
        character_payload = player.get('character') or {}
        released_character = characters.get(str(character_payload.get('id') or ''))
        if released_character:
            character = SimpleNamespace(
                id=released_character.get('id'),
                name=released_character.get('name') or '',
                datas=copy.deepcopy(released_character.get('datas') or {}),
            )
            initial_hp = initial_hp_for_character(character)
            player['initial_hp'] = initial_hp
            player['hp'] = initial_hp
            player['passive_state'] = initial_passive_state_for_character(character)
            character_payload.update({
                'name': released_character.get('name'),
                'img': released_character.get('body_img') or released_character.get('sd_img') or released_character.get('img'),
                'icon_img': released_character.get('icon_img'),
                'color': released_character.get('color'),
                'hand_table': character_hand_table(character),
            })
            for character_card in (player.get('zones') or {}).get('character') or []:
                character_card.update({
                    'name': released_character.get('name'),
                    'img': character_payload.get('img'),
                    'icon_img': released_character.get('icon_img'),
                    'color': released_character.get('color'),
                })
        for zone_cards in (player.get('zones') or {}).values():
            for card in zone_cards:
                released = cards.get(str(card.get('code') or ''))
                if not released or card.get('kind') == 'character':
                    continue
                for field_name in runtime_fields:
                    card[field_name] = copy.deepcopy(released.get(field_name))
    return state


def automatic_session_settings(
    *, ready_timeout_seconds=DEFAULT_AUTOMATIC_READY_SECONDS,
    effect_timeout_seconds=DEFAULT_AUTOMATIC_EFFECT_SECONDS,
):
    def normalized(value, label):
        if value in (None, '', 'none', 'unlimited', '0', 0):
            return None
        try:
            seconds = int(value)
        except (TypeError, ValueError):
            raise ValueError(f'{label} 제한 시간이 올바르지 않습니다.') from None
        if seconds not in AUTOMATIC_TIMER_CHOICES:
            raise ValueError(f'{label} 제한 시간이 지원 범위를 벗어났습니다.')
        return seconds

    return {
        'ready_timeout_seconds': normalized(
            ready_timeout_seconds, '레디 선택',
        ),
        'effect_timeout_seconds': normalized(
            effect_timeout_seconds, '효과 선택',
        ),
        'auto_advance_empty_phases': True,
        'rewind_enabled': AUTOMATIC_REWIND_ENABLED,
    }


def initialize_automatic_document(base_state, release, *, seed='', settings=None):
    ruleset = copy.deepcopy(release.snapshot or {})
    ruleset['version'] = release.version
    state = _pin_release_card_data(copy.deepcopy(base_state), ruleset)
    engine = AutomaticGameEngine.initialize(
        state, ruleset, now=timezone.now(), seed=seed,
        settings=copy.deepcopy(settings or {}),
    )
    return {
        'initial_state': copy.deepcopy(engine.state),
        'state': copy.deepcopy(engine.state),
        'events': copy.deepcopy(engine.events),
        'archived_event_count': 0,
        'event_archive_hash': '',
        'command_history': [],
        'command_results': [],
        'command_log': [],
        'command_archive_hash': '',
        'audit_log': [],
    }


def ensure_automatic_decks(player1_deck, player2_deck, *, ruleset=None):
    reports = [
        validate_automatic_deck(player1_deck, side='p1', ruleset=ruleset),
        validate_automatic_deck(player2_deck, side='p2', ruleset=ruleset),
    ]
    errors = [error for report in reports for error in report.errors]
    if errors:
        raise ValueError('자동 모드 덱 검증 실패: ' + ' / '.join(errors))
    return reports


def _role_for_command(session, body):
    seat = str(body.get('seat') or '')
    token = str(body.get('seat_token') or '')
    expected = session.player1_token if seat == 'p1' else session.player2_token if seat == 'p2' else ''
    if not expected or not token or not secrets.compare_digest(token, expected):
        raise PermissionDenied()
    return seat


@lru_cache(maxsize=8)
def _cached_ruleset(release_id):
    release = RulesetRelease.objects.only(
        'id', 'version', 'content_hash', 'snapshot',
    ).get(pk=release_id)
    result = ImmutableRulesetSnapshot(copy.deepcopy(release.snapshot or {}))
    result['version'] = release.version
    return result


@receiver(
    [post_save, post_delete], sender=RulesetRelease,
    dispatch_uid='battlelog.clear_automatic_ruleset_cache',
)
def _clear_ruleset_cache_on_release_change(**_kwargs):
    _cached_ruleset.cache_clear()


def _ruleset(session):
    attached = getattr(session, '_automatic_ruleset_cache', None)
    if attached is not None:
        return attached
    if not session.ruleset_release_id:
        raise AutomaticModeUnavailable('자동 세션에 고정된 규칙 릴리스가 없습니다.')
    result = _cached_ruleset(session.ruleset_release_id)
    session._automatic_ruleset_cache = result
    return result


def _command_fingerprint(body):
    allowed = {
        'command_id': body.get('command_id'),
        'seat': body.get('seat'),
        'action_id': body.get('action_id'),
        'selections': body.get('selections') or {},
    }
    raw = json.dumps(allowed, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def _compact_automatic_events(document):
    events = list(document.get('events') or [])
    if len(events) <= AUTOMATIC_EVENT_LIMIT:
        return
    remove = len(events) - AUTOMATIC_EVENT_KEEP
    rewind_boundaries = [
        int(entry.get('event_count_before') or 0)
        for entry in document.get('command_history') or []
    ]
    if rewind_boundaries:
        # Events needed to restore the retained rewind snapshots stay live.
        remove = min(remove, min(rewind_boundaries))
    if remove <= 0:
        return
    archived = events[:remove]
    previous_hash = str(document.get('event_archive_hash') or '')
    raw = json.dumps({'previous': previous_hash, 'events': archived}, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    document['event_archive_hash'] = hashlib.sha256(raw.encode()).hexdigest()
    document['events'] = events[remove:]
    document['archived_event_count'] = int(document.get('archived_event_count') or 0) + remove
    adjusted_history = []
    for entry in document.get('command_history') or []:
        event_count = int(entry.get('event_count_before') or 0)
        if event_count < remove:
            continue
        adjusted_history.append({**entry, 'event_count_before': event_count - remove})
    document['command_history'] = adjusted_history


def _compact_command_log(document):
    commands = list(document.get('command_log') or [])
    if len(commands) <= AUTOMATIC_COMMAND_LOG_LIMIT:
        return
    remove = len(commands) - AUTOMATIC_COMMAND_LOG_KEEP
    archived = commands[:remove]
    previous_hash = str(document.get('command_archive_hash') or '')
    raw = json.dumps({'previous': previous_hash, 'commands': archived}, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    document['command_archive_hash'] = hashlib.sha256(raw.encode()).hexdigest()
    document['archived_command_count'] = int(document.get('archived_command_count') or 0) + remove
    document['command_log'] = commands[remove:]


def _stable_hash(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def _upgrade_automatic_document(document):
    """Apply lightweight runtime defaults and remove retired rewind data."""
    changed = False
    state = document.setdefault('state', {})
    engine = state.setdefault('engine', {})
    settings = engine.setdefault('settings', {})
    defaults = automatic_session_settings()
    for key, value in defaults.items():
        if key not in settings:
            settings[key] = copy.deepcopy(value)
            changed = True
    if settings.get('rewind_enabled'):
        settings['rewind_enabled'] = False
        changed = True
    if document.get('command_history'):
        document['command_history'] = []
        changed = True
    if engine.pop('last_rewindable_command_id', None) is not None:
        changed = True
    if engine.get('rewind_request') is not None:
        engine['rewind_request'] = None
        changed = True
    return changed


def _automatic_document_needs_upgrade(document):
    state = (document or {}).get('state') or {}
    engine = state.get('engine') or {}
    settings = engine.get('settings') or {}
    return bool(
        any(
            key not in settings
            for key in automatic_session_settings()
        )
        or settings.get('rewind_enabled')
        or (document or {}).get('command_history')
        or engine.get('last_rewindable_command_id')
        or engine.get('rewind_request')
    )


def _automatic_document_needs_reconcile(
    document, *, now=None, both_players_disconnected=False,
):
    if _automatic_document_needs_upgrade(document):
        return True
    state = (document or {}).get('state') or {}
    engine = state.get('engine') or {}
    settings = engine.get('settings') or {}
    if (
        settings.get('auto_advance_empty_phases', False)
        and state.get('phase') in {'lumen', 'recovery'}
        and engine.get('step') == 'phase_actions'
    ):
        return True
    clock = engine.get('clock') or {}
    if not clock or clock.get('paused') or both_players_disconnected:
        return False
    deadline = parse_datetime(str(clock.get('deadline') or ''))
    if deadline is None:
        return False
    if timezone.is_naive(deadline):
        deadline = timezone.make_aware(deadline)
    return (now or timezone.now()) >= deadline


def _disclosed_information(events, *, include_private=False):
    disclosure_types = {
        'battle_revealed', 'card_visibility_changed', 'random_resolved',
        'decision_resolved', 'card_moved',
    }
    disclosures = []
    for event in events:
        if event.get('type') not in disclosure_types:
            continue
        private = event.get('visibility') == 'private'
        disclosures.append({
            'type': event.get('type'),
            'actor': event.get('actor'),
            'visibility': event.get('visibility', 'public'),
            'payload': (
                copy.deepcopy(event.get('payload') or {})
                if include_private or not private else {'redacted': True}
            ),
            'created_at': event.get('created_at'),
        })
    return disclosures


def _apply_accepted_rewind(document, current_state, current_events, *, now=None):
    request = ((current_state.get('engine') or {}).get('rewind_request') or {})
    if not request.get('accepted'):
        return current_state, current_events, False
    target_id = request.get('target_command_id')
    history = list(document.get('command_history') or [])
    target_index = next((index for index, item in enumerate(history) if item.get('command_id') == target_id), None)
    if target_index is None:
        raise IllegalAction('되감을 명령 기록이 만료되었습니다.')
    entry = history[target_index]
    event_count = int(entry.get('event_count_before') or 0)
    removed_events = current_events[event_count:]
    restored = copy.deepcopy(entry.get('state_before') or {})
    restored_engine = restored.setdefault('engine', {})
    restored_engine['rewind_request'] = None
    restored_engine['clock'] = None
    restored_engine['command_count'] = int((current_state.get('engine') or {}).get('command_count') or 0)
    applied_at = now or timezone.now()
    audit = {
        'id': str(hashlib.sha256(f'{target_id}:{applied_at.isoformat()}'.encode()).hexdigest()[:32]),
        'type': 'rewind_applied',
        'actor': request.get('answered_by'),
        'payload': {
            'target_command_id': target_id,
            'requested_by': request.get('requested_by'),
            'disclosed_information': _disclosed_information(removed_events, include_private=True),
        },
        'visibility': 'public',
        'created_at': applied_at.isoformat(),
    }
    document.setdefault('audit_log', []).append(copy.deepcopy(audit))
    public_audit = copy.deepcopy(audit)
    public_audit['payload']['disclosed_information'] = _disclosed_information(removed_events)
    document['command_history'] = history[:target_index]
    return restored, [*current_events[:event_count], public_audit], True


def _fallback_to_manual(session_id, failure, command_id):
    with transaction.atomic():
        locked = LumenSimulatorSession.objects.select_for_update().get(id=session_id)
        if locked.mode != LumenSimulatorSession.MODE_AUTOMATIC:
            return locked
        document = copy.deepcopy(locked.document or {})
        state = copy.deepcopy(document.get('state') or {})
        engine = state.get('engine') or {}

        def manual_state(value):
            value = copy.deepcopy(value or {})
            value.pop('engine', None)
            value.pop('random_seed', None)
            value['timer'] = {'started_at': None, 'duration_seconds': 10}
            value['status'] = {
                side: {'requested': False, 'done': False}
                for side in ('p1', 'p2')
            }
            return value

        state = manual_state(state)
        failure_payload = {
            'command_id': command_id,
            'error_type': type(failure).__name__,
            'message': str(failure)[:500],
            'at': timezone.now().isoformat(),
            'engine_step': engine.get('step'),
            'traceback': traceback.format_exc(limit=8)[-4000:],
        }
        report = AutomaticIssueReport.objects.create(
            session=locked,
            ruleset_release_id=locked.ruleset_release_id,
            origin=AutomaticIssueReport.ORIGIN_ENGINE,
            error_type=failure_payload['error_type'],
            summary=failure_payload['message'] or '자동 실행 오류',
            diagnostic={
                **copy.deepcopy(failure_payload),
                'session_version': locked.version,
                'state_hash': _stable_hash(document.get('state') or {}),
                'event_archive_hash': document.get('event_archive_hash') or '',
                'command_archive_hash': document.get('command_archive_hash') or '',
            },
        )
        failure_payload['report_id'] = str(report.public_id)
        document['initial_state'] = manual_state(document.get('initial_state') or state)
        document['state'] = state
        document.setdefault('events', []).append({
            'id': hashlib.sha256(f'fallback:{locked.id}:{locked.version}'.encode()).hexdigest()[:32],
            'type': 'automatic_fallback', 'actor': 'system', 'payload': {
                'command_id': command_id,
                'error_type': type(failure).__name__,
                'message': '자동 실행 오류로 수동 모드로 전환했습니다.',
            },
            'created_at': timezone.now().isoformat(),
        })
        locked.document = document
        locked.mode = LumenSimulatorSession.MODE_MANUAL
        locked.automation_failure = failure_payload
        locked.version += 1
        locked.save(update_fields=['document', 'mode', 'automation_failure', 'version', 'updated_at'])
        return locked


def perform_automatic_command(session, body, *, allow_ai=False):
    """Atomically validate, run and persist one idempotent automatic command."""
    command_id = str(body.get('command_id') or '').strip()
    action_id = str(body.get('action_id') or '').strip()
    if not command_id or len(command_id) > 100:
        raise ValueError('command_id가 필요합니다.')
    if not action_id:
        raise ValueError('action_id가 필요합니다.')
    try:
        expected_version = int(body.get('expected_version'))
    except (TypeError, ValueError):
        raise ValueError('expected_version이 필요합니다.') from None
    selections = body.get('selections') or {}
    if not isinstance(selections, dict):
        raise ValueError('selections는 객체여야 합니다.')
    fingerprint = _command_fingerprint(body)

    try:
        with transaction.atomic():
            locked = LumenSimulatorSession.objects.select_for_update().get(
                id=session.id,
            )
            if locked.mode != LumenSimulatorSession.MODE_AUTOMATIC:
                raise AutomaticModeUnavailable('이 세션은 자동 모드가 아닙니다.')
            role = _role_for_command(locked, body)
            controller = (
                locked.player1_controller if role == 'p1' else locked.player2_controller
            )
            if allow_ai and controller != LumenSimulatorSession.CONTROLLER_AI:
                raise PermissionDenied()
            if not allow_ai and controller == LumenSimulatorSession.CONTROLLER_AI:
                raise PermissionDenied()
            document = copy.deepcopy(locked.document or {})
            results = list(document.get('command_results') or [])
            previous = next((item for item in results if item.get('command_id') == command_id), None)
            if previous:
                if previous.get('fingerprint') != fingerprint:
                    raise CommandValidationError('같은 command_id를 다른 내용으로 재사용할 수 없습니다.')
                return locked
            command_now = timezone.now()
            state_before = copy.deepcopy(document.get('state') or {})
            events_before = list(document.get('events') or [])
            history = list(document.get('command_history') or [])
            rewind_enabled = bool(
                (state_before.get('engine') or {}).get('settings', {}).get(
                    'rewind_enabled', False,
                )
            )
            if rewind_enabled:
                state_before.setdefault('engine', {})['last_rewindable_command_id'] = (
                    history[-1].get('command_id') if history else None
                )
            else:
                history = []
                document['command_history'] = []
                state_before.setdefault('engine', {}).pop(
                    'last_rewindable_command_id', None,
                )
                state_before['engine']['rewind_request'] = None
            engine = AutomaticGameEngine(
                state_before, _ruleset(locked), version=locked.version,
                now=command_now, events=events_before, seed=f'session:{locked.id}',
            )
            action = next((item for item in engine.legal_actions(role) if item.get('action_id') == action_id), None)
            if expected_version != locked.version and not action:
                raise StaleState(
                    f'상태 버전이 오래되었습니다. 현재 버전: {locked.version}',
                )
            if not action:
                raise IllegalAction('현재 합법 행동이 아니거나 만료된 action_id입니다.')
            action_type = action.get('type')
            if action_type == 'request_rewind' and (
                not rewind_enabled or not history
            ):
                raise IllegalAction('되감을 사용자 명령이 없습니다.')
            engine.submit_action(role, action_id, selections, command_id=command_id)

            if rewind_enabled:
                state_after, events_after, rewound = _apply_accepted_rewind(
                    document, engine.state, engine.events, now=command_now,
                )
            else:
                state_after, events_after, rewound = (
                    engine.state, engine.events, False,
                )
                state_after.setdefault('engine', {}).pop(
                    'last_rewindable_command_id', None,
                )
                state_after['engine']['rewind_request'] = None
            command_log = list(document.get('command_log') or [])
            if rewound:
                target_id = next(
                    (
                        item.get('command_id') for item in reversed(command_log)
                        if not item.get('rewound_by')
                        and item.get('action_type') not in {'request_rewind', 'answer_rewind', 'pause_clock', 'resume_clock'}
                    ),
                    None,
                )
                if target_id:
                    command_log = [
                        {**item, 'rewound_by': command_id} if item.get('command_id') == target_id else item
                        for item in command_log
                    ]
            if (
                rewind_enabled
                and action_type not in {
                    'request_rewind', 'answer_rewind',
                    'pause_clock', 'resume_clock',
                }
                and not rewound
            ):
                history.append({
                    'command_id': command_id, 'actor': role, 'action_type': action_type,
                    'state_before': copy.deepcopy(document.get('state') or {}),
                    'event_count_before': len(events_before), 'created_at': command_now.isoformat(),
                })
                document['command_history'] = history[-AUTOMATIC_COMMAND_HISTORY_LIMIT:]
                state_after.setdefault('engine', {})['last_rewindable_command_id'] = command_id
            request = (state_after.get('engine') or {}).get('rewind_request') or {}
            if rewind_enabled and action_type == 'request_rewind':
                request['target_command_id'] = history[-1].get('command_id')

            results.append({'command_id': command_id, 'fingerprint': fingerprint, 'version': locked.version + 1})
            document['command_results'] = results[-AUTOMATIC_COMMAND_RESULT_LIMIT:]
            document['state'] = state_after
            document['events'] = events_after
            command_log.append({
                'command_id': command_id, 'actor': role, 'action_id': action_id,
                'action_type': action_type, 'selections': copy.deepcopy(selections),
                'expected_version': expected_version, 'result_version': locked.version + 1,
                'state_hash': _stable_hash(state_after), 'created_at': command_now.isoformat(),
            })
            document['command_log'] = command_log
            _compact_automatic_events(document)
            _compact_command_log(document)
            locked.document = document
            locked.version += 1
            locked.expires_at = command_now + timedelta(hours=1)
            locked.save(update_fields=['document', 'version', 'expires_at', 'updated_at'])
            return locked
    except (PermissionDenied, CommandValidationError, IllegalAction, StaleState, AutomaticModeUnavailable):
        raise
    except Exception as exc:
        _fallback_to_manual(session.id, exc, command_id)
        raise AutomaticRuntimeFailure('자동 실행 오류로 명령을 롤백하고 세션을 수동 모드로 전환했습니다.') from exc


def reconcile_automatic_session(session, *, both_players_disconnected=False):
    """Lazily settle an elapsed deadline on reconnect/read/command boundaries."""
    if session.mode != LumenSimulatorSession.MODE_AUTOMATIC:
        return session
    if not _automatic_document_needs_reconcile(
        session.document or {}, now=timezone.now(),
        both_players_disconnected=both_players_disconnected,
    ):
        return session
    try:
        with transaction.atomic():
            locked = LumenSimulatorSession.objects.select_for_update().get(
                id=session.id,
            )
            stored_document = locked.document or {}
            if _automatic_document_needs_upgrade(stored_document):
                document = copy.deepcopy(stored_document)
                upgraded = _upgrade_automatic_document(document)
            else:
                document = stored_document
                upgraded = False
            state = document.get('state') or {}
            clock = (state.get('engine') or {}).get('clock') or {}
            phase = state.get('phase')
            step = (state.get('engine') or {}).get('step')
            needs_auto_advance = (
                ((state.get('engine') or {}).get('settings') or {}).get(
                    'auto_advance_empty_phases', False,
                )
                and phase in {'lumen', 'recovery'}
                and step == 'phase_actions'
            )
            deadline = parse_datetime(str(clock.get('deadline') or ''))
            if deadline is not None:
                if timezone.is_naive(deadline):
                    deadline = timezone.make_aware(deadline)
            clock_due = bool(
                clock and not clock.get('paused')
                and not both_players_disconnected
                and deadline is not None
                and timezone.now() >= deadline
            )
            if not clock_due and not needs_auto_advance:
                if upgraded:
                    locked.document = document
                    locked.version += 1
                    locked.save(update_fields=[
                        'document', 'version', 'updated_at',
                    ])
                return locked
            engine = AutomaticGameEngine(
                state, _ruleset(locked),
                version=locked.version, now=timezone.now(),
                events=document.get('events') or [], seed=f'session:{locked.id}',
            )
            reconciled = engine.reconcile_clock(
                both_disconnected=both_players_disconnected,
            ) if clock_due else False
            if needs_auto_advance and not engine.is_waiting:
                engine._continue()
            if not reconciled and not needs_auto_advance and not upgraded:
                return locked
            document['state'] = engine.state
            document['events'] = engine.events
            _compact_automatic_events(document)
            locked.document = document
            locked.version += 1
            locked.save(update_fields=['document', 'version', 'updated_at'])
            return locked
    except Exception as exc:
        return _fallback_to_manual(session.id, exc, '')


def automatic_observation(session, role, *, include_state=True):
    if session.mode != LumenSimulatorSession.MODE_AUTOMATIC:
        return None
    engine = AutomaticGameEngine(
        (session.document or {}).get('state') or {}, _ruleset(session), version=session.version,
        now=timezone.now(), events=[], seed=f'session:{session.id}',
    )
    return engine.observe(role, include_state=include_state)


def _ai_roles(session):
    return [
        side for side, controller in (
            ('p1', session.player1_controller),
            ('p2', session.player2_controller),
        )
        if controller == LumenSimulatorSession.CONTROLLER_AI
    ]


def advance_ai_session(session, *, max_commands=100):
    """Advance every AI seat until the engine needs human input or finishes."""
    if session.mode != LumenSimulatorSession.MODE_AUTOMATIC or not _ai_roles(session):
        return session
    try:
        for _index in range(max_commands):
            session = LumenSimulatorSession.objects.select_related(
                'ai_policy',
            ).get(pk=session.pk)
            if session.mode != LumenSimulatorSession.MODE_AUTOMATIC:
                return session
            if not session.ai_policy_id:
                raise RuntimeError('AI 좌석에 검증된 정책이 고정되어 있지 않습니다.')
            state = (session.document or {}).get('state') or {}
            if (state.get('engine') or {}).get('status') != 'running':
                return session
            policy_payload = copy.deepcopy((session.document or {}).get('ai_policy') or {})
            weights = policy_payload.get('weights') or session.ai_policy.weights
            decisions = []
            for role in _ai_roles(session):
                observation = automatic_observation(session, role)
                decision = choose_action(
                    observation,
                    role,
                    weights=weights,
                    seed=f'session:{session.id}:version:{session.version}',
                )
                if decision:
                    decisions.append((role, decision))
            if not decisions:
                return session
            priority = state.get('priority_player')
            role, decision = sorted(
                decisions,
                key=lambda item: (item[1].score, item[0] == priority),
                reverse=True,
            )[0]
            token = session.player1_token if role == 'p1' else session.player2_token
            session = perform_automatic_command(
                session,
                {
                    'command_id': f'ai:{session.id}:{session.version}:{role}',
                    'expected_version': session.version,
                    'action_id': decision.action['action_id'],
                    'selections': decision.selections,
                    'seat': role,
                    'seat_token': token,
                },
                allow_ai=True,
            )
    except AutomaticRuntimeFailure:
        # perform_automatic_command already rolled back, reported the fault,
        # and persisted the permanent manual fallback.
        return LumenSimulatorSession.objects.select_related(
            'ai_policy',
        ).get(pk=session.pk)
    except Exception as exc:
        return _fallback_to_manual(
            session.id, exc, f'ai-driver:{session.version}',
        )
    failure = RuntimeError(f'AI가 한 요청에서 {max_commands}개보다 많은 명령을 생성했습니다.')
    return _fallback_to_manual(session.id, failure, f'ai-limit:{session.version}')


def _redact_client_diagnostic_text(value, session, limit):
    text = str(value or '')[:limit]
    secrets_to_redact = {
        str(session.view_token or ''),
        str(session.player1_token or ''),
        str(session.player2_token or ''),
    }
    for secret in sorted(secrets_to_redact, key=len, reverse=True):
        if secret:
            text = text.replace(secret, '[REDACTED]')
    text = re.sub(
        r'(?i)(seat_token=)[^&\s#]+', r'\1[REDACTED]', text,
    )
    return text


def add_client_issue_report(
    session, role, diagnostic, *, user_agent='', user=None,
):
    """Persist a privacy-bounded browser failure, deduplicated per session."""
    if not isinstance(diagnostic, dict):
        raise ValueError('브라우저 오류 정보는 객체여야 합니다.')
    with transaction.atomic():
        locked = LumenSimulatorSession.objects.select_for_update().get(
            pk=session.pk,
        )
        if (
            locked.mode != LumenSimulatorSession.MODE_AUTOMATIC
            and not locked.automation_failure
        ):
            raise ValueError('자동 모드에서 발생한 브라우저 오류만 자동 보고할 수 있습니다.')
        error_type = _redact_client_diagnostic_text(
            diagnostic.get('error_type') or 'ClientError', locked, 120,
        ) or 'ClientError'
        message = _redact_client_diagnostic_text(
            diagnostic.get('message') or '브라우저 자동 모드 오류',
            locked, 500,
        ) or '브라우저 자동 모드 오류'
        source = _redact_client_diagnostic_text(
            diagnostic.get('source'), locked, 1000,
        )
        stack = _redact_client_diagnostic_text(
            diagnostic.get('stack'), locked, CLIENT_ERROR_MAX_STACK,
        )
        context = _redact_client_diagnostic_text(
            diagnostic.get('context'), locked, 120,
        )
        safe_user_agent = _redact_client_diagnostic_text(
            user_agent, locked, 500,
        )
        try:
            line = max(0, min(10_000_000, int(diagnostic.get('line') or 0)))
            column = max(0, min(10_000_000, int(diagnostic.get('column') or 0)))
        except (TypeError, ValueError):
            raise ValueError('브라우저 오류 위치가 올바르지 않습니다.') from None
        fingerprint = _stable_hash({
            'error_type': error_type,
            'message': message,
            'source': source,
            'line': line,
            'column': column,
            'context': context,
        })
        now = timezone.now()
        recent = list(
            AutomaticIssueReport.objects.select_for_update().filter(
                session=locked,
                origin=AutomaticIssueReport.ORIGIN_CLIENT,
                created_at__gte=now - timedelta(
                    seconds=CLIENT_ERROR_DEDUP_SECONDS,
                ),
            ).order_by('-created_at', '-id')[:CLIENT_ERROR_MAX_DISTINCT_PER_WINDOW]
        )
        report = next((
            item for item in recent
            if (item.diagnostic or {}).get('fingerprint') == fingerprint
        ), None)
        if report is not None:
            stored = copy.deepcopy(report.diagnostic or {})
            stored['occurrences'] = int(stored.get('occurrences') or 1) + 1
            stored['last_seen_at'] = now.isoformat()
            stored['roles'] = sorted(set(stored.get('roles') or []) | {role})
            report.diagnostic = stored
            report.save(update_fields=['diagnostic', 'updated_at'])
            return report, False
        if len(recent) >= CLIENT_ERROR_MAX_DISTINCT_PER_WINDOW:
            report = recent[0]
            stored = copy.deepcopy(report.diagnostic or {})
            stored['occurrences'] = int(stored.get('occurrences') or 1) + 1
            stored['suppressed_distinct_errors'] = int(
                stored.get('suppressed_distinct_errors') or 0
            ) + 1
            stored['last_seen_at'] = now.isoformat()
            stored['roles'] = sorted(set(stored.get('roles') or []) | {role})
            report.diagnostic = stored
            report.save(update_fields=['diagnostic', 'updated_at'])
            return report, False
        document = locked.document or {}
        report = AutomaticIssueReport.objects.create(
            session=locked,
            ruleset_release_id=locked.ruleset_release_id,
            origin=AutomaticIssueReport.ORIGIN_CLIENT,
            error_type=error_type,
            summary=message,
            diagnostic={
                'kind': 'client_error',
                'fingerprint': fingerprint,
                'occurrences': 1,
                'first_seen_at': now.isoformat(),
                'last_seen_at': now.isoformat(),
                'roles': [role],
                'context': context,
                'source': source,
                'line': line,
                'column': column,
                'stack': stack,
                'user_agent': safe_user_agent,
                'session_version': locked.version,
                'mode': locked.mode,
                'state_hash': _stable_hash(document.get('state') or {}),
                'event_archive_hash': document.get('event_archive_hash') or '',
                'command_archive_hash': document.get('command_archive_hash') or '',
            },
        )
        return report, True


def add_issue_report(session, role, details, *, user=None, report_id=None):
    details = str(details or '').strip()
    if not details:
        raise ValueError('제보 내용을 입력해주세요.')
    if len(details) > 4000:
        raise ValueError('제보 내용은 4000자 이하여야 합니다.')
    with transaction.atomic():
        locked = LumenSimulatorSession.objects.select_for_update().get(
            pk=session.pk,
        )
        failure = locked.automation_failure or {}
        report = None
        requested_report_id = str(
            report_id or failure.get('report_id') or ''
        ).strip()
        if requested_report_id:
            try:
                report = AutomaticIssueReport.objects.filter(
                    public_id=requested_report_id, session=locked,
                ).first()
            except (ValidationError, ValueError):
                report = None
            if report is None:
                raise ValueError('이 세션에 연결된 제보 번호가 아닙니다.')
        if report is None:
            document = locked.document or {}
            report = AutomaticIssueReport.objects.create(
                session=locked,
                ruleset_release_id=locked.ruleset_release_id,
                origin=AutomaticIssueReport.ORIGIN_USER,
                error_type='',
                summary=details[:500],
                diagnostic={
                    'session_version': locked.version,
                    'mode': locked.mode,
                    'state_hash': _stable_hash(document.get('state') or {}),
                    'event_archive_hash': document.get('event_archive_hash') or '',
                    'command_archive_hash': document.get('command_archive_hash') or '',
                },
            )
        AutomaticIssueComment.objects.create(
            report=report,
            reporter=user if user and user.is_authenticated else None,
            role=role,
            body=details,
        )
        return report


def sanitize_automatic_state(
    serialized_state, observation, role=None, ruleset=None, *, copy_state=True,
):
    """Strip resolver internals and attach the role-specific public contract."""
    state = (
        copy.deepcopy(serialized_state or {})
        if copy_state else (serialized_state or {})
    )
    state.pop('random_seed', None)
    released_by_id = {
        str(card.get('id')): card
        for card in ((ruleset or {}).get('cards') or {}).values()
        if isinstance(card, dict) and card.get('id') is not None
    }
    released_by_code = {
        str(card.get('code') or code): card
        for code, card in ((ruleset or {}).get('cards') or {}).items()
        if isinstance(card, dict)
    }
    for player in (state.get('players') or {}).values():
        character_payload = player.get('character') or {}
        released_character = ((ruleset or {}).get('characters') or {}).get(
            str(character_payload.get('id') or '')
        )
        if released_character:
            character = SimpleNamespace(
                name=released_character.get('name') or '',
                datas=copy.deepcopy(released_character.get('datas') or {}),
            )
            character_payload['name'] = released_character.get('name')
            character_payload['hand_table'] = character_hand_table(character)
            hand_limit = hand_limit_for_hp(character, player.get('hp'))
            hand_limit_bonus = 0
            for card in ((player.get('zones') or {}).get('lumen') or []):
                if card.get('effects_negated'):
                    continue
                released_card = released_by_code.get(str(card.get('code') or '')) or {}
                definition = released_card.get('effect_definition') or {}
                hand_limit_bonus += int(definition.get('hand_limit_bonus') or 0)
            character_payload['hand_limit'] = (
                hand_limit + hand_limit_bonus if hand_limit is not None else None
            )
        passive_state = player.get('passive_state') or {}
        for key in list(passive_state):
            entry = passive_state.get(key) or {}
            if isinstance(entry, dict) and entry.get('visibility') == 'private' and entry.get('owner') != role:
                passive_state.pop(key, None)
        for cards in (player.get('zones') or {}).values():
            for card in cards:
                if card.get('hidden'):
                    for field_name in (
                        'instance_id', 'card_id', 'code', 'original_name', 'type', 'frame', 'damage',
                        'pos', 'special', 'text', 'detail_text', 'img', 'img_sm',
                    ):
                        card.pop(field_name, None)
                    continue
                released = released_by_id.get(str(card.get('card_id')))
                if released:
                    for field_name in (
                        'code', 'name', 'type', 'text', 'detail_text', 'frame', 'damage',
                        'pos', 'body', 'special', 'hit', 'guard', 'counter',
                        'g_top', 'g_mid', 'g_bot', 'ultimate', 'character_id',
                    ):
                        card[field_name] = copy.deepcopy(released.get(field_name))
    state['engine'] = copy.deepcopy(observation.get('engine_status') or {})
    return state
