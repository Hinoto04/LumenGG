"""레디 결과표를 카드별 수치표로 채우는 평가(ai_outcomes)와 열 정리."""

from django.test import SimpleTestCase

from .game.ai import choose_action
from .game.ai_matrix import dominated_free_columns, ready_matrix
from .game.ai_outcomes import (
    MIN_SAMPLES, WIN_VALUE, OutcomeRecorder, OutcomeTable, TableReadyEvaluator, build_ready_evaluator,
    state_key, table_for_profile,
)
from .game.ai_profile import ProfileError, parse_profile_text
from .test_ai_matrix import ready_engine
from .test_automatic_engine import attack, defense


def ready_actions(engine, side='p1'):
    return [action for action in engine.legal_actions(side) if action['type'] == 'ready_card']


class OutcomeTableTests(SimpleTestCase):
    def test_default_gain_uses_printed_damage_and_fp(self):
        card = {'code': 'A', 'damage': '700', 'hit': '+2'}

        gain = OutcomeTable().gain(card, 'hit')

        self.assertEqual(gain['damage'], 700)
        self.assertEqual(gain['fp'], 2)
        self.assertEqual(OutcomeTable().gain(card, 'countered')['damage'], 0)

    def test_few_samples_blend_with_the_default(self):
        table = OutcomeTable({'A': {'results': {'hit': {'n': 1, 'damage': 1600, 'fp': 0, 'counter': 3, 'card': 0}}}})

        gain = table.gain({'code': 'A', 'damage': '400'}, 'hit')

        self.assertAlmostEqual(gain['damage'], (1600 + 2 * 400) / MIN_SAMPLES)
        self.assertAlmostEqual(gain['counter'], 1.0)

    def test_measured_combo_damage_carries_to_unmeasured_starters(self):
        table = OutcomeTable({'A': {
            'character_id': 7, 'printed_damage': 400, 'combo': {'hit': True},
            'results': {'hit': {'n': 4, 'damage': 2400, 'fp': 0, 'counter': 0, 'card': 0}},
        }})

        gain = table.gain({'code': 'B', 'damage': '500', 'hit': '콤보', 'character_id': 7}, 'hit')

        self.assertEqual(gain['damage'], 2500)

    def test_profile_overrides_win(self):
        profile = parse_profile_text(
            '[outcome."A".hit]\ndamage = 2000\ncounter = 3\n[resources]\ncounter = 400\n'
        )
        table, rates = table_for_profile(profile, OutcomeTable({'A': {'results': {
            'hit': {'n': 9, 'damage': 900, 'fp': 1, 'counter': 0, 'card': 0},
        }}}))

        gain = table.gain({'code': 'A', 'damage': '400'}, 'hit')

        self.assertEqual((gain['damage'], gain['counter'], gain['fp']), (2000, 3, 1))
        self.assertEqual(rates['counter'], 1.0)

    def test_profile_rejects_unknown_result_and_resource(self):
        with self.assertRaises(ProfileError) as raised:
            parse_profile_text('[outcome."A".hitt]\ndamage = 1\n[outcome."B".hit]\nmana = 1\n')

        self.assertIn('hitt', str(raised.exception))
        self.assertIn('mana', str(raised.exception))

    def test_drift_needs_enough_judgments(self):
        table = OutcomeTable({'A': {'judged': 2, 'drift': 2}, 'B': {'judged': 10, 'drift': 5}})

        self.assertFalse(table.drifts({'code': 'A'}))
        self.assertTrue(table.drifts({'code': 'B'}))


class TableEvaluatorTests(SimpleTestCase):
    def test_cells_follow_the_judgment_and_table(self):
        fast = attack('fast', 'p1', frame=3, damage=500)
        slow = attack('slow', 'p1', frame=9, damage=500)
        rival = attack('rival', 'p2', frame=6, damage=400)
        engine = ready_engine([fast, slow], [rival])
        observation = engine.observe('p1', include_memory=True)
        evaluator = TableReadyEvaluator(observation, 'p1', table=OutcomeTable())
        by_id = {action['card']['instance_id']: action for action in ready_actions(engine)}
        rival_card = observation['memory']['rival_hand'][0]

        self.assertGreater(evaluator(by_id['fast'], rival_card), 0)
        self.assertLess(evaluator(by_id['slow'], rival_card), 0)

    def test_lethal_damage_adds_the_win_value(self):
        fast = attack('fast', 'p1', frame=3, damage=500)
        engine = ready_engine([fast, attack('slow', 'p1', frame=9)], [attack('rival', 'p2', frame=6)])
        engine.state['players']['p2']['hp'] = 500
        observation = engine.observe('p1', include_memory=True)
        evaluator = TableReadyEvaluator(observation, 'p1', table=OutcomeTable())
        action = next(a for a in ready_actions(engine) if a['card']['instance_id'] == 'fast')

        self.assertGreater(evaluator(action, observation['memory']['rival_hand'][0]), WIN_VALUE)

    def test_choose_action_reports_a_table_evaluation(self):
        engine = ready_engine(
            [attack('fast', 'p1', frame=3), attack('even', 'p1', frame=6), attack('slow', 'p1', frame=9)],
            [attack('rival', 'p2', frame=6)],
        )
        observation = engine.observe('p1', include_memory=True)

        decision = choose_action(
            observation, 'p1', seed='t', temperature=0,
            ready_evaluator=build_ready_evaluator(engine, observation, 'p1', engine_cells=False),
        )

        self.assertEqual(decision.action['card']['instance_id'], 'fast')
        self.assertTrue(decision.details['table_evaluated'])
        self.assertFalse(decision.details['engine_evaluated'])
        self.assertEqual(decision.details['engine_cells'], 0)


class RefineTests(SimpleTestCase):
    def test_only_drifting_cards_in_kept_columns_are_simulated(self):
        engine = ready_engine(
            [attack('fast', 'p1', frame=3), attack('slow', 'p1', frame=9)],
            [attack('quick', 'p2', frame=4), attack('dull', 'p2', frame=12), attack('odd', 'p2', frame=7)],
        )
        observation = engine.observe('p1', include_memory=True)
        calls = []

        def refiner(action, rival_card):
            calls.append((action['card']['instance_id'], rival_card['instance_id']))
            return 0.0

        table = OutcomeTable({'ODD': {'judged': 10, 'drift': 8}})
        evaluator = TableReadyEvaluator(observation, 'p1', table=table, refiner=refiner)

        matrix, options, _coverage = ready_matrix(observation, 'p1', ready_actions(engine), evaluator=evaluator)

        codes = [card['code'] for card in options]
        self.assertNotIn('DULL', codes)  # 'quick'보다 항상 상대에게 나쁜 카드
        self.assertIn('ODD', codes)  # 판정이 자주 바뀌는 카드는 남겨 엔진으로 본다
        self.assertEqual(evaluator.pruned, ['DULL'])
        self.assertEqual(sorted(rival for _mine, rival in calls), ['odd', 'odd'])
        self.assertEqual(matrix[0][codes.index('ODD')], 0.0)

    def test_dominated_columns(self):
        matrix = [[1, 3, 1, 0], [2, 4, 2, 5]]

        self.assertEqual(dominated_free_columns(matrix), [0, 3])
        self.assertEqual(dominated_free_columns(matrix, protected={1}), [0, 1, 3])


class RecorderTests(SimpleTestCase):
    def test_one_battle_is_recorded_for_both_cards(self):
        engine = ready_engine([attack('fast', 'p1', frame=3, damage=500)], [defense('wall', 'p2', top='방어')])
        recorder = OutcomeRecorder(engine.ruleset)
        turn = engine.state.get('turn')
        for step in range(60):
            recorder.step(engine)
            if engine.state.get('turn') != turn or engine.engine_state.get('status') != 'running':
                break
            decisions = [
                (side, choose_action(engine.observe(side, include_memory=True), side, seed=f'r{step}', temperature=0))
                for side in ('p1', 'p2')
            ]
            decisions = [(side, d) for side, d in decisions if d]
            side, decision = max(decisions, key=lambda item: item[1].score)
            engine.submit_action(side, decision.action['action_id'], decision.selections, command_id=f'r{step}')
        recorder.finish(engine)

        self.assertEqual(recorder.battles, 1)
        payload = recorder.table_payload()
        self.assertEqual(set(payload['cards']), {'FAST', 'WALL'})
        fast = payload['cards']['FAST']
        self.assertEqual(fast['judged'], 1)
        self.assertEqual(list(fast['results']), ['guarded'])
        self.assertEqual(fast['drift'], 0)


class SpeedOffsetTests(SimpleTestCase):
    def test_state_key_lists_on_off_states_only(self):
        player = {'passive_state': {'charge': {'value': True}, 'howling': {'count': 3, 'value': True}, 'off': {'value': False}}}
        engine_state = {'continuous_states': {'p1': {'saintess': ['src'], 'gone': []}}}

        self.assertEqual(state_key(player, engine_state, 'p1'), 'charge+saintess')

    def test_offset_prefers_card_state_then_state_average(self):
        table = OutcomeTable(
            {'A': {'speed': {'': {'n': 5, 'offset': 0.5}, 'charge': {'n': 4, 'offset': 2.0}}}},
            state_speed={'': {'n': 50, 'offset': 0.2}, 'charge': {'n': 20, 'offset': 2.2}, 'rare': {'n': 1, 'offset': 9}},
        )

        self.assertEqual(table.speed_offset('A'), 0.5)
        self.assertEqual(table.speed_offset('A', 'charge'), 2.0)
        self.assertAlmostEqual(table.speed_offset('B', 'charge'), 2.0)
        self.assertEqual(table.speed_offset('A', 'rare'), 0.5)

    def test_slower_own_card_flips_the_prediction(self):
        engine = ready_engine([attack('cut', 'p1', frame=5), attack('slow', 'p1', frame=9)], [attack('rival', 'p2', frame=6)])
        engine.state['players']['p1'].setdefault('passive_state', {})['charge'] = {'value': True}
        observation = engine.observe('p1', include_memory=True)
        action = next(a for a in ready_actions(engine) if a['card']['instance_id'] == 'cut')
        rival_card = observation['memory']['rival_hand'][0]
        plain = TableReadyEvaluator(observation, 'p1', table=OutcomeTable())
        charged = TableReadyEvaluator(observation, 'p1', table=OutcomeTable(
            {'CUT': {'speed': {'charge': {'n': 5, 'offset': 2.0}}}},
        ))

        self.assertEqual(charged.my_states, 'charge')
        self.assertGreater(plain(action, rival_card), 0)
        self.assertLess(charged(action, rival_card), 0)


class RecorderSpeedTests(SimpleTestCase):
    def test_recorder_keeps_the_real_speed(self):
        engine = ready_engine([attack('fast', 'p1', frame=3, damage=500)], [defense('wall', 'p2', top='방어')])
        recorder = OutcomeRecorder(engine.ruleset)
        turn = engine.state.get('turn')
        for step in range(60):
            recorder.step(engine)
            if engine.state.get('turn') != turn or engine.engine_state.get('status') != 'running':
                break
            decisions = [
                (side, choose_action(engine.observe(side, include_memory=True), side, seed=f's{step}', temperature=0))
                for side in ('p1', 'p2')
            ]
            side, decision = max([(s, d) for s, d in decisions if d], key=lambda item: item[1].score)
            engine.submit_action(side, decision.action['action_id'], decision.selections, command_id=f's{step}')
        recorder.finish(engine)

        payload = recorder.table_payload()
        self.assertEqual(payload['cards']['FAST']['speed'][''], {'n': 1, 'offset': 0.0})
        self.assertIn('', payload['state_speed'])
