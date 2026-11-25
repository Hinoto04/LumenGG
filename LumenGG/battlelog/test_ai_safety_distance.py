"""세이프티 디스턴스(CB03-AT-034) 사용 타이밍: 상대가 이번 배틀에서 콤보를 낼 수 있을 때만 쓴다."""

from django.test import SimpleTestCase

from .game.ai import choose_action
from .game.ai_decisions import annotate_effect_codes, decide, effect_combo_codes
from .game.ai_preview import rival_combo_threat
from .game.ai_profile import ProfileError, parse_profile_text
from .game.drafts import build_effect_draft
from .game.engine import AutomaticGameEngine
from .test_automatic_engine import attack, base_state, defense, ruleset
from .test_reported_fixes import SAFETY_DISTANCE_TEXT


def battle_observation(mine, theirs, *, rival_hand=(), my_fp=0, their_fp=0, effect_codes=None):
    observation = {
        'state': {'players': {
            'p1': {'hp': 5000, 'fp': my_fp, 'zones': {'battle': [mine], 'hand': [defense('spare', 'p1')]}},
            'p2': {'hp': 5000, 'fp': their_fp, 'zones': {'battle': [theirs], 'hand': list(rival_hand)}},
        }},
        'memory': {},
    }
    if effect_codes is not None:
        observation['effect_combo_codes'] = effect_codes
    return observation


class RivalComboThreatTests(SimpleTestCase):
    def test_combo_judgment_hit_is_a_threat(self):
        slow = attack('slow', 'p1', frame=9)
        fast = attack('fast', 'p2', frame=6, counter='콤보')

        self.assertEqual(rival_combo_threat(battle_observation(slow, fast), 'p1'), 'combo_hit')

    def test_plain_hit_is_not(self):
        slow = attack('slow', 'p1', frame=9)
        fast = attack('fast', 'p2', frame=6, counter='3')

        self.assertIsNone(rival_combo_threat(battle_observation(slow, fast), 'p1'))

    def guarded(self, starter_frame):
        poke = attack('poke', 'p1', frame=4)
        poke['guard'] = '-6'
        starter = attack('starter', 'p2', frame=starter_frame, hit='콤보')
        return battle_observation(poke, defense('block', 'p2'), rival_hand=[starter])

    def test_guard_fp_catch_with_a_combo_starter_is_a_threat(self):
        self.assertEqual(rival_combo_threat(self.guarded(6), 'p1'), 'catch_combo')

    def test_catch_starter_too_slow_is_not(self):
        self.assertIsNone(rival_combo_threat(self.guarded(7), 'p1'))

    def test_effect_cards(self):
        mine = attack('mine', 'p1', frame=5)
        theirs = attack('theirs', 'p2', code='CATCHER', frame=9)
        codes = {'start_combo': ['OPENER'], 'grant_catch': ['CATCHER']}

        self.assertEqual(rival_combo_threat(battle_observation(mine, theirs, effect_codes=codes), 'p1'), 'effect_combo')
        plain = attack('theirs', 'p2', code='PLAIN', frame=9)
        opener = attack('opener', 'p2', code='OPENER', frame=12)
        self.assertIsNone(rival_combo_threat(battle_observation(mine, plain, effect_codes=codes), 'p1'))
        self.assertEqual(
            rival_combo_threat(battle_observation(mine, plain, rival_hand=[opener], effect_codes=codes), 'p1'),
            'effect_combo',
        )

    def test_effect_codes_come_from_the_ruleset(self):
        rules = {'cards': {
            'A': {'effect_definition': {'abilities': [{'effects': [{'op': 'start_combo'}]}]}},
            'B': {'effect_definition': {'abilities': [{'effects': [{'op': 'conditional', 'then': [{'op': 'grant_catch', 'max_speed': 10}]}]}]}},
            'C': {'effect_definition': {'abilities': [{'effects': [{'op': 'deal_damage'}]}]}},
        }}

        self.assertEqual(
            effect_combo_codes(rules), {'start_combo': ['A'], 'grant_catch': ['B'], 'catch_speed': {'B': 10.0}},
        )


class SafetyDistanceDecisionTests(SimpleTestCase):
    ACTION = {'type': 'submit_decision', 'options': [{'id': 'accept'}, {'id': 'decline'}], 'minimum': 1, 'maximum': 1}

    def decide(self, observation):
        observation['pending_decision'] = {'kind': 'optional_effect', 'source': {'ability_id': 'cb03-at-034-n1'}}
        return decide(observation, 'p1', self.ACTION)

    def test_used_only_against_a_combo(self):
        slow = attack('slow', 'p1', frame=9)

        self.assertEqual(self.decide(battle_observation(slow, attack('f', 'p2', frame=6, counter='콤보'))), {'selected': ['accept']})
        self.assertEqual(self.decide(battle_observation(slow, attack('f', 'p2', frame=6, counter='3'))), {'selected': ['decline']})

    def test_profile_condition_must_be_boolean(self):
        parse_profile_text('[[effect]]\nability = "cb03-at-034-n1"\nwhen = { rival_combo_threat = false }\nuse = false\n')
        with self.assertRaises(ProfileError):
            parse_profile_text('[[effect]]\nability = "cb03-at-034-n1"\nwhen = { rival_combo_threat = 1 }\nuse = true\n')

    def engine(self, rival_counter):
        """루멘 존 세이프티 디스턴스, 내 느린 공격 대 상대 빠른 공격(가드 -3)으로 레디까지 진행."""
        mine = attack('mine', 'p1', code='MINE', frame=9)
        spare = defense('spare', 'p1')
        theirs = attack('theirs', 'p2', code='THEIRS', frame=6, counter=rival_counter)
        distance = {
            'instance_id': 'p1-distance', 'kind': 'card', 'owner': 'p1',
            'code': 'CB03-AT-034', 'name': '세이프티 디스턴스', 'type': '특수', 'face_up': True,
        }
        state = base_state([mine, spare], [theirs])
        state['players']['p1']['zones']['lumen'] = [distance]
        rules = ruleset(mine, spare, theirs)
        rules['cards']['THEIRS']['guard'] = '-3'
        rules['cards']['CB03-AT-034'] = {
            'code': 'CB03-AT-034', 'name': '세이프티 디스턴스', 'type': '특수',
            'effect_definition': build_effect_draft('CB03-AT-034', SAFETY_DISTANCE_TEXT),
        }
        engine = AutomaticGameEngine.initialize(state, rules, seed='safety-ai', run_startup=False)

        def act(role, kind, pick=None):
            engine.submit_action(role, next(
                a for a in engine.legal_actions(role)
                if a['type'] == kind and (pick is None or a['payload'].get('card_instance_id') == pick)
            )['action_id'])
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card', 'mine'); act('p2', 'ready_card')
        return engine

    def choice(self, rival_counter):
        engine = self.engine(rival_counter)
        decision = engine.engine_state.get('pending_decision') or {}
        self.assertEqual((decision.get('source') or {}).get('ability_id'), 'cb03-at-034-n1')
        observation = annotate_effect_codes(engine.observe('p1', include_memory=True), engine.ruleset)
        return choose_action(observation, 'p1', seed='t', temperature=0)

    def test_engine_offer_is_accepted_when_the_rival_counter_combos(self):
        self.assertEqual(self.choice('콤보').selections, {'selected': ['accept']})

    def test_engine_offer_is_declined_otherwise(self):
        self.assertEqual(self.choice('3').selections, {'selected': ['decline']})


CHARGING_BARRIER_TEXT = (
    '①상쇄 시, 자신은 패에서 같은 위치 판정 기술 1장을 '
    '버리지 않으면 상쇄할 수 없다.\n'
    '그 후, 상대 기술 데미지-500, 자신은 6FP를 얻는다.\n'
    '②사용 후, 상대가 수비 기술을 사용했다면 이 기술을 '
    '브레이크한다.'
)


class DefenseCostTests(SimpleTestCase):
    """선택형 수비 비용(차징 배리어 상쇄)은 엔진 기본값(거절) 대신 치른다. 거절하면 수비 실패로 그대로 맞는다."""

    def engine(self):
        barrier = defense('barrier', 'p1', top='상쇄', mid='방어', bottom='상쇄')
        barrier['code'] = 'ST2-010'
        spare = attack('spare', 'p1', frame=5, position='상단')
        other = attack('other', 'p1', frame=7, position='중단')
        theirs = attack('theirs', 'p2', frame=5, position='상단')
        state = base_state([barrier, spare, other], [theirs])
        rules = ruleset(barrier, spare, other, theirs)
        rules['cards']['ST2-010']['effect_definition'] = build_effect_draft('ST2-010', CHARGING_BARRIER_TEXT)
        engine = AutomaticGameEngine.initialize(state, rules, seed='barrier-cost', run_startup=False)

        def act(role, kind, pick=None):
            engine.submit_action(role, next(
                a for a in engine.legal_actions(role)
                if a['type'] == kind and (pick is None or a['payload'].get('card_instance_id') == pick)
            )['action_id'])
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card', 'barrier'); act('p2', 'ready_card')
        return engine

    def test_ai_pays_the_clash_cost(self):
        engine = self.engine()
        decision = engine.engine_state.get('pending_decision') or {}
        self.assertEqual(decision.get('kind'), 'defense_cost')
        self.assertEqual(decision.get('default'), ['decline'])

        choice = choose_action(engine.observe('p1', include_memory=True), 'p1', seed='t', temperature=0)
        self.assertEqual(choice.selections, {'selected': ['spare']})
        engine.submit_action('p1', choice.action['action_id'], choice.selections)
        judged = next(event for event in engine.events if event['type'] == 'battle_judged')
        self.assertEqual(judged['payload']['result']['p1'], 'clash')

    def test_profile_rule_can_still_decline(self):
        engine = self.engine()
        profile = parse_profile_text('[[effect]]\ndecision = "defense_cost"\nuse = false\n')

        choice = choose_action(engine.observe('p1', include_memory=True), 'p1', seed='t', temperature=0, profile=profile)
        self.assertEqual(choice.selections, {'selected': ['decline']})
