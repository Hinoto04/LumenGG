"""레디 행렬 게임(혼합 전략)과 엔진 시뮬레이션 평가."""

from django.test import SimpleTestCase

from .game.ai import choose_action
from .game.ai_engine_eval import EngineReadyEvaluator
from .game.ai_matrix import solve_zero_sum
from .game.engine import AutomaticGameEngine
from .test_automatic_engine import attack, base_state, defense, ruleset


class ZeroSumTests(SimpleTestCase):
    def test_rock_paper_scissors_mixes_evenly(self):
        strategy = solve_zero_sum([[0, -1, 1], [1, 0, -1], [-1, 1, 0]], iterations=3000)

        for probability in strategy:
            self.assertAlmostEqual(probability, 1 / 3, delta=0.03)

    def test_dominant_row_is_pure(self):
        self.assertEqual(solve_zero_sum([[2, 2], [1, -1]]), [1.0, 0.0])


def ready_engine(p1_hand, p2_hand):
    state = base_state(p1_hand, p2_hand)
    engine = AutomaticGameEngine.initialize(state, ruleset(*p1_hand, *p2_hand), seed='matrix')
    for side in ('p1', 'p2'):
        action = next(item for item in engine.legal_actions(side) if item['type'] == 'pass_phase')
        engine.submit_action(side, action['action_id'], {}, command_id=f'pass-{side}')
    return engine


class ReadyMatrixTests(SimpleTestCase):
    def test_matrix_choice_reports_details_and_uses_known_cards(self):
        fast = attack('fast', 'p1', frame=3)
        middle = attack('middle', 'p1', frame=5)
        slow = attack('slow', 'p1', frame=9)
        engine = ready_engine([fast, middle, slow], [attack('rival', 'p2', frame=6)])

        decision = choose_action(engine.observe('p1', include_memory=True), 'p1', seed='m', temperature=0)

        self.assertEqual(decision.action['card']['instance_id'], 'fast')
        self.assertEqual(decision.details['coverage'], 1.0)
        self.assertEqual(decision.details['options'], ['RIVAL'])
        self.assertFalse(decision.details['engine_evaluated'])

    def test_policy_strategy_skips_the_matrix(self):
        engine = ready_engine([attack('a', 'p1'), attack('b', 'p1', frame=7)], [attack('rival', 'p2')])

        decision = choose_action(
            engine.observe('p1', include_memory=True), 'p1', seed='m', ready_strategy='policy',
        )

        self.assertIsNone(decision.details)

    def test_without_memory_the_policy_decides(self):
        engine = ready_engine([attack('a', 'p1'), attack('b', 'p1', frame=7)], [attack('rival', 'p2')])

        decision = choose_action(engine.observe('p1'), 'p1', seed='m')

        self.assertIsNone(decision.details)


class EngineEvaluatorTests(SimpleTestCase):
    def test_simulated_battle_values_follow_damage(self):
        fast = attack('fast', 'p1', frame=3, damage=500)
        slow = attack('slow', 'p1', frame=9, damage=500)
        guard = defense('guard', 'p1', top='방어')
        rival = attack('rival', 'p2', frame=6, damage=400)
        engine = ready_engine([fast, slow, guard], [rival])
        evaluator = EngineReadyEvaluator(engine, 'p1')
        actions = {
            action['card']['instance_id']: action
            for action in engine.legal_actions('p1') if action['type'] == 'ready_card'
        }
        rival_card = {'instance_id': 'rival', 'code': 'RIVAL'}

        win = evaluator(actions['fast'], rival_card)
        loss = evaluator(actions['slow'], rival_card)
        guarded = evaluator(actions['guard'], rival_card)

        self.assertGreater(win, 0)
        self.assertLess(loss, 0)
        self.assertGreater(guarded, loss)
        self.assertEqual(evaluator.simulations, 3)
        self.assertEqual(evaluator(actions['fast'], rival_card), win)  # 캐시
        self.assertEqual(evaluator.simulations, 3)
        # 원래 엔진은 그대로다.
        self.assertEqual(engine.state['phase'], 'ready')
        self.assertEqual(len(engine._zone('p1', 'hand')), 3)

    def test_face_down_ready_is_replaced_by_each_candidate(self):
        guard_low = defense('guard-low', 'p1', top=None, bottom='방어')
        fast_top = attack('fast-top', 'p1', frame=3, position='상단')
        low = {**attack('rival-low', 'p2', frame=6, position='하단', damage=400), 'guard': '-6'}
        top = attack('rival-top', 'p2', frame=6, position='상단', damage=400)
        engine = ready_engine([guard_low, fast_top], [low, top])
        rival_ready = next(
            item for item in engine.legal_actions('p2')
            if item['type'] == 'ready_card' and item['payload']['card_instance_id'] == 'rival-top'
        )
        engine.submit_action('p2', rival_ready['action_id'], {}, command_id='rival-ready')
        evaluator = EngineReadyEvaluator(engine, 'p1')
        guard_action = next(
            item for item in engine.legal_actions('p1')
            if item['type'] == 'ready_card' and item['card']['instance_id'] == 'guard-low'
        )

        versus_low = evaluator(guard_action, {'instance_id': 'rival-low'})
        versus_top = evaluator(guard_action, {'instance_id': 'rival-top'})

        # 하단 공격이었다면 막고, 상단 공격(실제로 낸 카드)이었다면 맞는다.
        self.assertGreater(versus_low, versus_top)

    def test_unknown_card_returns_none(self):
        engine = ready_engine([attack('a', 'p1')], [attack('rival', 'p2')])
        action = next(item for item in engine.legal_actions('p1') if item['type'] == 'ready_card')

        self.assertIsNone(EngineReadyEvaluator(engine, 'p1')(action, {'instance_id': 'missing'}))

    def test_choose_action_uses_the_engine_evaluator(self):
        engine = ready_engine(
            [attack('fast', 'p1', frame=3), attack('middle', 'p1', frame=5), attack('slow', 'p1', frame=9)],
            [attack('rival', 'p2', frame=6)],
        )
        observation = engine.observe('p1', include_memory=True)

        decision = choose_action(
            observation, 'p1', seed='m', temperature=0,
            ready_evaluator=EngineReadyEvaluator(engine, 'p1'),
        )

        self.assertTrue(decision.details['engine_evaluated'])
        self.assertEqual(decision.action['card']['instance_id'], 'fast')
