"""CB04 부쿠키 카드 자동 효과 초안의 엔진 동작 테스트."""

from django.test import SimpleTestCase

from .game.drafts import build_effect_draft
from .game.engine import AutomaticGameEngine
from .game.schema import validate_effect_definition
from .test_automatic_engine import attack, base_state, defense, ruleset


BUKUKI = '부쿠키'


def bukuki(card):
    card['character_key'] = BUKUKI
    return card


def passive_card(instance_id, owner, code):
    return {
        'instance_id': instance_id, 'kind': 'card', 'owner': owner, 'code': code,
        'name': instance_id, 'type': '특성', 'frame': None, 'damage': None,
        'hit': '0', 'guard': '0', 'counter': '0', 'face_up': True,
        'character_key': BUKUKI,
    }


class CB04AutomaticEffectTests(SimpleTestCase):
    def engine_for(self, state, cards, *, seed):
        release = ruleset(*cards)
        for card in cards:
            if card['code'].startswith('CB04-'):
                definition = build_effect_draft(card['code'], '')
                self.assertEqual(validate_effect_definition(definition, card_has_text=True), [])
                release['cards'][card['code']]['effect_definition'] = definition
        engine = AutomaticGameEngine.initialize(state, release, seed=seed)
        engine.state['phase'] = 'battle'
        return engine

    def resolve(self, engine, *, accept=True, choose=None):
        """Answer pending optional prompts and choices, returning choice owners."""
        owners = []
        for _ in range(10):
            decision = engine.engine_state.get('pending_decision') or {}
            if not decision:
                return owners
            options = [item.get('id') for item in decision.get('options') or []]
            if decision.get('kind') == 'effect_choice':
                owners.append(decision['owner'])
                selected = [choose] if choose in options else options[:1]
            elif decision.get('kind') == 'optional_effect':
                selected = ['accept' if accept and 'accept' in options else options[-1]]
            else:
                selected = options[:1]
            engine._submit_decision(decision['owner'], decision['id'], selected)
            engine._continue()
        self.fail('결정이 끝나지 않았습니다.')

    def frost(self, engine, side):
        return (engine.state['players'][side]['passive_state'].get('frost') or {}).get('value')

    def test_frost_veil_guard_gives_frost_to_opponent_and_stocks_lumen(self):
        veil = passive_card('veil', 'p1', 'CB04-PS-001')
        stock = bukuki(attack('stock', 'p1', code='CB04-AT-002'))
        other = attack('other', 'p1', code='OTHER-001')
        state = base_state([stock, other], [])
        state['players']['p1']['zones']['passive'] = [veil]
        engine = self.engine_for(state, [veil, stock, other], seed='frost-veil-guard')

        engine._fire('guard', {'controller': 'p1'})
        self.resolve(engine)

        self.assertTrue(self.frost(engine, 'p2'))
        self.assertFalse(self.frost(engine, 'p1'))
        expirations = engine.engine_state['state_expirations']
        self.assertEqual(
            [(item['player'], item['state'], item['phase'], item['remaining']) for item in expirations],
            [('p2', 'frost', 'recovery', 2)],
        )
        self.assertEqual(expirations[0]['remaining'], 2)
        self.assertIsNotNone(engine._find_card('stock', owner='p1', zone='lumen'))
        self.assertIsNotNone(engine._find_card('other', owner='p1', zone='hand'))

    def test_frost_veil_ignores_opponent_guard(self):
        veil = passive_card('veil', 'p1', 'CB04-PS-001')
        state = base_state([], [])
        state['players']['p1']['zones']['passive'] = [veil]
        engine = self.engine_for(state, [veil], seed='frost-veil-opponent-guard')

        engine._fire('guard', {'controller': 'p2'})

        self.assertFalse(self.frost(engine, 'p2'))

    def test_frost_veil_recovery_returns_lumen_bukuki_only_when_behind_in_fp(self):
        for p1_fp, p2_fp, expected_zone in ((1, 3, 'list'), (3, 3, 'lumen')):
            with self.subTest(p1_fp=p1_fp, p2_fp=p2_fp):
                veil = passive_card('veil', 'p1', 'CB04-PS-001')
                stored = bukuki(attack('stored', 'p1', code='CB04-AT-007'))
                state = base_state([], [], p1_fp=p1_fp, p2_fp=p2_fp)
                state['players']['p1']['zones']['passive'] = [veil]
                state['players']['p1']['zones']['lumen'] = [stored]
                engine = self.engine_for(state, [veil, stored], seed=f'frost-veil-recovery-{p1_fp}')
                engine.state['phase'] = 'recovery'

                engine._fire('phase_start', {'phase': 'recovery'})
                self.resolve(engine)

                self.assertIsNotNone(engine._find_card('stored', owner='p1', zone=expected_zone))

    def test_bitter_cold_dodges_only_x_guard_and_powers_bukuki_combo_from_lumen(self):
        cold = bukuki(attack('cold', 'p1', code='CB04-AT-012', frame=14, damage=600))
        cold['guard'] = '-4'
        combo_card = bukuki(attack('combo', 'p1', code='CB04-AT-002', damage=400))
        x_attack = attack('x-attack', 'p2')
        x_attack['guard'] = 'X'
        normal_attack = attack('normal-attack', 'p2')
        normal_attack['guard'] = '-4'
        state = base_state([], [])
        state['players']['p1']['zones']['lumen'] = [cold]
        state['players']['p1']['zones']['battle'] = [combo_card]
        engine = self.engine_for(state, [cold, combo_card, x_attack, normal_attack], seed='bitter-cold')

        self.assertTrue(engine._defense_judgment_allowed(cold, x_attack, 'dodge', 'p2'))
        self.assertFalse(engine._defense_judgment_allowed(cold, normal_attack, 'dodge', 'p2'))

        engine._fire('use', {
            'controller': 'p1', 'source_card': combo_card,
            'source_card_instance_id': combo_card['instance_id'], 'combo': False,
        })
        self.assertEqual(engine.card_stat(combo_card, 'damage', 'p1'), 400)
        engine._fire('use', {
            'controller': 'p1', 'source_card': combo_card,
            'source_card_instance_id': combo_card['instance_id'], 'combo': True,
        })
        self.assertEqual(engine.card_stat(combo_card, 'damage', 'p1'), 500)

    def test_snow_country_negates_opponent_effects_then_gives_frost_and_breaks(self):
        snow = bukuki(defense('snow', 'p1', top='방어', mid='방어', bottom='방어'))
        snow['code'] = 'CB04-AT-001'
        snow['ultimate'] = True
        enemy = attack('enemy', 'p2', code='ENEMY-001')
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [snow]
        state['players']['p2']['zones']['battle'] = [enemy]
        engine = self.engine_for(state, [snow, enemy], seed='snow-country')
        engine.engine_state['battle'] = {
            'p1': {'instance_id': 'snow', 'card': snow},
            'p2': {'instance_id': 'enemy', 'card': enemy},
        }
        context = {'controller': 'p1', 'source_card': snow, 'source_card_instance_id': 'snow'}

        engine._fire('use', dict(context))
        self.resolve(engine)
        _owner, _zone, _index, live_enemy = engine._find_location('enemy')
        self.assertTrue(live_enemy.get('numbered_effects_negated'))
        self.assertIsNotNone(engine._find_card('enemy', owner='p2', zone='battle'))

        engine._fire('after_use', dict(context))
        self.resolve(engine)
        self.assertTrue(self.frost(engine, 'p2'))
        self.assertIsNotNone(engine._find_card('snow', owner='p1', zone='break'))

    def test_snow_country_play_condition_requires_hp_2500_or_less(self):
        definition = build_effect_draft('CB04-AT-001', '')
        self.assertEqual(definition['play_condition'], {
            'op': 'lte', 'left': 'context.controller_hp', 'right': 2500,
        })

    def test_winter_fangs_dodge_gives_opponent_fp_and_user_picks_lumen_bukuki(self):
        fangs = bukuki(attack('fangs', 'p1', code='CB04-AT-002', frame=5))
        stored = bukuki(attack('stored', 'p1', code='CB04-AT-007'))
        unrelated = attack('unrelated', 'p1', code='OTHER-002')
        enemy = attack('enemy', 'p2', code='ENEMY-002')
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [fangs]
        state['players']['p1']['zones']['lumen'] = [stored, unrelated]
        state['players']['p2']['zones']['battle'] = [enemy]
        engine = self.engine_for(state, [fangs, stored, unrelated, enemy], seed='winter-fangs-dodge')

        engine._fire('opponent_dodge', {
            'controller': 'p1', 'source_card': fangs,
            'source_card_instance_id': 'fangs', 'opponent_card': enemy,
        })
        decision = engine.engine_state.get('pending_decision') or {}
        # Q-AUTO-009: 리스트로 보낼 기술은 윈터 팽스 사용자가 고른다.
        self.assertEqual(decision.get('owner'), 'p1')
        self.assertEqual([item['id'] for item in decision['options']], ['stored'])
        self.resolve(engine)

        self.assertEqual(engine.state['players']['p2']['fp'], 2)
        self.assertIsNotNone(engine._find_card('stored', owner='p1', zone='list'))
        self.assertIsNotNone(engine._find_card('unrelated', owner='p1', zone='lumen'))

    def test_winter_fangs_hit_may_send_bukuki_to_lumen(self):
        fangs = bukuki(attack('fangs', 'p1', code='CB04-AT-002'))
        listed = bukuki(attack('listed', 'p1', code='CB04-AT-012'))
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [fangs]
        state['players']['p1']['zones']['list'] = [listed]
        engine = self.engine_for(state, [fangs, listed], seed='winter-fangs-hit')

        engine._fire('hit', {'controller': 'p1', 'source_card': fangs, 'source_card_instance_id': 'fangs'})
        self.resolve(engine)

        self.assertIsNotNone(engine._find_card('listed', owner='p1', zone='lumen'))

    def test_winter_fangs_hit_and_combo_in_same_turn_send_only_once(self):
        fangs = bukuki(attack('fangs', 'p1', code='CB04-AT-002'))
        first = bukuki(attack('first', 'p1', code='CB04-AT-012'))
        second = bukuki(attack('second', 'p1', code='CB04-AT-007'))
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [fangs]
        state['players']['p1']['zones']['list'] = [first, second]
        engine = self.engine_for(state, [fangs, first, second], seed='winter-fangs-once')
        context = {'controller': 'p1', 'source_card': fangs, 'source_card_instance_id': 'fangs'}

        engine._fire('hit', dict(context))
        self.resolve(engine)
        engine._fire('combo', dict(context))
        self.resolve(engine)

        self.assertEqual(len(engine.state['players']['p1']['zones']['lumen']), 1)

    def test_blizzard_frost_damage_hit_frost_and_lumen_combo_rule(self):
        blizzard = bukuki(attack('blizzard', 'p1', code='CB04-AT-007', frame=9, damage=400))
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [blizzard]
        engine = self.engine_for(state, [blizzard], seed='blizzard')
        engine._refresh_continuous_rules()
        self.assertEqual(engine.card_stat(blizzard, 'damage', 'p1'), 400)

        context = {'controller': 'p1', 'source_card': blizzard, 'source_card_instance_id': 'blizzard'}
        engine._fire('hit', dict(context))
        self.resolve(engine)
        self.assertTrue(self.frost(engine, 'p2'))
        engine._refresh_continuous_rules()
        self.assertEqual(engine.card_stat(blizzard, 'damage', 'p1'), 600)

        engine._fire('combo', dict(context))
        self.resolve(engine)
        combo_modifiers = [
            item for item in engine.engine_state.get('modifiers') or []
            if item.get('op') == 'modify_combo'
        ]
        self.assertEqual(len(combo_modifiers), 1)
        self.assertEqual(combo_modifiers[0]['allow_zones'], ['lumen'])
        self.assertEqual(combo_modifiers[0]['where']['character_key'], BUKUKI)
        self.assertEqual(combo_modifiers[0]['duration'], 'turn')

    def test_blizzard_dodges_only_speed_eight_or_lower(self):
        blizzard = bukuki(attack('blizzard', 'p1', code='CB04-AT-007', frame=9))
        fast = attack('fast', 'p2', frame=8)
        slow = attack('slow', 'p2', frame=9)
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [blizzard]
        engine = self.engine_for(state, [blizzard, fast, slow], seed='blizzard-dodge')

        self.assertTrue(engine._defense_judgment_allowed(blizzard, fast, 'dodge', 'p2'))
        self.assertFalse(engine._defense_judgment_allowed(blizzard, slow, 'dodge', 'p2'))

    def test_frost_regrant_triggers_frost_veil_again_without_turn_limit(self):
        # Q-AUTO-007: 이미 서리 상태여도 ②가 발동하고, 턴당 1회 제한이 없다.
        veil = passive_card('veil', 'p1', 'CB04-PS-001')
        blizzard = bukuki(attack('blizzard', 'p1', code='CB04-AT-007', frame=9))
        first = bukuki(attack('first', 'p1', code='CB04-AT-012'))
        second = bukuki(attack('second', 'p1', code='CB04-AT-002'))
        state = base_state([first, second], [])
        state['players']['p1']['zones']['passive'] = [veil]
        state['players']['p1']['zones']['battle'] = [blizzard]
        engine = self.engine_for(state, [veil, blizzard, first, second], seed='frost-regrant')

        engine._fire('guard', {'controller': 'p1'})
        self.resolve(engine)
        self.assertTrue(self.frost(engine, 'p2'))
        engine._fire('hit', {
            'controller': 'p1', 'source_card': blizzard, 'source_card_instance_id': 'blizzard',
        })
        self.resolve(engine)

        self.assertEqual(len(engine.state['players']['p1']['zones']['lumen']), 2)

    def test_frost_regrant_keeps_the_longer_expiration(self):
        # Q-AUTO-007: 재부여 시 더 오래 지속되는 쪽을 유지한다.
        engine = self.engine_for(base_state([], []), [], seed='frost-expiration')
        long_frost = {'event': 'phase_end', 'phase': 'recovery', 'occurrences': 2, 'keep_longer': True}
        engine.set_passive('p2', 'frost', value=True, expires=dict(long_frost))
        engine.set_passive('p2', 'frost', value=True, expires={**long_frost, 'occurrences': 1})
        self.assertEqual(engine.engine_state['state_expirations'][0]['remaining'], 2)

        engine.engine_state['state_expirations'][0]['remaining'] = 1
        engine.set_passive('p2', 'frost', value=True, expires=dict(long_frost))
        self.assertEqual(engine.engine_state['state_expirations'][0]['remaining'], 2)

    def test_bitter_cold_also_powers_bukuki_combo_starter_once(self):
        # Q-AUTO-010: 1콤보 시동 기술에도 +100을 적용한다.
        cold = bukuki(attack('cold', 'p1', code='CB04-AT-012', frame=14, damage=600))
        starter = bukuki(attack('starter', 'p1', code='CB04-AT-007', damage=400, hit='콤보'))
        other = attack('other-starter', 'p1', code='OTHER-003', damage=400, hit='콤보')
        state = base_state([], [])
        state['players']['p1']['zones']['lumen'] = [cold]
        state['players']['p1']['zones']['battle'] = [starter, other]
        engine = self.engine_for(state, [cold, starter, other], seed='bitter-cold-starter')

        for card in (starter, other):
            for _ in range(2):
                engine._fire('combo', {
                    'controller': 'p1', 'source_card': card,
                    'source_card_instance_id': card['instance_id'],
                    'combo_judgment': True, 'combo_number': 1,
                })
                self.resolve(engine)

        self.assertEqual(engine.card_stat(starter, 'damage', 'p1'), 500)
        self.assertEqual(engine.card_stat(other, 'damage', 'p1'), 400)
