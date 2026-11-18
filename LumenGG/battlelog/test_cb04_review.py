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
