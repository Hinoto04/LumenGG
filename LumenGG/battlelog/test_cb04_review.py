"""CB04 카드별 자동 검토 시나리오(review_cb04)의 게시 요건 테스트."""

import copy

from django.test import SimpleTestCase

from .game.drafts_cb04 import BUILDERS, build_cb04_definition
from .game.review import review_automatic_definition
from .game.schema import validate_effect_definition


def snapshot(code):
    type_ = '공격'
    if code in ('CB04-AT-001', 'CB04-AT-013', 'CB04-AT-037'):
        type_ = '수비'
    elif code == 'CB04-PS-001':
        type_ = '특성'
    elif code == 'CB04-AT-034':
        type_ = '특수'
    elif code == 'CB04-TK-001':
        type_ = '토큰'
    names = {'CB04-AT-034': 'OPTION: 팡 하켄'}
    return {'code': code, 'name': names.get(code, code), 'type': type_, 'frame': 9, 'damage': 400}


class CB04ReviewTests(SimpleTestCase):
    def test_every_cb04_definition_passes_with_publishable_evidence(self):
        for code in BUILDERS:
            with self.subTest(code=code):
                definition = build_cb04_definition(code)
                result = review_automatic_definition(
                    definition, card_has_text=True, card_snapshot=snapshot(code),
                )
                self.assertTrue(result.passed, result.as_dict())
                published = copy.deepcopy(definition)
                published.update({'reviewed': True, 'draft': False, 'review_evidence': result.as_dict()})
                for ability in published['abilities']:
                    ability['draft'] = False
                issues = [
                    issue for issue in validate_effect_definition(
                        published, require_coverage=True, card_has_text=True,
                    )
                    if issue.path.startswith('$.review_evidence') or issue.code == 'missing_ability_review'
                ]
                self.assertEqual(issues, [])

    def test_changed_definition_is_not_auto_approved(self):
        definition = build_cb04_definition('CB04-AT-013')
        definition['abilities'][0]['effects'][0]['amount'] = -6
        result = review_automatic_definition(
            definition, card_has_text=True, card_snapshot=snapshot('CB04-AT-013'),
        )
        self.assertFalse(result.passed)

    def test_negative_scenarios_detect_wrong_behaviour(self):
        # 아크틱 자벨린 ①이 소유자 조건 없이 모든 공격 기술을 막으면 실패해야 한다(Q-AUTO-015).
        from .game import review_cb04

        definition = build_cb04_definition('CB04-AT-010')
        definition['abilities'][0]['effects'][0].pop('condition')
        runner, cases = review_cb04.CASES['cb04-at-010-n1']
        scenarios = review_cb04._scenarios(runner, definition, snapshot('CB04-AT-010'), cases)
        self.assertFalse(all(item['passed'] for item in scenarios))

    def test_frenzy_slice_lock_targets_only_opponent(self):
        # 프렌지 슬라이스 ②가 자신의 특수 기술을 막으면 검토가 실패해야 한다.
        from .game import review_cb04

        definition = build_cb04_definition('CB04-AT-040')
        definition['abilities'][1]['effects'][0]['player'] = {'controller': True}
        runner, cases = review_cb04.CASES['cb04-at-040-n2']
        scenarios = review_cb04._scenarios(runner, definition, snapshot('CB04-AT-040'), cases)
        self.assertFalse(all(item['passed'] for item in scenarios))


class CardEffectLockTests(SimpleTestCase):
    """prevent kind card_effects: 잠긴 특수 기술의 번호 효과는 유발되지 않는다."""

    def test_locked_special_technique_does_not_trigger_until_lock_ends(self):
        from .game import review_cb04

        owner, other = 'p1', 'p2'
        special_definition = {
            'schema_version': 1, 'reviewed': True, 'no_effect': False,
            'abilities': [{
                'id': 'review-special-n1', 'kind': 'effect', 'mode': 'mandatory',
                'timing': 'lumen', 'visibility': 'public', 'draft_compiled': True,
                'trigger': {'event': 'turn_start'}, 'active_zones': ['lumen'],
                'effects': [{'op': 'change_fp', 'player': {'controller': True}, 'amount': 1}],
            }],
        }
        source = review_cb04._source(snapshot('CB04-AT-040'), 'CB04-AT-040', owner)
        special = review_cb04._card(f'{other}-special', other, code='REVIEW-LOCK-SPECIAL', type_='특수')
        engine = review_cb04._engine(
            build_cb04_definition('CB04-AT-040'), source,
            {owner: {'battle': [source]}, other: {'lumen': [special]}},
            seed='card-effect-lock', definitions={'REVIEW-LOCK-SPECIAL': special_definition},
        )

        def lumen_fp_gain():
            before = engine.state['players'][other]['fp']
            engine._fire('turn_start', {'controller': other})
            review_cb04._resolve(engine)
            return engine.state['players'][other]['fp'] - before

        self.assertEqual(lumen_fp_gain(), 1)
        review_cb04._fire(engine, 'hit', source)
        self.assertEqual(lumen_fp_gain(), 0)
        for _ in range(2):
            engine.state['turn'] += 1
            engine._expire_modifiers('turn')
        self.assertFalse(engine._find_card(special['instance_id']).get('numbered_effects_negated'))
        self.assertEqual(lumen_fp_gain(), 1)
