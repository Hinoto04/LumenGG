"""캐치: 콤보 시동기(히트 판정이 콤보인 카드)로 캐치해 콤보로 잇는 판단, 루트 예시 프로필의 캐치 속도 규칙."""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from .game.ai import action_features, choose_action
from .game.ai_profile import parse_profile_text
from .test_ai_deck import observation
from .test_automatic_engine import attack

ROUTE_PROFILE = Path(settings.BASE_DIR).parent / 'docs' / 'ROUTE_AI_EXAMPLE.toml'


def catch_action(card):
    return {
        'type': 'play_catch_card', 'action_id': f'catch-{card["instance_id"]}',
        'card': {'instance_id': card['instance_id'], 'code': card['code']},
    }


DECLINE = {'type': 'decline_catch', 'action_id': 'decline'}


class CatchScenario:
    def setUp(self):
        # 루트킷: 8속도 중단, 히트 판정 콤보. 커팅·패니 슬라이드: 이어 칠 공격.
        self.kit = attack('kit', 'p1', code='ST2-004', frame=8, damage=500, position='중단', hit='콤보')
        self.cutting = attack('cutting', 'p1', code='ST1-016', frame=5, hit='2')
        self.slide = attack('slide', 'p1', code='ST2-002', frame=6, position='하단', hit='2')

    def obs(self, hand, catchable, *, my_fp=0, rival_fp=-8):
        result = observation(my_hand=hand)
        result['state']['phase'] = 'battle'
        result['state']['players']['p1']['fp'] = my_fp
        result['state']['players']['p2']['fp'] = rival_fp
        result['legal_actions'] = [catch_action(card) for card in catchable] + [DECLINE]
        return result


class CatchComboTests(CatchScenario, SimpleTestCase):
    def test_combo_starter_with_a_followup_counts(self):
        obs = self.obs([self.kit, self.cutting], [self.kit, self.cutting])

        self.assertEqual(action_features(obs, 'p1', catch_action(self.kit))['catch_combo'], 1.0)
        self.assertEqual(action_features(obs, 'p1', catch_action(self.cutting))['catch_combo'], 0.0)

    def test_combo_starter_without_a_followup_does_not_count(self):
        obs = self.obs([self.kit], [self.kit])

        self.assertEqual(action_features(obs, 'p1', catch_action(self.kit))['catch_combo'], 0.0)

    def test_default_ai_catches_with_the_combo_starter(self):
        obs = self.obs([self.kit, self.cutting, self.slide], [self.kit, self.cutting, self.slide])

        decision = choose_action(obs, 'p1', seed='t', temperature=0)

        self.assertEqual(decision.action['action_id'], 'catch-kit')


class RouteProfileCatchTests(CatchScenario, SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.profile = parse_profile_text(ROUTE_PROFILE.read_text(encoding='utf-8'))

    def choose(self, obs):
        return choose_action(obs, 'p1', seed='t', temperature=0, profile=self.profile).action['action_id']

    def test_rival_minus_8_catches_with_rootkit(self):
        hand = [self.kit, self.cutting, self.slide]

        self.assertEqual(self.choose(self.obs(hand, hand)), 'catch-kit')

    def test_own_plus_8_catches_with_rootkit(self):
        hand = [self.kit, self.cutting, self.slide]

        self.assertEqual(self.choose(self.obs(hand, hand, my_fp=8, rival_fp=0)), 'catch-kit')

    # 저속 캐치를 거절하고 FP 우위를 남기면 상대가 수비로 받아 내고 오히려 루트가 가드당해 캐치당하는 일이
    # 많아(요한전 12판 4승 → 10승), 콤보 시동기가 없거나 이어 칠 공격이 없어도 캐치한다.
    def test_speed_8_without_a_combo_starter_still_catches(self):
        hand = [self.cutting, self.slide]

        self.assertNotEqual(self.choose(self.obs(hand, hand)), 'decline')

    def test_rootkit_alone_still_catches(self):
        self.assertEqual(self.choose(self.obs([self.kit], [self.kit])), 'catch-kit')
