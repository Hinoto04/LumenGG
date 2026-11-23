"""겟 페이즈: 상대 카드에 강한 패 유지, 가득 찬 패의 교체·패스, 교체 후 버릴 카드."""

from django.test import SimpleTestCase

from .game.ai import _get_plan, choose_action
from .game.ai_hand import HandValue
from .game.ai_profile import ProfileError, normalize_profile
from .test_ai_deck import observation, visible
from .test_automatic_engine import attack, defense


def get_action(card):
    return {
        'type': 'select_get_card', 'action_id': f'get-{card["instance_id"]}',
        'card': {'instance_id': card['instance_id'], 'code': card['code']},
    }


PASS = {'type': 'pass_phase', 'action_id': 'pass'}


def discard_action(cards):
    return {
        'type': 'submit_decision', 'action_id': 'discard', 'minimum': 1, 'maximum': 1,
        'options': [{'id': card['instance_id']} for card in cards],
    }


class GetPhaseTests(SimpleTestCase):
    def setUp(self):
        # 상대 손패: 하단 공격, 상단 공격. 내 패: 상단만 막는 가드 둘, 느린 공격.
        self.rival = {'hand': [
            visible(attack('r-low', 'p2', frame=5, position='하단')),
            visible(attack('r-high', 'p2', frame=5)),
        ]}
        self.hand = [
            defense('high-1', 'p1', top='방어'),
            defense('high-2', 'p1', top='방어'),
            attack('slow', 'p1', frame=9),
        ]
        self.low_guard = defense('low-guard', 'p1', top='회피', bottom='방어')
        self.high_3 = {**defense('high-3', 'p1', top='방어'), 'code': 'HIGH-1'}

    def obs(self, my_list, *, full=True, rival=None):
        result = observation(rival=self.rival if rival is None else rival, my_hand=self.hand, my_list=my_list)
        result['state']['phase'] = 'get'
        result['legal_actions'] = [get_action(card) for card in my_list] + ([PASS] if full else [])
        return result

    def choose(self, obs, profile=None):
        return choose_action(obs, 'p1', seed='t', temperature=0, profile=profile)

    def test_full_hand_takes_the_missing_answer(self):
        decision = self.choose(self.obs([self.low_guard, self.high_3]))

        self.assertEqual(decision.action['action_id'], 'get-low-guard')

    def test_full_hand_passes_when_no_swap_helps(self):
        # 리스트에는 패의 느린 공격보다 나을 것 없는 카드뿐이다.
        obs = self.obs([attack('slower', 'p1', frame=12), attack('slowest', 'p1', frame=14)])

        decision = self.choose(obs)

        self.assertEqual(decision.action['type'], 'pass_phase')
        self.assertTrue(all(gain < 0.1 for gain in decision.details['get_gains'].values()))

    def test_open_hand_always_takes_a_card(self):
        obs = self.obs([self.high_3, attack('slower', 'p1', frame=12)], full=False)

        self.assertEqual(self.choose(obs).action['type'], 'select_get_card')

    def test_full_hand_with_no_known_rival_cards_passes(self):
        obs = self.obs([self.low_guard], rival={'hand': [{'instance_id': 'x', 'hidden': True}]})

        self.assertEqual(self.choose(obs).action['type'], 'pass_phase')

    def test_discard_throws_back_the_weakest_card_not_the_new_one(self):
        # 하단 가드를 가져온 뒤: 두 공격 모두에 지는 느린 공격을 돌려놓는다.
        self.hand = [*self.hand, self.low_guard]
        obs = observation(rival=self.rival, my_hand=self.hand)
        obs['pending_decision'] = {'kind': 'hand_limit_discard'}
        obs['legal_actions'] = [discard_action(self.hand)]

        selected = self.choose(obs).selections['selected']

        self.assertEqual(selected, ['slow'])

    def test_profile_rule_still_decides_the_discard(self):
        self.hand = [*self.hand, self.low_guard]
        obs = observation(rival=self.rival, my_hand=self.hand)
        obs['pending_decision'] = {'kind': 'hand_limit_discard'}
        obs['legal_actions'] = [discard_action(self.hand)]
        profile = normalize_profile({'effect': [{'decision': 'hand_limit_discard', 'pick': ['LOW-GUARD']}]})

        self.assertEqual(self.choose(obs, profile).selections['selected'], ['low-guard'])

    def test_rival_list_counts_at_half_weight(self):
        value = HandValue(observation(rival={'list': [attack('r-low', 'p2', position='하단')]}), 'p1')

        self.assertEqual(value.total, 0.5)
        self.assertTrue(value.known)

    def test_hand_keeps_a_few_strong_cards_not_one_answer(self):
        # 한 장으로 모든 상대 카드에 대처돼도, 강한 카드를 더 쥔 패가 낫다.
        fast = attack('fast', 'p1', frame=3)
        value = HandValue(observation(rival=self.rival), 'p1')

        self.assertGreater(value.value([fast, {**fast, 'instance_id': 'fast-2'}]), value.value([fast, self.hand[2]]))

    def test_profile_can_turn_the_hand_plan_off(self):
        profile = normalize_profile({'hand': {'enabled': False}})
        obs = self.obs([self.high_3, attack('slower', 'p1', frame=12)])

        self.assertEqual(_get_plan(obs, 'p1', obs['legal_actions'], profile), {'bonus': {}, 'pass': None, 'gains': {}})
        self.assertEqual(self.choose(obs, profile).action['type'], 'select_get_card')

    def test_profile_settings_are_checked(self):
        tuned = normalize_profile({'hand': {'bonus': 4, 'keep': 2, 'swap_margin': 0.3}})

        self.assertEqual(tuned['hand'], {'enabled': True, 'bonus': 4.0, 'keep': 2, 'swap_margin': 0.3})
        with self.assertRaises(ProfileError):
            normalize_profile({'hand': {'keep': 0}})
        with self.assertRaises(ProfileError):
            normalize_profile({'hand': {'swap_margin': -1}})
