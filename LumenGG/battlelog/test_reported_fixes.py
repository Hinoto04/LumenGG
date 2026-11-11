"""덱 관리·자동 시뮬레이터 제보(2026-11) 회귀 테스트."""
import copy
from types import SimpleNamespace

from django.test import SimpleTestCase

from deck.game_validation import validate_automatic_deck

from .automatic_services import _remove_game_start_counter_grants
from .game.engine import AutomaticGameEngine
from .test_automatic_engine import attack, base_state, defense, ruleset


class OpeningReviewTests(SimpleTestCase):
    """게임 시작 효과 전에 양쪽이 서로의 시작 패를 확인한다."""

    def setUp(self):
        self.p1_card = attack('review-p1', 'p1', code='REVIEW-P1')
        self.p2_card = defense('review-p2', 'p2')
        self.engine = AutomaticGameEngine.initialize(
            base_state([self.p1_card], [self.p2_card]),
            ruleset(self.p1_card, self.p2_card),
            seed='opening-review', settings={'opening_review': True},
        )

    def confirm(self, role):
        [action] = self.engine.legal_actions(role)
        self.assertEqual(action['type'], 'confirm_opening_review')
        self.engine.submit_action(role, action['action_id'])

    def test_game_start_waits_until_both_players_confirm(self):
        self.assertEqual(self.engine.engine_state['startup_stage'], 'opening_review')
        self.confirm('p1')
        self.assertEqual(self.engine.legal_actions('p1'), [])
        self.assertEqual(self.engine.engine_state['startup_stage'], 'opening_review')
        self.confirm('p2')
        self.assertNotEqual(self.engine.engine_state.get('startup_stage'), 'opening_review')
        self.assertNotIn('opening_review', self.engine.engine_state)
        self.assertTrue(any(e['type'] == 'opening_review_confirmed' and e['actor'] == 'p2' for e in self.engine.events))
        self.assertEqual(self.engine.legal_actions('p1')[0]['type'] != 'confirm_opening_review', True)

    def test_opponent_hand_is_visible_only_during_review(self):
        hand = self.engine.observe('p1')['state']['players']['p2']['zones']['hand']
        self.assertEqual(hand[0]['instance_id'], 'review-p2')
        self.confirm('p1')
        self.confirm('p2')
        hand = self.engine.observe('p1')['state']['players']['p2']['zones']['hand']
        self.assertTrue(hand[0]['hidden'])

    def test_without_setting_game_starts_immediately(self):
        engine = AutomaticGameEngine.initialize(
            base_state([self.p1_card], [self.p2_card]),
            ruleset(self.p1_card, self.p2_card), seed='opening-review-off',
        )
        self.assertNotEqual(engine.engine_state.get('startup_stage'), 'opening_review')


class GameStartCounterGrantTests(SimpleTestCase):
    """요한: 수동 계산기의 예지 2는 게임 시작 효과 결과이므로 자동 모드는 0에서 시작한다."""

    def test_trait_game_start_counter_is_not_granted_twice(self):
        player = {
            'passive_state': {'foresight_counter': {'count': 2, 'label': '예지 카운터'}},
            'zones': {'passive': [{'code': 'CRS-PS-002'}]},
        }
        cards = {'CRS-PS-002': {'effect_definition': {'abilities': [{
            'trigger': {'event': 'game_start'}, 'active_zones': ['passive'],
            'effects': [{
                'op': 'change_counter', 'player': {'controller': True},
                'counter': 'foresight', 'amount': 2, 'min': 0,
            }],
        }]}}}
        _remove_game_start_counter_grants(player, cards)
        self.assertEqual(player['passive_state']['foresight_counter']['count'], 0)


class PresentedComboCostTests(SimpleTestCase):
    """키스 슈타이너: 함께 제시돼 먼저 배틀 존에 놓여도 리스트 사용 비용(패 2장 버리기)을 지불한다."""

    def test_list_cost_applies_to_card_presented_from_list(self):
        starter = attack('keith-starter', 'p1', frame=5, hit='콤보')
        first = attack('keith-first', 'p1', frame=5)
        keith = attack('keith-card', 'p1', frame=6, code='KEITH')
        fodder = [attack(f'keith-fodder-{i}', 'p1', frame=9) for i in range(2)]
        opposing = attack('keith-opposing', 'p2', frame=7)
        state = base_state([], [])
        state['phase'] = 'battle'
        state['players']['p1']['zones']['battle'] = [starter]
        state['players']['p1']['zones']['hand'] = [first, *fodder]
        state['players']['p1']['zones']['list'] = [keith]
        state['players']['p2']['zones']['battle'] = [opposing]
        rules = ruleset(starter, first, keith, *fodder, opposing)
        rules['cards']['KEITH']['effect_definition'] = {
            **copy.deepcopy(rules['cards']['KEITH']['effect_definition']),
            'combo_rules': [{'allow_zones': ['list']}],
            'play_costs': [{
                'operation': 'discard', 'use_contexts': ['combo'], 'source_zones': ['list'],
                'selector': {
                    'kind': 'card', 'player': {'controller': True}, 'zones': ['hand'],
                    'min': 2, 'max': 2, 'exclude_source': True,
                },
            }],
        }
        engine = AutomaticGameEngine.initialize(state, rules, seed='keith-presented')
        engine.state['phase'] = 'battle'
        engine.engine_state['battle'] = {
            'p1': {'instance_id': 'keith-starter', 'card': starter},
            'p2': {'instance_id': 'keith-opposing', 'card': opposing},
        }
        engine.grant_combo('p1', source='keith-starter')
        engine._play_combo('p1', ['keith-first', 'keith-card'])
        engine._continue()
        decision = engine.engine_state.get('pending_decision') or {}
        self.assertEqual(decision.get('kind'), 'play_cost')
        self.assertEqual(
            sorted(option['id'] for option in decision['options']),
            ['keith-fodder-0', 'keith-fodder-1'],
        )


class PartsSupplementDeckTests(SimpleTestCase):
    """핀프 Parts는 핀프 카드이며 기본 20장에도, 추가 4장 슬롯에도 들어갈 수 있다."""

    PINP = 17

    def card(self, name, *, character_id=PINP, card_type='공격', parts=False):
        return SimpleNamespace(
            name=name, code=name, type=card_type, ultimate=False, character_id=character_id,
            text='', effect_definition={'token_key': 'parts'} if parts else {},
        )

    def validate(self, base_pinp, base_parts, base_neutral, supplement_parts):
        rules = {
            'supplements': [{
                'where': {'token_key': 'parts'}, 'max_count': 4,
                'allow_foreign_mark': False, 'allow_non_technique': False,
                'allow_base_copies': True,
            }],
            'main_size': {'min': 20, 'max': 24, 'base_excludes_supplements': True},
        }
        trait = SimpleNamespace(trait_config={}, effect_definition={'deck_rules': rules}, code='RFS-PS-002')
        deck = SimpleNamespace(
            character_id=self.PINP, schema_version=2, trait_card=trait,
            character=SimpleNamespace(datas={}),
        )
        cards = (
            [self.card(f'pinp-{i}') for i in range(base_pinp)]
            + [self.card(f'parts-{i}', card_type='특수', parts=True) for i in range(base_parts + supplement_parts)]
            + [self.card(f'neutral-{i}', character_id=1) for i in range(base_neutral)]
        )
        entries = [SimpleNamespace(card=c, count=1, hand=0, side=0) for c in cards]
        return validate_automatic_deck(deck, entries=entries, check_setup=False).errors

    def test_parts_in_base_deck_count_as_pinp_marks(self):
        self.assertEqual(self.validate(8, 2, 10, 4), [])

    def test_extra_parts_beyond_supplement_slots_fill_base_deck(self):
        self.assertEqual(self.validate(10, 2, 8, 4), [])

    def test_base_deck_must_still_be_twenty(self):
        errors = self.validate(10, 0, 9, 0)
        self.assertTrue(any('기술 카드' in error or '기본 기술 덱' in error for error in errors), errors)
