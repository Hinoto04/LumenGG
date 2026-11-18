"""상대가 이득 프레임일 때를 대비한 가드 획득, 방어 불가 기술의 예측."""

from django.test import SimpleTestCase

from .game.ai import _counter_bonus, guard_targets
from .game.ai_preview import minimum_answer_cards, preview_battle
from .game.ai_profile import normalize_profile
from .game.engine import AutomaticGameEngine, prevents_opponent_guard
from .test_ai_deck import observation, visible
from .test_automatic_engine import attack, base_state, defense, ruleset

UNGUARDABLE = {
    'schema_version': 1, 'reviewed': True,
    'abilities': [{
        'id': 'x-function', 'kind': 'function', 'mode': 'continuous', 'timing': 'function',
        'effects': [{'op': 'prevent', 'kind': 'guard', 'player': {'opponent': True}, 'duration': 'continuous'}],
    }],
}


def get_action(card):
    return {'type': 'select_get_card', 'action_id': f'get-{card["instance_id"]}', 'card': {'instance_id': card['instance_id'], 'code': card['code']}}


class UnguardableTests(SimpleTestCase):
    def test_only_unconditional_guard_prevention_counts(self):
        conditional = {'abilities': [{**UNGUARDABLE['abilities'][0], 'condition': {'op': 'equals', 'left': 'context.controller_fp', 'right': 2}}]}
        own_guard = {'abilities': [{**UNGUARDABLE['abilities'][0], 'effects': [{'op': 'prevent', 'kind': 'guard', 'player': {'controller': True}}]}]}

        self.assertTrue(prevents_opponent_guard(UNGUARDABLE))
        self.assertFalse(prevents_opponent_guard(conditional))
        self.assertFalse(prevents_opponent_guard(own_guard))
        self.assertFalse(prevents_opponent_guard(None))

    def test_observation_flags_unguardable_cards(self):
        grab = attack('grab', 'p2', position='상단', special='그랩')
        rules = ruleset(grab, attack('plain', 'p1'))
        rules['cards']['GRAB']['effect_definition'] = UNGUARDABLE
        engine = AutomaticGameEngine.initialize(base_state([attack('plain', 'p1')], [grab]), rules, seed='u')

        own = engine.observe('p2')
        rival = engine.observe('p1', include_memory=True)

        self.assertTrue(own['state']['players']['p2']['zones']['hand'][0]['unguardable'])
        self.assertNotIn('unguardable', own['state']['players']['p1']['zones']['hand'][0])
        self.assertTrue(all(card.get('unguardable') for card in rival['memory']['rival_hand']))

    def test_guard_fails_but_dodge_still_works(self):
        grab = {**attack('grab', 'p2', position='상단', special='그랩'), 'unguardable': True}

        self.assertEqual(preview_battle(defense('wall', 'p1', top='방어'), grab), ('failed_defense', 'hit'))
        self.assertEqual(preview_battle(defense('duck', 'p1', top='회피'), grab), ('dodge', 'opponent_dodge'))
        self.assertEqual(preview_battle(defense('wall', 'p1', top='방어'), {**grab, 'unguardable': False}), ('guard', 'guarded'))


class GuardGetTests(SimpleTestCase):
    def setUp(self):
        # 손패: 빠른 상단 공격, 상·중단 가드. 상대: 빠른 하단 공격. 리스트: 하단 가드, 공격.
        self.low = visible(attack('low', 'p2', frame=5, position='하단'))
        self.fast = attack('fast', 'p1', frame=4)
        self.high_guard = defense('high-guard', 'p1', top='방어', mid='방어')
        self.low_guard = defense('low-guard', 'p1', top='회피', bottom='방어')
        self.other = attack('other', 'p1', frame=6)
        self.obs = observation(
            rival={'hand': [self.low]}, my_hand=[self.fast, self.high_guard], my_list=[self.low_guard, self.other],
        )
        self.obs['state']['players']['p2']['fp'] = 1  # 상대가 이득 프레임
        self.candidates = [get_action(self.low_guard), get_action(self.other)]

    def test_fast_attack_answers_at_even_fp_but_not_under_a_rival_lead(self):
        cards = [self.low_guard, self.other]
        self.obs['state']['players']['p2']['fp'] = 0

        self.assertEqual(minimum_answer_cards(self.obs, 'p1', cards), ([], []))
        _threats, covers = minimum_answer_cards(self.obs, 'p1', cards, rival_fp_lead=3)
        self.assertEqual(covers, [{'low-guard'}])

    def test_guard_bonus_goes_to_the_missing_guard(self):
        self.assertEqual(guard_targets(self.obs, 'p1', self.candidates), {'low-guard'})
        self.assertEqual(_counter_bonus(self.obs, 'p1', self.candidates, None), {'get-low-guard': 6.0})

    def test_profile_can_tune_or_turn_off_the_guard_bonus(self):
        tuned = normalize_profile({'counter': {'guard_bonus': 4, 'guard_fp': 2}})
        off = normalize_profile({'counter': {'guard_bonus': 0}})

        self.assertEqual(_counter_bonus(self.obs, 'p1', self.candidates, tuned), {'get-low-guard': 4.0})
        self.assertEqual(guard_targets(self.obs, 'p1', self.candidates, off), set())

    def test_pinned_profile_without_the_new_keys_uses_defaults(self):
        old = {'counter': {'enabled': True, 'bonus': 2.0, 'scope': 'hand'}}

        self.assertEqual(_counter_bonus(self.obs, 'p1', self.candidates, old), {'get-low-guard': 6.0})

    def test_no_guard_bonus_while_even_or_ahead(self):
        for fp in (0, 2):
            self.obs['state']['players']['p1']['fp'] = fp
            self.obs['state']['players']['p2']['fp'] = 0
            self.assertEqual(guard_targets(self.obs, 'p1', self.candidates), set())
