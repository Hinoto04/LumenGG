"""대전 클라이언트: 효과로 바뀐 카드 수치·판정(stat_changes)."""
from django.test import SimpleTestCase

from .play_card_changes import attach_card_changes, card_changes, collect_card_changes


class StubEngine:
    """card_stat은 수정자 합계를, 인쇄값은 printed에서 돌려주는 최소 엔진."""

    def __init__(self, state, printed, deltas):
        self.state = state
        self.printed = printed
        self.deltas = deltas

    def _printed_card_snapshot(self, card):
        return {**card, **self.printed.get(card['code'], {})}

    def card_stat(self, card, stat, controller, *, include_fp=False):
        return (card.get(stat) or 0) + self.deltas.get((card['instance_id'], stat), 0)


class CardChangesTests(SimpleTestCase):
    def setUp(self):
        self.attack = {'instance_id': 'p1-1', 'code': 'AT-1', 'frame': 5, 'damage': 3, 'pos': '중단', 'special': None}
        self.state = {'players': {
            'p1': {'zones': {'battle': [self.attack], 'hand': [], 'list': []}},
            'p2': {'zones': {'battle': [], 'hand': []}},
        }}
        printed = {'AT-1': {'frame': 5, 'damage': 3, 'pos': '중단', 'special': None}}
        self.engine = StubEngine(self.state, printed, {})

    def test_unchanged_card_has_no_changes(self):
        self.assertEqual(card_changes(self.engine, self.attack, 'p1'), {})
        self.assertEqual(collect_card_changes(self.engine), {})

    def test_modifier_and_overwritten_judgment_are_reported(self):
        self.engine.deltas = {('p1-1', 'frame'): -2, ('p1-1', 'damage'): 1}
        self.attack['pos'] = '상단'
        self.attack['special'] = '가드 불가'
        self.assertEqual(collect_card_changes(self.engine), {'p1-1': {
            'frame': {'base': 5, 'current': 3},
            'damage': {'base': 3, 'current': 4},
            'pos': {'base': '중단', 'current': '상단'},
            'special': {'base': None, 'current': '가드 불가'},
        }})

    def test_defense_card_speed_change_is_not_reported(self):
        """수비 기술은 속도 비교 대상이 아니므로 속도 변화를 표시하지 않는다."""
        defense = {'instance_id': 'p1-2', 'code': 'DF-1', 'type': '수비', 'frame': 0, 'damage': None, 'g_top': '방어'}
        self.state['players']['p1']['zones']['battle'].append(defense)
        self.engine.printed['DF-1'] = {'frame': 0, 'g_top': '방어'}
        self.engine.deltas = {('p1-2', 'frame'): 3}
        defense['g_top'] = '회피'
        self.assertEqual(card_changes(self.engine, defense, 'p1'), {
            'g_top': {'base': '방어', 'current': '회피'},
        })

    def test_attach_only_to_visible_cards(self):
        changes = {'p1-1': {'frame': {'base': 5, 'current': 3}}}
        filtered = {'players': {
            'p1': {'zones': {'battle': [{'instance_id': 'p1-1', 'hidden': False}]}},
            'p2': {'zones': {'battle': [{'hidden': True, 'name': ''}]}},
        }}
        attach_card_changes(filtered, changes)
        self.assertEqual(filtered['players']['p1']['zones']['battle'][0]['stat_changes'], changes['p1-1'])
        self.assertNotIn('stat_changes', filtered['players']['p2']['zones']['battle'][0])
