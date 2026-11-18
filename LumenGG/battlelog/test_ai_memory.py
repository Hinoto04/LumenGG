"""AI가 기억하는 상대 손패(공개됐던 카드)와 그것을 쓴 배틀 예측."""

from django.test import SimpleTestCase

from .game.ai import choose_action, score_action
from .game.ai_preview import battle_outlook, rival_hand_view, rival_option_view
from .game.engine import AutomaticGameEngine
from .test_automatic_engine import attack, base_state, defense, ruleset


def engine_with(p1_hand, p2_hand, *, p2_list=(), phase='lumen'):
    state = base_state(p1_hand, p2_hand)
    state['players']['p2']['zones']['list'] = list(p2_list)
    state['phase'] = phase
    return AutomaticGameEngine.initialize(state, ruleset(*p1_hand, *p2_hand, *p2_list), seed='memory')


class PublicMemoryTests(SimpleTestCase):
    """상대 손패는 모두 한 번 이상 공개되므로 AI는 손패 전체를 기억한다."""

    def test_ai_remembers_the_whole_hidden_hand_humans_see_nothing_new(self):
        engine = engine_with([attack('mine', 'p1')], [attack('rival-a', 'p2'), attack('rival-b', 'p2', frame=7)])

        human = engine.observe('p1')
        ai_view = engine.observe('p1', include_memory=True)

        self.assertNotIn('memory', human)
        self.assertTrue(all(card.get('hidden') for card in human['state']['players']['p2']['zones']['hand']))
        self.assertEqual(sorted(card['code'] for card in ai_view['memory']['rival_hand']), ['RIVAL-A', 'RIVAL-B'])
        known, unknown = rival_hand_view(ai_view, 'p1')
        self.assertEqual((len(known), unknown), (2, 0))

    def test_face_down_ready_is_only_known_as_a_pool(self):
        engine = engine_with([attack('mine', 'p1')], [attack('rival-a', 'p2'), attack('rival-b', 'p2', frame=7)])
        engine.move_card('rival-b', 'battle', reason='test-ready', face_up=False)

        memory = engine.observe('p1', include_memory=True)['memory']

        # 어느 카드를 냈는지는 모르고, 레디 전 손패 두 장 중 하나라는 것만 안다.
        self.assertEqual(memory['rival_hand'], [])
        self.assertEqual([card['code'] for card in memory['rival_ready_pool']], ['RIVAL-A', 'RIVAL-B'])
        self.assertNotIn('rival_battle', memory)


class BattleOutlookTests(SimpleTestCase):
    def observation(self, my_hand, rival_known, *, hidden=0):
        rival_hand = [{'hidden': True} for _ in range(len(rival_known) + hidden)]
        return {
            'state': {'turn': 2, 'players': {
                'p1': {'hp': 5000, 'fp': 0, 'zones': {'hand': my_hand}},
                'p2': {'hp': 5000, 'fp': 0, 'zones': {'hand': rival_hand}},
            }, 'engine': {}},
            'memory': {'rival_hand': rival_known, 'rival_hand_size': len(rival_hand)},
            'legal_actions': [
                {'type': 'ready_card', 'action_id': f'ready-{card["instance_id"]}', 'card': card}
                for card in my_hand
            ],
        }

    def test_coverage_counts_unknown_cards(self):
        guard = defense('guard-low', 'p1', top=None, bottom='방어')
        rival = {**attack('rival-low', 'p2', frame=3, position='하단'), 'guard': '-6'}
        obs = self.observation([guard], [rival], hidden=1)

        value, coverage = battle_outlook(obs, 'p1', guard)

        self.assertEqual(coverage, 0.5)
        self.assertGreater(value, 0)

    def test_ai_guards_the_attack_it_expects(self):
        slow = attack('slow', 'p1', frame=9, position='상단')
        guard = defense('guard-low', 'p1', top=None, bottom='방어')
        rival = {**attack('rival-low', 'p2', frame=4, position='하단'), 'guard': '-6'}

        known = self.observation([slow, guard], [rival])
        unknown = self.observation([slow, guard], [], hidden=1)

        self.assertEqual(choose_action(known, 'p1', seed='g', temperature=0).action['card']['instance_id'], 'guard-low')
        self.assertEqual(choose_action(unknown, 'p1', seed='g', temperature=0).action['card']['instance_id'], 'slow')

    def test_prediction_weights_the_rivals_likely_card(self):
        # 상대가 낼 법한 빠른 상단 공격을 막는 수비가, 낼 것 같지 않은 하단 공격을 막는 수비보다 낫다.
        guard_top = defense('guard-top', 'p1', top='방어')
        guard_low = defense('guard-low', 'p1', top=None, bottom='방어')
        likely = attack('rival-fast-top', 'p2', frame=3, position='상단', damage=600)
        unlikely = attack('rival-slow-low', 'p2', frame=11, position='하단', damage=100)
        obs = self.observation([guard_top, guard_low], [likely, unlikely])

        top = score_action(obs, 'p1', obs['legal_actions'][0])
        low = score_action(obs, 'p1', obs['legal_actions'][1])

        self.assertGreater(top, low)
