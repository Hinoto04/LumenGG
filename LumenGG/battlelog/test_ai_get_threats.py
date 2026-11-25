"""겟 페이즈 대처: 인쇄 수치로는 막히는 것처럼 보여도 실제로는 필중인 위협에 가드를 가져온다.

사용자 대전 보고(2026-11-25, 루트 수비형):
- 니아가 +6FP로 세츠메이 킥·스플릿 커터를 쥐었는데, 수비가 차징 배리어뿐인 루트가 다운 가드를 가져오지 않았다.
  차징 배리어의 하단 상쇄는 같은 위치(하단) 패를 버려야만 되는데, 예측은 늘 상쇄되는 것으로 봤다.
- 은연이 켜진 비올라의 페인 프리즌(13속도, FP가 유리하지 않으면 판정 전 8 가속)에 다운 가드를 쥐지 않았다.
  예측은 인쇄 속도 13으로만 봐서 루트의 공격이 이긴다고 여겼다.
"""

from django.test import SimpleTestCase

from .game.ai import _counter_bonus, choose_action
from .game.ai_hand import HandValue
from .game.ai_preview import defense_cost_blocked, is_loss, minimum_answer_cards, threat_card
from .test_ai_deck import observation, visible
from .test_automatic_engine import attack, defense


def get_action(card):
    return {
        'type': 'select_get_card', 'action_id': f'get-{card["instance_id"]}',
        'card': {'instance_id': card['instance_id'], 'code': card['code']},
    }


PASS = {'type': 'pass_phase', 'action_id': 'pass'}

HINTS = {
    'start_combo': [], 'grant_catch': [], 'catch_speed': {},
    'speed_boost': {'ST6-009': -8.0},
    'play_counter': {'ST6-009': 'hidden_bond'},
    'defense_costs': {'ST2-010': [{
        'judgment': 'clash', 'where': {'is_technique': True, 'pos': {'path': 'context.opponent_card.pos'}},
    }]},
}


def card(card, code, **fields):
    return {**card, 'code': code, **fields}


def barrier(owner='p1'):
    return card(defense('barrier', owner, top='상쇄', mid='방어', bottom='상쇄'), 'ST2-010')


def down_guard(owner='p1'):
    return card(defense('down-guard', owner, top='회피', bottom='방어'), 'ST1-012')


class SplitCutterTests(SimpleTestCase):
    """니아 +6FP, 세츠메이 킥·스플릿 커터 대 수비가 차징 배리어뿐인 루트."""

    def setUp(self):
        self.rival = {'hand': [
            visible(card(attack('kick', 'p2', frame=8, damage=500, position='중단', hit='콤보', counter='콤보'), 'ST1-018')),
            visible(card(attack('split', 'p2', frame=10, damage=400, position='하단', hit='콤보'), 'AWL-AT-051')),
        ]}
        # 하단 기술이 없는 손패: 차징 배리어의 하단 상쇄 비용을 치를 수 없다.
        self.hand = [
            barrier(),
            attack('cutting', 'p1', frame=5, position='상단'),
            attack('badman', 'p1', frame=7, position='중단'),
            attack('instant', 'p1', frame=8, position='중단'),
            attack('astra', 'p1', frame=8, position='상단'),
            attack('kit', 'p1', frame=8, position='중단'),
        ]
        self.guard = down_guard()
        self.other = attack('grinder', 'p1', frame=13, damage=800, position='상단')
        self.obs = observation(rival=self.rival, my_hand=self.hand, my_list=[self.guard, self.other])
        self.obs['state']['players']['p2']['fp'] = 6
        self.obs['effect_combo_codes'] = HINTS
        self.obs['legal_actions'] = [get_action(self.guard), get_action(self.other), PASS]

    def test_barrier_cannot_pay_the_low_clash(self):
        split = self.rival['hand'][1]

        self.assertTrue(defense_cost_blocked(self.obs, self.hand[0], split, self.hand))
        with_low = [*self.hand, attack('slide', 'p1', frame=6, position='하단')]
        self.assertFalse(defense_cost_blocked(self.obs, self.hand[0], split, with_low))

    def test_split_cutter_stays_a_threat_and_down_guard_answers_it(self):
        threats, covers = minimum_answer_cards(self.obs, 'p1', [self.guard, self.other])

        self.assertEqual([threat['instance_id'] for threat in threats], ['split'])
        self.assertEqual(covers, [{'down-guard'}])
        self.assertEqual(_counter_bonus(self.obs, 'p1', self.obs['legal_actions'], None)['get-down-guard'], 6.0)

    def test_full_hand_takes_the_down_guard_instead_of_passing(self):
        decision = choose_action(self.obs, 'p1', seed='t', temperature=0)

        self.assertEqual(decision.action['action_id'], 'get-down-guard')

    def test_route_defense_profile_also_takes_it(self):
        from pathlib import Path

        from .game.ai_profile import parse_profile_text
        text = (Path(__file__).resolve().parents[2] / 'docs' / 'ROUTE_AI_DEFENSE.toml').read_text(encoding='utf-8')
        decision = choose_action(self.obs, 'p1', seed='t', temperature=0, profile=parse_profile_text(text))

        self.assertEqual(decision.action['action_id'], 'get-down-guard')

    def test_without_the_cost_hint_the_barrier_looked_enough(self):
        self.obs['effect_combo_codes'] = {}

        threats, _covers = minimum_answer_cards(self.obs, 'p1', [self.guard, self.other])
        self.assertEqual(threats, [])


class PainPrisonTests(SimpleTestCase):
    """은연(hidden_bond)이 켜진 비올라의 페인 프리즌: FP가 유리하지 않으면 판정 전 8 가속(13 → 5속도 하단)."""

    def setUp(self):
        self.prison = visible(card(
            attack('prison', 'p2', frame=13, damage=600, position='하단', hit='콤보', counter='콤보'), 'ST6-009',
        ))
        self.hand = [
            attack('cutting', 'p1', frame=5, position='상단'),
            attack('slide', 'p1', frame=6, position='하단'),
            attack('badman', 'p1', frame=7, position='중단'),
            card(defense('offense-break', 'p1', top='방어', mid='방어'), 'DFR-AT-049'),
        ]
        self.guard = down_guard()
        self.other = attack('grinder', 'p1', frame=13, damage=800, position='상단')
        self.obs = observation(rival={'hand': [self.prison]}, my_hand=self.hand, my_list=[self.guard, self.other])
        self.obs['state']['players']['p2']['passive_state'] = {'hidden_bond': {'count': 1}}
        self.obs['effect_combo_codes'] = HINTS
        self.obs['legal_actions'] = [get_action(self.guard), get_action(self.other)]

    def test_prison_is_judged_at_its_boosted_speed(self):
        rival = self.obs['state']['players']['p2']

        self.assertEqual(threat_card(self.obs, rival, self.prison)['frame'], 5)
        rival['passive_state'] = {}
        self.assertIsNone(threat_card(self.obs, rival, self.prison))

    def test_trading_hits_into_a_combo_is_a_loss(self):
        boosted = threat_card(self.obs, self.obs['state']['players']['p2'], self.prison)

        self.assertTrue(is_loss(self.hand[0], boosted))  # 커팅 5속도 대 5속도: 동시 히트지만 상대만 콤보

    def test_down_guard_is_fetched_while_hidden_bond_is_on(self):
        bonus = _counter_bonus(self.obs, 'p1', self.obs['legal_actions'], None)
        self.assertEqual(bonus.get('get-down-guard'), 2.0)
        self.assertEqual(choose_action(self.obs, 'p1', seed='t', temperature=0).action['action_id'], 'get-down-guard')

    def test_no_hidden_bond_means_no_prison_threat(self):
        self.obs['state']['players']['p2']['passive_state'] = {}

        self.assertEqual(_counter_bonus(self.obs, 'p1', self.obs['legal_actions'], None), {})
        self.assertEqual(HandValue(self.obs, 'p1').threats, [])
