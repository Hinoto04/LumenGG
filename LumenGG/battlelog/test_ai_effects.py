"""AI의 선택형 효과·패시브 결정: [[effect]] 규칙, 캐릭터별 기본 규칙, 엔진 결정 출처."""

from django.test import SimpleTestCase

from .game.ai import choose_action
from .game.ai_decisions import DEFAULT_EFFECT_RULES, decide
from .game.ai_profile import ProfileError, normalize_profile, parse_profile_text
from .game.drafts import build_effect_draft
from .game.engine import AutomaticGameEngine
from .test_automatic_engine import attack, base_state, defense, ruleset

CHARGE_TEXT = (
    '①루멘 페이즈 시 이번 턴까지 자신에게 [[state:charge]]상태를 부여할 수 있다.\n'
    '②[[state:charge]]: 자신은 레디 페이즈에 공격 기술만 레디한다.\n'
    '레디한 기술 사용 시, 2속도가 느려지며 기술 데미지+200\n'
    '③[[state:charge]]상태 해제 시, 다음 자신 루멘 페이즈를 스킵한다.'
)
LEGION_TEXT = (
    '①게임 중, 자신에게 [[state:saintess]]를 부여한다.\n'
    '②루멘 페이즈 시, 자신은 [[state:guardian]], [[state:assassin]], [[state:paladin]] 중 하나의 레기온을 축복한다.\n'
    ' 이번 턴 종료까지 축복한 레기온의 효과와 상태를 적용한다.\n'
    ' -[[state:guardian]]: 방어 및 상쇄 시, 2FP를 얻는다.\n'
    ' -[[state:assassin]]: 카운터 시, 상대에게 100데미지를 준다.\n'
    ' -[[state:paladin]]: 1턴당 1번 콤보 시, 자신의 리스트에서 기술 1장을 획득한다.\n'
    ' 축복한 레기온은 다음 턴, 축복할 수 없다.'
)


def observation(kind, *, ability='some-ability', card='SOME-CARD', hand=(), lumen=(),
                passive_state=None, my_hp=5000, rival_hp=5000):
    return {
        'pending_decision': {'kind': kind, 'source': {'ability_id': ability, 'card_code': card}, 'default': []},
        'state': {'turn': 2, 'players': {
            'p1': {'hp': my_hp, 'fp': 0, 'passive_state': passive_state or {},
                   'zones': {'hand': list(hand), 'lumen': list(lumen), 'list': []}},
            'p2': {'hp': rival_hp, 'fp': 0, 'zones': {}},
        }, 'engine': {}},
    }


def decision_action(option_ids, minimum=1, maximum=1):
    return {
        'type': 'submit_decision', 'action_id': 'decide',
        'options': [{'id': option_id, 'label': option_id} for option_id in option_ids],
        'minimum': minimum, 'maximum': maximum,
    }


def card(instance_id, code, kind='공격'):
    return {'instance_id': instance_id, 'code': code, 'type': kind, 'owner': 'p1'}


class EffectRuleTextTests(SimpleTestCase):
    def test_effect_rules_parse(self):
        profile = parse_profile_text('''
[effects]
default_use = false
[[effect]]
name = "예지 카운터 2개 이상이면 사용"
ability = "crs-ps-002-n1"
when = { my_counter_min = { foresight = 2 } }
use = true
[[effect]]
card = ["X-1", "X-2"]
decision = "effect_choice"
pick = ["A", "B"]
avoid = "C"
count = "max"
''')

        first, second = profile['effects']
        self.assertEqual(first['when'], {'my_counter_min': {'foresight': 2.0}})
        self.assertTrue(first['use'])
        self.assertEqual(second['card'], ['X-1', 'X-2'])
        self.assertEqual(second['decision'], ['effect_choice'])
        self.assertEqual(second['avoid'], ['C'])
        self.assertFalse(profile['effect_settings']['default_use'])

    def test_effect_rule_errors(self):
        with self.assertRaises(ProfileError) as caught:
            parse_profile_text('''
[[effect]]
use = "yes"
[[effect]]
ability = "a"
decision = "mystery"
count = "all"
[[effect]]
ability = "b"
''')

        message = str(caught.exception)
        self.assertIn('ability, card, decision 중 하나는', message)
        self.assertIn('use는 true 또는 false', message)
        self.assertIn('알 수 없는 결정 종류입니다: mystery', message)
        self.assertIn('count는 "max", "min"', message)
        self.assertIn('use, choose, pick, avoid, count, amount 중 하나는', message)

    def test_built_in_defaults_cover_every_passive_with_a_choice(self):
        abilities = {ability for rule in DEFAULT_EFFECT_RULES for ability in rule['ability']}

        self.assertEqual(abilities, {
            'st2-ps1-charge-enter', 'crs-ps-002-n1', 'dfr-ps-001-n1', 'lmi-ps-001-bless',
            'pmp-ps-001-n2', 'st1-ps1-over-limit-recovery', 'st5-ps1-intimidation-enter',
            'cb01-ps-001-n3', 'cb04-ps-001-n2',
            # 패시브는 아니지만 사용 타이밍이 중요한 공용 특수 카드(세이프티 디스턴스)
            'cb03-at-034-n1',
        })


class EffectDecisionTests(SimpleTestCase):
    def test_optional_effects_are_used_unless_a_rule_or_setting_says_no(self):
        action = decision_action(['accept', 'decline'])
        obs = observation('optional_effect')

        self.assertEqual(decide(obs, 'p1', action), {'selected': ['accept']})
        self.assertEqual(
            decide(obs, 'p1', action, normalize_profile({'effects': {'default_use': False}})),
            {'selected': ['decline']},
        )
        profile = normalize_profile({'effect': [{'ability': 'some-ability', 'use': False}]})
        self.assertEqual(decide(obs, 'p1', action, profile), {'selected': ['decline']})

    def test_deck_rules_win_over_built_in_defaults(self):
        action = decision_action(['accept', 'decline'])
        obs = observation('optional_effect', ability='st2-ps1-charge-enter', card='ST2-PS1')
        always = normalize_profile({'effect': [{'ability': 'st2-ps1-charge-enter', 'use': True}]})

        self.assertEqual(decide(obs, 'p1', action), {'selected': ['decline']})  # 기본: 공격 2장 미만
        self.assertEqual(decide(obs, 'p1', action, always), {'selected': ['accept']})

    def test_conditions_on_hand_lumen_and_counters(self):
        action = decision_action(['accept', 'decline'])
        profile = normalize_profile({'effect': [
            {'ability': 'x', 'when': {'my_counter_min': {'foresight': 2}, 'my_lumen_max': 3}, 'use': True},
            {'ability': 'x', 'use': False},
        ]})

        rich = observation('optional_effect', ability='x', passive_state={'foresight': {'count': 2}})
        poor = observation('optional_effect', ability='x', passive_state={'foresight': {'count': 1}})
        crowded = observation(
            'optional_effect', ability='x', passive_state={'foresight': {'count': 3}},
            lumen=[card(f'l{i}', 'L') for i in range(4)],
        )

        self.assertEqual(decide(rich, 'p1', action, profile), {'selected': ['accept']})
        self.assertEqual(decide(poor, 'p1', action, profile), {'selected': ['decline']})
        self.assertEqual(decide(crowded, 'p1', action, profile), {'selected': ['decline']})

    def test_branch_choice_follows_preference_and_skips_unavailable(self):
        profile = normalize_profile({'effect': [{'ability': 'x', 'choose': ['paladin', 'guardian']}]})
        obs = observation('effect_branch', ability='x')

        self.assertEqual(decide(obs, 'p1', decision_action(['guardian', 'assassin', 'paladin']), profile),
                         {'selected': ['paladin']})
        self.assertEqual(decide(obs, 'p1', decision_action(['guardian', 'assassin']), profile),
                         {'selected': ['guardian']})

    def test_card_choice_picks_avoids_and_counts(self):
        hand = [card('h1', 'A'), card('h2', 'B'), card('h3', 'C'), card('h4', 'D')]
        obs = observation('effect_choice', ability='x', hand=hand)
        action = decision_action(['h1', 'h2', 'h3', 'h4'], minimum=1, maximum=3)

        picked = decide(obs, 'p1', action, normalize_profile({'effect': [{'ability': 'x', 'pick': ['C', 'A']}]}),
                        fallback={'selected': ['h1']})
        maxed = decide(obs, 'p1', action, normalize_profile({'effect': [{'ability': 'x', 'count': 'max', 'avoid': ['A']}]}),
                       fallback={'selected': ['h1']})
        none = decide(observation('effect_choice', ability='x', hand=hand),
                      'p1', decision_action(['h1', 'h2'], minimum=0, maximum=2),
                      normalize_profile({'effect': [{'ability': 'x', 'use': False}]}))

        self.assertEqual(picked, {'selected': ['h3', 'h1']})
        self.assertEqual(len(maxed['selected']), 3)
        self.assertNotIn('h1', maxed['selected'])
        self.assertEqual(none, {'selected': []})

    def test_amount(self):
        obs = observation('effect_amount', ability='x')
        action = decision_action(['0', '1', '2', '3'])

        for value, expected in (('min', '0'), ('max', '3'), (2, '2')):
            profile = normalize_profile({'effect': [{'ability': 'x', 'amount': value}]})
            self.assertEqual(decide(obs, 'p1', action, profile), {'selected': [expected]})

    def test_no_rule_keeps_the_engine_default(self):
        obs = observation('effect_choice', ability='unknown')
        fallback = {'selected': ['h2']}

        self.assertIs(decide(obs, 'p1', decision_action(['h1', 'h2']), fallback=fallback), fallback)


class PassiveEngineTests(SimpleTestCase):
    def passive_engine(self, code, text, hand, *, hp=5000, rival_hp=5000, rival_frame=None):
        passive = {
            'instance_id': f'{code.lower()}-passive', 'kind': 'card', 'owner': 'p1', 'code': code,
            'name': code, 'type': '특성', 'face_up': True,
        }
        rival = attack('rival', 'p2') if rival_frame is None else attack('rival', 'p2', frame=rival_frame)
        state = base_state(hand, [rival])
        state['players']['p1']['hp'] = hp
        state['players']['p2']['hp'] = rival_hp
        state['players']['p1']['zones']['passive'] = [passive]
        rules = ruleset(*hand, rival, passive)
        rules['cards'][code]['effect_definition'] = build_effect_draft(code, text)
        return AutomaticGameEngine.initialize(state, rules, seed=f'passive-{code}')

    def ai_answer(self, engine, *, memory=False):
        obs = engine.observe('p1', include_memory=memory)
        decision = choose_action(obs, 'p1', seed='passive')
        return obs['pending_decision'], decision

    def test_decision_names_its_source_only_for_the_owner(self):
        engine = self.passive_engine('ST2-PS1', CHARGE_TEXT, [attack('a1', 'p1')])

        mine = engine.observe('p1')['pending_decision']
        theirs = engine.observe('p2')['pending_decision']

        self.assertEqual(mine['source'], {'ability_id': 'st2-ps1-charge-enter', 'card_code': 'ST2-PS1'})
        self.assertNotIn('source', theirs)

    def test_route_charge_is_used_only_with_two_attacks(self):
        two = self.passive_engine('ST2-PS1', CHARGE_TEXT, [attack('a1', 'p1'), attack('a2', 'p1')])
        one = self.passive_engine('ST2-PS1', CHARGE_TEXT, [attack('a1', 'p1'), defense('d1', 'p1')])

        self.assertEqual(self.ai_answer(two)[1].selections, {'selected': ['accept']})
        self.assertEqual(self.ai_answer(one)[1].selections, {'selected': ['decline']})

    def test_route_charge_waits_when_slowing_down_loses_the_speed_race(self):
        hand = [attack('a1', 'p1', frame=5), attack('a2', 'p1', frame=7)]
        fast_rival = self.passive_engine('ST2-PS1', CHARGE_TEXT, hand, rival_frame=5)
        slow_rival = self.passive_engine('ST2-PS1', CHARGE_TEXT, hand, rival_frame=9)

        self.assertEqual(self.ai_answer(fast_rival, memory=True)[1].selections, {'selected': ['decline']})
        self.assertEqual(self.ai_answer(slow_rival, memory=True)[1].selections, {'selected': ['accept']})

    def test_rita_blesses_assassin_by_default_and_guardian_when_behind(self):
        hand = [attack('a1', 'p1'), attack('a2', 'p1')]
        ahead = self.passive_engine('LMI-PS-001', LEGION_TEXT, hand)
        behind = self.passive_engine('LMI-PS-001', LEGION_TEXT, hand, hp=2000, rival_hp=4000)

        pending, decision = self.ai_answer(ahead)
        self.assertEqual(pending['kind'], 'effect_branch')
        self.assertEqual(pending['source']['ability_id'], 'lmi-ps-001-bless')
        self.assertEqual(decision.selections, {'selected': ['assassin']})
        self.assertEqual(self.ai_answer(behind)[1].selections, {'selected': ['guardian']})


class RouteExampleProfileTests(SimpleTestCase):
    """docs/ROUTE_AI_EXAMPLE.toml(평문 예시를 옮긴 설정)이 계속 유효한지."""

    def profile(self):
        from pathlib import Path
        text = (Path(__file__).resolve().parents[2] / 'docs' / 'ROUTE_AI_EXAMPLE.toml').read_text(encoding='utf-8')
        return parse_profile_text(text)

    def test_example_parses(self):
        profile = self.profile()

        self.assertEqual(len(profile['situations']), 7)
        self.assertEqual(len(profile['combos']), 2)
        self.assertEqual(profile['effects'][0]['when'], {'fp_lead_min': 4.0})

    def test_fp_lead_switches_charge_and_preferences(self):
        profile = self.profile()
        action = decision_action(['accept', 'decline'])

        def obs(my_fp, rival_fp):
            result = observation('optional_effect', ability='st2-ps1-charge-enter', card='ST2-PS1',
                                 hand=[card('a', 'A'), card('b', 'B')])
            result['state']['players']['p1']['fp'] = my_fp
            result['state']['players']['p2']['fp'] = rival_fp
            return result

        self.assertEqual(decide(obs(5, 1), 'p1', action, profile), {'selected': ['accept']})
        self.assertEqual(decide(obs(3, 1), 'p1', action, profile), {'selected': ['decline']})


class RouteAttackProfileTests(SimpleTestCase):
    """docs/ROUTE_AI_ATTACK.toml(커뮤니티 공략을 옮긴 루트 공격형 설정)이 계속 유효한지."""

    def profile(self):
        from pathlib import Path
        text = (Path(__file__).resolve().parents[2] / 'docs' / 'ROUTE_AI_ATTACK.toml').read_text(encoding='utf-8')
        return parse_profile_text(text)

    def test_attack_profile_parses_without_the_banned_pair(self):
        profile = self.profile()
        codes = {code for situation in profile['situations'] for code in (situation.get('prefer') or {})}

        # 금지제한: 파워풀 스윕(UNC-AT-016)과 차징 배리어(ST2-010)는 함께 넣을 수 없다. 공격형은 스윕을 쓴다.
        self.assertIn('UNC-AT-016', codes)
        self.assertNotIn('ST2-010', codes)
        self.assertEqual(len(profile['combos']), 3)
        self.assertEqual(
            [rule['use'] for rule in profile['effects'] if rule.get('ability') == ['st2-ps1-charge-enter']],
            [True, False],
        )


class RouteDefenseProfileTests(SimpleTestCase):
    """docs/ROUTE_AI_DEFENSE.toml(커뮤니티 공략을 옮긴 루트 수비형 설정)이 계속 유효한지."""

    def test_defense_profile_parses_without_the_banned_pair(self):
        from pathlib import Path
        text = (Path(__file__).resolve().parents[2] / 'docs' / 'ROUTE_AI_DEFENSE.toml').read_text(encoding='utf-8')
        profile = parse_profile_text(text)
        codes = {code for situation in profile['situations'] for code in (situation.get('prefer') or {})}

        # 금지제한: 수비형은 차징 배리어(ST2-010)를 쓰고 파워풀 스윕(UNC-AT-016)은 뺀다.
        self.assertIn('ST2-010', codes)
        self.assertNotIn('UNC-AT-016', codes)
        guard_get = next(s for s in profile['situations'] if s['when'].get('hand_defense_max') == 1)
        self.assertEqual(guard_get['when']['action'], ['get'])
