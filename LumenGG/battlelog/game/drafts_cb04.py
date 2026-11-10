"""CB04 부쿠키 카드의 카드별 자동 효과 초안.

일반 문구 해석기는 「서리」를 자신에게 부여하거나 [부쿠키] 필터를 놓치므로
카드 단위로 정의를 고정한다. 초안은 draft 상태로만 만들어지며, 운영진의 수동
검수를 거쳐야 공개 릴리스에 포함된다. 룰 해석이 불확실한 부분은
AUTOMATIC_EFFECT_RULE_QUESTIONS_KO.txt에 질문으로 남겼다.
"""

import copy

from .spec import EFFECT_SCHEMA_VERSION


BUKUKI_KEY = '부쿠키'
FROST_STATE = 'frost'
FROST_LABEL = '서리'
BUKUKI_TECHNIQUE = {'character_key': BUKUKI_KEY, 'is_technique': True}
# "다음 턴 종료 시까지": 부여한 턴과 다음 턴의 리커버리 페이즈 종료(턴 종료)까지.
# Q-AUTO-008: 이미 서리 상태여도 재부여가 되며, 지속은 더 오래 가는 쪽을 유지한다.
UNTIL_NEXT_TURN_END = {
    'event': 'phase_end', 'phase': 'recovery', 'occurrences': 2, 'keep_longer': True,
}


def _give_frost():
    return {
        'op': 'gain_state', 'player': {'opponent': True},
        'state': FROST_STATE, 'label': FROST_LABEL,
        'expires': copy.deepcopy(UNTIL_NEXT_TURN_END),
        'refire_when_active': True,
    }


def _send_bukuki_to_lumen(selection_key):
    selector = {
        'kind': 'card', 'player': {'controller': True}, 'zones': ['hand', 'list'],
        'min': 1, 'max': 1, 'where': dict(BUKUKI_TECHNIQUE),
        'as_operation': 'move_card', 'to_zone': 'lumen',
    }
    return {
        'op': 'request_choice', 'player': {'controller': True},
        'prompt': '루멘 존으로 보낼 [부쿠키] 기술을 선택하세요.',
        'selector': selector, 'selection_key': selection_key,
        'default': [], 'skip_if_unavailable': True,
        'then': [{'op': 'move_card', 'selection_key': selection_key, 'to_zone': 'lumen'}],
    }


def _lumen_bukuki_to_list(selection_key, *, chooser):
    return {
        'op': 'request_choice', 'player': {chooser: True},
        'prompt': '리스트로 보낼 루멘 존의 [부쿠키] 기술을 선택하세요.',
        'selector': {
            'kind': 'card', 'player': {'controller': True}, 'zones': ['lumen'],
            'min': 1, 'max': 1, 'where': dict(BUKUKI_TECHNIQUE),
            'as_operation': 'move_card', 'to_zone': 'list',
        },
        'selection_key': selection_key, 'default': [],
        'then': [{'op': 'move_card', 'selection_key': selection_key, 'to_zone': 'list'}],
    }


def _ability(code, suffix, label, *, kind='effect', mode='mandatory', timing, effects, **extra):
    return {
        'id': f'{code.lower()}-{suffix}', 'label': label, 'kind': kind, 'mode': mode,
        'timing': timing, 'visibility': 'public', 'draft': True, 'draft_text': label,
        'draft_compiled': True, 'effects': effects, **extra,
    }


def _frost_veil(code):
    return {}, [
        _ability(
            code, 'n1', '방어 및 상쇄 시, 다음 턴 종료 시까지 상대에게 「서리」상태를 부여한다.',
            timing='guard', active_zones=['passive'],
            trigger={'event': 'guard', 'events': ['guard', 'clash']},
            condition={'op': 'equals', 'left': 'context.event_controller', 'right': {'controller': True}},
            effects=[_give_frost()],
        ),
        _ability(
            code, 'n2',
            '상대에게 「서리」상태를 부여할 때마다 패나 리스트의 [부쿠키] 기술 1장을 루멘 존에 보낼 수 있다.',
            mode='optional', timing='result', active_zones=['passive'],
            trigger={'event': 'state_gained'},
            condition={'op': 'all', 'conditions': [
                {'op': 'equals', 'left': 'context.state', 'right': FROST_STATE},
                {'op': 'equals', 'left': 'context.player', 'right': {'opponent': True}},
            ]},
            availability_selector={
                'kind': 'card', 'player': {'controller': True}, 'zones': ['hand', 'list'],
                'min': 1, 'max': 1, 'where': dict(BUKUKI_TECHNIQUE),
                'as_operation': 'move_card', 'to_zone': 'lumen',
            },
            effects=[_send_bukuki_to_lumen('cb04_ps_001_frost_lumen')],
        ),
        _ability(
            code, 'n3',
            '리커버리 페이즈 시, FP가 불리할 경우 루멘 존의 [부쿠키] 기술 1장을 리스트로 보낸다.',
            timing='function', active_zones=['passive'],
            trigger={'event': 'phase_start'},
            condition={'op': 'all', 'conditions': [
                {'op': 'phase_is', 'phase': 'recovery'},
                {'op': 'lt', 'left': 'context.controller_fp', 'right': {'path': 'context.opponent_fp'}},
                {'op': 'zone_count', 'player': {'controller': True}, 'zone': 'lumen',
                 'min': 1, 'where': dict(BUKUKI_TECHNIQUE)},
            ]},
            effects=[_lumen_bukuki_to_list('cb04_ps_001_recovery_list', chooser='controller')],
        ),
    ]


def _bitter_cold(code):
    return {
        'defense_rules': [{'judgment': 'dodge', 'where': {'guard': ['X', 'x']}}],
    }, [
        _ability(
            code, 'function', '이 기술은 가드 판정이 <X>인 기술만 회피한다.',
            kind='function', mode='continuous', timing='function', active_zones=['battle'],
            effects=[{'op': 'static_rule', 'rules': ['defense_rules']}],
        ),
        _ability(
            code, 'n1', '이 기술이 루멘 존에 존재하는 한, 콤보 시 [부쿠키] 기술 데미지+100',
            timing='use', active_zones=['lumen'], trigger={'event': 'use'},
            condition={'op': 'all', 'conditions': [
                {'op': 'equals', 'left': 'context.event_controller', 'right': {'controller': True}},
                {'op': 'equals', 'left': 'context.combo', 'right': True},
                {'op': 'card_matches', 'card': {'path': 'context.event_card'},
                 'where': dict(BUKUKI_TECHNIQUE)},
            ]},
            effects=[_bitter_cold_bonus()],
        ),
        # Q-AUTO-011: 콤보 타임을 연 1콤보 시동 기술도 대상이다. 시동 기술의
        # '콤보' 이벤트는 배틀 데미지 계산 전에 발생한다.
        _ability(
            code, 'n1-starter', '이 기술이 루멘 존에 존재하는 한, 콤보 시 [부쿠키] 기술 데미지+100',
            timing='combo', active_zones=['lumen'], trigger={'event': 'combo'},
            limit={'scope': 'turn', 'max': 1, 'key': 'cb04-at-012-n1-starter', 'per_event_card': True},
            condition={'op': 'all', 'conditions': [
                {'op': 'equals', 'left': 'context.event_controller', 'right': {'controller': True}},
                {'op': 'equals', 'left': 'context.combo_number', 'right': 1},
                {'op': 'card_matches', 'card': {'path': 'context.event_card'},
                 'where': dict(BUKUKI_TECHNIQUE)},
            ]},
            effects=[_bitter_cold_bonus()],
        ),
    ]


def _bitter_cold_bonus():
    return {
        'op': 'modify_stat', 'player': {'controller': True}, 'target_card': 'event_card',
        'stat': 'damage', 'amount': 100, 'duration': 'battle',
    }


def _snow_country(code):
    play_condition = {'op': 'lte', 'left': 'context.controller_hp', 'right': 2500}
    return {'play_condition': copy.deepcopy(play_condition)}, [
        _ability(
            code, 'function', '이 기술은 자신의 체력이 2500 이하일 경우에만 사용할 수 있다.',
            kind='function', mode='continuous', timing='function',
            effects=[{'op': 'static_rule', 'rules': ['play_condition']}],
            condition=copy.deepcopy(play_condition),
        ),
        _ability(
            code, 'n1', '사용 시, 배틀 존의 상대 기술 효과를 무효로 한다.',
            timing='use', active_zones=['battle'], trigger={'event': 'use'},
            effects=[{'op': 'negate_battle_card_effects', 'player': {'opponent': True}}],
        ),
        _ability(
            code, 'n2',
            '사용 후, 이 기술을 브레이크하고 다음 턴 종료 시까지 상대에게 「서리」상태를 부여한다. '
            '그 후, 배틀 페이즈를 종료한다.',
            timing='after_use', active_zones=['battle'], trigger={'event': 'after_use'},
            effects=[
                {'op': 'break_card', 'continue_resolution': True},
                _give_frost(),
                {'op': 'end_battle'},
            ],
        ),
    ]


def _winter_fangs(code):
    return {}, [
        _ability(
            code, 'n1',
            '상대 회피 시, 상대는 2FP를 얻고 루멘 존의 [부쿠키] 기술을 1장 골라 리스트로 보낸다.',
            timing='opponent_dodge', active_zones=['battle'], trigger={'event': 'opponent_dodge'},
            effects=[
                {'op': 'change_fp', 'player': {'opponent': True}, 'amount': 2},
                # Q-AUTO-010: FP는 상대가 얻고, 리스트로 보낼 기술은 사용자가 고른다.
                _lumen_bukuki_to_list('cb04_at_002_dodge_list', chooser='controller'),
            ],
        ),
        _ability(
            code, 'n2', '히트/카운터/콤보 시, 패나 리스트의 [부쿠키] 기술 1장을 루멘 존에 보낼 수 있다.',
            mode='optional', timing='hit_counter', active_zones=['battle'],
            trigger={'event': 'hit', 'events': ['hit', 'counter', 'combo']},
            # Q-AUTO-006: 번호 효과는 히트·콤보가 겹쳐도 한 턴에 한 번만 발동한다.
            limit={'scope': 'turn', 'max': 1, 'key': 'cb04-at-002-n2:usage'},
            availability_selector={
                'kind': 'card', 'player': {'controller': True}, 'zones': ['hand', 'list'],
                'min': 1, 'max': 1, 'where': dict(BUKUKI_TECHNIQUE),
                'as_operation': 'move_card', 'to_zone': 'lumen',
            },
            effects=[_send_bukuki_to_lumen('cb04_at_002_lumen')],
        ),
    ]


def _blizzard(code):
    return {'defense_rules': [{'judgment': 'dodge', 'max_speed': 8}]}, [
        _ability(
            code, 'function', '이 기술은 <8속도 이하>기술만 회피한다.',
            kind='function', mode='continuous', timing='function', active_zones=['battle'],
            effects=[{'op': 'static_rule', 'rules': ['defense_rules']}],
        ),
        _ability(
            code, 'n1', '상대 「서리」: 이 기술 데미지 +200',
            mode='continuous', timing='function', active_zones=['battle'],
            condition={'op': 'has_state', 'player': {'opponent': True}, 'state': FROST_STATE},
            effects=[{
                'op': 'modify_stat', 'player': {'controller': True},
                'stat': 'damage', 'amount': 200, 'duration': 'continuous',
            }],
        ),
        _ability(
            code, 'n2', '히트 및 카운터 시, 다음 턴 종료 시까지 상대에게 「서리」상태를 부여한다.',
            timing='hit_counter', active_zones=['battle'],
            trigger={'event': 'hit', 'events': ['hit', 'counter']},
            effects=[_give_frost()],
        ),
        _ability(
            code, 'n3', '콤보 시, 이번 턴 루멘 존의 [부쿠키] 기술을 콤보에 사용할 수 있다.',
            timing='combo', active_zones=['battle'], trigger={'event': 'combo'},
            effects=[{
                'op': 'modify_combo', 'player': {'controller': True},
                'allow_zones': ['lumen'], 'where': dict(BUKUKI_TECHNIQUE),
                'usage_key': 'cb04-at-007-lumen-combo', 'duration': 'turn',
            }],
        ),
    ]


BUILDERS = {
    'CB04-PS-001': _frost_veil,
    'CB04-AT-012': _bitter_cold,
    'CB04-AT-001': _snow_country,
    'CB04-AT-002': _winter_fangs,
    'CB04-AT-007': _blizzard,
}


def build_cb04_definition(card_code, *, qna_ids=(), detail_text=''):
    """Return the CB04 card draft, or ``None`` for any other card code."""
    code = str(card_code or '').upper()
    builder = BUILDERS.get(code)
    if builder is None:
        return None
    source_refs = {
        'rulebook_pages': [48, 49], 'qna_ids': list(qna_ids or []), 'card_text': True,
        **({'detail_text': True} if str(detail_text or '').strip() else {}),
    }
    rules, abilities = builder(code)
    for ability in abilities:
        ability['source_refs'] = copy.deepcopy(source_refs)
    return {
        'schema_version': EFFECT_SCHEMA_VERSION, 'reviewed': False, 'no_effect': False,
        'draft': True, 'source_refs': source_refs, **rules, 'abilities': abilities,
    }
