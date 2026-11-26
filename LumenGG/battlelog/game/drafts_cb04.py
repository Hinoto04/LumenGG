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
        # 루멘 존에 있는 동안 계속 적용되는 효과다. 콤보에 쓰인 [부쿠키] 기술(콤보를 연 1콤보
        # 시동 기술 포함, Q-AUTO-011)의 데미지를 한 번씩만 올리며, 콤보마다 유발되지 않는다.
        _ability(
            code, 'n1', '이 기술이 루멘 존에 존재하는 한, 콤보 시 [부쿠키] 기술 데미지+100',
            mode='continuous', timing='function', active_zones=['lumen'],
            effects=[_bitter_cold_bonus()],
        ),
    ]


def _bitter_cold_bonus():
    return {
        'op': 'modify_stat', 'player': {'controller': True}, 'scope': 'player_cards',
        'where': {**BUKUKI_TECHNIQUE, 'combo_member': True},
        'stat': 'damage', 'amount': 100, 'duration': 'continuous',
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
                'duration': 'turn',
            }],
        ),
    ]


# --- CB04 2차 공개분(2026-11-10~16): CMYK·델피·부쿠키·타오 -----------------

CMYK_TECHNIQUE = {'character_key': 'cmyk'}
DRUM_TEXT = {'text_contains_any': ['[[token:drum]]', '【드럼】']}


def _attached_count(where=None):
    value = {
        'op': 'attached_count', 'player': {'controller': True},
        'host': {'path': 'context.source_card_instance_id'},
    }
    if where:
        value['where'] = dict(where)
    return value


def _set_to_cmyk_condition():
    return {'op': 'all', 'conditions': [
        {'op': 'equals', 'left': 'context.source_card.attached_to',
         'right': {'path': 'context.event_card.instance_id'}},
        {'op': 'card_matches', 'card': {'path': 'context.event_card'}, 'where': dict(CMYK_TECHNIQUE)},
    ]}


def _frost_damage_bonus(code, suffix, label):
    return _ability(
        code, suffix, label, mode='continuous', timing='function', active_zones=['battle'],
        condition={'op': 'has_state', 'player': {'opponent': True}, 'state': FROST_STATE},
        effects=[{
            'op': 'modify_stat', 'player': {'controller': True},
            'stat': 'damage', 'amount': 200, 'duration': 'continuous',
        }],
    )


def _break_from_list_then(selection_key, then):
    """'리스트에서 기술 1장을 브레이크할 수 있다. 그 경우, …' 형태의 선택 효과."""
    selector = {
        'kind': 'card', 'player': {'controller': True}, 'zones': ['list'],
        'min': 1, 'max': 1, 'where': {'is_technique': True}, 'as_operation': 'break_card',
    }
    done_key = f'{selection_key}_done'
    return selector, [{
        'op': 'request_choice', 'player': {'controller': True},
        'prompt': '브레이크할 리스트의 기술을 선택하세요.',
        'selector': copy.deepcopy(selector), 'selection_key': selection_key, 'default': [],
        'then': [
            {'op': 'break_card', 'selection_key': selection_key, 'result_key': done_key},
            {'op': 'conditional', 'condition': {
                'op': 'gte', 'left': {'op': 'selection_count', 'selection_key': done_key}, 'right': 1,
            }, 'then': then, 'else': []},
        ],
    }]


def _fan_service(code):
    return {
        'attached_effect_multiplier': {
            'event': 'use', 'value': 2, 'where': dict(CMYK_TECHNIQUE), 'numbered_effect': True,
        },
    }, [
        _ability(
            code, 'n1', '【보컬】(사용 시, 이 기술에 세트된 [CMYK] 기술의 효과를 적용할 때 그 수치를 2배로 한다.)',
            timing='use', active_zones=['battle'], trigger={'event': 'use'},
            effects=[{'op': 'static_rule', 'rules': ['attached_effect_multiplier']}],
        ),
        _ability(
            code, 'n2', '판정 전, 이 기술에 세트된 기술이 1장 이상이라면 상대는 이 기술을 상쇄할 수 없다.',
            timing='before_judgment', active_zones=['battle'], trigger={'event': 'before_judgment'},
            condition={'op': 'gte', 'left': _attached_count(), 'right': 1},
            effects=[{'op': 'prevent', 'kind': 'clash', 'player': {'opponent': True}, 'duration': 'battle'}],
        ),
        _ability(
            code, 'n3', '히트/카운터/콤보 시, 리스트에서 카드를 2장까지 획득한다.',
            timing='hit_counter', active_zones=['battle'],
            trigger={'event': 'hit', 'events': ['hit', 'counter', 'combo']},
            # Q-AUTO-006: 히트·콤보가 겹쳐도 번호 효과는 한 턴에 한 번만 발동한다.
            limit={'scope': 'turn', 'max': 1, 'key': 'cb04-at-035-n3:usage'},
            effects=[{
                'op': 'request_choice', 'player': {'controller': True},
                'prompt': '리스트에서 획득할 카드를 2장까지 선택하세요.',
                'selector': {
                    'kind': 'card', 'player': {'controller': True}, 'zones': ['list'],
                    'min': 0, 'max': 2, 'as_operation': 'move_card', 'to_zone': 'hand',
                },
                'selection_key': 'cb04_at_035_list_gain', 'default': [], 'optional': True,
                'then': [{'op': 'move_card', 'selection_key': 'cb04_at_035_list_gain', 'to_zone': 'hand'}],
            }],
        ),
    ]


def _chromatic_alternate(code):
    drum_set = {'op': 'gte', 'left': _attached_count(DRUM_TEXT), 'right': 1}
    return {}, [
        _ability(
            code, 'n1', '【기타】([CMYK] 기술에 세트된 경우, 사용 시 해당 기술 데미지+100 이 효과는 중첩되지 않는다.)',
            timing='use', trigger={'event': 'use'}, active_when_attached=True,
            dedupe_trigger_key='cmyk:set:guitar', condition=_set_to_cmyk_condition(),
            effects=[{
                'op': 'modify_stat', 'player': {'controller': True}, 'stat': 'damage',
                'amount': 100, 'duration': 'battle', 'target_card': 'event_card',
            }],
        ),
        # 같은 '사용 시'에 발동하는 세트된 【드럼】의 FP 획득보다 먼저 대체 규칙을 둔다.
        _ability(
            code, 'n2', '사용 시, 세트된 기술 【드럼】효과가 있다면 FP를 얻는 대신 데미지+200.',
            timing='replacement', active_zones=['battle'], trigger={'event': 'use'},
            condition=drum_set,
            effects=[
                {'op': 'prevent', 'kind': 'fp_gain', 'player': {'controller': True},
                 'where': dict(DRUM_TEXT), 'duration': 'battle'},
                {'op': 'modify_stat', 'player': {'controller': True}, 'stat': 'damage',
                 'amount': 200, 'duration': 'battle'},
            ],
        ),
    ]


def _rainbow_train(code):
    list_techniques = {
        'op': 'zone_count', 'player': {'controller': True}, 'zone': 'list',
        'where': {'is_technique': True},
    }
    gain_count = {'op': 'min', 'values': [_attached_count(), list_techniques]}
    return {
        'defense_rules': [{'judgment': 'dodge', 'where': {'judgment_not_contains': '콤보'}}],
    }, [
        _ability(
            code, 'function', '이 기술은 <콤보> 판정이 없는 기술만 회피한다.',
            kind='function', mode='continuous', timing='function', active_zones=['battle'],
            effects=[{'op': 'static_rule', 'rules': ['defense_rules']}],
        ),
        _ability(
            code, 'n1', '회피 시, 2FP를 얻는다. 그 후, 이 기술에 세트된 기술 1장당 리스트에서 기술 1장을 획득한다.',
            timing='dodge', active_zones=['battle'], trigger={'event': 'dodge'},
            effects=[
                {'op': 'change_fp', 'player': {'controller': True}, 'amount': 2},
                {
                    'op': 'request_choice', 'player': {'controller': True},
                    'prompt': '세트된 기술 수만큼 리스트에서 획득할 기술을 선택하세요.',
                    'selector': {
                        'kind': 'card', 'player': {'controller': True}, 'zones': ['list'],
                        'min': copy.deepcopy(gain_count), 'max': copy.deepcopy(gain_count),
                        'where': {'is_technique': True},
                        'as_operation': 'move_card', 'to_zone': 'hand',
                    },
                    'selection_key': 'cb04_at_037_list_gain', 'default': [],
                    'then': [{'op': 'move_card', 'selection_key': 'cb04_at_037_list_gain', 'to_zone': 'hand'}],
                },
            ],
        ),
    ]


def _garage_token(code):
    return {'token_key': 'garage', 'token_usage': ['token', 'counter']}, [
        _ability(
            code, 'function', '이 카드는 【토큰】 또는 【카운터】 로 사용할 수 있다.',
            kind='function', mode='continuous', timing='function',
            effects=[{'op': 'static_rule', 'rules': ['token_usage']}],
        ),
    ]


def _silent_out(code):
    selector, effects = _break_from_list_then('cb04_at_003_break', [_give_frost()])
    return {}, [
        _frost_damage_bonus(code, 'n1', '상대 「서리」: 이 기술 데미지+200'),
        _ability(
            code, 'n2', '상대 회피 시, 상대는 3FP를 얻는다.',
            timing='opponent_dodge', active_zones=['battle'], trigger={'event': 'opponent_dodge'},
            effects=[{'op': 'change_fp', 'player': {'opponent': True}, 'amount': 3}],
        ),
        _ability(
            code, 'n3',
            '카운터 시, 리스트에서 기술 1장을 브레이크할 수 있다. 그 경우, 다음 턴 종료 시까지 상대에게 「서리」 상태를 부여한다',
            mode='optional', timing='hit_counter', active_zones=['battle'], trigger={'event': 'counter'},
            availability_selector=selector, effects=effects,
        ),
    ]


def _glasskate(code):
    selector, effects = _break_from_list_then('cb04_at_004_break', [{
        'op': 'request_choice', 'player': {'controller': True},
        'prompt': '사이드 덱에서 루멘 존으로 보낼 [부쿠키] 기술을 선택하세요.',
        'selector': {
            'kind': 'card', 'player': {'controller': True}, 'zones': ['side'],
            'min': 1, 'max': 1, 'where': dict(BUKUKI_TECHNIQUE),
            'as_operation': 'move_card', 'to_zone': 'lumen',
        },
        'selection_key': 'cb04_at_004_side_lumen', 'default': [], 'else': [],
        'then': [{'op': 'move_card', 'selection_key': 'cb04_at_004_side_lumen', 'to_zone': 'lumen'}],
    }])
    return {'defense_rules': [{'judgment': 'dodge', 'max_speed': 8}]}, [
        _ability(
            code, 'function', '이 기술은 <8속도 이하>기술만 회피한다.',
            kind='function', mode='continuous', timing='function', active_zones=['battle'],
            effects=[{'op': 'static_rule', 'rules': ['defense_rules']}],
        ),
        _ability(
            code, 'n1',
            '히트 및 카운터 시, 리스트에서 기술 1장을 브레이크할 수 있다. 그 경우, 사이드 덱에서 [부쿠키] 기술 1장을 루멘 존에 보낸다.',
            mode='optional', timing='hit_counter', active_zones=['battle'],
            trigger={'event': 'hit', 'events': ['hit', 'counter']},
            availability_selector=selector, effects=effects,
        ),
    ]


def _glacial_bloom(code):
    self_broken = 'cb04_at_006_self_broken'
    return {'defense_rules': [{'judgment': 'clash', 'max_speed': 8}]}, [
        _ability(
            code, 'function', '이 기술은 <8속도 이하> 기술만 상쇄한다.',
            kind='function', mode='continuous', timing='function', active_zones=['battle'],
            effects=[{'op': 'static_rule', 'rules': ['defense_rules']}],
        ),
        _ability(
            code, 'n1', '상쇄 시, 상대 기술의 히트 판정을 <-2>로 변경한다.',
            timing='clash', active_zones=['battle'], trigger={'event': 'clash'},
            effects=[{'op': 'modify_judgment', 'player': {'opponent': True}, 'field': 'hit', 'value': '-2'}],
        ),
        _ability(
            code, 'n2', '상대 히트 시, 루멘 존의 이 기술을 브레이크할 수 있다. 그 경우, 보호막 400을 얻고 3FP를 얻는다.',
            mode='optional', timing='opponent_hit_counter', active_zones=['lumen'],
            trigger={'event': 'opponent_hit'},
            condition={'op': 'equals', 'left': 'context.event_controller', 'right': {'controller': True}},
            effects=[
                {'op': 'break_card', 'card_instance_id': {'path': 'context.source_card_instance_id'},
                 'result_key': self_broken},
                {'op': 'conditional', 'condition': {
                    'op': 'gte', 'left': {'op': 'selection_count', 'selection_key': self_broken}, 'right': 1,
                }, 'then': [
                    {'op': 'gain_shield', 'player': {'controller': True}, 'amount': 400, 'duration': 'turn'},
                    {'op': 'change_fp', 'player': {'controller': True}, 'amount': 3},
                ], 'else': []},
            ],
        ),
    ]


def _counter(counter):
    return {'op': 'counter_count', 'player': {'controller': True}, 'counter': counter}


def _drunken_spirit(code):
    removed = 'cb04_at_021_yang_removed'
    return {}, [
        _ability(
            code, 'function', '상대는 이 기술을 방어할 수 없다.',
            kind='function', mode='continuous', timing='function', active_zones=['battle'],
            effects=[{'op': 'prevent', 'kind': 'guard', 'player': {'opponent': True}, 'duration': 'continuous'}],
        ),
        _ability(
            code, 'n1',
            '판정 전, 서로의 속도를 고정한다. 그 후, [양]카운터를 1개 제거할 수 있다. 「음」: [음]카운터를 1개 얻는다.',
            timing='before_judgment', active_zones=['battle'], trigger={'event': 'before_judgment'},
            # Q-AUTO-019: 「음」 문구는 [양] 카운터 제거 전, 유발 시점의 상태로 결정된다.
            trigger_snapshot={'yin': {'op': 'has_state', 'player': {'controller': True}, 'state': 'yin'}},
            effects=[
                {'op': 'fix_speed', 'player': {'controller': True}, 'stat': 'frame',
                 'value': {'path': 'context.controller_speed'}, 'duration': 'battle'},
                {'op': 'fix_speed', 'player': {'opponent': True}, 'stat': 'frame',
                 'value': {'path': 'context.opponent_speed'}, 'duration': 'battle'},
                {'op': 'conditional', 'condition': {
                    'op': 'counter_at_least', 'player': {'controller': True}, 'counter': 'yang', 'value': 1,
                }, 'then': [{
                    'op': 'request_amount', 'player': {'controller': True},
                    'prompt': '제거할 양 카운터 수를 선택하세요.', 'min': 0, 'max': 1, 'default': 0,
                    'selection_key': removed,
                    'then': [{
                        'op': 'change_counter', 'player': {'controller': True}, 'counter': 'yang',
                        'amount': {'op': 'negate', 'value': {'op': 'selected_value', 'selection_key': removed}},
                        'min': 0,
                    }],
                }], 'else': []},
                {'op': 'conditional', 'condition': {
                    'op': 'equals', 'left': 'context.trigger_snapshot.yin', 'right': True,
                }, 'then': [{'op': 'change_counter', 'player': {'controller': True}, 'counter': 'yin',
                             'amount': 1, 'min': 0, 'max': 4}], 'else': []},
            ],
        ),
        _ability(
            code, 'n2', '「조화」: 히트 및 카운터 시, 이 기술 데미지+400',
            timing='hit_counter', active_zones=['battle'],
            trigger={'event': 'hit', 'events': ['hit', 'counter']},
            condition={'op': 'has_state', 'player': {'controller': True}, 'state': 'harmony'},
            effects=[{'op': 'modify_stat', 'player': {'controller': True}, 'stat': 'damage',
                      'amount': 400, 'duration': 'battle'}],
        ),
    ]


def _twin_tail(code):
    return {}, [
        _ability(
            code, 'function', '상대는 이 기술을 특수 판정으로 회피할 수 없다.',
            kind='function', mode='continuous', timing='function', active_zones=['battle'],
            effects=[{'op': 'prevent', 'kind': 'dodge', 'player': {'opponent': True},
                      'duration': 'continuous', 'where': {'special_truthy': True}}],
        ),
        _ability(
            code, 'n1', '판정 전, [양]카운터 2개당 1FP를 얻는다. 「양」: 대신 1개당 1FP를 얻는다.',
            timing='before_judgment', active_zones=['battle'], trigger={'event': 'before_judgment'},
            # Q-AUTO-019: 「양」 문구 적용 여부는 유발 시점의 상태로 결정된다.
            trigger_snapshot={'yang': {'op': 'has_state', 'player': {'controller': True}, 'state': 'yang'}},
            effects=[{'op': 'change_fp', 'player': {'controller': True}, 'amount': {
                'op': 'if',
                'condition': {'op': 'equals', 'left': 'context.trigger_snapshot.yang', 'right': True},
                'then': _counter('yang'),
                'else': {'op': 'floor_divide', 'left': _counter('yang'), 'right': 2},
            }}],
        ),
        _ability(
            code, 'n2', '「조화」: 상대는 이 기술을 회피할 수 없다.',
            mode='continuous', timing='function', active_zones=['battle'],
            condition={'op': 'has_state', 'player': {'controller': True}, 'state': 'harmony'},
            effects=[{'op': 'prevent', 'kind': 'dodge', 'player': {'opponent': True}, 'duration': 'continuous'}],
        ),
        _ability(
            code, 'n3', '콤보 타임 종료 시, 배틀 존의 기술을 모두 획득한다.',
            timing='combo_end', active_zones=['battle'], trigger={'event': 'combo_end'},
            requires_combo_use=True,
            effects=[{'op': 'move_card', 'to_zone': 'hand', 'selector': {
                'kind': 'card', 'player': {'controller': True}, 'zones': ['battle'],
                'all': True, 'where': {'is_technique': True},
            }}],
        ),
    ]


def _arctic_javelin(code):
    return {}, [
        _ability(
            code, 'n1', '이 기술이 루멘 존에 존재하는 한, 상대는 공격 기술의 효과로 FP를 얻을 수 없다.',
            mode='continuous', timing='function', active_zones=['lumen'],
            # Q-AUTO-015: 상대가 소유한 공격 기술의 효과만 막는다. 자신의 기술로
            # 상대가 얻는 FP와 판정 결과로 얻는 FP는 그대로 얻는다.
            effects=[{'op': 'prevent', 'kind': 'fp_gain', 'player': {'opponent': True},
                      'where': {'type_contains': '공격'},
                      'condition': {'op': 'equals', 'left': 'context.source_card.owner',
                                    'right': {'path': 'context.player'}},
                      'duration': 'continuous'}],
        ),
        _ability(
            code, 'n2', '상쇄 시, 리스트의 이 기술을 루멘 존에 보낸다.',
            timing='clash', active_zones=['list'], trigger={'event': 'clash'},
            allow_non_source_trigger=True,
            condition={'op': 'equals', 'left': 'context.event_controller', 'right': {'controller': True}},
            effects=[{'op': 'move_card', 'card_instance_id': {'path': 'context.source_card_instance_id'},
                      'to_zone': 'lumen'}],
        ),
    ]


def _frostborn(code):
    return {'combo_rules': [{'min_combo': 4}]}, [
        _ability(
            code, 'function', '상대는 이 기술을 상쇄할 수 없다. 이 기술은 3콤보 후에만 콤보에 사용할 수 있다.',
            kind='function', mode='continuous', timing='function', active_zones=['battle'],
            effects=[
                {'op': 'prevent', 'kind': 'clash', 'player': {'opponent': True}, 'duration': 'continuous'},
                {'op': 'static_rule', 'rules': ['combo_rules']},
            ],
        ),
        _frost_damage_bonus(code, 'n1', '상대 「서리」 : 이 기술 데미지+200'),
    ]


def _cold_release(code):
    return {}, [
        _ability(
            code, 'n1', '판정 후, 데미지를 받지 않았다면 상대는 8FP를 잃는다. 그 후, 상대에게 「서리」 상태를 부여한다.',
            timing='after_judgment', active_zones=['battle'], trigger={'event': 'after_judgment'},
            condition={'op': 'equals', 'left': 'context.controller_damage_received', 'right': 0},
            effects=[
                {'op': 'change_fp', 'player': {'opponent': True}, 'amount': -8},
                _give_frost(),
            ],
        ),
    ]


ONI_FLASH = 'RFS-AT-002'  # [귀섬]


def _snatch(code):
    oni_flash_count = {
        'op': 'zone_count', 'player': {'controller': True}, 'zone': 'lumen',
        'where': {'code': ONI_FLASH},
    }
    return {
        'defense_rules': [{'judgment': 'clash', 'where': {'body_not_in': ['발']}}],
    }, [
        _ability(
            code, 'function', '이 기술은 <발> 판정 이외의 기술만 상쇄한다.',
            kind='function', mode='continuous', timing='function', active_zones=['battle'],
            effects=[{'op': 'prevent', 'kind': 'clash', 'player': {'controller': True},
                      'duration': 'continuous',
                      'condition': {'op': 'equals', 'left': 'context.opponent_card.body', 'right': '발'}}],
        ),
        _ability(
            code, 'n1',
            '상쇄 시, 루멘 존의 [귀섬] 1장당 1FP와 보호막 100을 얻는다. '
            '3장 이상인 경우, 상대 기술의 히트 판정을 <+2>로 변경한다.',
            timing='clash', active_zones=['battle'], trigger={'event': 'clash'},
            # 보호막 지속 시간이 적혀 있지 않으면 이번 턴 종료 시까지 유지한다(Q-AUTO-017).
            effects=[
                {'op': 'change_fp', 'player': {'controller': True}, 'amount': copy.deepcopy(oni_flash_count)},
                {'op': 'gain_shield', 'player': {'controller': True}, 'duration': 'turn',
                 'amount': {'op': 'multiply', 'values': [copy.deepcopy(oni_flash_count), 100]}},
                {'op': 'conditional', 'condition': {
                    'op': 'gte', 'left': copy.deepcopy(oni_flash_count), 'right': 3,
                }, 'then': [
                    {'op': 'modify_judgment', 'player': {'opponent': True}, 'field': 'hit', 'value': '+2'},
                ], 'else': []},
            ],
        ),
    ]


def _jigger_impact(code):
    return {}, [
        _ability(
            code, 'n1', '콤보 시, 3콤보 후라면 리커버리 페이즈 시 4FP를 얻는다.',
            timing='combo', active_zones=['battle'], trigger={'event': 'combo'},
            condition={'op': 'gt', 'left': 'context.combo_number', 'right': 3},
            effects=[{'op': 'schedule', 'when': {'event': 'phase_start', 'phase': 'recovery'},
                      'duration': 'turn',
                      'effect': {'op': 'change_fp', 'player': {'controller': True}, 'amount': 4}}],
        ),
    ]


def _oni_flash_count():
    return {
        'op': 'zone_count', 'player': {'controller': True}, 'zone': 'lumen',
        'where': {'code': ONI_FLASH},
    }


def _tiptoe_walk(code):
    returned = 'cb04_at_031_oni_flash_side'
    gained = 'cb04_at_031_list_gain'
    return {}, [
        _ability(
            code, 'n1', '콤보 시, 루멘 존의 [귀섬] 1장당 이 기술 데미지+100',
            timing='combo', active_zones=['battle'], trigger={'event': 'combo'},
            effects=[{'op': 'modify_stat', 'player': {'controller': True}, 'stat': 'damage',
                      'amount': {'op': 'multiply', 'values': [_oni_flash_count(), 100]},
                      'duration': 'battle'}],
        ),
        _ability(
            code, 'n2',
            '「청염」: 사용 후, 리커버리 페이즈 시 루멘 존의 [귀섬] 2장을 사이드 덱으로 되돌리고 '
            '리스트에서 기술 1장을 획득한다.',
            timing='after_use', active_zones=['battle'], trigger={'event': 'after_use'},
            condition={'op': 'has_state', 'player': {'controller': True}, 'state': 'blue_flame'},
            # Q-AUTO-021: [귀섬]이 1장 이하면 발동할 수 없다(되돌리지도 획득하지도 않는다).
            effects=[{'op': 'schedule', 'when': {'event': 'phase_start', 'phase': 'recovery'},
                      'duration': 'turn', 'effect': {
                'op': 'request_choice', 'player': {'controller': True},
                'prompt': '사이드 덱으로 되돌릴 루멘 존의 귀섬 2장을 선택하세요.',
                'selector': {'kind': 'card', 'player': {'controller': True}, 'zones': ['lumen'],
                             'min': 2, 'max': 2, 'where': {'code': ONI_FLASH},
                             'as_operation': 'move_card', 'to_zone': 'side'},
                'selection_key': returned, 'default': [], 'skip_if_unavailable': True,
                'then': [
                    {'op': 'move_card', 'selection_key': returned, 'to_zone': 'side',
                     'result_key': f'{returned}_done'},
                    {'op': 'conditional', 'condition': {
                        'op': 'gte', 'left': {'op': 'selection_count', 'selection_key': f'{returned}_done'},
                        'right': 2,
                    }, 'then': [{
                        'op': 'request_choice', 'player': {'controller': True},
                        'prompt': '리스트에서 획득할 기술을 선택하세요.',
                        'selector': {'kind': 'card', 'player': {'controller': True}, 'zones': ['list'],
                                     'min': 1, 'max': 1, 'where': {'is_technique': True},
                                     'as_operation': 'move_card', 'to_zone': 'hand'},
                        'selection_key': gained, 'default': [], 'skip_if_unavailable': True,
                        'then': [{'op': 'move_card', 'selection_key': gained, 'to_zone': 'hand'}],
                    }], 'else': []},
                ],
            }}],
        ),
    ]


ARM_CONDITION = {
    'op': 'zone_count', 'player': {'controller': True}, 'zone': 'lumen', 'min': 2,
    'where': {'name_contains': 'ARM', 'is_technique': True},
}


def _panzer_reisser(code):
    return {
        'catch_rules': [{'fixed_speed': 9, 'numbered_effect': True,
                         'condition': copy.deepcopy(ARM_CONDITION)}],
    }, [
        _ability(
            code, 'n1',
            '루멘 존에 "ARM"명을 포함하는 기술이 2장 있을 경우, 이 기술은 회피할 수 없고 '
            '<9속도>로 캐치할 수 있다.',
            mode='continuous', timing='function', active_zones=['battle'],
            condition=copy.deepcopy(ARM_CONDITION),
            effects=[
                {'op': 'prevent', 'kind': 'dodge', 'player': {'opponent': True}, 'duration': 'continuous'},
                {'op': 'static_rule', 'rules': ['catch_rules']},
            ],
        ),
    ]


def _fang_haken(code):
    discarded = 'cb04_at_034_discard'
    return {
        'zone_limits': [{'zone': 'lumen', 'max': 1, 'where': {'name_contains': 'OPTION'}}],
        'token_key': 'parts',
    }, [
        _ability(
            code, 'function', '"OPTION"명을 포함하는 기술은 루멘 존에 1장만 배치할 수 있다.',
            kind='function', mode='continuous', timing='function', active_zones=[],
            effects=[{'op': 'static_rule', 'rules': ['zone_limits']}],
        ),
        _ability(
            code, 'n1',
            '1턴에 1번 콤보 시, 패를 1장 버릴 수 있다. 그 후, 속도를 무시하고 [핀프] 기술로 '
            '이을 수 있다. 이번 턴 자신의 리커버리 페이즈를 스킵한다.',
            mode='optional', timing='combo', active_zones=['lumen'], trigger={'event': 'combo'},
            condition={'op': 'equals', 'left': 'context.event_controller', 'right': {'controller': True}},
            limit={'scope': 'turn', 'max': 1, 'key': f'{code.lower()}-n1:usage'},
            availability_selector={'kind': 'card', 'player': {'controller': True}, 'zones': ['hand'],
                                   'min': 1, 'max': 1, 'as_operation': 'discard'},
            # Q-AUTO-020: 패가 없으면 발동할 수 없고, 패를 버린 경우에만 속도 무시 연결을 적용한다.
            # Q-AUTO-022: 리커버리 스킵은 자신의 리커버리 처리만 건너뛴다(엔진 PER_PLAYER_SKIP_PHASES).
            effects=[{
                'op': 'request_choice', 'player': {'controller': True},
                'prompt': '버릴 패 1장을 선택하세요.',
                'selector': {'kind': 'card', 'player': {'controller': True}, 'zones': ['hand'],
                             'min': 1, 'max': 1, 'as_operation': 'discard'},
                'selection_key': discarded, 'default': [],
                'then': [
                    {'op': 'discard', 'selection_key': discarded, 'result_key': f'{discarded}_done'},
                    {'op': 'conditional', 'condition': {
                        'op': 'gte', 'left': {'op': 'selection_count', 'selection_key': f'{discarded}_done'},
                        'right': 1,
                    }, 'then': [
                        {'op': 'modify_combo', 'player': {'controller': True},
                         'where': {'character_key': 'pinp'}, 'ignore_speed': True, 'duration': 'battle'},
                        {'op': 'skip_phase', 'player': {'controller': True}, 'phase': 'recovery'},
                    ], 'else': []},
                ],
            }],
        ),
    ]


def _blazing_thunder(code):
    ember_speeds = [6, 7, 8]
    return {
        'combo_rules': [{'speed_options': list(ember_speeds), 'numbered_effect': True}],
    }, [
        _ability(
            code, 'n1',
            '콤보 시, <6~8속도>로 사용할 수 있다. 그 경우, 이 기술을 브레이크하고 [불씨]카운터를 3개 얻는다.',
            timing='combo', active_zones=['battle'], trigger={'event': 'combo'},
            # Q-AUTO-025: 그 속도로 사용하면 콤보 시 타이밍에 바로 브레이크한다(판정·데미지 처리는 이어진다).
            # 일반 브레이크이므로 나찰염희(CRS-PS-001)의 [불씨] 1개도 얻어 합계 4개가 된다.
            effects=[
                {'op': 'static_rule', 'rules': ['combo_rules']},
                {'op': 'conditional',
                 'condition': {'op': 'in', 'left': 'context.combo_speed', 'right': list(ember_speeds)},
                 'then': [
                     {'op': 'break_card', 'card_instance_id': {'path': 'context.source_card_instance_id'},
                      'continue_resolution': True},
                     {'op': 'change_counter', 'player': {'controller': True}, 'counter': 'ember',
                      'amount': 3, 'min': 0},
                 ],
                 'else': []},
            ],
        ),
        _ability(
            code, 'n2', '이 기술이 그랩 무효 되었을 경우, [불씨]카운터를 1개 얻는다.',
            timing='result', active_zones=['battle'], trigger={'event': 'grab_negated'},
            condition={'op': 'equals', 'left': 'context.event_controller', 'right': {'controller': True}},
            effects=[{'op': 'change_counter', 'player': {'controller': True}, 'counter': 'ember',
                      'amount': 1, 'min': 0}],
        ),
    ]


def _merciful_lullaby(code):
    moved = 'cb04_at_027_spider_lumen'
    rival_spiders = {
        'kind': 'card', 'player': {'opponent': True}, 'zones': ['list'], 'min': 1, 'all': True,
        'where': {'token_key': 'spider'}, 'as_operation': 'move_card', 'to_zone': 'lumen',
        'allow_special_destination': True,
    }
    return {
        'combo_rules': [{'speed_options': [9], 'numbered_effect': True}],
    }, [
        _ability(
            code, 'n1',
            '히트/카운터/콤보 시, 상대 리스트의 [거미]토큰을 전부 자신의 루멘 존에 배치하고 '
            '1장당 200데미지를 줄 수 있다.',
            mode='optional', timing='hit_counter', active_zones=['battle'],
            trigger={'event': 'hit', 'events': ['hit', 'counter', 'combo']},
            availability_selector=copy.deepcopy(rival_spiders),
            effects=[
                {'op': 'move_card', 'selector': copy.deepcopy(rival_spiders), 'to_zone': 'lumen',
                 'to_player': {'controller': True}, 'allow_special_destination': True,
                 'result_key': moved},
                {'op': 'deal_damage', 'player': {'opponent': True},
                 'amount': {'op': 'multiply', 'values': [
                     {'op': 'selection_count', 'selection_key': moved}, 200,
                 ]}},
            ],
        ),
        _ability(
            code, 'n2', '콤보 시, <9속도>로 사용할 수 있다.',
            timing='combo', trigger={'event': 'combo'},
            effects=[{'op': 'static_rule', 'rules': ['combo_rules']}],
        ),
    ]


# --- CB04 추가 공개분(2026-11-21): 부쿠키 -----------------------------------------

def _lumen_bukuki_combo(code, suffix):
    return _ability(
        code, suffix, '콤보 시, 이번 턴 루멘 존의 [부쿠키] 기술을 콤보에 사용할 수 있다.',
        timing='combo', active_zones=['battle'], trigger={'event': 'combo'},
        effects=[{
            'op': 'modify_combo', 'player': {'controller': True},
            # 장수 제한이 없는 허가다. usage_key를 붙이면 1장으로 제한된다.
            'allow_zones': ['lumen'], 'where': dict(BUKUKI_TECHNIQUE),
            'duration': 'turn',
        }],
    )


def _ice_blow(code):
    return {}, [
        _ability(
            code, 'n1', '판정 전, 루멘 존에 [부쿠키] 기술이 3장 이상인 경우 히트 및 카운터 판정을 <콤보>로 변경한다.',
            timing='before_judgment', active_zones=['battle'], trigger={'event': 'before_judgment'},
            condition={'op': 'zone_count', 'player': {'controller': True}, 'zone': 'lumen',
                       'min': 3, 'where': dict(BUKUKI_TECHNIQUE)},
            effects=[
                {'op': 'modify_judgment', 'player': {'controller': True}, 'field': 'hit', 'value': '콤보'},
                {'op': 'modify_judgment', 'player': {'controller': True}, 'field': 'counter', 'value': '콤보'},
            ],
        ),
        _lumen_bukuki_combo(code, 'n2'),
    ]


def _icicle_pillar(code):
    return {
        'defense_rules': [
            {'judgment': 'clash', 'where': {'body': '손'}},
            {'judgment': 'clash', 'where': {'body': '발'}},
        ],
    }, [
        _ability(
            code, 'function', '이 기술은 <손> 및 <발>판정 기술만 상쇄한다.',
            kind='function', mode='continuous', timing='function', active_zones=['battle'],
            effects=[{'op': 'static_rule', 'rules': ['defense_rules']}],
        ),
        _ability(
            code, 'n1', '판정 전, 상대 기술이 500데미지 이상 공격 기술인 경우 <중단 상쇄> 특수 판정을 추가한다.',
            timing='before_judgment', active_zones=['battle'], trigger={'event': 'before_judgment'},
            condition={'op': 'all', 'conditions': [
                {'op': 'card_matches', 'card': {'path': 'context.opponent_card'},
                 'where': {'type_contains': '공격'}},
                {'op': 'gte', 'left': 'context.opponent_damage', 'right': 500},
            ]},
            effects=[{'op': 'modify_judgment', 'player': {'controller': True},
                      'field': 'special', 'value': '중단 상쇄', 'mode': 'append'}],
        ),
        _ability(
            code, 'n2', '상쇄 시, 상대 기술의 히트 판정을 <+0>로 변경한다. 그 후, 사용한 이 기술을 브레이크한다.',
            timing='clash', active_zones=['battle'], trigger={'event': 'clash'},
            effects=[
                {'op': 'modify_judgment', 'player': {'opponent': True}, 'field': 'hit', 'value': '+0'},
                {'op': 'break_card', 'card_instance_id': {'path': 'context.source_card_instance_id'},
                 'continue_resolution': True},
            ],
        ),
    ]


def _trigger_crevasse(code):
    return {}, [
        _ability(
            code, 'n1', '상대 「서리」: 이 기술이 루멘 존에 존재하는 한, 상대는 캐치할 수 없다.',
            mode='continuous', timing='function', active_zones=['lumen'],
            condition={'op': 'has_state', 'player': {'opponent': True}, 'state': FROST_STATE},
            effects=[{'op': 'prevent', 'kind': 'catch', 'player': {'opponent': True},
                      'duration': 'continuous'}],
        ),
    ]



# --- CB04 추가 공개분(2026-11-25): 세츠메이 ----------------------------------------

SPECIAL_TECHNIQUE = {'type_contains': '특수'}


def _frenzy_slice(code):
    return {
        'catch_rules': [{'optional_fixed_speed': 7, 'numbered_effect': True}],
    }, [
        # 추가 캐치 금지는 <7속도>로 사용했을 때만 적용한다(Q-AUTO-027).
        _ability(
            code, 'n1', '캐치 시, <7속도>로 사용할 수 있다. 그 후, 이번 턴 추가로 캐치할 수 없다.',
            timing='catch', active_zones=['battle'], trigger={'event': 'catch'},
            condition={'op': 'equals', 'left': {'path': 'context.fixed_speed'}, 'right': 7},
            effects=[
                {'op': 'static_rule', 'rules': ['catch_rules']},
                {'op': 'prevent', 'kind': 'catch', 'player': {'controller': True}, 'duration': 'turn'},
            ],
        ),
        _ability(
            code, 'n2', '히트 시, 상대는 다음 턴까지 특수 기술의 효과를 사용할 수 없다.',
            timing='hit_counter', active_zones=['battle'], trigger={'event': 'hit'},
            effects=[{
                'op': 'prevent', 'kind': 'card_effects', 'player': {'opponent': True},
                'where': dict(SPECIAL_TECHNIQUE), 'duration': 'next_turn',
            }],
        ),
    ]


def _dust_sweep(code):
    return {
        'combo_rules': [{'ignore_damage_penalty': True, 'damage_bonus': -500, 'numbered_effect': True}],
    }, [
        _ability(
            code, 'n1',
            '콤보 시, 데미지 보정을 적용하지 않고 이 기술 데미지-500. '
            '그 후, 이 기술 뒤에 리스트의 <13속도> 기술로 이을 수 있다.',
            timing='combo', active_zones=['battle'], trigger={'event': 'combo'},
            effects=[
                {'op': 'static_rule', 'rules': ['combo_rules']},
                {
                    'op': 'modify_combo', 'player': {'controller': True}, 'allow_zones': ['list'],
                    # 인쇄 속도 13이거나 자기 효과로 13속도로 쓸 수 있는 기술(Q-AUTO-028).
                    'where': {'is_technique': True}, 'usable_speed': 13,
                    'after_source': True, 'duration': 'battle',
                },
            ],
        ),
    ]


BUILDERS = {
    'CB04-AT-040': _frenzy_slice,
    'CB04-AT-041': _dust_sweep,
    'CB04-AT-005': _ice_blow,
    'CB04-AT-008': _icicle_pillar,
    'CB04-AT-009': _trigger_crevasse,
    'CB04-AT-024': _blazing_thunder,
    'CB04-AT-027': _merciful_lullaby,
    'CB04-AT-031': _tiptoe_walk,
    'CB04-AT-033': _panzer_reisser,
    'CB04-AT-034': _fang_haken,
    'CB04-AT-030': _snatch,
    'CB04-AT-032': _jigger_impact,
    'CB04-PS-001': _frost_veil,
    'CB04-AT-012': _bitter_cold,
    'CB04-AT-001': _snow_country,
    'CB04-AT-002': _winter_fangs,
    'CB04-AT-007': _blizzard,
    'CB04-AT-035': _fan_service,
    'CB04-AT-036': _chromatic_alternate,
    'CB04-AT-037': _rainbow_train,
    'CB04-TK-001': _garage_token,
    'CB04-AT-003': _silent_out,
    'CB04-AT-004': _glasskate,
    'CB04-AT-006': _glacial_bloom,
    'CB04-AT-021': _drunken_spirit,
    'CB04-AT-022': _twin_tail,
    'CB04-AT-010': _arctic_javelin,
    'CB04-AT-011': _frostborn,
    'CB04-AT-013': _cold_release,
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
