"""Registry for deterministic escape-hatch handlers used by effect definitions."""

from collections.abc import Callable


class HandlerRegistrationError(ValueError):
    pass


_HANDLERS: dict[str, Callable] = {}
_HANDLER_TESTS: dict[str, tuple] = {}


def effect_handler(name, *, deterministic_tests=()):
    normalized = str(name or '').strip()
    if not normalized:
        raise HandlerRegistrationError('효과 핸들러 이름이 비어 있습니다.')

    def decorator(func):
        if normalized in _HANDLERS:
            raise HandlerRegistrationError(f'효과 핸들러가 중복 등록되었습니다: {normalized}')
        _HANDLERS[normalized] = func
        _HANDLER_TESTS[normalized] = tuple(deterministic_tests or getattr(func, 'deterministic_tests', ()) or ())
        return func

    return decorator


def get_handler(name):
    return _HANDLERS.get(str(name or '').strip())


def registered_handler_names():
    return frozenset(_HANDLERS)


def handler_has_deterministic_tests(name):
    return bool(_HANDLER_TESTS.get(str(name or '').strip()))


def run_handler_deterministic_tests(name):
    failures = []
    for index, test in enumerate(_HANDLER_TESTS.get(str(name or '').strip(), ())):
        if not callable(test):
            failures.append(f'test {index + 1}: callable이 아닙니다.')
            continue
        try:
            result = test()
        except Exception as exc:  # Publication reports the handler-owned failure.
            failures.append(f'test {index + 1}: {type(exc).__name__}: {exc}')
        else:
            if result is False:
                failures.append(f'test {index + 1}: 실패를 반환했습니다.')
    return failures


def _counter_count(state, side, key):
    return int(
        (((state.get('players') or {}).get(side) or {}).get('passive_state') or {})
        .get(key, {}).get('count') or 0
    )


def _state_enabled(state, side, key):
    return bool(
        (((state.get('players') or {}).get(side) or {}).get('passive_state') or {})
        .get(key, {}).get('value')
    )


def _bagua_state_commands(state, context):
    side = context.get('controller')
    yin = _counter_count(state, side, 'yin')
    yang = _counter_count(state, side, 'yang')
    harmony = _state_enabled(state, side, 'harmony')
    self_player = {'controller': True}
    clear_yin_yang = [
        {'op': 'lose_state', 'player': self_player, 'state': 'yin'},
        {'op': 'lose_state', 'player': self_player, 'state': 'yang'},
    ]
    if yin >= 4 and yang >= 4 and not harmony:
        return [
            {'op': 'gain_state', 'player': self_player, 'state': 'harmony'},
            *clear_yin_yang,
            {
                'op': 'choose_effect', 'player': self_player,
                'prompt': '조화 상태 동안 적용할 효과를 선택하세요.',
                'default': 'damage',
                'options': [
                    {
                        'id': 'damage', 'label': '타오 기술 데미지 +100',
                        'effects': [
                            {'op': 'gain_state', 'player': self_player, 'state': 'harmony_damage'},
                            {'op': 'lose_state', 'player': self_player, 'state': 'harmony_fp'},
                        ],
                    },
                    {
                        'id': 'fp', 'label': '턴당 1번 루멘 페이즈에 1FP',
                        'effects': [
                            {'op': 'gain_state', 'player': self_player, 'state': 'harmony_fp'},
                            {'op': 'lose_state', 'player': self_player, 'state': 'harmony_damage'},
                        ],
                    },
                ],
            },
        ]
    if harmony and yin >= 3 and yang >= 3:
        return clear_yin_yang

    effects = []
    if harmony:
        effects.extend([
            {'op': 'lose_state', 'player': self_player, 'state': 'harmony'},
            {'op': 'lose_state', 'player': self_player, 'state': 'harmony_damage'},
            {'op': 'lose_state', 'player': self_player, 'state': 'harmony_fp'},
        ])
    if yin > yang:
        effects.extend([
            {'op': 'gain_state', 'player': self_player, 'state': 'yin'},
            {'op': 'lose_state', 'player': self_player, 'state': 'yang'},
        ])
    elif yang > yin:
        effects.extend([
            {'op': 'gain_state', 'player': self_player, 'state': 'yang'},
            {'op': 'lose_state', 'player': self_player, 'state': 'yin'},
        ])
    else:
        effects.extend(clear_yin_yang)
    return effects


def _test_bagua_enters_harmony():
    state = {
        'players': {
            'p1': {'passive_state': {'yin': {'count': 4}, 'yang': {'count': 4}}},
        },
    }
    effects = _bagua_state_commands(state, {'controller': 'p1'})
    return (
        effects[0].get('op') == 'gain_state'
        and effects[0].get('state') == 'harmony'
        and effects[-1].get('op') == 'choose_effect'
    )


def _test_bagua_harmony_persists_at_three():
    state = {
        'players': {
            'p1': {
                'passive_state': {
                    'yin': {'count': 3}, 'yang': {'count': 4},
                    'harmony': {'value': True},
                },
            },
        },
    }
    effects = _bagua_state_commands(state, {'controller': 'p1'})
    return all(effect.get('state') in {'yin', 'yang'} for effect in effects)


def _test_bagua_uses_printed_speed_parity():
    odd = _bagua_counter_commands({}, {
        'event_card': {'frame': 7}, 'controller': 'p1',
    })
    even = _bagua_counter_commands({}, {
        'event_card': {'frame': 8}, 'controller': 'p1',
    })
    return odd[0].get('counter') == 'yin' and even[0].get('counter') == 'yang'


@effect_handler(
    'tao_bagua_reconcile',
    deterministic_tests=(_test_bagua_enters_harmony, _test_bagua_harmony_persists_at_three),
)
def tao_bagua_reconcile(state, context, ability):
    return _bagua_state_commands(state, context)


def _bagua_counter_commands(state, context):
    frame = int((context.get('event_card') or {}).get('frame') or 0)
    side = context.get('controller')
    player = ((state.get('players') or {}).get(side) or {})
    passive_state = player.get('passive_state') or {}
    mujin_active = bool(
        (passive_state.get('mujin_active') or {}).get('value')
    )
    mujin_card = next((
        card for card in ((player.get('zones') or {}).get('ultimate') or [])
        if card.get('code') == 'CB01-AT-025'
        and not card.get('numbered_effects_negated')
    ), None)
    if mujin_active and mujin_card and int(player.get('hp') or 0) <= 3000:
        self_player = {'controller': True}
        return [{
            'op': 'choose_effect', 'player': self_player,
            'prompt': '팔괘 효과로 획득할 카운터를 선택하세요.',
            'default': 'yin',
            'options': [
                {
                    'id': 'yin', 'label': '음 카운터',
                    'effects': [{
                        'op': 'change_counter', 'player': self_player,
                        'counter': 'yin', 'amount': 1, 'min': 0, 'max': 4,
                    }],
                },
                {
                    'id': 'yang', 'label': '양 카운터',
                    'effects': [{
                        'op': 'change_counter', 'player': self_player,
                        'counter': 'yang', 'amount': 1, 'min': 0, 'max': 4,
                    }],
                },
            ],
        }]
    return [{
        'op': 'change_counter', 'player': {'controller': True},
        'counter': 'yin' if frame % 2 else 'yang',
        'amount': 1, 'min': 0, 'max': 4,
    }]


def _test_mujin_allows_desired_bagua_counter():
    state = {
        'players': {
            'p1': {
                'hp': 3000,
                'passive_state': {'mujin_active': {'value': True}},
                'zones': {
                    'ultimate': [{
                        'code': 'CB01-AT-025',
                        'instance_id': 'p1-mujin',
                    }],
                },
            },
        },
    }
    effects = _bagua_counter_commands(state, {
        'event_card': {'frame': 7}, 'controller': 'p1',
    })
    return bool(
        effects and effects[0].get('op') == 'choose_effect'
        and [
            option.get('id') for option in effects[0].get('options') or []
        ] == ['yin', 'yang']
    )


@effect_handler(
    'tao_bagua_counter_gain',
    deterministic_tests=(
        _test_bagua_uses_printed_speed_parity,
        _test_mujin_allows_desired_bagua_counter,
    ),
)
def tao_bagua_counter_gain(state, context, ability):
    return _bagua_counter_commands(state, context)
