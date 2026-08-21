"""Stateless, isolated effect sandbox used by the card review screen.

The sandbox deliberately uses the same ``AutomaticGameEngine`` and public
``submit_action`` contract as a live automatic game.  It does not persist a
session and it limits the source ruleset to one selected ability so unfinished
cards can be exercised safely during review.
"""

import copy
import json
from datetime import datetime, timedelta, timezone

from .engine import AutomaticGameEngine, EngineError
from .spec import ALL_ZONES, PHASES, PLAYER_SIDES, TRIGGERS


SANDBOX_VERSION = 1
SANDBOX_EPOCH = datetime(2026, 6, 1, tzinfo=timezone.utc)
MAX_SUPPORT_CARDS = 36
SANDBOX_PROTOTYPE_PREFIX = 'sandbox-prototype:'
NO_EFFECT_DEFINITION = {
    'schema_version': 1,
    'reviewed': True,
    'no_effect': True,
    'source_refs': {'rulebook_pages': [], 'qna_ids': []},
    'abilities': [],
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
        'active_zones': ['battle'], 'trigger': {'event': 'use'},
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
            'frame_lte', 'code_in', 'owner', 'face_up',
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


def _empty_player(name, hp, fp, passive_state):
    return {
        'name': name, 'initial_hp': max(5000, hp), 'hp': hp, 'fp': fp,
        'passive_state': copy.deepcopy(passive_state or {}),
        'zones': {zone: [] for zone in ALL_ZONES},
    }


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
    if ability.get('mode') != 'continuous' and event not in TRIGGERS:
        raise EffectSandboxError('실행할 유효한 트리거를 선택해 주세요.')

    source_code = str(source_snapshot.get('code') or 'SANDBOX-SOURCE')
    isolated_definition = copy.deepcopy(definition)
    isolated_definition['abilities'] = [ability]
    isolated_source = copy.deepcopy(source_snapshot)
    isolated_source['code'] = source_code
    isolated_source['effect_definition'] = isolated_definition
    ruleset_cards = {source_code: isolated_source}

    normalized_support = {}
    for raw_id, snapshot in (support_snapshots or {}).items():
        code = str(snapshot.get('code') or f'SANDBOX-CARD-{raw_id}')
        support = copy.deepcopy(snapshot)
        support['code'] = code
        support['effect_definition'] = _card_definition_without_triggered_abilities(
            snapshot.get('effect_definition'),
        )
        ruleset_cards[code] = support
        normalized_support[str(raw_id)] = support

    ruleset = {
        'version': 'effect-sandbox-v1',
        'engine_schema_version': 1,
        'effect_schema_version': 1,
        'cards': ruleset_cards,
        'characters': {},
    }
    player_config = config.get('players') if isinstance(config.get('players'), dict) else {}
    players = {}
    for side in PLAYER_SIDES:
        values = player_config.get(side) if isinstance(player_config.get(side), dict) else {}
        hp = _integer(values.get('hp'), 4000)
        fp = _integer(values.get('fp'), 5, 0, 999)
        passive = values.get('passive_state') if isinstance(values.get('passive_state'), dict) else {}
        players[side] = _empty_player(side, hp, fp, passive)

    source = _runtime_card(isolated_source, controller, 'sandbox-source')
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

    if ability.get('mode') == 'continuous':
        engine._refresh_continuous_rules()
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
        'now': SANDBOX_EPOCH.isoformat(),
        'step': 0,
        'decision_history': [],
    }


def continue_effect_sandbox(payload, selected):
    """Resolve one pending decision through the engine's public action API."""
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
    owner = decision.get('owner')
    if owner not in PLAYER_SIDES:
        raise EffectSandboxError('현재 응답할 선택 요청이 없습니다.')
    action = next((
        item for item in engine.list_legal_actions(owner)
        if item.get('type') == 'submit_decision'
    ), None)
    if not action:
        raise EffectSandboxError('현재 선택을 실행할 합법 행동을 찾을 수 없습니다.')
    selected_ids = [str(item) for item in (selected or [])]
    option_lookup = {
        str(option.get('id')): option
        for option in decision.get('options') or []
    }
    try:
        engine.submit_action(
            owner, action['action_id'], {'selected': selected_ids},
            command_id=f'effect-sandbox-{step + 1}',
        )
    except EngineError as exc:
        raise EffectSandboxError(str(exc)) from exc
    result = copy.deepcopy(payload)
    decision_history = copy.deepcopy(payload.get('decision_history') or [])
    decision_history.append({
        'id': decision.get('id'), 'owner': owner,
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
    result.update({
        'state': engine.state,
        'events': engine.events,
        'engine_version': engine.version,
        'now': now.isoformat(),
        'step': step + 1,
        'decision_history': decision_history,
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


def _project_card(card):
    return {
        'instance_id': str(card.get('instance_id') or ''),
        'code': str(card.get('code') or ''),
        'name': str(card.get('name') or card.get('code') or '카드'),
        'type': str(card.get('type') or ''),
        'face_up': bool(card.get('face_up')),
        'fixture': bool(card.get('sandbox_fixture')),
        'attached_to': card.get('attached_to'),
    }


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


def project_effect_sandbox(payload):
    """Return the bounded, reviewer-facing state and decision projection."""
    state = payload.get('state') or {}
    engine_state = state.get('engine') or {}
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
    if decision:
        status, status_label = 'waiting', '플레이어 선택 대기'
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
            'passive_state': copy.deepcopy(player.get('passive_state') or {}),
            'zones': {
                zone: [_project_card(card) for card in (player.get('zones') or {}).get(zone) or []]
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
    return {
        'sandbox_version': SANDBOX_VERSION,
        'step': payload.get('step', 0),
        'ability_id': ability_id, 'event': payload.get('event'),
        'event_label': EVENT_LABELS.get(payload.get('event'), payload.get('event')),
        'status': status, 'status_label': status_label,
        'resolved': resolved, 'pending_decision': projected_decision,
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
    }


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
    return [
        {'value': event, 'label': EVENT_LABELS.get(event, event)}
        for event in events if event in TRIGGERS
    ]
