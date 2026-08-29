"""Stateless, isolated effect sandbox used by the card review screen.

The sandbox deliberately uses the same ``AutomaticGameEngine`` and public
``submit_action`` contract as a live automatic game.  It does not persist a
session and it limits the source ruleset to one selected ability so unfinished
cards can be exercised safely during review.
"""

import copy
import json
from datetime import datetime, timedelta, timezone

from common.localization import (
    render_visible_markup,
    term_translation_key,
    translate_key,
    translation_source_exists,
)

from .engine import AutomaticGameEngine, EngineError
from .deck_rules import merge_deck_rules
from .spec import ALL_ZONES, PHASES, PLAYER_SIDES, TRIGGERS


SANDBOX_VERSION = 1
SANDBOX_EPOCH = datetime(2026, 6, 1, tzinfo=timezone.utc)
MAX_SUPPORT_CARDS = 36
SANDBOX_PROTOTYPE_PREFIX = 'sandbox-prototype:'
BATTLE_PIPELINE_EVENTS = frozenset({
    'battle_reveal', 'use', 'before_judgment',
    'dodge', 'opponent_dodge', 'guard', 'opponent_guard',
    'hit', 'opponent_hit', 'counter', 'opponent_counter',
    'clash', 'opponent_clash', 'combo', 'grab_negated',
    'damage_before', 'damage_after', 'hp_changed', 'fp_changed',
    'after_judgment', 'after_use', 'battle_end', 'card_moved',
})
COMBO_PIPELINE_EVENTS = frozenset({
    'combo', 'combo_window', 'use', 'after_use', 'combo_end',
    'opponent_combo_end',
})
CATCH_PIPELINE_EVENTS = frozenset({'use', 'catch', 'hit', 'after_use', 'combo'})
PHASE_PIPELINE_EVENTS = frozenset({
    'game_start', 'turn_start', 'turn_end', 'phase_start', 'phase_end',
})
SANDBOX_ACTION_TYPES = frozenset({
    'ready_card', 'declare_no_response', 'pass_phase',
    'select_get_card', 'select_ultimate',
    'select_combo_first', 'cancel_combo_first', 'select_combo_followup',
    'play_combo_sequence', 'play_combo_pair', 'play_combo_card',
    'end_combo', 'play_catch_card', 'decline_catch',
})
NO_EFFECT_DEFINITION = {
    'schema_version': 1,
    'reviewed': True,
    'no_effect': True,
    'source_refs': {'rulebook_pages': [], 'qna_ids': []},
    'abilities': [],
}

PASSIVE_STATE_SLUG_ALIASES = {
    'root_charge': 'charge',
    'notice': 'advance_notice',
    'silver_counter': 'hidden_bond',
    'yang_counter': 'yang',
    'yin_counter': 'yin',
    'foresight_counter': 'foresight',
    'ember_token': 'ember',
    'howling_counter': 'howling',
}
PASSIVE_STATE_KO_LABELS = {
    'charge': '충전',
    'advance_notice': '예고',
    'hidden_bond': '은연',
    'yin': '음',
    'yang': '양',
    'harmony': '조화',
    'harmony_damage': '조화: 타오 기술 데미지 +100',
    'harmony_fp': '조화: 루멘 페이즈 1FP',
    'mujin_active': '무진 적용',
    'mujin_declined': '무진 미적용',
    'saintess': '성녀',
    'guardian': '가디언 축복',
    'assassin': '어쌔신 축복',
    'paladin': '팔라딘 축복',
    'legion_guardian_cooldown': '가디언 재축복 제한',
    'legion_assassin_cooldown': '어쌔신 재축복 제한',
    'legion_paladin_cooldown': '팔라딘 재축복 제한',
    'foresight': '예지',
    'ember': '불씨',
    'howling': '하울링',
    'over_limit': '오버 리미트',
    'intimidation': '위압',
    'dark_night': '암야',
    'down_stance': '다운 스탠스',
}


def _prototype_ability(
    ability_id, label, prompt, selector, effects, *, chooser=None,
):
    source_refs = {
        'rulebook_pages': [48], 'qna_ids': [], 'card_text': False,
    }
    return {
        'id': f'{SANDBOX_PROTOTYPE_PREFIX}{ability_id}',
        'label': label,
        'draft_text': (
            '카드별 구현과 독립적으로 강제 선택과 영역 이동을 확인하는 '
            '검수 전용 효과입니다.'
        ),
        'kind': 'effect', 'mode': 'mandatory', 'timing': 'use',
        'visibility': 'public', 'draft': True, 'draft_compiled': True,
        # Reviewer-only prototypes are independent of the printed source
        # card.  Allow them in every zone so a passive/ultimate continuous
        # rule can remain active while the prototype exercises a real domain
        # movement or selection command.
        'active_zones': list(ALL_ZONES), 'trigger': {'event': 'use'},
        'source_refs': copy.deepcopy(source_refs),
        'effects': [{
            'op': 'request_choice',
            'player': copy.deepcopy(chooser or {'controller': True}),
            'prompt': prompt, 'selector': copy.deepcopy(selector),
            'selection_key': 'sandbox_prototype_selected', 'default': [],
            'then': copy.deepcopy(effects),
        }],
    }


SANDBOX_PROTOTYPE_ABILITIES = (
    _prototype_ability(
        'acquire-one', '공통 테스트 · 리스트에서 기술 1장 획득',
        '리스트에서 획득할 기술 1장을 반드시 선택하세요.',
        {
            'kind': 'card', 'player': {'controller': True},
            'zones': ['list'], 'min': 1, 'max': 1,
            'where': {'is_technique': True},
        },
        [{
            'op': 'move_card', 'selection_key': 'sandbox_prototype_selected',
            'to_zone': 'hand',
        }],
    ),
    _prototype_ability(
        'acquire-two', '공통 테스트 · 리스트에서 기술 2장 획득',
        '리스트에서 획득할 기술 2장을 반드시 선택하세요.',
        {
            'kind': 'card', 'player': {'controller': True},
            'zones': ['list'], 'min': 2, 'max': 2,
            'where': {'is_technique': True},
        },
        [{
            'op': 'move_card', 'selection_key': 'sandbox_prototype_selected',
            'to_zone': 'hand',
        }],
    ),
    _prototype_ability(
        'break-one', '공통 테스트 · 리스트의 기술 1장 브레이크',
        '리스트에서 브레이크할 기술 1장을 반드시 선택하세요.',
        {
            'kind': 'card', 'player': {'controller': True},
            'zones': ['list'], 'min': 1, 'max': 1,
            'where': {'is_technique': True}, 'as_operation': 'break_card',
        },
        [{
            'op': 'break_card', 'selection_key': 'sandbox_prototype_selected',
        }],
    ),
    _prototype_ability(
        'discard-one', '공통 테스트 · 패의 기술 1장 버리기',
        '패에서 버릴 기술 1장을 반드시 선택하세요.',
        {
            'kind': 'card', 'player': {'controller': True},
            'zones': ['hand'], 'min': 1, 'max': 1,
            'where': {'is_technique': True},
        },
        [{
            'op': 'discard', 'selection_key': 'sandbox_prototype_selected',
        }],
    ),
    _prototype_ability(
        'move-side-lumen-one',
        '공통 테스트 · 사이드 덱에서 루멘으로 기술 1장 이동',
        '사이드 덱에서 루멘 존으로 이동할 기술 1장을 반드시 선택하세요.',
        {
            'kind': 'card', 'player': {'controller': True},
            'zones': ['side'], 'min': 1, 'max': 1,
            'where': {'is_technique': True},
        },
        [{
            'op': 'move_card', 'selection_key': 'sandbox_prototype_selected',
            'to_zone': 'lumen',
        }],
    ),
    _prototype_ability(
        'opponent-discard-one',
        '공통 테스트 · 상대가 자신의 패 1장 버리기',
        '상대는 자신의 패에서 버릴 기술 1장을 반드시 선택하세요.',
        {
            'kind': 'card', 'player': {'opponent': True},
            'zones': ['hand'], 'min': 1, 'max': 1,
            'where': {'is_technique': True},
        },
        [{
            'op': 'discard', 'selection_key': 'sandbox_prototype_selected',
        }],
        chooser={'opponent': True},
    ),
)


def sandbox_prototype_definition(ability_id):
    """Return an isolated reviewer-only definition for a built-in scenario."""
    selected = next((
        ability for ability in SANDBOX_PROTOTYPE_ABILITIES
        if ability.get('id') == str(ability_id or '')
    ), None)
    if selected is None:
        return None
    return {
        'schema_version': 1, 'reviewed': False, 'draft': True,
        'source_refs': {
            'rulebook_pages': [48], 'qna_ids': [], 'card_text': False,
        },
        'abilities': [copy.deepcopy(selected)],
    }


def sandbox_prototype_abilities():
    """Describe built-in scenarios in the same shape as card abilities."""
    return [copy.deepcopy(ability) for ability in SANDBOX_PROTOTYPE_ABILITIES]

EVENT_LABELS = {
    'game_start': '게임 시작', 'turn_start': '턴 시작', 'turn_end': '턴 종료',
    'phase_start': '페이즈 시작', 'phase_end': '페이즈 종료',
    'battle_end': '배틀 종료', 'ready': '레디',
    'battle_reveal': '배틀 공개·사용 조건', 'use': '사용 시',
    'before_judgment': '판정 전', 'dodge': '회피 시',
    'opponent_dodge': '상대 회피 시', 'guard': '방어 시',
    'opponent_guard': '상대 방어 시', 'hit': '히트 시',
    'opponent_hit': '상대 히트 시', 'counter': '카운터 시',
    'opponent_counter': '상대 카운터 시', 'clash': '상쇄 시',
    'opponent_clash': '상대 상쇄 시', 'combo': '콤보 시',
    'combo_window': '콤보 타임', 'catch': '캐치 시',
    'combo_end': '콤보 종료', 'opponent_combo_end': '상대 콤보 종료',
    'after_judgment': '판정 후', 'after_use': '사용 후',
    'damage_before': '데미지 전', 'damage_after': '데미지 후',
    'hp_changed': 'HP 변경', 'fp_changed': 'FP 변경',
    'card_moved': '카드 이동', 'card_broken': '카드 브레이크',
    'card_attached': '카드 세트', 'card_discarded': '카드 버리기',
    'state_gained': '상태 획득', 'state_lost': '상태 상실',
    'counter_changed': '카운터 변경', 'ability_completed': '효과 완료',
    'speed_fixed': '속도 고정', 'no_response': '대응하지 않음',
    'sudden_death_start': '서든 데스', 'defense_over': '디펜스 오버',
    'card_guess_resolved': '카드 추측 결과', 'grab_negated': '그랩 무효',
}

ZONE_LABELS = {
    'character': '캐릭터', 'passive': '패시브', 'battle': '배틀 존',
    'list': '리스트', 'hand': '패', 'side': '사이드 덱',
    'break': '브레이크', 'lumen': '루멘', 'ultimate': '얼티밋',
}

EVENT_TYPE_LABELS = {
    'effect_resolved': '효과 실행', 'decision_requested': '선택 요청',
    'decision_resolved': '선택 확정', 'effect_choice_skipped': '선택 후보 부족',
    'ability_target_skipped': '대상 후보 부족', 'card_moved': '카드 이동',
    'card_broken': '카드 브레이크', 'card_break_prevented': '브레이크 방지',
    'card_move_prevented': '카드 이동 방지', 'card_effect_ignored': '효과 무시',
    'hp_changed': 'HP 변경', 'fp_changed': 'FP 변경',
    'damage_dealt': '데미지', 'state_changed': '상태 변경',
    'counter_changed': '카운터 변경', 'modifier_added': '수정자 추가',
    'card_attached': '카드 세트', 'card_discarded': '카드 버리기',
    'command': '테스트 명령',
}


class EffectSandboxError(ValueError):
    """Invalid sandbox configuration or stale/tampered state."""


def _integer(value, default=0, minimum=0, maximum=99999):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _side(value, default='p1'):
    return value if value in PLAYER_SIDES else default


def _zone(value, default='battle'):
    return value if value in ALL_ZONES else default


def _phase(value):
    return value if value in PHASES else 'battle'


def _sandbox_passive_state(value):
    """Normalize reviewer-friendly state JSON into the engine shape."""
    if value is None or value == '':
        return {}
    if not isinstance(value, dict):
        raise EffectSandboxError('패시브 상태 JSON은 객체여야 합니다.')
    normalized = {}
    for raw_key, raw_entry in value.items():
        key = str(raw_key or '').strip()
        if not key:
            raise EffectSandboxError('패시브 상태 키는 비어 있을 수 없습니다.')
        if isinstance(raw_entry, bool):
            normalized[key] = {'value': raw_entry}
        elif isinstance(raw_entry, (int, float)):
            normalized[key] = {'count': raw_entry}
        elif isinstance(raw_entry, dict):
            entry = copy.deepcopy(raw_entry)
            if (
                'active' in entry
                and 'value' not in entry
                and 'count' not in entry
            ):
                entry['value'] = bool(entry.get('active'))
            normalized[key] = entry
        else:
            raise EffectSandboxError(
                f'{key} 상태 값은 객체, 불리언 또는 숫자여야 합니다.'
            )
    return normalized


def _card_definition_without_triggered_abilities(definition):
    """Retain static card constraints while isolating triggered support effects."""
    result = copy.deepcopy(definition) if isinstance(definition, dict) else {}
    result.update({
        'schema_version': 1,
        'reviewed': True,
        'abilities': [],
    })
    if not result.get('source_refs'):
        result['source_refs'] = {'rulebook_pages': [], 'qna_ids': []}
    if not any(
        key for key in result
        if key not in {'schema_version', 'reviewed', 'draft', 'source_refs', 'source_digest', 'abilities'}
    ):
        result['no_effect'] = True
    return result


def _runtime_card(snapshot, owner, instance_id, *, sandbox_fixture=False):
    excluded = {'effect_definition', 'effect_revision', 'effect_updated_at'}
    card = {
        key: copy.deepcopy(value)
        for key, value in (snapshot or {}).items()
        if key not in excluded
    }
    card.update({
        'instance_id': str(instance_id), 'kind': 'card', 'owner': owner,
        'face_up': True,
    })
    if sandbox_fixture:
        card['sandbox_fixture'] = True
    return card


def _fixture_snapshot(code, name, card_type, *, frame=6, damage=400, pos='중단'):
    is_defense = '수비' in card_type
    return {
        'id': None, 'code': code, 'name': name, 'type': card_type,
        'text': '', 'detail_text': '', 'frame': frame,
        'damage': 0 if is_defense else damage, 'pos': None if is_defense else pos,
        'body': '손', 'special': '', 'hit': '+1', 'guard': '0', 'counter': '+1',
        'g_top': '방어' if is_defense else '',
        'g_mid': '방어' if is_defense else '',
        'g_bot': '방어' if is_defense else '',
        'ultimate': False, 'character_id': 1, 'keyword': '',
        'hiddenKeyword': '', 'search': '',
        'effect_definition': copy.deepcopy(NO_EFFECT_DEFINITION),
    }


def _fixture_cards(side, zones, ruleset_cards):
    fixtures = []
    kinds = (
        ('attack', '테스트 공격 기술', '공격', 5, 400, '상단'),
        ('defense', '테스트 수비 기술', '수비', 8, 0, None),
        ('special', '테스트 특수 공격', '특수 공격', 10, 600, '하단'),
    )
    for zone in zones:
        for key, label, card_type, frame, damage, pos in kinds:
            code = f'SANDBOX-{side.upper()}-{zone.upper()}-{key.upper()}'
            snapshot = _fixture_snapshot(
                code, f'{label} ({side} {ZONE_LABELS.get(zone, zone)})', card_type,
                frame=frame, damage=damage, pos=pos,
            )
            ruleset_cards[code] = snapshot
            fixtures.append((
                zone,
                _runtime_card(
                    snapshot, side, f'sandbox-fixture-{side}-{zone}-{key}',
                    sandbox_fixture=True,
                ),
            ))
    return fixtures


def _effect_selectors(ability):
    selectors = []
    selectors.extend(
        selector for selector in ability.get('targets') or []
        if isinstance(selector, dict) and selector.get('kind', 'card') == 'card'
    )

    def visit(value):
        if isinstance(value, dict):
            if value.get('op') == 'request_choice':
                selector = value.get('selector') or {}
                if selector.get('kind', 'card') == 'card':
                    selectors.append(selector)
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(ability.get('cost') or [])
    visit(ability.get('effects') or [])
    return selectors


def _selector_side(selector, controller):
    raw = selector.get('player', {'controller': True})
    if isinstance(raw, dict) and 'opponent' in raw:
        return 'p2' if controller == 'p1' else 'p1'
    if raw in PLAYER_SIDES:
        return raw
    return controller


def _selector_fixture_snapshot(selector, code, name):
    where = selector.get('where') if isinstance(selector.get('where'), dict) else {}
    exact_code = where.get('code')
    if not exact_code and isinstance(where.get('code_in'), list) and where['code_in']:
        exact_code = where['code_in'][0]
    card_type = '공격'
    if where.get('type_contains'):
        expected = str(where['type_contains'])
        card_type = '수비' if '수비' in expected else ('특수 공격' if '특수' in expected else expected)
    elif isinstance(where.get('type_in'), list) and where['type_in']:
        card_type = str(where['type_in'][0])
    if str(where.get('type_not_contains') or '') in card_type:
        card_type = '수비' if '공격' in card_type else '공격'
    snapshot = _fixture_snapshot(
        str(exact_code or code), name, card_type,
        frame=max(1, _integer(where.get('frame_gte'), 6, 1, 99)),
        damage=400, pos=str(where.get('pos') or '중단'),
    )
    if where.get('frame_lte') is not None:
        snapshot['frame'] = max(1, min(snapshot['frame'], _integer(where['frame_lte'], 6, 1, 99)))
    for key, value in where.items():
        if key in {
            'type_contains', 'type_not_contains', 'name_contains', 'name_not_contains',
            'judgment_contains', 'judgment_contains_any', 'instance_id_not', 'keyword_any',
            'text_contains', 'text_contains_any', 'text_not_contains', 'type_in',
            'is_technique', 'special_truthy', 'special_contains', 'frame_gte',
            'frame_lte', 'code_in', 'owner', 'face_up', 'body',
        }:
            continue
        snapshot[key] = copy.deepcopy(value)
    if where.get('name_contains'):
        snapshot['name'] = f'{where["name_contains"]} {name}'
    if where.get('name_not_contains') and str(where['name_not_contains']) in snapshot['name']:
        snapshot['name'] = name
    text_parts = []
    if where.get('text_contains'):
        text_parts.append(str(where['text_contains']))
    if isinstance(where.get('text_contains_any'), list) and where['text_contains_any']:
        text_parts.append(str(where['text_contains_any'][0]))
    snapshot['text'] = ' '.join(text_parts)
    if where.get('text_not_contains') and str(where['text_not_contains']) in snapshot['text']:
        snapshot['text'] = ''
    if isinstance(where.get('keyword_any'), list) and where['keyword_any']:
        snapshot['keyword'] = f'{where["keyword_any"][0]}/'
    if where.get('judgment_contains'):
        snapshot['hit'] = str(where['judgment_contains'])
    if isinstance(where.get('judgment_contains_any'), list) and where['judgment_contains_any']:
        snapshot['hit'] = str(where['judgment_contains_any'][0])
    if isinstance(where.get('body'), list) and where['body']:
        snapshot['body'] = str(where['body'][0])
    elif where.get('body') is not None:
        snapshot['body'] = str(where['body'])
    if where.get('special_truthy'):
        snapshot['special'] = str(where.get('special_contains') or '그랩')
    elif where.get('special_contains'):
        snapshot['special'] = str(where['special_contains'])
    if where.get('is_technique') is False:
        snapshot['non_technique_while_face_down'] = True
    snapshot['effect_definition'] = copy.deepcopy(NO_EFFECT_DEFINITION)
    return snapshot


def _selector_fixture_cards(ability, controller, ruleset_cards, source_instance_id):
    fixtures = []
    seen = set()
    for selector_index, selector in enumerate(_effect_selectors(ability), start=1):
        zones = selector.get('zones') or [selector.get('zone', 'hand')]
        zones = [zone for zone in zones if zone in ALL_ZONES]
        if not zones or selector.get('selection_key') or selector.get('history'):
            continue
        side = _selector_side(selector, controller)
        signature = json.dumps({
            'side': side, 'zones': zones, 'where': selector.get('where') or {},
            'attached_to_source': bool(selector.get('attached_to_source')),
            'attached_to_event': bool(selector.get('attached_to_event')),
            'minimum': selector.get('min'), 'maximum': selector.get('max'),
        }, ensure_ascii=False, sort_keys=True, default=str)
        if signature in seen:
            continue
        seen.add(signature)
        maximum = selector.get('max')
        if isinstance(maximum, int) and not isinstance(maximum, bool):
            count = max(0, min(3, maximum))
        else:
            count = 3
        minimum = selector.get('min', 1)
        if isinstance(minimum, int) and not isinstance(minimum, bool):
            count = max(count, min(3, minimum))
        for candidate_index in range(count):
            code = f'SANDBOX-SELECTOR-{selector_index}-{candidate_index + 1}'
            snapshot = _selector_fixture_snapshot(
                selector, code,
                f'조건 일치 테스트 카드 {selector_index}-{candidate_index + 1}',
            )
            released_code = str(snapshot.get('code') or code)
            ruleset_cards.setdefault(released_code, snapshot)
            card = _runtime_card(
                snapshot, side,
                f'sandbox-selector-{selector_index}-{candidate_index + 1}',
                sandbox_fixture=True,
            )
            if selector.get('attached_to_source') or selector.get('attached_to_event'):
                card['attached_to'] = source_instance_id
                card['set_order'] = candidate_index + 1
            if isinstance((selector.get('where') or {}).get('face_up'), bool):
                card['face_up'] = selector['where']['face_up']
            fixtures.append((side, zones[0], card))
    return fixtures


def _empty_player(name, hp, fp, passive_state, character=None):
    player = {
        'name': name, 'initial_hp': max(5000, hp), 'hp': hp, 'fp': fp,
        'passive_state': _sandbox_passive_state(passive_state),
        'zones': {zone: [] for zone in ALL_ZONES},
    }
    if isinstance(character, dict) and character:
        player['character'] = copy.deepcopy(character)
    return player


def _selected_ability(definition, ability_id):
    for ability in (definition or {}).get('abilities') or []:
        if str(ability.get('id') or '') == str(ability_id or ''):
            return copy.deepcopy(ability)
    raise EffectSandboxError('선택한 효과를 현재 정의에서 찾을 수 없습니다.')


def _battle_card(engine, side):
    return next((
        card for card in engine.state['players'][side]['zones']['battle']
        if not card.get('attached_to')
    ), None)


def _set_battle_context(engine):
    battle = {}
    for side in PLAYER_SIDES:
        card = _battle_card(engine, side)
        if card:
            battle[side] = {
                'card': copy.deepcopy(card),
                'instance_id': card.get('instance_id'),
            }
    battle['actual_damage_received'] = {side: 0 for side in PLAYER_SIDES}
    engine.engine_state['battle'] = battle


def _is_attack(card):
    return (
        not (card or {}).get('non_technique_while_face_down')
        and '공격' in str((card or {}).get('type') or '')
    )


def _is_defense(card):
    return (
        not (card or {}).get('non_technique_while_face_down')
        and '수비' in str((card or {}).get('type') or '')
    )


def _matching_guard_position(card, judgment):
    marker = {'dodge': '회피', 'guard': '방어', 'clash': '상쇄'}.get(judgment)
    if not marker:
        return None
    for position, field in (('상단', 'g_top'), ('중단', 'g_mid'), ('하단', 'g_bot')):
        if marker in str((card or {}).get(field) or ''):
            return position
    return None


def _has_guard_judgment(card, judgment, position):
    marker = {
        'dodge': '회피', 'guard': '방어', 'clash': '상쇄',
    }.get(judgment)
    field = {
        '상단': 'g_top', '중단': 'g_mid', '하단': 'g_bot',
    }.get(position)
    return bool(
        marker and field and marker in str((card or {}).get(field) or '')
    )


def _matching_special_positions(card, judgment):
    marker = {'dodge': '회피', 'clash': '상쇄'}.get(judgment)
    text = str((card or {}).get('special') or '').replace('•', '·').replace('ㆍ', '·')
    if not marker or marker not in text:
        return []
    if '상·중·하단' in text:
        return ['상단', '중단', '하단']
    return [position for position in ('상단', '중단', '하단') if position in text]


def _sandbox_defense_reference_speed(
    card, fallback, *, judgment='dodge', position=None,
):
    """Choose a synthetic opponent Speed inside unconditional defense rules.

    Real battle reviews shape only sandbox fixture opponents. A Technique such
    as Belgian Kick has a printed top Dodge plus a numberless ``9 Speed or
    higher`` restriction. Position-only shaping therefore produced a
    Counter and never reached the selected Dodge timing. Conditional rules
    remain the reviewer's responsibility; only unconditional bounds which
    apply to the requested judgment/position are safe to synthesize here.
    """
    definition = (card or {}).get('effect_definition') or {}
    rules = definition.get('defense_rules') or []
    applicable = []
    for rule in rules:
        if not isinstance(rule, dict) or rule.get('condition'):
            continue
        rule_judgment = str(rule.get('judgment') or '')
        if rule_judgment and rule_judgment != judgment:
            continue
        rule_position = str(rule.get('position') or '')
        if rule_position and position and rule_position != position:
            continue
        applicable.append(rule)
    speed = max(1, _integer(fallback, 7, 1, 999))
    minimums = [
        _integer(rule.get('min_speed'), 0, 0, 999)
        for rule in applicable if rule.get('min_speed') is not None
    ]
    maximums = [
        _integer(rule.get('max_speed'), 999, 1, 999)
        for rule in applicable if rule.get('max_speed') is not None
    ]
    minimum = max(minimums) if minimums else 1
    maximum = min(maximums) if maximums else 999
    if minimum > maximum:
        return speed
    return min(max(speed, minimum), maximum)


def _sandbox_defense_reference_body(
    card, *, judgment='dodge', position=None,
):
    """Choose an unambiguous body judgment required by a defense rule.

    Position shaping alone cannot reproduce cards such as ST1-005, whose
    printed Special Clash works only against a foot judgment.  Only a single
    unconditional ``where.body`` value is safe to synthesize; conflicting or
    conditional requirements remain explicit reviewer input.
    """
    definition = (card or {}).get('effect_definition') or {}
    bodies = set()
    for rule in definition.get('defense_rules') or []:
        if not isinstance(rule, dict) or rule.get('condition'):
            continue
        rule_judgment = str(rule.get('judgment') or '')
        if rule_judgment and rule_judgment != judgment:
            continue
        rule_position = str(rule.get('position') or '')
        if rule_position and position and rule_position != position:
            continue
        where = rule.get('where') if isinstance(rule.get('where'), dict) else {}
        body = str(where.get('body') or '')
        if body in {'손', '발'}:
            bodies.add(body)
    return next(iter(bodies)) if len(bodies) == 1 else None


def _make_fixture_attack(card, *, frame=None, position='중단', body=None):
    if not card.get('sandbox_fixture'):
        return False
    card.update({
        'type': '공격', 'damage': max(100, _integer(card.get('damage'), 400)),
        'pos': position, 'special': '',
        'g_top': '', 'g_mid': '', 'g_bot': '',
    })
    if frame is not None:
        card['frame'] = max(1, int(frame))
    if body in {'손', '발'}:
        card['body'] = body
    return True


def _make_fixture_defense(card, judgment='hit', *, position='중단'):
    if not card.get('sandbox_fixture'):
        return False
    marker = {'dodge': '회피', 'guard': '방어', 'clash': '상쇄'}.get(judgment, '')
    card.update({
        'type': '수비', 'damage': 0, 'pos': None, 'special': '',
        'g_top': '', 'g_mid': '', 'g_bot': '',
    })
    field = {'상단': 'g_top', '중단': 'g_mid', '하단': 'g_bot'}[position]
    card[field] = marker
    return True


def _sandbox_ready_card_legal(engine, role, card):
    """Evaluate a Battle source as the Hand card it was before Ready.

    The battle sandbox starts after both cards have already been placed in
    Battle, while production action generation calls ``_legal_ready_card``
    from Hand.  Temporarily projecting the reviewed source back to Hand keeps
    play conditions and Hand-scoped costs authoritative without emitting any
    synthetic movement events.
    """
    owner, zone, index, live_card = engine._find_location(
        (card or {}).get('instance_id'),
    )
    if owner != role or not live_card:
        return False
    if zone == 'hand':
        return engine._legal_ready_card(live_card)
    if zone != 'battle':
        return False
    battle = engine.state['players'][role]['zones']['battle']
    hand = engine.state['players'][role]['zones']['hand']
    projected = battle.pop(index)
    hand.append(projected)
    try:
        engine._refresh_continuous_rules()
        return engine._legal_ready_card(projected)
    finally:
        hand.remove(projected)
        battle.insert(index, projected)
        engine._refresh_continuous_rules()


def _prepare_pipeline_battle(
    engine, controller, source_instance_id, event, config=None,
):
    """Prepare a real battle that naturally reaches ``event`` where possible.

    Only synthetic fixture cards are rewritten. Explicit cards placed by the
    reviewer retain their printed values so the sandbox can test an exact
    matchup; if that matchup does not produce the requested result timing the
    selected ability must remain untriggered.
    """
    if event not in BATTLE_PIPELINE_EVENTS:
        raise EffectSandboxError(
            '선택한 타이밍은 아직 실제 배틀 진행 모드를 지원하지 않습니다. '
            '직접 이벤트 비교 모드를 사용해 주세요.'
        )
    controller_card = _battle_card(engine, controller)
    other = 'p2' if controller == 'p1' else 'p1'
    opponent_card = _battle_card(engine, other)
    if not controller_card or not opponent_card:
        raise EffectSandboxError('실제 배틀 진행에는 양쪽 배틀 기술이 필요합니다.')
    if (
        controller_card.get('instance_id') == source_instance_id
        and not _sandbox_ready_card_legal(engine, controller, controller_card)
    ):
        raise EffectSandboxError('현재 상태에서는 이 기술을 레디할 수 없습니다.')

    allowed_override_fields = {
        'type', 'frame', 'damage', 'pos', 'body', 'special',
        'hit', 'guard', 'counter', 'g_top', 'g_mid', 'g_bot',
    }
    overrides = (config or {}).get('battle_overrides')
    if isinstance(overrides, dict):
        for key, card in (('controller', controller_card), ('opponent', opponent_card)):
            values = overrides.get(key)
            if isinstance(values, dict):
                for field, value in values.items():
                    if field in allowed_override_fields:
                        card[field] = copy.deepcopy(value)

    # Exact-match review must be able to exercise card-specific judgment
    # rules (for example, attack-vs-attack Clash granted only against a hand
    # judgment). In this mode the reviewer owns both printed snapshots and the
    # normal resolver, rather than this fixture helper, must decide whether the
    # requested timing is actually reached.
    setup_event = (
        '' if (config or {}).get('preserve_battle_overrides') else event
    )

    # Result timings are configured through normal printed card values. The
    # actual judgment resolver still decides the outcome; no event is fired by
    # this helper.
    if setup_event in {'hit', 'combo'}:
        if not _is_attack(controller_card):
            if not _make_fixture_attack(controller_card):
                raise EffectSandboxError(
                    f'{EVENT_LABELS[event]}를 재현할 효과 사용자의 배틀 기술이 공격 기술이 아닙니다.'
                )
        if setup_event == 'combo':
            hit_combo = '콤보' in str(controller_card.get('hit') or '')
            counter_combo = '콤보' in str(controller_card.get('counter') or '')
            if not (hit_combo or counter_combo):
                raise EffectSandboxError(
                    '실제 콤보 타이밍을 열려면 히트 또는 카운터 판정에 콤보가 인쇄된 '
                    '공격 기술이 필요합니다.'
                )
            if counter_combo and not hit_combo:
                if not _is_attack(opponent_card) and not _make_fixture_attack(opponent_card):
                    raise EffectSandboxError(
                        '카운터 콤보를 재현할 상대 배틀 기술이 공격 기술이 아닙니다.'
                    )
                controller_frame = max(
                    1, _integer(controller_card.get('frame'), 6, 1, 999),
                )
                opponent_frame = max(
                    1, _integer(opponent_card.get('frame'), 7, 1, 999),
                )
                engine.state['players'][controller]['fp'] = 0
                engine.state['players'][other]['fp'] = 0
                if opponent_card.get('sandbox_fixture'):
                    opponent_card['frame'] = controller_frame + 3
                elif controller_card.get('sandbox_fixture'):
                    controller_card['frame'] = max(1, opponent_frame - 3)
            else:
                position = str(controller_card.get('pos') or '중단')
                _make_fixture_defense(opponent_card, 'hit', position=position)
        else:
            position = str(controller_card.get('pos') or '중단')
            _make_fixture_defense(opponent_card, 'hit', position=position)
    elif setup_event in {'counter', 'opponent_counter'}:
        if not _is_attack(controller_card) and not _make_fixture_attack(controller_card):
            raise EffectSandboxError('카운터 판정을 재현할 내 배틀 기술이 공격 기술이 아닙니다.')
        if not _is_attack(opponent_card) and not _make_fixture_attack(opponent_card):
            raise EffectSandboxError('카운터 판정을 재현할 상대 배틀 기술이 공격 기술이 아닙니다.')
        controller_frame = max(1, _integer(controller_card.get('frame'), 6, 1, 999))
        opponent_frame = max(1, _integer(opponent_card.get('frame'), 7, 1, 999))
        engine.state['players'][controller]['fp'] = 0
        engine.state['players'][other]['fp'] = 0
        if setup_event == 'counter':
            if opponent_card.get('sandbox_fixture'):
                opponent_card['frame'] = controller_frame + 3
            elif controller_card.get('sandbox_fixture'):
                controller_card['frame'] = max(1, opponent_frame - 3)
        else:
            if opponent_card.get('sandbox_fixture'):
                opponent_card['frame'] = max(1, controller_frame - 3)
            elif controller_card.get('sandbox_fixture'):
                controller_card['frame'] = opponent_frame + 3
    elif setup_event in {'dodge', 'guard'}:
        special_positions = (
            _matching_special_positions(controller_card, 'dodge')
            if setup_event == 'dodge' and _is_attack(controller_card) else []
        )
        if special_positions:
            if opponent_card.get('sandbox_fixture'):
                # Runtime cards intentionally omit their effect definition;
                # static defense bounds live on the immutable ruleset card.
                controller_rules_card = (
                    (engine.ruleset.get('cards') or {}).get(
                        str(controller_card.get('code') or ''),
                    )
                    or controller_card
                )
                opponent_frame = _sandbox_defense_reference_speed(
                    controller_rules_card,
                    opponent_card.get('frame'),
                    judgment='dodge',
                    position=special_positions[0],
                )
                opponent_body = _sandbox_defense_reference_body(
                    controller_rules_card,
                    judgment='dodge',
                    position=special_positions[0],
                )
                _make_fixture_attack(
                    opponent_card, frame=opponent_frame,
                    position=special_positions[0],
                    body=opponent_body,
                )
            elif (
                not _is_attack(opponent_card)
                or opponent_card.get('pos') not in special_positions
            ):
                raise EffectSandboxError(
                    '상대 공격 기술의 판정 위치가 내 특수 회피 '
                    '조건과 맞지 않습니다.'
                )
        elif not _is_defense(controller_card):
            if not _make_fixture_defense(controller_card, event):
                raise EffectSandboxError(
                    f'{EVENT_LABELS[event]}를 재현할 효과 사용자의 배틀 기술이 수비 기술이 아닙니다.'
                )
        if not special_positions:
            position = _matching_guard_position(controller_card, event)
            if not position:
                raise EffectSandboxError(
                    f'선택한 수비 기술에 {EVENT_LABELS[event]} 판정이 인쇄된 위치가 없습니다.'
                )
            _make_fixture_attack(opponent_card, position=position)
    elif setup_event in {'opponent_dodge', 'opponent_guard'}:
        judgment = 'dodge' if setup_event == 'opponent_dodge' else 'guard'
        if not _is_attack(controller_card) and not _make_fixture_attack(controller_card):
            raise EffectSandboxError(f'{EVENT_LABELS[event]}를 재현할 내 배틀 기술이 공격 기술이 아닙니다.')
        position = str(controller_card.get('pos') or '중단')
        if not _make_fixture_defense(opponent_card, judgment, position=position):
            printed_defense_matches = (
                _is_defense(opponent_card)
                and _has_guard_judgment(
                    opponent_card, judgment, position,
                )
            )
            special_dodge_matches = (
                judgment == 'dodge'
                and _is_attack(opponent_card)
                and position in _matching_special_positions(
                    opponent_card, 'dodge',
                )
            )
            if not printed_defense_matches and not special_dodge_matches:
                raise EffectSandboxError(
                    f'상대 기술이 {position}에서 {EVENT_LABELS[event]}를 만들지 않습니다.'
                )
    elif setup_event == 'opponent_hit':
        if not _is_defense(controller_card) and not _make_fixture_defense(controller_card, 'hit'):
            raise EffectSandboxError('상대 히트를 재현할 내 배틀 기술이 수비 기술이 아닙니다.')
        position = next((
            item for item, field in (('상단', 'g_top'), ('중단', 'g_mid'), ('하단', 'g_bot'))
            if not str(controller_card.get(field) or '')
        ), '중단')
        _make_fixture_attack(opponent_card, position=position)
    elif setup_event == 'clash':
        if _is_defense(controller_card):
            position = _matching_guard_position(controller_card, 'clash')
            if not position:
                raise EffectSandboxError('선택한 수비 기술에 상쇄 판정이 없습니다.')
            _make_fixture_attack(opponent_card, position=position)
        else:
            if not _is_attack(controller_card) and not _make_fixture_attack(controller_card):
                raise EffectSandboxError('상쇄를 재현할 내 배틀 기술이 공격 기술이 아닙니다.')
            special_positions = _matching_special_positions(
                controller_card, 'clash',
            )
            if special_positions:
                if opponent_card.get('sandbox_fixture'):
                    source_frame = max(
                        2, _integer(controller_card.get('frame'), 7, 1, 999),
                    )
                    controller_rules_card = (
                        (engine.ruleset.get('cards') or {}).get(
                            str(controller_card.get('code') or ''),
                        )
                        or controller_card
                    )
                    opponent_frame = _sandbox_defense_reference_speed(
                        controller_rules_card,
                        source_frame - 1,
                        judgment='clash',
                        position=special_positions[0],
                    )
                    opponent_body = _sandbox_defense_reference_body(
                        controller_rules_card,
                        judgment='clash',
                        position=special_positions[0],
                    )
                    _make_fixture_attack(
                        opponent_card, frame=opponent_frame,
                        position=special_positions[0],
                        body=opponent_body,
                    )
                elif (
                    not _is_attack(opponent_card)
                    or opponent_card.get('pos') not in special_positions
                ):
                    raise EffectSandboxError(
                        '상대 공격 기술의 판정 위치가 내 특수 상쇄 '
                        '조건과 맞지 않습니다.'
                    )
            else:
                position = str(controller_card.get('pos') or '중단')
                if not _make_fixture_defense(opponent_card, 'clash', position=position):
                    if not _is_defense(opponent_card) or not _has_guard_judgment(
                        opponent_card, 'clash', position,
                    ):
                        raise EffectSandboxError('상대 기술이 해당 위치에서 상쇄를 만들지 않습니다.')

    engine.state['phase'] = 'battle'
    engine.engine_state['step'] = 'battle_resolution'
    # Production Ready records both revealed Battle Techniques through
    # ``_ready_card`` before starting the battle pipeline.  Sandbox cards are
    # placed directly in Battle, so reproduce that history here.  Without it,
    # effects that ask whether a character Technique was used this turn (for
    # example Atelier of Pain) resolve differently in the reviewer than in a
    # real automatic session.
    used_instance_ids = {
        str(item.get('instance_id') or '')
        for item in engine.engine_state.get('card_use_history') or []
        if isinstance(item, dict)
    }
    for role, card in ((controller, controller_card), (other, opponent_card)):
        if str(card.get('instance_id') or '') not in used_instance_ids:
            engine._mark_card_used(card, role, 'ready')
    engine.engine_state['ready_cards'] = {
        controller: controller_card['instance_id'],
        other: opponent_card['instance_id'],
    }
    engine.engine_state['battle'] = {}
    engine.engine_state['pipeline'] = {'kind': 'battle', 'stage': 'start'}


def _run_with_battle_pipeline_trace(engine, trace, callback):
    """Run engine work while recording the real battle pipeline boundaries."""
    original = engine._advance_battle_pipeline

    def traced(pipeline):
        stage = str((pipeline or {}).get('stage') or '')
        entry = {'stage': stage}
        if stage == 'reveal_cost':
            entry['event'] = 'battle_reveal'
        elif stage in {'use', 'before_judgment', 'after_judgment', 'after_use'}:
            entry['event'] = stage
        elif stage == 'result_triggers':
            battle = engine.engine_state.get('battle') or {}
            index = _integer((pipeline or {}).get('trigger_index'), 0, 0, 999)
            triggers = battle.get('trigger_sequence') or []
            if index < len(triggers):
                entry['event'] = str(triggers[index][0])
        trace.append(entry)
        return original(pipeline)

    engine._advance_battle_pipeline = traced
    try:
        callback()
    finally:
        engine._advance_battle_pipeline = original


def _prepare_combo_pipeline(engine, controller, source_instance_id, config):
    """Start one real Combo-card resolution after a synthetic 1-Combo.

    A hand/list/side source is itself used as the follow-up card.  A source
    which watches Combo from Battle/Lumen/Passive instead remains in that
    active zone while a synthetic, effectless follow-up is used.  This is
    essential for cards such as Madness: its ``Combo`` and ``Combo end``
    effects are reactions from Lumen, not text on a Technique being played.

    ``opponent_combo_end`` likewise runs an actual Combo owned by the
    opponent.  Legality, play costs, continuous Combo modifiers and every
    per-card timing still use the normal engine.
    """
    source_owner, source_zone, _index, source = engine._find_location(
        source_instance_id,
    )
    if source_owner != controller:
        raise EffectSandboxError('효과 카드의 소유자가 효과 사용자와 다릅니다.')
    other = 'p2' if controller == 'p1' else 'p1'
    combo_owner = (
        other if str(config.get('event') or '') == 'opponent_combo_end'
        else controller
    )
    combo_opponent = 'p2' if combo_owner == 'p1' else 'p1'
    starter = _battle_card(engine, combo_owner)
    opposing = _battle_card(engine, combo_opponent)
    if not starter or not opposing:
        raise EffectSandboxError('실제 콤보 해석에는 양쪽 배틀 기술이 필요합니다.')

    use_source = (
        combo_owner == controller
        and source_zone in {'hand', 'list', 'side'}
        and _is_attack(source)
    )
    combo_card = source
    if not use_source:
        code = f'SANDBOX-{combo_owner.upper()}-COMBO-FOLLOWUP'
        snapshot = _fixture_snapshot(
            code, f'테스트 콤보 기술 ({combo_owner})', '공격',
            frame=6, damage=400,
        )
        if combo_owner == controller:
            snapshot.update({
                'character_id': source.get('character_id'),
                'character_key': source.get('character_key') or '',
            })
        engine.ruleset.setdefault('cards', {})[code] = snapshot
        combo_card = _runtime_card(
            snapshot, combo_owner,
            f'sandbox-fixture-{combo_owner}-combo-followup',
            sandbox_fixture=True,
        )
        engine.state['players'][combo_owner]['zones']['hand'].append(
            combo_card,
        )

    source_frame = max(1, _integer(combo_card.get('frame'), 6, 1, 999))
    previous_speed = _integer(
        config.get('combo_previous_speed'),
        max(1, source_frame - 1), 1, 999,
    )
    if starter.get('sandbox_fixture'):
        _make_fixture_attack(starter, frame=previous_speed)
    engine.state['phase'] = 'battle'
    engine.engine_state['step'] = 'combo'
    engine.engine_state['ready_cards'] = {
        combo_owner: starter['instance_id'],
        combo_opponent: opposing['instance_id'],
    }
    engine.engine_state['battle'] = {
        combo_owner: {
            'card': copy.deepcopy(starter),
            'instance_id': starter['instance_id'],
        },
        combo_opponent: {
            'card': copy.deepcopy(opposing),
            'instance_id': opposing['instance_id'],
        },
        'actual_damage_received': {side: 0 for side in PLAYER_SIDES},
    }
    engine.grant_combo(
        combo_owner, source=starter['instance_id'], special=False,
        # A Lumen/Passive/Battle watcher must observe the real 1-Combo
        # opening event.  When the reviewed Technique itself is the later
        # follow-up, its own per-card Combo event is emitted by
        # ``_start_combo_card`` instead, so do not manufacture a second
        # source-card trigger here.
        trigger_event=not use_source,
    )
    combo = engine.engine_state['combo']
    requested_combo_number = max(
        2,
        _integer(config.get('combo_number'), 2, 1, 99),
    )
    previous_card_code = str(
        config.get('combo_previous_card_code') or ''
    ).strip().upper()
    previous_card_snapshot = None
    if previous_card_code:
        if requested_combo_number < 3:
            raise EffectSandboxError(
                '직전 콤보 카드 코드는 3콤보 이상을 검증할 때만 '
                '지정할 수 있습니다.'
            )
        previous_card_snapshot = (
            (engine.ruleset.get('cards') or {}).get(previous_card_code)
        )
        if not previous_card_snapshot:
            raise EffectSandboxError(
                f'직전 콤보 카드 정의를 찾을 수 없습니다: '
                f'{previous_card_code}'
            )
    history_ids = []
    history_count = max(0, requested_combo_number - 2)
    for index in range(history_count):
        combo_number = index + 2
        is_last = index == history_count - 1
        history_frame = (
            previous_speed
            if is_last
            else max(1, previous_speed - (history_count - index))
        )
        if is_last and previous_card_snapshot:
            history = _runtime_card(
                previous_card_snapshot, combo_owner,
                f'sandbox-previous-{combo_owner}-combo-history-'
                f'{combo_number}',
            )
        else:
            code = (
                f'SANDBOX-{combo_owner.upper()}-COMBO-HISTORY-'
                f'{combo_number}'
            )
            snapshot = _fixture_snapshot(
                code,
                f'테스트 {combo_number}콤보 이력 ({combo_owner})',
                '공격', frame=history_frame, damage=400,
            )
            engine.ruleset.setdefault('cards', {})[code] = snapshot
            history = _runtime_card(
                snapshot, combo_owner,
                f'sandbox-fixture-{combo_owner}-combo-history-'
                f'{combo_number}',
                sandbox_fixture=True,
            )
        history['combo_history_fixture'] = True
        engine.state['players'][combo_owner]['zones']['battle'].append(
            history,
        )
        history_ids.append(history['instance_id'])
    if history_ids:
        combo['used'] = list(history_ids)
        combo['next_penalty'] = (requested_combo_number - 1) * 100
        combo['proposal_submitted'] = True
    combo['last_speed'] = previous_speed
    requested_speed = config.get('combo_speed')
    combo_speeds = (
        [_integer(requested_speed, source_frame, 1, 999)]
        if requested_speed not in {None, ''} else []
    )
    followup_code = str(config.get('combo_followup_code') or '').strip().upper()
    followup_card = None
    if followup_code:
        if not use_source or requested_combo_number != 2:
            raise EffectSandboxError(
                '동시 후속 카드 제안은 검수 카드가 첫 2콤보 기술일 때만 '
                '사용할 수 있습니다.'
            )
        for zone_cards in (
            engine.state['players'][combo_owner].get('zones') or {}
        ).values():
            followup_card = next((
                card for card in zone_cards
                if card.get('instance_id') != combo_card.get('instance_id')
                and str(card.get('code') or '').upper() == followup_code
            ), None)
            if followup_card:
                break
        if not followup_card:
            raise EffectSandboxError(
                f'함께 제시할 후속 카드를 찾을 수 없습니다: {followup_code}'
            )
    # Production play treats an illegal later Combo card as a normal Combo
    # interruption and therefore does not raise.  In the review sandbox that
    # would make an invalid requested Combo number/Speed look successful.
    # Validate the reviewed card through the same authoritative helpers first
    # so the editor can distinguish a genuine timing result from an illegal
    # test setup.
    engine._refresh_continuous_rules()
    if followup_card:
        followup_speed = config.get('combo_followup_speed')
        # Exact two-card review proposals must use production initial-Combo
        # staging.  The general review-isolation enumerator intentionally
        # keeps the synthetic 1-Combo Speed so an arbitrary later slot can be
        # inspected alone, but that would incorrectly reject a slower first
        # 2-Combo card even though the real rules leave its Speed free.
        previous_review_mode = engine.ruleset.get('review_execution_mode')
        engine.ruleset['review_execution_mode'] = 'battle_pipeline'
        try:
            available_actions = engine._combo_actions(combo_owner, combo)
        finally:
            engine.ruleset['review_execution_mode'] = previous_review_mode
        pair_actions = [
            action for action in available_actions
            if action.get('type') == 'play_combo_pair'
            and (action.get('payload') or {}).get('card_instance_ids') == [
                combo_card['instance_id'], followup_card['instance_id'],
            ]
        ]
        if combo_speeds:
            pair_actions = [
                action for action in pair_actions
                if _integer(
                    ((action.get('payload') or {}).get('combo_speeds') or [-1])[0],
                    -1, -1, 999,
                ) == combo_speeds[0]
            ]
        if followup_speed not in {None, ''}:
            requested_followup_speed = _integer(
                followup_speed, 0, 1, 999,
            )
            pair_actions = [
                action for action in pair_actions
                if _integer(
                    ((action.get('payload') or {}).get('combo_speeds') or [-1, -1])[1],
                    -1, -1, 999,
                ) == requested_followup_speed
            ]
        if not pair_actions:
            available_pairs = [
                str(action.get('label') or '')
                for action in available_actions
                if action.get('type') == 'play_combo_pair'
            ][:8]
            available_hint = (
                f' 현재 가능한 조합: {" / ".join(available_pairs)}'
                if available_pairs else (
                    ' 현재 가능한 2·3콤보 조합이 없습니다.'
                    f' 단일/연속 후보: '
                    f'{" / ".join(str(action.get("label") or "") for action in available_actions[:8])}'
                )
            )
            raise EffectSandboxError(
                '선택한 두 기술과 속도로 제시할 수 있는 실제 2·3콤보가 없습니다.'
                + available_hint
            )
        pair = sorted(
            pair_actions,
            key=lambda action: tuple(
                (action.get('payload') or {}).get('combo_speeds') or []
            ),
        )[0]
        payload = pair.get('payload') or {}
        engine._play_combo(
            combo_owner,
            list(payload.get('card_instance_ids') or []),
            list(payload.get('combo_speeds') or []),
            list(payload.get('ignore_damage_penalty') or [False, False]),
            list(payload.get('ignore_speed') or [False, False]),
        )
        return
    found_owner, found_zone, _found_index, live_combo_card = (
        engine._find_location(combo_card['instance_id'])
    )
    projected_card, combo_rules, borrow_rule = (
        engine._combo_candidate_projection(
            combo_owner, live_combo_card, combo,
            found_owner=found_owner, found_zone=found_zone,
        ) if live_combo_card else (None, [], None)
    )
    if (
        not live_combo_card
        or (found_owner != combo_owner and not borrow_rule)
        or not engine._combo_zone_allowed(
            combo_owner, live_combo_card, found_zone, combo,
        )
        or not engine._combo_card_legal(
            combo_owner, projected_card, combo,
            selected_speed=(combo_speeds[0] if combo_speeds else None),
        )
    ):
        raise EffectSandboxError('사용할 수 없는 콤보 카드입니다.')
    engine._start_combo_card(
        combo_owner, [combo_card['instance_id']], combo_speeds,
    )


def _run_with_combo_pipeline_trace(engine, trace, callback):
    """Run engine work while recording actual Combo and Combo-end timings."""
    original_combo = engine._advance_combo_pipeline
    original_end = engine._advance_combo_end_pipeline

    def traced_combo(pipeline):
        stage = str((pipeline or {}).get('stage') or '')
        event = stage if stage in {
            'combo', 'combo_window', 'use', 'after_use',
        } else None
        trace.append({
            'pipeline': 'combo_resolution', 'stage': stage,
            **({'event': event} if event else {}),
        })
        return original_combo(pipeline)

    def traced_end(pipeline):
        stage = str((pipeline or {}).get('stage') or '')
        event = (
            'combo_end' if stage == 'owner_effects'
            else ('opponent_combo_end' if stage == 'opponent_effects' else None)
        )
        trace.append({
            'pipeline': 'combo_end', 'stage': stage,
            **({'event': event} if event else {}),
        })
        return original_end(pipeline)

    engine._advance_combo_pipeline = traced_combo
    engine._advance_combo_end_pipeline = traced_end
    try:
        callback()
    finally:
        engine._advance_combo_pipeline = original_combo
        engine._advance_combo_end_pipeline = original_end


def _prepare_catch_pipeline(engine, controller, source_instance_id, config):
    """Declare a card through the normal Catch action contract.

    A Hand/List attack is itself the Catch Technique.  Persistent Lumen,
    Passive, or Ultimate cards instead keep watching from their real zone
    while a same-character reviewer fixture performs the Catch.  This mirrors
    the Combo sandbox and makes cards such as Jetpack testable without
    pretending that the Special card itself is an attack.
    """
    source_owner, source_zone, _index, source = engine._find_location(
        source_instance_id,
    )
    if source_owner != controller or source_zone not in {
        'hand', 'list', 'side', 'break', 'lumen', 'passive', 'ultimate',
    }:
        raise EffectSandboxError(
            '실제 캐치 해석을 하려면 효과 카드의 시작 영역을 '
            '패·리스트·사이드 덱·브레이크·루멘·패시브·얼티밋 중 '
            '하나로 지정해 주세요.'
        )
    catch_card = source
    catch_zone = source_zone
    if not _is_attack(source):
        if source_zone not in {'lumen', 'passive', 'ultimate'}:
            raise EffectSandboxError(
                '지속 영역 밖의 비공격 카드는 실제 캐치 기술로 사용할 수 '
                '없습니다.'
            )
        requested_speed = config.get('catch_speed')
        frame = _integer(requested_speed, 6, 1, 99)
        code = f'SANDBOX-{controller.upper()}-CATCH-ATTACK'
        snapshot = _fixture_snapshot(
            code, f'테스트 캐치 기술 ({controller})', '공격',
            frame=frame, damage=400, pos='중단',
        )
        snapshot.update({
            'character_id': source.get('character_id'),
            'character_key': source.get('character_key') or '',
            # Keep the observer's FP assertion independent from the
            # synthetic Catch card's printed judgment.
            'hit': '0', 'counter': '0',
        })
        engine.ruleset.setdefault('cards', {})[code] = snapshot
        catch_card = _runtime_card(
            snapshot, controller, f'sandbox-{controller}-catch-attack',
            sandbox_fixture=True,
        )
        catch_card['face_up'] = False
        catch_zone = 'hand'
        engine.state['players'][controller]['zones']['hand'].append(
            catch_card
        )
    engine.state['phase'] = 'battle'
    engine.engine_state['step'] = 'catch'
    engine.engine_state['catch'] = {
        'owner': controller, 'source': 'sandbox-catch-opportunity',
        'allow_zones': [catch_zone], 'max_speed': 999,
    }
    requested_speed = config.get('catch_speed')
    actions = [
        action for action in engine.list_legal_actions(controller)
        if action.get('type') == 'play_catch_card'
        and (
            (action.get('card') or {}).get('instance_id')
            == catch_card.get('instance_id')
        )
    ]
    if requested_speed not in {None, ''}:
        speed = _integer(requested_speed, 0, 0, 999)
        actions = [
            action for action in actions
            if _integer(action.get('choice_speed'), -1, -1, 999) == speed
        ]
    if not actions:
        raise EffectSandboxError(
            '선택한 카드와 속도로 실행할 수 있는 실제 캐치 행동이 없습니다.'
        )
    return sorted(
        actions,
        key=lambda item: (
            _integer(item.get('choice_speed'), 999, 0, 999),
            str(item.get('action_id') or ''),
        ),
    )[0]


def _run_with_catch_pipeline_trace(engine, trace, callback):
    """Run engine work while recording actual Catch-card timing stages."""
    original = engine._advance_catch_pipeline

    def traced(pipeline):
        stage = str((pipeline or {}).get('stage') or '')
        event = stage if stage in {'use', 'catch', 'hit', 'after_use'} else None
        trace.append({
            'pipeline': 'catch_resolution', 'stage': stage,
            **({'event': event} if event else {}),
        })
        return original(pipeline)

    engine._advance_catch_pipeline = traced
    try:
        callback()
    finally:
        engine._advance_catch_pipeline = original


def _run_with_event_trace(engine, trace, callback, *, pipeline='phase_machine'):
    """Record timing windows that the domain/state machine actually fires."""
    original = engine._fire

    def traced(event, context=None):
        trace.append({
            'pipeline': pipeline, 'stage': str(event), 'event': str(event),
        })
        return original(event, context)

    engine._fire = traced
    try:
        callback()
    finally:
        engine._fire = original


def _run_with_battle_family_trace(engine, trace, callback):
    """Trace Battle, Combo and Catch continuations opened by one another."""
    _run_with_event_trace(
        engine, trace,
        lambda: _run_with_battle_pipeline_trace(
            engine, trace,
            lambda: _run_with_combo_pipeline_trace(
                engine, trace,
                lambda: _run_with_catch_pipeline_trace(
                    engine, trace, callback,
                ),
            ),
        ),
        pipeline='domain_events',
    )


def _run_phase_pipeline(engine, event, config):
    """Reach game/turn/phase windows through the normal state machine."""
    target_phase = _phase(config.get('phase'))
    previous_phase = {
        'lumen': 'recovery', 'ready': 'lumen', 'battle': 'ready',
        'get': 'battle', 'recovery': 'get',
    }[target_phase]
    if event == 'game_start':
        engine.engine_state['startup_stage'] = 'after_game_start'
        engine._fire('game_start', {'turn': engine.state.get('turn', 1)})
        engine._continue()
        return
    if event == 'turn_start':
        engine.engine_state['startup_stage'] = 'after_game_start'
        engine._continue()
        return
    if event == 'turn_end':
        engine.state['phase'] = 'recovery'
        engine.engine_state['step'] = 'phase_actions'
        engine._advance_phase('lumen')
        engine._continue()
        return
    engine.state['phase'] = previous_phase if event == 'phase_start' else target_phase
    engine.engine_state['step'] = 'phase_actions'
    engine.engine_state['phase_passes'] = []
    engine.engine_state['phase_skipped_players'] = []
    next_phase = target_phase if event == 'phase_start' else {
        'lumen': 'ready', 'ready': 'battle', 'battle': 'get',
        'get': 'recovery', 'recovery': 'lumen',
    }[target_phase]
    engine._advance_phase(next_phase)
    engine._continue()


def _apply_engine_overrides(engine, value):
    if not isinstance(value, dict):
        return
    allowed = {
        'usage', 'card_use_history', 'ability_resolution_history',
        'battle_result_history', 'turn_damage_received', 'effect_damage_counts',
    }
    for key in allowed:
        if key in value and isinstance(value[key], (dict, list)):
            engine.engine_state[key] = copy.deepcopy(value[key])


def _event_context(engine, controller, source_instance_id, config):
    other = 'p2' if controller == 'p1' else 'p1'
    source = engine._find_card(source_instance_id)
    opponent_card = _battle_card(engine, other)
    context = copy.deepcopy(config.get('context') or {})
    if not isinstance(context, dict):
        context = {}
    context.update({
        'controller': controller,
        'source_card_instance_id': source_instance_id,
        'source_card': copy.deepcopy(source),
        'source_zone': engine._find_location(source_instance_id)[1],
        'opponent_card': copy.deepcopy(opponent_card),
        'source_only_event': True,
        'result': str(config.get('result') or context.get('result') or ''),
        'controller_speed': _integer(
            config.get('controller_speed'), source.get('frame') or 0,
        ),
        'opponent_speed': _integer(
            config.get('opponent_speed'), (opponent_card or {}).get('frame') or 0,
        ),
        'controller_damage_received': _integer(config.get('controller_damage_received')),
        'opponent_damage_received': _integer(config.get('opponent_damage_received')),
        'combo_number': _integer(config.get('combo_number'), 1, 0, 99),
    })
    if config.get('event') == 'combo_end':
        context['combo_owner'] = controller
    elif config.get('event') == 'opponent_combo_end':
        context['combo_owner'] = other
    return context


def start_effect_sandbox(source_snapshot, definition, ability_id, support_snapshots, config):
    """Create and execute one isolated ability until a user decision is needed."""
    ability = _selected_ability(definition, ability_id)
    controller = _side(config.get('controller'))
    other = 'p2' if controller == 'p1' else 'p1'
    source_zone = _zone(
        config.get('source_zone'),
        ((ability.get('active_zones') or ['battle'])[0]),
    )
    phase = _phase(config.get('phase'))
    event = str(config.get('event') or (ability.get('trigger') or {}).get('event') or '')
    execution_mode = str(config.get('execution_mode') or 'direct_event')
    if execution_mode not in {
        'direct_event', 'battle_pipeline', 'combo_pipeline', 'catch_pipeline',
        'phase_pipeline',
    }:
        raise EffectSandboxError('지원하지 않는 효과 테스트 실행 방식입니다.')
    if ability.get('mode') != 'continuous' and event not in TRIGGERS:
        raise EffectSandboxError('실행할 유효한 트리거를 선택해 주세요.')
    defined_events = set((ability.get('trigger') or {}).get('events') or [])
    if (ability.get('trigger') or {}).get('event'):
        defined_events.add((ability.get('trigger') or {}).get('event'))
    if (
        execution_mode in {
            'battle_pipeline', 'combo_pipeline', 'catch_pipeline',
            'phase_pipeline',
        }
        and ability.get('mode') != 'continuous'
        and event not in defined_events
    ):
        raise EffectSandboxError(
            '실제 진행 경로 모드에서는 해당 효과에 정의된 타이밍만 '
            '검증할 수 있습니다. 다른 타이밍 비교는 직접 이벤트 모드를 사용해 주세요.'
        )

    source_code = str(source_snapshot.get('code') or 'SANDBOX-SOURCE')
    isolated_definition = copy.deepcopy(definition)
    if config.get('include_source_effects'):
        source_abilities = copy.deepcopy(definition.get('abilities') or [])
        source_ability_ids = {
            str(item.get('id') or '')
            for item in source_abilities if isinstance(item, dict)
        }
        # Common sandbox prototypes are deliberately not stored in the
        # reviewed card definition.  Keeping the prototype alongside all
        # source abilities makes the “include this card's other effects”
        # switch usable for testing continuous limits and replacements.
        if str(ability.get('id') or '') not in source_ability_ids:
            source_abilities.insert(0, copy.deepcopy(ability))
        isolated_definition['abilities'] = source_abilities
    else:
        isolated_definition['abilities'] = [ability]
    isolated_source = copy.deepcopy(source_snapshot)
    isolated_source['code'] = source_code
    isolated_source['effect_definition'] = isolated_definition
    ruleset_cards = {source_code: isolated_source}

    include_support_effects = bool(config.get('include_support_effects'))
    normalized_support = {}
    for raw_id, snapshot in (support_snapshots or {}).items():
        code = str(snapshot.get('code') or f'SANDBOX-CARD-{raw_id}')
        support = copy.deepcopy(snapshot)
        support['code'] = code
        support['effect_definition'] = (
            copy.deepcopy(snapshot.get('effect_definition') or NO_EFFECT_DEFINITION)
            if include_support_effects
            else _card_definition_without_triggered_abilities(
                snapshot.get('effect_definition'),
            )
        )
        ruleset_cards[code] = support
        normalized_support[str(raw_id)] = support

    ruleset_characters = {}
    for snapshot in [isolated_source, *normalized_support.values()]:
        character_id = snapshot.get('character_id')
        if character_id is None:
            continue
        key = str(character_id)
        entry = ruleset_characters.setdefault(key, {
            'id': character_id,
            'key': snapshot.get('character_key') or '',
            'deck_rules': {},
        })
        definition = snapshot.get('effect_definition') or {}
        entry['deck_rules'] = merge_deck_rules(
            entry.get('deck_rules'), definition.get('deck_rules'),
        )

    ruleset = {
        # The engine reserves this version for one-card review isolation. It
        # permits a normal Combo timing to open without manufacturing the
        # unrelated mandatory 2/3-Combo pair, while production releases keep
        # the full pair requirement.
        'version': 'automatic-effect-v2',
        'review_execution_mode': execution_mode,
        'engine_schema_version': 1,
        'effect_schema_version': 1,
        'cards': ruleset_cards,
        'characters': ruleset_characters,
    }
    player_config = config.get('players') if isinstance(config.get('players'), dict) else {}
    players = {}
    for side in PLAYER_SIDES:
        values = player_config.get(side) if isinstance(player_config.get(side), dict) else {}
        hp = _integer(values.get('hp'), 4000)
        fp = _integer(values.get('fp'), 5, 0, 999)
        passive = values.get('passive_state') if isinstance(values.get('passive_state'), dict) else {}
        character = (
            copy.deepcopy(values.get('character'))
            if isinstance(values.get('character'), dict)
            else (
                copy.deepcopy(isolated_source.get('character') or {})
                if side == controller else {}
            )
        )
        if values.get('hand_limit') is not None:
            character['hand_limit'] = _integer(
                values.get('hand_limit'), 0, 0, 99,
            )
        players[side] = _empty_player(
            side, hp, fp, passive, character=character,
        )

    source = _runtime_card(isolated_source, controller, 'sandbox-source')
    # A reviewed Technique that starts in Hand must have the same hidden
    # orientation as a production Hand card.  Hand-reaction definitions can
    # intentionally require ``context.source_card.face_up == False`` (for
    # example CB02-AT-035), so forcing every review source face-up silently
    # prevents the real timing from being exercised in battle-pipeline mode.
    if source_zone == 'hand':
        source['face_up'] = False
    players[controller]['zones'][source_zone].append(source)

    fixture_mode = str(config.get('fixture_mode') or 'choices')
    if fixture_mode not in {'choices', 'minimal', 'none'}:
        fixture_mode = 'choices'
    if fixture_mode == 'choices':
        for side, zone, card in _selector_fixture_cards(
            ability, controller, ruleset_cards, source['instance_id'],
        ):
            players[side]['zones'][zone].append(card)
        fixture_zones = ('hand', 'list', 'side', 'lumen', 'break')
        for side in PLAYER_SIDES:
            for zone, card in _fixture_cards(side, fixture_zones, ruleset_cards):
                players[side]['zones'][zone].append(card)

    placements = config.get('cards') if isinstance(config.get('cards'), list) else []
    if len(placements) > MAX_SUPPORT_CARDS:
        raise EffectSandboxError(f'추가 카드는 최대 {MAX_SUPPORT_CARDS}장까지 배치할 수 있습니다.')
    for index, placement in enumerate(placements):
        if not isinstance(placement, dict):
            continue
        card_id = str(placement.get('card_id') or '')
        snapshot = normalized_support.get(card_id)
        if not snapshot:
            raise EffectSandboxError(f'배치할 카드를 찾을 수 없습니다: {card_id}')
        side = _side(placement.get('owner'))
        zone = _zone(placement.get('zone'), 'hand')
        card = _runtime_card(snapshot, side, f'sandbox-card-{index + 1}-{card_id}')
        card['face_up'] = bool(placement.get('face_up', zone not in {'hand', 'side'}))
        if placement.get('attached_to_source'):
            if side != controller:
                raise EffectSandboxError(
                    '효과 카드에 세트할 추가 카드는 효과 사용자와 소유자가 같아야 합니다.'
                )
            if source_zone != 'battle':
                raise EffectSandboxError(
                    '추가 카드를 세트하려면 효과 카드 영역을 배틀 존으로 지정해야 합니다.'
                )
            card['attached_to'] = source['instance_id']
            # Review rows represent cards already set for the current Battle.
            # Production set cards lose that relationship during Battle
            # cleanup; keeping only ``attached_to`` here left a card in List
            # still pointing at a host which had already returned to Hand.
            card['attachment_expires'] = 'battle'
        players[side]['zones'][zone].append(card)

    if fixture_mode in {'choices', 'minimal'}:
        for side in PLAYER_SIDES:
            if not any(not card.get('attached_to') for card in players[side]['zones']['battle']):
                code = f'SANDBOX-{side.upper()}-BATTLE-ATTACK'
                snapshot = _fixture_snapshot(
                    code, f'테스트 배틀 기술 ({side})', '공격', frame=7, damage=500,
                )
                ruleset_cards[code] = snapshot
                players[side]['zones']['battle'].append(_runtime_card(
                    snapshot, side, f'sandbox-fixture-{side}-battle-attack',
                    sandbox_fixture=True,
                ))

    state = {
        'turn': _integer(config.get('turn'), 1, 1, 999),
        'phase': phase,
        'priority_player': _side(config.get('priority_player'), controller),
        'random_seed': str(config.get('seed') or f'sandbox:{source_code}:{ability_id}'),
        'players': players,
    }
    engine = AutomaticGameEngine(
        state, ruleset, version=1, seed=state['random_seed'], now=SANDBOX_EPOCH,
    )
    _set_battle_context(engine)
    _apply_engine_overrides(engine, config.get('engine'))
    engine.engine_state['turn_damage_received'] = {
        controller: _integer(config.get('controller_turn_damage_received')),
        other: _integer(config.get('opponent_turn_damage_received')),
    }
    context = _event_context(engine, controller, source['instance_id'], {
        **copy.deepcopy(config), 'event': event,
    })

    pipeline_trace = []
    if ability.get('mode') == 'continuous' and execution_mode == 'direct_event':
        engine._refresh_continuous_rules()
    elif execution_mode == 'battle_pipeline':
        _prepare_pipeline_battle(
            engine, controller, source['instance_id'], event, config,
        )
        _run_with_battle_family_trace(
            engine, pipeline_trace, engine._continue,
        )
    elif execution_mode == 'combo_pipeline':
        if event not in COMBO_PIPELINE_EVENTS:
            raise EffectSandboxError(
                '선택한 타이밍은 실제 콤보 기술 해석 모드를 '
                '지원하지 않습니다.'
            )
        _prepare_combo_pipeline(
            engine, controller, source['instance_id'], config,
        )
        _run_with_battle_family_trace(
            engine, pipeline_trace, engine._continue,
        )
    elif execution_mode == 'catch_pipeline':
        if event not in CATCH_PIPELINE_EVENTS:
            raise EffectSandboxError(
                '선택한 타이밍은 실제 캐치 기술 해석 모드를 '
                '지원하지 않습니다.'
            )
        action = _prepare_catch_pipeline(
            engine, controller, source['instance_id'], config,
        )

        def submit_catch():
            engine.submit_action(
                controller, action['action_id'],
                command_id='effect-sandbox-catch-start',
            )

        _run_with_event_trace(
            engine, pipeline_trace,
            lambda: _run_with_battle_family_trace(
                engine, pipeline_trace, submit_catch,
            ),
            pipeline='catch_events',
        )
    elif execution_mode == 'phase_pipeline':
        if event not in PHASE_PIPELINE_EVENTS:
            raise EffectSandboxError(
                '선택한 타이밍은 실제 게임·턴·페이즈 진행 모드를 '
                '지원하지 않습니다.'
            )
        _run_with_event_trace(
            engine, pipeline_trace,
            lambda: _run_phase_pipeline(engine, event, config),
        )
    else:
        engine._fire(event, context)
        engine._continue()

    return {
        'sandbox_version': SANDBOX_VERSION,
        'ruleset': ruleset,
        'state': engine.state,
        'events': engine.events,
        'engine_version': engine.version,
        'source_instance_id': source['instance_id'],
        'source_code': source_code,
        'ability_id': str(ability_id),
        'ability_mode': ability.get('mode'),
        'event': event,
        'execution_mode': execution_mode,
        'pipeline_trace': pipeline_trace,
        'now': SANDBOX_EPOCH.isoformat(),
        'step': 0,
        'decision_history': [],
        'action_history': [],
    }


def continue_effect_sandbox(
    payload, selected=None, *, action_id=None, owner=None,
):
    """Continue a pending choice or normal game action via the public API."""
    if not isinstance(payload, dict) or payload.get('sandbox_version') != SANDBOX_VERSION:
        raise EffectSandboxError('지원하지 않는 효과 테스트 데이터입니다.')
    step = _integer(payload.get('step'))
    now = SANDBOX_EPOCH + timedelta(seconds=step + 1)
    engine = AutomaticGameEngine(
        payload.get('state') or {}, payload.get('ruleset') or {},
        version=payload.get('engine_version') or 1,
        events=payload.get('events') or [],
        seed=(payload.get('state') or {}).get('random_seed') or 'effect-sandbox',
        now=now,
    )
    decision = engine.engine_state.get('pending_decision') or {}
    decision_owner = decision.get('owner')
    if decision_owner in PLAYER_SIDES:
        actor = decision_owner
        action = next((
            item for item in engine.list_legal_actions(actor)
            if item.get('type') == 'submit_decision'
        ), None)
        if not action:
            raise EffectSandboxError('현재 선택을 실행할 합법 행동을 찾을 수 없습니다.')
    else:
        if owner not in PLAYER_SIDES:
            raise EffectSandboxError('게임 행동을 수행할 플레이어가 올바르지 않습니다.')
        actor = owner
        action = next((
            item for item in engine.list_legal_actions(actor)
            if item.get('action_id') == str(action_id or '')
            and item.get('type') in SANDBOX_ACTION_TYPES
        ), None)
        if not action:
            raise EffectSandboxError('현재 진행할 수 있는 검수용 게임 행동이 아닙니다.')
    selected_ids = [str(item) for item in (selected or [])]
    option_lookup = {
        str(option.get('id')): option
        for option in decision.get('options') or []
    }
    pipeline_trace = copy.deepcopy(payload.get('pipeline_trace') or [])

    def submit():
        engine.submit_action(
            actor, action['action_id'], {'selected': selected_ids},
            command_id=f'effect-sandbox-{step + 1}',
        )

    try:
        if payload.get('execution_mode') in {
            'battle_pipeline', 'combo_pipeline', 'catch_pipeline',
        }:
            if payload.get('execution_mode') == 'catch_pipeline':
                _run_with_event_trace(
                    engine, pipeline_trace,
                    lambda: _run_with_battle_family_trace(
                        engine, pipeline_trace, submit,
                    ),
                    pipeline='catch_events',
                )
            else:
                _run_with_battle_family_trace(
                    engine, pipeline_trace, submit,
                )
        elif payload.get('execution_mode') == 'phase_pipeline':
            _run_with_event_trace(engine, pipeline_trace, submit)
        else:
            submit()
    except EngineError as exc:
        raise EffectSandboxError(str(exc)) from exc
    result = copy.deepcopy(payload)
    decision_history = copy.deepcopy(payload.get('decision_history') or [])
    action_history = copy.deepcopy(payload.get('action_history') or [])
    if decision_owner in PLAYER_SIDES:
        decision_history.append({
            'id': decision.get('id'), 'owner': actor,
            'kind': decision.get('kind'), 'prompt': decision.get('prompt'),
            'minimum': int(decision.get('minimum') or 0),
            'maximum': int(decision.get('maximum') or 0),
            'optional': bool(decision.get('optional')),
            'selected': [
                {
                    'id': selected_id,
                    'label': str(
                        (option_lookup.get(selected_id) or {}).get('label')
                        or selected_id
                    ),
                    'owner': (option_lookup.get(selected_id) or {}).get('owner'),
                    'zone': (option_lookup.get(selected_id) or {}).get('zone'),
                }
                for selected_id in selected_ids
            ],
        })
    else:
        action_history.append({
            'owner': actor, 'action_id': action.get('action_id'),
            'type': action.get('type'), 'label': action.get('label'),
        })
    result.update({
        'state': engine.state,
        'events': engine.events,
        'engine_version': engine.version,
        'now': now.isoformat(),
        'step': step + 1,
        'decision_history': decision_history,
        'action_history': action_history,
        'pipeline_trace': pipeline_trace,
    })
    return result


def _card_lookup(state):
    lookup = {}
    for side in PLAYER_SIDES:
        zones = (((state.get('players') or {}).get(side) or {}).get('zones') or {})
        for zone, cards in zones.items():
            for card in cards:
                lookup[str(card.get('instance_id'))] = {
                    'name': card.get('name') or card.get('code') or '카드',
                    'code': card.get('code') or '', 'owner': side, 'zone': zone,
                }
    return lookup


def _project_card(card, engine=None, owner=None):
    projected = {
        'instance_id': str(card.get('instance_id') or ''),
        'code': str(card.get('code') or ''),
        'name': str(card.get('name') or card.get('code') or '카드'),
        'type': str(card.get('type') or ''),
        'frame': card.get('frame'), 'damage': card.get('damage'),
        'position': card.get('pos'), 'body': card.get('body'),
        'special': card.get('special'),
        'face_up': bool(card.get('face_up')),
        'fixture': bool(card.get('sandbox_fixture')),
        'attached_to': card.get('attached_to'),
    }
    if engine is not None and owner in PLAYER_SIDES:
        if card.get('frame') is not None:
            projected['effective_frame'] = engine.card_stat(
                card, 'frame', owner,
            )
        if card.get('damage') is not None:
            projected['effective_damage'] = engine.card_stat(
                card, 'damage', owner,
            )
    return projected


def _event_summary(event, cards):
    payload = event.get('payload') or {}
    event_type = str(event.get('type') or '')
    card = cards.get(str(payload.get('card_instance_id') or '')) or {}
    name = card.get('name') or payload.get('card_instance_id') or ''
    if event_type == 'card_moved':
        return (
            f'{name}: {ZONE_LABELS.get(payload.get("from_zone"), payload.get("from_zone"))}'
            f' → {ZONE_LABELS.get(payload.get("to_zone"), payload.get("to_zone"))}'
        )
    if event_type in {'card_broken', 'card_break_prevented'}:
        return f'{name}: {EVENT_TYPE_LABELS.get(event_type, event_type)}'
    if event_type in {'hp_changed', 'fp_changed'}:
        return f'{event.get("actor")}: {payload.get("before")} → {payload.get("after")}'
    if event_type == 'decision_resolved':
        return f'선택: {", ".join(str(item) for item in payload.get("selected") or []) or "없음"}'
    if event_type == 'effect_resolved':
        return str(payload.get('ability_id') or '')
    if event_type in {'ability_target_skipped', 'effect_choice_skipped'}:
        return f'필수 {payload.get("minimum", 0)}장 / 후보 {payload.get("candidate_count", 0)}장'
    return str(payload.get('reason') or payload.get('source') or '')


def _project_sandbox_actions(payload):
    """Expose only ephemeral game actions useful for continuing a review."""
    state = payload.get('state') or {}
    if (state.get('engine') or {}).get('pending_decision'):
        return []
    step = _integer(payload.get('step'))
    engine = AutomaticGameEngine(
        copy.deepcopy(state), copy.deepcopy(payload.get('ruleset') or {}),
        version=payload.get('engine_version') or 1,
        events=copy.deepcopy(payload.get('events') or []),
        seed=state.get('random_seed') or 'effect-sandbox',
        now=SANDBOX_EPOCH + timedelta(seconds=step + 1),
    )
    projected = []
    for owner in PLAYER_SIDES:
        for action in engine.list_legal_actions(owner):
            if action.get('type') not in SANDBOX_ACTION_TYPES:
                continue
            projected.append({
                'owner': owner,
                'action_id': str(action.get('action_id') or ''),
                'type': str(action.get('type') or ''),
                'label': str(action.get('label') or action.get('type') or ''),
                'card': copy.deepcopy(action.get('card') or None),
                'choice_speed': action.get('choice_speed'),
            })
    return projected


def _project_passive_state(passive_state, language):
    """Attach the same semantic labels shown by the live simulator."""
    projected = copy.deepcopy(passive_state or {})
    for key, entry in projected.items():
        if not isinstance(entry, dict):
            continue
        semantic_kind = 'token' if 'count' in entry else 'state'
        semantic_slug = PASSIVE_STATE_SLUG_ALIASES.get(str(key), str(key))
        source_key = term_translation_key(semantic_kind, semantic_slug)
        stored_label = str(entry.get('label') or '').strip()
        fallback = (
            PASSIVE_STATE_KO_LABELS.get(semantic_slug)
            or (stored_label if stored_label and stored_label != str(key) else '')
            or str(key).replace('_', ' ')
        )
        if translation_source_exists(source_key):
            entry['display_label'] = translate_key(
                source_key, language, fallback=fallback,
            )
            continue
        entry['display_label'] = fallback
    return projected


def project_effect_sandbox(payload, *, language='ko'):
    """Return the bounded, reviewer-facing state and decision projection."""
    state = payload.get('state') or {}
    engine_state = state.get('engine') or {}
    projection_engine = AutomaticGameEngine(
        copy.deepcopy(state), copy.deepcopy(payload.get('ruleset') or {}),
        version=payload.get('engine_version') or 1,
        events=copy.deepcopy(payload.get('events') or []),
        seed=state.get('random_seed') or 'effect-sandbox',
        now=SANDBOX_EPOCH + timedelta(
            seconds=_integer(payload.get('step')) + 1,
        ),
    )
    cards = _card_lookup(state)
    decision = engine_state.get('pending_decision') or None
    projected_decision = None
    if decision:
        projected_decision = {
            'id': decision.get('id'), 'owner': decision.get('owner'),
            'kind': decision.get('kind'), 'prompt': decision.get('prompt'),
            'minimum': int(decision.get('minimum') or 0),
            'maximum': int(decision.get('maximum') or 0),
            'optional': bool(decision.get('optional')),
            'options': [
                {
                    'id': str(option.get('id')),
                    'label': str(option.get('label') or option.get('id')),
                    'owner': option.get('owner'), 'zone': option.get('zone'),
                }
                for option in decision.get('options') or []
            ],
        }
    events = []
    for event in payload.get('events') or []:
        events.append({
            'id': event.get('id'), 'type': event.get('type'),
            'label': EVENT_TYPE_LABELS.get(event.get('type'), event.get('type')),
            'actor': event.get('actor'),
            'summary': _event_summary(event, cards),
            'payload': copy.deepcopy(event.get('payload') or {}),
        })
    ability_id = payload.get('ability_id')
    resolved = any(
        event.get('type') == 'effect_resolved'
        and (event.get('payload') or {}).get('ability_id') == ability_id
        for event in payload.get('events') or []
    )
    skipped = next((
        event for event in reversed(payload.get('events') or [])
        if event.get('type') in {'ability_target_skipped', 'effect_choice_skipped'}
    ), None)
    declined = any(
        event.get('type') == 'decision_resolved'
        and 'decline' in ((event.get('payload') or {}).get('selected') or [])
        for event in payload.get('events') or []
    )
    available_actions = _project_sandbox_actions(payload)
    if decision:
        status, status_label = 'waiting', '플레이어 선택 대기'
    elif available_actions:
        status, status_label = 'waiting_action', '게임 행동 선택 대기'
    elif skipped:
        status, status_label = 'blocked', '필수 선택 후보 부족'
    elif declined:
        status, status_label = 'declined', '선택 효과 거절'
    elif resolved:
        status, status_label = 'completed', '효과 실행 완료'
    elif payload.get('ability_mode') == 'continuous':
        status, status_label = 'continuous', '상시 규칙 재계산 완료'
    else:
        status, status_label = 'not_triggered', '조건 불충족 또는 미발동'

    players = {}
    for side in PLAYER_SIDES:
        player = (state.get('players') or {}).get(side) or {}
        players[side] = {
            'hp': player.get('hp'), 'fp': player.get('fp'),
            'passive_state': _project_passive_state(
                player.get('passive_state'), language,
            ),
            'zones': {
                zone: [
                    _project_card(card, projection_engine, side)
                    for card in (player.get('zones') or {}).get(zone) or []
                ]
                for zone in ALL_ZONES
            },
        }
    decision_audit = [
        {**copy.deepcopy(item), 'status': 'resolved'}
        for item in payload.get('decision_history') or []
        if isinstance(item, dict)
    ]
    if projected_decision:
        decision_audit.append({
            **copy.deepcopy(projected_decision),
            'status': 'waiting', 'selected': [],
        })
    movement_audit = []
    operation_audit = []
    for event in payload.get('events') or []:
        event_type = event.get('type')
        event_payload = event.get('payload') or {}
        card_id = str(event_payload.get('card_instance_id') or '')
        card = cards.get(card_id) or {}
        if event_type == 'card_moved':
            movement_audit.append({
                'card_instance_id': card_id,
                'label': card.get('name') or card_id or '카드',
                'owner': card.get('owner') or event.get('actor'),
                'from_zone': event_payload.get('from_zone'),
                'to_zone': event_payload.get('to_zone'),
                'reason': event_payload.get('reason') or '',
            })
        elif event_type in {
            'card_broken', 'card_discarded', 'card_break_prevented',
            'card_move_prevented', 'card_effect_ignored',
        }:
            operation_audit.append({
                'type': event_type,
                'label': EVENT_TYPE_LABELS.get(event_type, event_type),
                'card_instance_id': card_id,
                'card_label': card.get('name') or card_id or '카드',
                'reason': event_payload.get('reason') or '',
            })
    return render_visible_markup({
        'sandbox_version': SANDBOX_VERSION,
        'step': payload.get('step', 0),
        'ability_id': ability_id, 'event': payload.get('event'),
        'event_label': EVENT_LABELS.get(payload.get('event'), payload.get('event')),
        'execution_mode': payload.get('execution_mode') or 'direct_event',
        'execution_mode_label': (
            '실제 배틀 진행'
            if payload.get('execution_mode') == 'battle_pipeline'
            else (
                '실제 콤보 기술 해석'
                if payload.get('execution_mode') == 'combo_pipeline'
                else (
                    '실제 캐치 기술 해석'
                    if payload.get('execution_mode') == 'catch_pipeline'
                    else (
                        '실제 게임·턴·페이즈 진행'
                        if payload.get('execution_mode') == 'phase_pipeline'
                        else '직접 이벤트 비교'
                    )
                )
            )
        ),
        'pipeline_trace': copy.deepcopy(payload.get('pipeline_trace') or []),
        'pipeline_reached_events': list(dict.fromkeys(
            item.get('event')
            for item in payload.get('pipeline_trace') or []
            if isinstance(item, dict) and item.get('event')
        )),
        'status': status, 'status_label': status_label,
        'resolved': resolved, 'pending_decision': projected_decision,
        'available_actions': available_actions,
        'players': players, 'events': events,
        'audit': {
            'decisions': decision_audit,
            'movements': movement_audit,
            'operations': operation_audit,
            'blocked': bool(skipped),
        },
        'engine': {
            'modifiers': copy.deepcopy(engine_state.get('modifiers') or []),
            'replacements': copy.deepcopy(engine_state.get('replacements') or []),
            'scheduled': copy.deepcopy(engine_state.get('scheduled') or []),
            'usage': copy.deepcopy(engine_state.get('usage') or {}),
        },
    })


def describe_ability_choices(ability):
    """Explain every server decision and flag implicit selector execution."""
    steps = []
    automatic_steps = []
    warnings = []
    if ability.get('mode') == 'optional':
        steps.append({
            'kind': 'optional_effect', 'label': '효과 발동 여부를 선택',
            'minimum': 1, 'maximum': 1, 'required': True,
        })
    for index, selector in enumerate(ability.get('targets') or [], start=1):
        minimum = selector.get('min', 1)
        maximum = selector.get('max', minimum)
        steps.append({
            'kind': 'ability_target',
            'label': selector.get('prompt') or f'효과 대상 {index} 선택',
            'minimum': minimum, 'maximum': maximum,
            'required': isinstance(minimum, int) and minimum >= 1,
            'zones': selector.get('zones') or [selector.get('zone', 'hand')],
        })

    def visit(nodes, path='effects'):
        if isinstance(nodes, list):
            for index, node in enumerate(nodes):
                visit(node, f'{path}[{index}]')
            return
        if not isinstance(nodes, dict):
            return
        op = nodes.get('op')
        if op == 'request_choice':
            selector = nodes.get('selector') or {}
            minimum = selector.get('min', 1)
            maximum = selector.get('max', minimum)
            steps.append({
                'kind': 'effect_choice',
                'label': nodes.get('prompt') or '카드 선택',
                'minimum': minimum, 'maximum': maximum,
                'required': isinstance(minimum, int) and minimum >= 1,
                'zones': selector.get('zones') or [selector.get('zone', 'hand')],
                'path': path,
            })
        elif op == 'request_amount':
            minimum = nodes.get('min', 0)
            maximum = nodes.get('max', minimum)
            steps.append({
                'kind': 'effect_amount',
                'label': nodes.get('prompt') or '수치 선택',
                'minimum': minimum, 'maximum': maximum,
                'required': True, 'path': path,
            })
        elif op == 'choose_effect':
            steps.append({
                'kind': 'effect_branch',
                'label': nodes.get('prompt') or '적용할 효과 선택',
                'minimum': 1, 'maximum': 1, 'required': True, 'path': path,
            })
        elif op == 'guess_hand_parity':
            steps.append({
                'kind': 'hand_guess',
                'label': nodes.get('prompt') or '상대 패 카드와 홀짝 추측 선택',
                'minimum': 1, 'maximum': 1, 'required': True, 'path': path,
            })
        if op in {'move_card', 'break_card', 'discard', 'attach_card', 'delete_token'}:
            if nodes.get('selector') and not nodes.get('selection_key'):
                selector = nodes.get('selector') or {}
                maximum = selector.get('max')
                where = selector.get('where') or {}
                zones = selector.get('zones') or [selector.get('zone', 'hand')]
                if selector.get('all') is True or maximum is None:
                    automatic_steps.append({
                        'kind': op,
                        'label': f'{op}: 조건에 맞는 카드를 모두 자동 처리',
                        'zones': zones, 'path': path,
                    })
                elif set(where).issubset({'code', 'code_in', 'token_key'}) and where:
                    automatic_steps.append({
                        'kind': op,
                        'label': f'{op}: 같은 코드·토큰 후보 중 최대 {maximum}장 자동 처리',
                        'zones': zones, 'path': path,
                    })
                else:
                    warnings.append(
                        f'{path}: {op}가 플레이어 결정 없이 안정 정렬 순서로 대상을 처리합니다.'
                    )
        for key in ('then', 'else', 'effects', 'commands'):
            visit(nodes.get(key), f'{path}.{key}')
        choices = nodes.get('choices')
        if isinstance(choices, list):
            for index, choice in enumerate(choices):
                visit((choice or {}).get('effects'), f'{path}.choices[{index}].effects')

    visit(ability.get('cost') or [], 'cost')
    visit(ability.get('effects') or [])
    return {
        'steps': steps,
        'automatic_steps': automatic_steps,
        'warnings': list(dict.fromkeys(warnings)),
    }


def sandbox_event_options(ability):
    trigger = ability.get('trigger') or {}
    events = list(trigger.get('events') or [])
    default = trigger.get('event')
    if default and default not in events:
        events.insert(0, default)
    timing = str(ability.get('timing') or '')
    if not events and timing in TRIGGERS:
        events.append(timing)
    return [
        {'value': event, 'label': EVENT_LABELS.get(event, event)}
        for event in events if event in TRIGGERS
    ]
