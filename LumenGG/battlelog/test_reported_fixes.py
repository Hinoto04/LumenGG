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

    def pay_hp(self, engine):
        engine.change_hp('p1', -200, context={'controller': 'p1', 'effect_cost': True})
        engine._continue()
        decision = engine.engine_state.get('pending_decision')
        if decision:
            engine._submit_decision('p1', decision['id'], [decision['options'][0]['id']])
        engine._continue()

    def test_placed_spider_is_created_not_taken_from_side_deck(self):
        """Q-AUTO-012: 토큰은 사이드 덱에서 꺼내는 것이 아니라 생성한다."""
        engine = self.build(self.JEZEBEL)
        self.pay_hp(engine)
        [spider] = self.spiders(engine, 'lumen')
        self.assertNotIn('token_supply', spider)
        created = [
            event for event in engine.events
            if event['type'] == 'token_created'
            and event['payload'].get('card_instance_id') == spider['instance_id']
        ]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]['payload']['zone'], 'lumen')

    def test_spider_count_has_no_supply_limit(self):
        """Q-AUTO-012: 카드에 최대 수가 없으면 토큰 수 제한도 없다."""
        engine = self.build(self.JEZEBEL)
        for _ in range(12):
            self.pay_hp(engine)
        self.assertEqual(len(self.spiders(engine, 'lumen')), 12)

    def test_waiting_tokens_are_not_side_deck_cards(self):
        """생성 대기 토큰은 사이드 덱 장 수·일반 사이드 덱 선택에 들어가지 않는다."""
        engine = self.build(self.JEZEBEL)
        real = {
            'instance_id': 'p1-side-real', 'kind': 'card', 'owner': 'p1',
            'code': 'X-AT-001', 'name': '사이드 기술', 'type': '공격', 'face_up': False,
        }
        engine.state['players']['p1']['zones']['side'].insert(0, real)
        context = {'controller': 'p1'}
        any_side = {'kind': 'card', 'player': {'controller': True}, 'zones': ['side'], 'min': 0, 'max': 9}
        self.assertEqual(
            [option['id'] for option in engine.selector_options(any_side, context)],
            ['p1-side-real'],
        )
        spider_side = {**any_side, 'where': {'token_key': 'spider'}}
        self.assertEqual(len(engine.selector_options(spider_side, context)), 8)
        from .game.effects import condition_matches, resolve_value
        self.assertEqual(resolve_value(
            {'op': 'zone_count', 'player': {'controller': True}, 'zone': 'side'},
            engine.state, context,
        ), 1)
        self.assertTrue(condition_matches(
            {'op': 'zone_count', 'player': {'controller': True}, 'zone': 'side',
             'min': 2, 'where': {'token_key': 'spider'}},
            engine.state, context,
        ))
        observed = engine.observe('p1')['state']['players']['p1']['zones']['side']
        self.assertEqual([card.get('instance_id') for card in observed], ['p1-side-real'])
        opponent_view = engine.observe('p2')['state']['players']['p1']['zones']['side']
        self.assertEqual(len(opponent_view), 1)

    def test_token_returned_to_side_deck_disappears(self):
        engine = self.build(self.JEZEBEL)
        self.pay_hp(engine)
        [spider] = self.spiders(engine, 'lumen')
        engine.move_card(spider['instance_id'], 'side', reason='test')
        engine._continue()
        self.assertEqual(self.spiders(engine, 'lumen'), [])
        side = self.spiders(engine, 'side')
        self.assertEqual(len(side), 8)
        self.assertTrue(all(card.get('token_supply') for card in side))
        self.assertEqual(engine.observe('p1')['state']['players']['p1']['zones']['side'], [])

    def test_spiders_are_shown_as_player_state_counter(self):
        """Q-AUTO-012: 무한히 쌓이는 거미는 플레이어 상태에 개수로 표시한다."""
        engine = self.build(self.JEZEBEL)
        state = engine.observe('p2')['state']
        self.assertEqual(state['players']['p1']['passive_state']['spider_token']['count'], 0)
        for _ in range(3):
            self.pay_hp(engine)
        state = engine.observe('p2')['state']
        counter = state['players']['p1']['passive_state']['spider_token']
        self.assertEqual(counter['count'], 3)
        self.assertEqual(counter['label'], '거미 토큰')
        self.assertTrue(counter['derived'])
        lumen = state['players']['p1']['zones']['lumen']
        self.assertEqual(
            [card.get('state_counter_token') for card in lumen],
            ['spider_token'] * 3,
        )
        # 표시 전용: 엔진 상태에는 표식이 남지 않는다.
        self.assertNotIn('spider_token', engine.state['players']['p1']['passive_state'])
        self.assertNotIn('state_counter_token', self.spiders(engine, 'lumen')[0])
        self.assertNotIn('spider_token', engine.observe('p1')['state']['players']['p2']['passive_state'])


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


class AnyZoneToHandRevealTests(SimpleTestCase):
    """패로 들어가는 카드는 어느 존에서 오든 공개한다(특수 기술이 아님을 확인할 의무)."""

    def test_face_down_lumen_card_to_hand_is_public(self):
        card = {**attack('lumen-face-down', 'p1'), 'face_up': False}
        state = base_state([], [])
        state['players']['p1']['zones']['lumen'] = [card]
        engine = AutomaticGameEngine.initialize(state, ruleset(card), seed='lumen-hand', run_startup=False)
        engine.set_card_visibility('lumen-face-down', False)
        engine.move_card('lumen-face-down', 'hand', reason='effect')
        event = next(e for e in reversed(engine.events) if e['type'] == 'card_moved')
        self.assertEqual(event['visibility'], 'public')
        self.assertTrue(event['payload']['revealed'])
        self.assertTrue(engine.observe('p2')['state']['players']['p1']['zones']['hand'][0]['hidden'])

    def test_move_between_other_zones_stays_private(self):
        card = attack('side-to-list', 'p1')
        state = base_state([], [])
        state['players']['p1']['zones']['side'] = [card]
        engine = AutomaticGameEngine.initialize(state, ruleset(card), seed='side-lumen', run_startup=False)
        engine.move_card('side-to-list', 'battle', reason='effect', face_up=False)
        event = next(e for e in reversed(engine.events) if e['type'] == 'card_moved')
        self.assertEqual(event['visibility'], 'private')


def _jezebel_engine_with_empress():
    engine = SideTokenSupplyTests().build(SideTokenSupplyTests.JEZEBEL)
    source = attack('empress', 'p1', code='PMP-AT-010')
    engine.ruleset['cards']['PMP-AT-010'] = {
        'code': 'PMP-AT-010', 'name': '여제의 영역', 'type': '공격', 'character_id': 13,
        'effect_definition': {'abilities': [{
            'id': 'pmp-at-010-n1', 'label': '사용 시, 체력 300을 지불한다.',
            'kind': 'effect', 'mode': 'mandatory', 'timing': 'use', 'visibility': 'public',
            'draft_text': '사용 시, 체력 300을 지불한다.',
            'effects': [{'op': 'change_hp', 'player': {'controller': True}, 'amount': -300}],
            'cost': [], 'trigger': {'event': 'use'}, 'active_zones': ['battle'],
            'condition': {'op': 'equals', 'left': 'context.event_controller', 'right': {'controller': True}},
        }]},
    }
    engine.state['players']['p1']['zones']['battle'] = [source]
    return engine, source


class EffectHpPaymentSpiderTests(SimpleTestCase):
    """여제의 영역: 사용 시 효과로 체력을 지불하면 이제벨 특성 ①이 발동한다.
    똑같은 거미 토큰 중에서 고르는 선택은 엔진이 고를 카드를 정해 준다(auto_select)."""

    def lumen_spiders(self, engine):
        return [c for c in engine.state['players']['p1']['zones']['lumen'] if c.get('token_key') == 'spider']

    def test_use_effect_payment_places_spider_without_choice(self):
        engine, source = _jezebel_engine_with_empress()
        before = engine.state['players']['p1']['hp']
        engine._fire('use', {
            'controller': 'p1', 'source_card': source, 'source_card_instance_id': 'empress',
        })
        engine._continue()
        self.assertEqual(engine.state['players']['p1']['hp'], before - 300)
        decision = engine.observe('p1')['pending_decision']
        # 똑같은 거미 중에서 고르는 선택은 화면이 묻지 않고 auto_select를 바로 제출한다.
        self.assertEqual(len(decision['auto_select']), 1)
        engine._submit_decision('p1', decision['id'], decision['auto_select'])
        engine._continue()
        self.assertEqual(len(self.lumen_spiders(engine)), 1)
        moved = next(e for e in reversed(engine.events) if e['type'] == 'card_moved')
        self.assertEqual(moved['payload']['counter_token'], 'spider_token')

    def test_damage_is_not_a_payment(self):
        engine, _source = _jezebel_engine_with_empress()
        engine.change_hp('p1', -300, source='effect', context={'controller': 'p2'})
        engine._continue()
        self.assertEqual(self.lumen_spiders(engine), [])


class DaggerCounterTokenTests(SimpleTestCase):
    """레브 단검도 루멘 존 카드 대신 체력 아래 개수로 보여 준다."""

    def test_daggers_in_lumen_are_shown_as_counter(self):
        daggers = [{
            'instance_id': f'dagger-{i}', 'kind': 'token', 'owner': 'p1', 'code': 'LMI-TK-DAGGER',
            'name': '「단검」', 'type': '토큰', 'token_key': 'dagger', 'face_up': True,
        } for i in range(2)]
        state = base_state([], [])
        state['players']['p1']['zones']['lumen'] = daggers
        engine = AutomaticGameEngine.initialize(state, ruleset(), seed='dagger-counter', run_startup=False)
        observed = engine.observe('p2')['state']['players']['p1']
        self.assertEqual(observed['passive_state']['dagger_token']['count'], 2)
        self.assertEqual(observed['passive_state']['dagger_token']['label'], '단검 토큰')
        self.assertEqual(
            [card.get('state_counter_token') for card in observed['zones']['lumen']],
            ['dagger_token', 'dagger_token'],
        )


DRIFT_CONVERSION = {
    'abilities': [{
        'id': 'crs-at-054-n1', 'kind': 'effect', 'mode': 'optional', 'timing': 'combo',
        'visibility': 'public', 'trigger': {'event': 'combo_window'}, 'active_zones': ['side'],
        'limit': {'scope': 'turn', 'max': 1},
        'condition': {'op': 'all', 'conditions': [
            {'op': 'equals', 'left': 'context.event_controller', 'right': {'path': 'context.controller'}},
            {'op': 'equals', 'left': 'context.combo_number', 'right': 2},
        ]},
        'effects': [
            {'op': 'break_card', 'result_key': 'crs_at_054_source_broken'},
            {'op': 'conditional', 'condition': {
                'op': 'gte', 'left': {'op': 'selection_count', 'selection_key': 'crs_at_054_source_broken'},
                'right': 1,
            }, 'then': [{
                'op': 'modify_combo', 'player': {'controller': True}, 'allow_zones': ['hand'],
                'source_zones': ['hand'], 'min_combo': 3, 'max_combo': 3, 'ignore_speed': True,
                'requires_followup': True, 'end_after_use': True, 'usage_key': 'crs_at_054_followup',
                'usage_key_source_scoped': True, 'max_uses': 1, 'usage_scope': 'battle', 'duration': 'combo',
            }], 'else': []},
        ],
    }],
}


class DriftConversionPresentedPairTests(SimpleTestCase):
    """드리프트 컨버전: 2콤보와 함께 제시한 패의 기술을 속도를 무시하고 3콤보로 잇는다."""

    def test_presented_hand_card_continues_after_conversion(self):
        starter = attack('st', 'p1', frame=5, hit='콤보')
        first = attack('a', 'p1', frame=5)
        slow = attack('b', 'p1', frame=6)
        drift = {**attack('drift', 'p1', code='CRS-AT-054'), 'type': '특수', 'frame': None, 'damage': None}
        opposing = attack('opp', 'p2', frame=9)
        state = base_state([], [])
        state['phase'] = 'battle'
        state['players']['p1']['zones']['battle'] = [starter]
        state['players']['p1']['zones']['hand'] = [first, slow]
        state['players']['p1']['zones']['side'] = [drift]
        state['players']['p2']['zones']['battle'] = [opposing]
        rules = ruleset(starter, first, slow, drift, opposing)
        rules['cards']['CRS-AT-054'].update({'type': '특수', 'effect_definition': DRIFT_CONVERSION})
        engine = AutomaticGameEngine.initialize(state, rules, seed='drift-pair', run_startup=False)
        engine.state['phase'] = 'battle'
        engine.engine_state['battle'] = {
            'p1': {'instance_id': 'st', 'card': starter},
            'p2': {'instance_id': 'opp', 'card': opposing},
        }
        engine.grant_combo('p1', source='st')
        engine._play_combo('p1', ['a', 'b'])
        engine._continue()
        decision = engine.engine_state['pending_decision']
        self.assertEqual(decision['kind'], 'optional_effect')
        engine._submit_decision('p1', decision['id'], ['accept'])
        engine._continue()
        used = [e['payload']['card_instance_id'] for e in engine.events if e['type'] == 'combo_card_used']
        self.assertEqual(used, ['a', 'b'])
        self.assertFalse(any(e['type'] == 'combo_interrupted' for e in engine.events))


class IdenticalTokenPlayCostTests(SimpleTestCase):
    """피의 만찬: 루멘 존의 거미 4장을 제거하는 사용 비용은 고를 카드를 엔진이 정해 준다."""

    def test_spider_play_cost_is_paid_without_choice(self):
        feast = attack('feast', 'p1', code='PMP-AT-009', frame=7)
        spiders = [{
            'instance_id': f'spider-{i}', 'kind': 'token', 'owner': 'p1', 'code': 'PMP-AT-053',
            'name': '「거미」', 'type': '토큰', 'token_key': 'spider', 'face_up': True,
        } for i in range(5)]
        state = base_state([feast], [defense('guard', 'p2')])
        state['players']['p1']['zones']['lumen'] = spiders
        rules = ruleset(feast)
        rules['cards']['PMP-AT-009']['effect_definition'] = {
            **copy.deepcopy(rules['cards']['PMP-AT-009']['effect_definition']),
            'play_costs': [{'operation': 'delete_token', 'selector': {
                'kind': 'card', 'player': {'controller': True}, 'zones': ['lumen'],
                'min': 4, 'max': 4, 'where': {'token_key': 'spider'},
            }}],
        }
        engine = AutomaticGameEngine.initialize(state, rules, seed='feast-cost', run_startup=False)
        engine.state['phase'] = 'ready'
        engine._ready_card('p1', 'feast')
        engine._continue()
        decision = engine.engine_state['pending_decision']
        self.assertEqual(decision['kind'], 'play_cost')
        self.assertEqual(len(decision['auto_select']), 4)
        engine._submit_decision('p1', decision['id'], decision['auto_select'])
        engine._continue()
        left = [c for c in engine.state['players']['p1']['zones']['lumen'] if c.get('token_key') == 'spider']
        self.assertEqual(len(left), 1)
        self.assertEqual(engine._find_location('feast')[1], 'battle')


class UltimateTechniqueComboBanScopeTests(SimpleTestCase):
    """스톰슬레이어(얼티밋 존)의 "이 기술은 콤보에 사용할 수 없다"는 그 기술에만 적용된다."""

    BAN = {'abilities': [{
        'id': 'dfr-at-015-function', 'kind': 'function', 'mode': 'continuous',
        'timing': 'function', 'visibility': 'public',
        'effects': [{'op': 'prevent', 'kind': 'combo', 'player': {'controller': True}, 'duration': 'continuous'}],
    }]}

    def build(self, zone):
        slayer = attack('slayer', 'p1', code='DFR-AT-015', frame=6)
        follow = attack('follow', 'p1', frame=6)
        state = base_state([], [])
        state['players']['p1']['zones'][zone] = [slayer]
        state['players']['p1']['zones']['hand'] += [follow]
        rules = ruleset(slayer, follow)
        rules['cards']['DFR-AT-015']['effect_definition'] = self.BAN
        engine = AutomaticGameEngine.initialize(state, rules, seed=f'slayer-{zone}', run_startup=False)
        engine._refresh_continuous_rules()
        return engine, slayer, follow

    def test_ultimate_zone_ban_does_not_block_other_techniques(self):
        engine, slayer, follow = self.build('ultimate')
        self.assertFalse(engine._rule_blocked('combo', 'p1', follow))
        self.assertTrue(engine._rule_blocked('combo', 'p1', engine._find_card('slayer')))

    def test_ultimate_unguardable_text_applies_only_to_that_technique(self):
        """라스트 워드(얼티밋 존)의 "상대는 이 기술을 방어할 수 없다"가
        히트 매니퓰레이터 등 다른 기술의 방어까지 막던 문제."""
        last_word = attack('last-word', 'p1', code='RFS-AT-013', frame=6)
        manipulator = attack('manipulator', 'p1', frame=9)
        state = base_state([], [])
        state['players']['p1']['zones']['ultimate'] = [last_word]
        state['players']['p1']['zones']['battle'] = [manipulator]
        rules = ruleset(last_word, manipulator)
        rules['cards']['RFS-AT-013']['effect_definition'] = {'abilities': [{
            'id': 'rfs-at-013-function', 'kind': 'function', 'mode': 'continuous',
            'timing': 'function', 'visibility': 'public',
            'effects': [{'op': 'prevent', 'kind': 'guard', 'player': {'opponent': True}, 'duration': 'continuous'}],
        }]}
        engine = AutomaticGameEngine.initialize(state, rules, seed='last-word', run_startup=False)
        engine._refresh_continuous_rules()
        self.assertFalse(engine._rule_blocked('guard', 'p2', None, manipulator))
        self.assertTrue(engine._rule_blocked('guard', 'p2', None, engine._find_card('last-word')))

    def test_special_card_in_lumen_still_bans_globally(self):
        engine, slayer, follow = self.build('lumen')
        engine._find_card('slayer').update({'type': '특수', 'frame': None, 'damage': None})
        engine._refresh_continuous_rules()
        self.assertTrue(engine._rule_blocked('combo', 'p1', follow))


class CatchCardRevealTests(SimpleTestCase):
    """캐치한 기술은 공개된 채 배틀 존으로 이동한다(상대 화면에 뒷면으로 남지 않는다)."""

    def test_catch_move_event_is_public(self):
        source = attack('catch-source', 'p1', hit='+5')
        catcher = attack('catcher', 'p1', frame=3)
        opposing = attack('catch-opposing', 'p2')
        state = base_state([catcher], [])
        state['phase'] = 'battle'
        state['players']['p1']['zones']['battle'] = [source]
        state['players']['p2']['zones']['battle'] = [opposing]
        engine = AutomaticGameEngine.initialize(
            state, ruleset(source, catcher, opposing), seed='catch-reveal', run_startup=False,
        )
        engine.state['phase'] = 'battle'
        engine.engine_state['step'] = 'catch'
        engine.engine_state['catch'] = {'owner': 'p1', 'source': 'fp', 'max_speed': 5}
        engine.state['players']['p1']['fp'] = 5
        engine._play_catch('p1', 'catcher')
        moved = next(
            e for e in engine.events
            if e['type'] == 'card_moved' and e['payload'].get('card_instance_id') == 'catcher'
        )
        self.assertEqual(moved['visibility'], 'public')
        battle = engine.observe('p2')['state']['players']['p1']['zones']['battle']
        self.assertIn('catcher', [card.get('instance_id') for card in battle])


class ChildOfStarlightSpecialExclusionTests(SimpleTestCase):
    """별빛의 아이 ①: 사이드 덱의 특수 기술(빛의 루멘)은 세트 대상이 아니다."""

    def test_special_card_is_not_offered(self):
        from .game.drafts import build_effect_draft
        text = (
            '①턴당 1번 카운터/상쇄/캐치/콤보 시, 사이드 덱에서 '
            '[[state:saintess]] 효과를 가진 기술 1장을 이 기술에 세트할 수 있다.'
        )
        definition = build_effect_draft('DFR-AT-027', text)
        attach = next(a for a in definition['abilities'] if a['id'] == 'dfr-at-027-n1')
        selector = attach['effects'][0]['selector']
        self.assertEqual(selector['where'].get('type_not_contains'), '특수')
        technique = {**attack('saintess-attack', 'p1'), 'text': '[[state:saintess]] 효과'}
        light = {
            **attack('light-lumen', 'p1', code='LMI-AT-001'), 'type': '특수',
            'frame': None, 'damage': None, 'text': '[[state:saintess]] 효과',
        }
        state = base_state([], [])
        state['players']['p1']['zones']['side'] = [technique, light]
        engine = AutomaticGameEngine.initialize(state, ruleset(technique, light), seed='starlight', run_startup=False)
        options = engine.selector_options(selector, {'controller': 'p1'})
        self.assertEqual([option['id'] for option in options], ['saintess-attack'])


class RecoveryKeepsNegativeFpTests(SimpleTestCase):
    """Q-AUTO-023: 가디언·화접으로 캐치가 성립하지 않아도 음수 FP는 리커버리에서 유지된다."""

    def test_negative_fp_survives_recovery_when_opponent_has_fp(self):
        state = base_state([], [], p1_fp=-6, p2_fp=2)
        engine = AutomaticGameEngine.initialize(state, ruleset(), seed='recovery-fp', run_startup=False)
        engine._recovery_core()
        self.assertEqual(engine.state['players']['p1']['fp'], -6)
        self.assertEqual(engine.state['players']['p2']['fp'], 2)
