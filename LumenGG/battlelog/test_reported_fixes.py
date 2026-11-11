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


SPIDER_PAYMENT_ABILITY = {
    'id': 'pmp-ps-001-n1', 'kind': 'effect', 'mode': 'mandatory', 'timing': 'result',
    'visibility': 'public', 'trigger': {'event': 'hp_changed'}, 'active_zones': ['passive'],
    'condition': {'op': 'all', 'conditions': [
        {'op': 'equals', 'left': 'context.player', 'right': {'controller': True}},
        {'op': 'equals', 'left': 'context.effect_cost', 'right': True},
        {'op': 'lt', 'left': 'context.amount', 'right': 0},
    ]},
    'availability_selector': {
        'kind': 'card', 'player': {'controller': True}, 'zones': ['side'], 'min': 1, 'max': 1,
        'where': {'token_key': 'spider'}, 'as_operation': 'move_card', 'to_zone': 'lumen',
    },
    'effects': [{
        'op': 'request_choice', 'player': {'controller': True},
        'prompt': '루멘 존에 배치할 거미 토큰을 선택하세요.',
        'selector': {
            'kind': 'card', 'player': {'controller': True}, 'zones': ['side'], 'min': 1, 'max': 1,
            'where': {'token_key': 'spider'}, 'as_operation': 'move_card', 'to_zone': 'lumen',
        },
        'selection_key': 'pmp_ps_001_payment_spider', 'default': [],
        'then': [{'op': 'move_card', 'selection_key': 'pmp_ps_001_payment_spider', 'to_zone': 'lumen'}],
    }],
}


class SideTokenSupplyTests(SimpleTestCase):
    """이제벨 특성 ①: 거미 토큰은 덱에 없어도 사이드 공급분에서 루멘 존으로 배치된다."""

    JEZEBEL = 13

    def build(self, character_id):
        passive = {
            'instance_id': 'p1-passive-1', 'kind': 'card', 'owner': 'p1',
            'code': 'PMP-PS-001', 'name': '피의 잔향', 'type': '특성', 'face_up': True,
        }
        state = base_state([], [])
        state['players']['p1']['character'] = {'id': character_id}
        state['players']['p1']['zones']['passive'] = [passive]
        rules = ruleset()
        rules['cards'] = {
            'PMP-PS-001': {
                'code': 'PMP-PS-001', 'name': '피의 잔향', 'type': '특성',
                'character_id': self.JEZEBEL,
                'effect_definition': {'abilities': [SPIDER_PAYMENT_ABILITY]},
            },
            'PMP-AT-053': {
                'code': 'PMP-AT-053', 'name': '「거미」', 'type': '토큰',
                'character_id': self.JEZEBEL,
                'effect_definition': {'token_key': 'spider', 'token_usage': ['token', 'counter']},
            },
        }
        return AutomaticGameEngine.initialize(state, rules, seed='spider-supply', run_startup=False)

    def spiders(self, engine, zone):
        return [c for c in engine.state['players']['p1']['zones'][zone] if c.get('token_key') == 'spider']

    def test_hp_payment_places_spider_from_supply(self):
        engine = self.build(self.JEZEBEL)
        self.assertGreater(len(self.spiders(engine, 'side')), 0)
        engine.change_hp('p1', -200, context={'controller': 'p1', 'effect_cost': True})
        engine._continue()
        decision = engine.engine_state.get('pending_decision')
        if decision:
            engine._submit_decision('p1', decision['id'], [decision['options'][0]['id']])
        self.assertEqual(len(self.spiders(engine, 'lumen')), 1)
        # 공급분은 다시 채워진다.
        engine._continue()
        self.assertEqual(len(self.spiders(engine, 'side')), 8)

    def test_other_characters_do_not_receive_the_supply(self):
        engine = self.build(2)
        self.assertEqual(self.spiders(engine, 'side'), [])


class UnrestrictedSetupPlacementTests(SimpleTestCase):
    """무금제 덱도 시작 배치 규칙(특수 기술은 사이드, 얼티밋은 얼티밋 영역)을 지킨다."""

    def snapshot(self, special_side, ultimate_side=0):
        from deck.validation import validate
        catalog = {
            '1': {'id': 1, 'name': '특성', 'code': 'X-PS-001', 'type': '특성', 'character_id': 2},
            '2': {'id': 2, 'name': '특수기', 'code': 'X-AT-002', 'type': '특수', 'character_id': 2},
            '3': {'id': 3, 'name': '얼티밋', 'code': 'X-AT-003', 'type': '공격', 'character_id': 2, 'ultimate': True},
        }
        snapshot = {
            'character_id': 2, 'character': {'id': 2, 'name': 'X', 'datas': {}},
            'trait_card_id': 1, 'catalog': catalog, 'reserve_cards': [],
            'regulation_rules': None,
            'cards': [
                {'card_id': 2, 'count': 1, 'hand': 0, 'side': special_side},
                {'card_id': 3, 'count': 1, 'hand': 0, 'side': ultimate_side},
            ],
        }
        return validate(snapshot, stage='setup')

    def test_special_in_list_blocks_setup(self):
        report = self.snapshot(special_side=0)
        self.assertFalse(report['is_valid'])
        self.assertIn('setup_placement', [issue['code'] for issue in report['issues']])

    def test_special_in_side_is_allowed(self):
        self.assertTrue(self.snapshot(special_side=1)['is_valid'])

    def test_ultimate_in_side_blocks_setup(self):
        self.assertFalse(self.snapshot(special_side=1, ultimate_side=1)['is_valid'])


class ForcedFirstNoResponseTests(SimpleTestCase):
    """상대가 먼저 레디해야 할 때(서드아이 등) 그 플레이어가 무응답이면, 남은 플레이어의 레디를 기다린다.

    자동 오류 리포트 #10·#11: 바로 배틀로 넘어가 '배틀 카드가 없습니다'로 엔진이 멈췄다.
    """

    def test_battle_waits_for_the_other_player_after_forced_first_timeout(self):
        p1_cards = [attack('ff-p1-a', 'p1', frame=5)]
        p2_cards = [attack('ff-p2-a', 'p2', frame=6)]
        engine = AutomaticGameEngine.initialize(
            base_state(p1_cards, p2_cards), ruleset(*p1_cards, *p2_cards),
            seed='forced-first', run_startup=False,
            settings={'ready_timeout_seconds': 30},
        )
        engine.state['phase'] = 'ready'
        engine.engine_state.update({'step': 'ready_actions', 'ready_cards': {}, 'forced_ready_first': 'p2'})
        self.assertEqual([a['type'] for a in engine.legal_actions('p1') if a['type'] == 'ready_card'], [])

        engine._ready_timeout('p2')
        decision = engine.engine_state['pending_decision']
        self.assertEqual((decision['owner'], decision['kind']), ('p1', 'no_response_card'))
        engine._submit_decision('p1', decision['id'], ['ff-p2-a'])
        engine._continue()

        self.assertEqual(engine.state['phase'], 'ready')
        self.assertEqual(engine.engine_state['ready_cards'], {'p2': 'ff-p2-a'})
        ready = next(a for a in engine.legal_actions('p1') if a['type'] == 'ready_card')
        engine.submit_action('p1', ready['action_id'])
        self.assertEqual(engine.engine_state['status'], 'running')
        self.assertNotEqual(engine.state['phase'], 'ready')


class SameNameLimitedTriggerTests(SimpleTestCase):
    """턴 1회 제한 효과는 같은 이름 카드 여러 장이 동시에 유발돼도 한 번만 제시한다(드리프트 컨버전)."""

    def test_two_copies_collect_one_optional_trigger(self):
        ability = {
            'id': 'same-name-n1', 'kind': 'effect', 'mode': 'optional', 'timing': 'function',
            'trigger': {'event': 'phase_start'}, 'active_zones': ['side'],
            'limit': {'scope': 'turn', 'max': 1},
            'effects': [{'op': 'change_fp', 'player': {'controller': True}, 'amount': 1}],
        }
        copies = [
            {**attack(f'same-{index}', 'p1', code='SAME-NAME'), 'type': '특수'}
            for index in range(2)
        ]
        state = base_state([], [])
        state['players']['p1']['zones']['side'] = copies
        rules = ruleset(*copies)
        rules['cards']['SAME-NAME']['effect_definition'] = {'abilities': [ability]}
        engine = AutomaticGameEngine.initialize(state, rules, seed='same-name', run_startup=False)
        engine._fire('phase_start', {'phase': 'lumen'})
        engine._continue()
        decision = engine.engine_state['pending_decision']
        self.assertEqual(decision['kind'], 'optional_effect')


class SideToHandRevealTests(SimpleTestCase):
    """사이드 덱에서 패로 가져가는 카드는 공개한다(패에 들어간 뒤에는 비공개)."""

    def test_side_to_hand_move_is_public_but_card_stays_hidden(self):
        card = attack('side-card', 'p1')
        state = base_state([], [])
        state['players']['p1']['zones']['side'] = [card]
        engine = AutomaticGameEngine.initialize(state, ruleset(card), seed='side-hand', run_startup=False)
        engine.move_card('side-card', 'hand', reason='effect')
        event = next(e for e in reversed(engine.events) if e['type'] == 'card_moved')
        self.assertEqual(event['visibility'], 'public')
        self.assertTrue(event['payload']['revealed'])
        self.assertFalse(engine._find_card('side-card')['face_up'])
        hand = engine.observe('p2')['state']['players']['p1']['zones']['hand']
        self.assertTrue(hand[0]['hidden'])
