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


class ChimeraImportedDeckTests(SimpleTestCase):
    """키메라: 타 캐릭터 공격 기술은 키메라 기술로도 취급하므로 최소 10장에 포함된다."""

    CHIMERA = 15
    RULES = {
        'main_size': {'min': 30, 'max': 30},
        'other_character_cards': {
            'allowed_types': ['공격'], 'exclude_ultimate': True,
            'exclude_character_ids': [1], 'max_per_character': 3,
            'treat_as_own_character': True, 'negate_effects': True,
            'break_after_use': True,
        },
    }

    def card(self, name, character_id, card_type='공격'):
        return SimpleNamespace(
            name=name, code=name, type=card_type, ultimate=False,
            character_id=character_id, text='', effect_definition={},
        )

    def validate(self, cards, rules=None):
        trait = SimpleNamespace(
            trait_config={}, effect_definition={'deck_rules': rules or self.RULES},
            code='CB02-PS-001',
        )
        deck = SimpleNamespace(
            character_id=self.CHIMERA, schema_version=2, trait_card=trait,
            character=SimpleNamespace(datas={}),
        )
        entries = [SimpleNamespace(card=c, count=1, hand=0, side=0) for c in cards]
        return validate_automatic_deck(deck, entries=entries, check_setup=False).errors

    def imported_deck(self):
        # 실제 키메라 덱처럼 키메라 기술 1장 + 세츠메이(중립)가 아닌 타 캐릭터 공격 29장
        cards = [self.card('chimera-own', self.CHIMERA)]
        for index in range(29):
            cards.append(self.card(f'foreign-{index}', 2 + index // 3))
        return cards

    def test_imported_attacks_count_toward_character_minimum(self):
        self.assertEqual(self.validate(self.imported_deck()), [])

    def test_without_own_treatment_imported_attacks_do_not_count(self):
        rules = copy.deepcopy(self.RULES)
        rules['other_character_cards']['treat_as_own_character'] = False
        errors = self.validate(self.imported_deck(), rules)
        self.assertTrue(any('캐릭터 마크 기술은 최소' in e for e in errors), errors)

    def test_neutral_cards_are_not_imported(self):
        cards = self.imported_deck()[:-3] + [
            self.card(f'neutral-{index}', 1) for index in range(3)
        ]
        self.assertEqual(self.validate(cards), [])
        defenses = self.imported_deck()[:-1] + [self.card('foreign-def', 9, '수비')]
        errors = self.validate(defenses)
        self.assertTrue(any('사용할 수 없는 캐릭터 마크' in e for e in errors), errors)


PROVIDENCE_ACQUIRE_ABILITY = {
    'id': 'cb02-at-002-n1', 'kind': 'effect', 'mode': 'optional', 'timing': 'cleanup',
    'visibility': 'public', 'trigger': {'event': 'card_broken'}, 'active_zones': ['lumen'],
    'recheck_condition': True,
    'condition': {'op': 'all', 'conditions': [
        {'op': 'equals', 'left': 'context.event_controller', 'right': {'controller': True}},
        {'op': 'card_matches', 'card': {'path': 'context.event_card'}, 'where': {'is_technique': True}},
        {'op': 'equals', 'left': {'path': 'engine.combo'}, 'right': None},
    ]},
    'availability_selector': {
        'kind': 'card', 'player': {'controller': True}, 'zones': ['list'],
        'min': 1, 'max': 1, 'as_operation': 'move_card', 'to_zone': 'hand',
    },
    'effects': [{
        'op': 'request_choice', 'player': {'controller': True},
        'prompt': '리스트에서 획득할 기술을 선택하세요.',
        'selector': {
            'kind': 'card', 'player': {'controller': True}, 'zones': ['list'],
            'min': 1, 'max': 1, 'as_operation': 'move_card', 'to_zone': 'hand',
        },
        'selection_key': 'cb02_at_002_acquire', 'default': [],
        'then': [{'op': 'move_card', 'selection_key': 'cb02_at_002_acquire', 'to_zone': 'hand'}],
    }],
}


class BreakReplenishBeforeProvidenceTests(SimpleTestCase):
    """9.2.1: 브레이크 보충을 먼저 끼워 넣고, 섭리의 궤 획득은 그 뒤에 묻는다."""

    def build(self):
        broken = attack('chimera-broken', 'p1', code='CHIMERA-BROKEN')
        listed = attack('chimera-listed', 'p1', code='CHIMERA-LISTED')
        spare = attack('chimera-spare', 'p1', code='CHIMERA-SPARE')
        providence = {
            'instance_id': 'p1-providence', 'kind': 'card', 'owner': 'p1',
            'code': 'CB02-AT-002', 'name': '섭리의 궤', 'type': '특수', 'face_up': True,
        }
        state = base_state([broken], [])
        zones = state['players']['p1']['zones']
        zones['list'] = [listed]
        zones['side'] = [spare]
        zones['lumen'] = [providence]
        rules = ruleset(broken, listed, spare)
        rules['cards']['CB02-AT-002'] = {
            'code': 'CB02-AT-002', 'name': '섭리의 궤', 'type': '특수',
            'effect_definition': {'abilities': [PROVIDENCE_ACQUIRE_ABILITY]},
        }
        return AutomaticGameEngine.initialize(state, rules, seed='providence-order', run_startup=False)

    def assert_replenish_then_providence(self, engine):
        decision = engine.engine_state.get('pending_decision') or {}
        self.assertEqual(decision.get('kind'), 'break_replenish')
        engine._submit_decision('p1', decision['id'], ['chimera-spare'])
        engine._continue()
        list_ids = [c['instance_id'] for c in engine.state['players']['p1']['zones']['list']]
        self.assertIn('chimera-spare', list_ids)
        decision = engine.engine_state.get('pending_decision') or {}
        self.assertEqual(decision.get('kind'), 'optional_effect')
        ability = ((decision.get('continuation') or {}).get('item') or {}).get('ability') or {}
        self.assertEqual(ability.get('id'), 'cb02-at-002-n1')

    def test_single_break_offers_replenish_before_providence(self):
        engine = self.build()
        engine.break_card('chimera-broken', reason='deck_rule_after_use')
        engine._continue()
        self.assert_replenish_then_providence(engine)

    def test_batch_break_offers_replenish_before_providence(self):
        engine = self.build()
        engine.break_cards(['chimera-broken'], reason='deck_rule_after_use')
        engine._continue()
        self.assert_replenish_then_providence(engine)


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


DRIFT_TEXT = (
    '이 기술은 3장까지 덱에 넣을 수 있다.\n'
    '①콤보 시, 사이드 덱에서 이 기술을 브레이크할 수 있다.'
    '(사이드 덱에서 브레이크할 경우, 사이드 덱에서 리스트로 카드를 놓지 않는다.)\n'
    '그 경우, 3콤보 기술을 속도를 무시하고 패에서 1장 이을 수 있다.\n'
    '그 기술의 사용 후, 콤보 타임을 종료한다.'
)


class DriftConversionComboEntryTests(SimpleTestCase):
    """드리프트 컨버전: 콤보 타임 진입 시, 적용하면 2·3콤보를 이을 수 있을 때 유발한다.

    3콤보만 패에서 속도를 무시하고 잇고, 3콤보 후 콤보 타임을 끝낸다.
    """

    def build(self, hand_frames):
        from .game.drafts import build_effect_draft
        starter = attack('st', 'p1', frame=5, hit='콤보')
        hand = [attack(f'h{i}', 'p1', frame=frame) for i, frame in enumerate(hand_frames)]
        drift = {**attack('drift', 'p1', code='CRS-AT-054'), 'type': '특수', 'frame': None, 'damage': None}
        opposing = defense('opp', 'p2', top=None, mid=None, bottom=None)
        state = base_state([], [])
        state['phase'] = 'battle'
        state['players']['p1']['zones']['battle'] = [starter]
        state['players']['p1']['zones']['hand'] = hand
        state['players']['p1']['zones']['side'] = [drift]
        state['players']['p2']['zones']['battle'] = [opposing]
        rules = ruleset(starter, *hand, drift, opposing)
        rules['cards']['CRS-AT-054'].update({
            'type': '특수', 'effect_definition': build_effect_draft('CRS-AT-054', DRIFT_TEXT, qna_ids=[594]),
        })
        engine = AutomaticGameEngine.initialize(state, rules, seed='drift-entry', run_startup=False)
        engine.state['phase'] = 'battle'
        engine.engine_state['battle'] = {
            'p1': {'instance_id': 'st', 'card': starter},
            'p2': {'instance_id': 'opp', 'card': opposing},
        }
        return engine

    def open_combo(self, engine):
        item = {'owner': 'p1', 'source': 'st', 'special': False, 'combo_triggered': True}
        can_open = engine._combo_grant_can_open(item)
        if can_open:
            engine.grant_combo('p1', source='st', trigger_event=False)
            engine._continue()
        return can_open

    def answer(self, engine, accept):
        decision = engine.engine_state['pending_decision']
        self.assertEqual(decision['kind'], 'optional_effect')
        engine._submit_decision('p1', decision['id'], ['accept' if accept else 'decline'])
        engine._continue()

    def play_pair(self, engine, first, second):
        action = next(
            a for a in engine.legal_actions('p1')
            if a['type'] == 'select_combo_first' and a['payload'].get('card_instance_id') == first
        )
        engine.submit_action('p1', action['action_id'])
        action = next(
            a for a in engine.legal_actions('p1')
            if a['type'] == 'select_combo_followup' and second in str(a['payload'])
        )
        engine.submit_action('p1', action['action_id'])

    def test_slow_third_combo_then_combo_time_ends(self):
        engine = self.build([10, 2])
        self.assertTrue(self.open_combo(engine))
        self.answer(engine, True)
        self.assertEqual(engine._find_location('drift')[1], 'break')
        self.play_pair(engine, 'h0', 'h1')
        used = [e['payload']['card_instance_id'] for e in engine.events if e['type'] == 'combo_card_used']
        self.assertEqual(used, ['h0', 'h1'])
        self.assertTrue(any(e['type'] == 'combo_ended' for e in engine.events))
        self.assertFalse(any(e['type'] == 'combo_continuation_opened' for e in engine.events))

    def test_combo_ends_after_three_even_with_linked_fourth(self):
        engine = self.build([10, 11, 12])
        self.open_combo(engine)
        self.answer(engine, True)
        self.play_pair(engine, 'h0', 'h1')
        self.assertTrue(any(e['type'] == 'combo_ended' for e in engine.events))
        self.assertFalse(any(e['type'] == 'combo_continuation_opened' for e in engine.events))

    def test_declined_conversion_without_pair_ends_combo(self):
        engine = self.build([10, 2])
        self.open_combo(engine)
        self.answer(engine, False)
        self.assertEqual(engine._find_location('drift')[1], 'side')
        self.assertTrue(any(e['type'] == 'combo_ended' for e in engine.events))
        self.assertIsNone(engine.engine_state.get('pending_decision'))

    def test_not_offered_without_two_hand_techniques(self):
        engine = self.build([10])
        self.assertFalse(self.open_combo(engine))
        self.assertEqual(engine._find_location('drift')[1], 'side')


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
        technique = {**attack('saintess-attack', 'p1'), 'text': '①[[state:saintess]]: 효과'}
        light = {
            **attack('light-lumen', 'p1', code='LMI-AT-001'), 'type': '특수',
            'frame': None, 'damage': None, 'text': '①[[state:saintess]]: 효과',
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


class AttackClashSpeedTests(SimpleTestCase):
    """Q-AUTO-024: 공격 상쇄는 FP까지 반영한 판정 속도가 상대보다 느릴 때만 일어난다."""

    def judge(self, p1_fp):
        stomp = attack('stomp', 'p1', frame=7, position='하단', special='하단 상쇄')
        slide = attack('slide', 'p2', frame=6, position='하단')
        state = base_state([stomp], [slide], p1_fp=p1_fp)
        engine = AutomaticGameEngine.initialize(state, ruleset(stomp, slide), seed=f'clash-{p1_fp}', run_startup=False)
        act = lambda role, kind: engine.submit_action(role, next(
            a for a in engine.legal_actions(role) if a['type'] == kind)['action_id'])
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card'); act('p2', 'ready_card')
        return next(e for e in engine.events if e['type'] == 'battle_judged')['payload']['result']

    def test_slower_clash_attack_clashes(self):
        self.assertEqual(self.judge(0), {'p1': 'clash', 'p2': 'clash'})

    def test_clash_attack_made_faster_by_fp_counters(self):
        self.assertEqual(self.judge(2), {'p1': 'counter', 'p2': 'countered'})


class ClashTimingOwnerTests(SimpleTestCase):
    """6.1.3: "상쇄 시"는 "자신이 상쇄 시"다. 상쇄 판정을 쓴 쪽만 상쇄 시 효과를 맞는다.

    허퓨즈가 상대 방어를 상쇄로 바꿔 수비 상쇄가 나도 공격 측(레브)의 검은 깃털은
    유발되지 않는다. 공격끼리의 상쇄도 상쇄 판정을 가진 느린 공격 쪽만 해당한다.
    """

    ON_CLASH = {'abilities': [{
        'id': 'on-clash', 'kind': 'effect', 'mode': 'mandatory', 'timing': 'clash',
        'visibility': 'public', 'trigger': {'event': 'clash'},
        'effects': [{'op': 'change_fp', 'player': {'controller': True}, 'amount': 10}],
    }]}

    def run_battle(self, p1_card, p2_card):
        rules = ruleset(p1_card, p2_card)
        for card in (p1_card, p2_card):
            rules['cards'][card['code']]['effect_definition'] = self.ON_CLASH
        engine = AutomaticGameEngine.initialize(
            base_state([p1_card], [p2_card]), rules, seed='clash-owner', run_startup=False,
        )
        act = lambda role, kind: engine.submit_action(role, next(
            a for a in engine.legal_actions(role) if a['type'] == kind)['action_id'])
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card'); act('p2', 'ready_card')
        judged = next(e for e in engine.events if e['type'] == 'battle_judged')['payload']['result']
        resolved = [
            e['actor'] for e in engine.events
            if e['type'] == 'effect_resolved' and e['payload'].get('ability_id') == 'on-clash'
        ]
        return judged, resolved

    def test_defense_clash_triggers_only_defender(self):
        hit = attack('hapfuse', 'p1', frame=11, position='상단')
        guard = defense('changed-guard', 'p2', top='상쇄')
        judged, resolved = self.run_battle(hit, guard)
        self.assertEqual(judged, {'p1': 'clash', 'p2': 'clash'})
        self.assertEqual(resolved, ['p2'])

    def test_attack_clash_triggers_only_slower_clashing_attack(self):
        cutter = attack('cutter', 'p1', frame=10, position='하단', special='하단 상쇄')
        slide = attack('slide', 'p2', frame=6, position='하단')
        judged, resolved = self.run_battle(cutter, slide)
        self.assertEqual(judged, {'p1': 'clash', 'p2': 'clash'})
        self.assertEqual(resolved, ['p1'])


class ChainedFpCatchTests(SimpleTestCase):
    """8.8.1 연속 캐치: 캐치 기술의 히트로 다시 같은 FP를 얻어도 다시 캐치할 수 있다.

    네메시스(히트 +5) → 달빛화살 캐치(히트 +5) → 패의 5속도 달빛펀치로 캐치.
    """

    def test_same_fp_after_catch_opens_next_catch(self):
        nemesis = attack('nemesis', 'p1', frame=8, hit='5')
        arrow = attack('arrow', 'p1', frame=5, hit='5')
        punch = attack('punch', 'p1', frame=5, hit='1')
        guard = defense('guard', 'p2', top=None, mid=None, bottom=None)
        state = base_state([nemesis, arrow, punch], [guard])
        engine = AutomaticGameEngine.initialize(
            state, ruleset(nemesis, arrow, punch, guard), seed='chain-catch', run_startup=False,
        )
        act = lambda role, kind, pick=None: engine.submit_action(role, next(
            a for a in engine.legal_actions(role)
            if a['type'] == kind and (pick is None or a['payload'].get('card_instance_id') == pick)
        )['action_id'])
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card', 'nemesis'); act('p2', 'ready_card')
        self.assertEqual(engine.engine_state.get('step'), 'catch')
        act('p1', 'play_catch_card', 'arrow')
        self.assertEqual(engine.engine_state.get('step'), 'catch')
        self.assertEqual(engine.engine_state['catch'].get('max_speed'), 5)
        act('p1', 'play_catch_card', 'punch')
        caught = [
            e['payload']['card_instance_id'] for e in engine.events
            if e['type'] == 'card_moved' and e['payload'].get('reason') == 'catch'
        ]
        self.assertEqual(caught, ['arrow', 'punch'])


class DeckRuleBreakAfterUseTimingTests(SimpleTestCase):
    """키메라 특성: 타 캐릭터 기술의 '사용 후 브레이크'는 그 기술의 사용 후 타이밍에 처리한다.

    배틀 정리까지 미루면 프레임 캐치보다 늦게 브레이크된다.
    """

    def build(self, ready_imported=True, catch_imported=False):
        ready = attack('ready', 'p1', frame=8, hit='5')
        arrow = attack('arrow', 'p1', frame=5, hit='5')
        punch = attack('punch', 'p1', frame=5, hit='1')
        if ready_imported:
            ready['break_after_use'] = True
        if catch_imported:
            arrow['break_after_use'] = True
        guard = defense('guard', 'p2', top=None, mid=None, bottom=None)
        engine = AutomaticGameEngine.initialize(
            base_state([ready, arrow, punch], [guard]),
            ruleset(ready, arrow, punch, guard), seed='after-use-break', run_startup=False,
        )

        def act(role, kind, pick=None):
            engine.submit_action(role, next(
                a for a in engine.legal_actions(role)
                if a['type'] == kind and (pick is None or a['payload'].get('card_instance_id') == pick)
            )['action_id'])
        return engine, act

    def zone_of(self, engine, instance_id):
        return engine._find_location(instance_id)[1]

    def test_ready_card_breaks_before_frame_catch_opens(self):
        engine, act = self.build()
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card', 'ready'); act('p2', 'ready_card')
        self.assertEqual(engine.engine_state.get('step'), 'catch')
        self.assertEqual(self.zone_of(engine, 'ready'), 'break')

    def test_catch_card_breaks_before_next_catch_opens(self):
        engine, act = self.build(ready_imported=False, catch_imported=True)
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card', 'ready'); act('p2', 'ready_card')
        act('p1', 'play_catch_card', 'arrow')
        self.assertEqual(engine.engine_state.get('step'), 'catch')
        self.assertEqual(self.zone_of(engine, 'arrow'), 'break')
        breaks = [
            e for e in engine.events
            if e['type'] == 'card_broken' and e['payload'].get('card_instance_id') == 'arrow'
        ]
        self.assertEqual(len(breaks), 1)


class ChimeraImportedFunctionTests(SimpleTestCase):
    """키메라 특성: 가져온 기술은 번호 효과(①…)만 무효이고, 번호 없는 기능은 적용된다."""

    def test_unnumbered_function_applies_and_numbered_effect_is_negated(self):
        from .game.drafts import build_effect_draft

        imported = attack('imported', 'p1', code='IMPORTED', frame=5, position='상단')
        guard = defense('guard', 'p2', top='방어')
        state = base_state([imported], [guard])
        state['players']['p1']['character'] = {'id': 15}
        state['players']['p2']['character'] = {'id': 2}
        rules = ruleset(imported, guard)
        rules['cards']['IMPORTED']['character_id'] = 3
        rules['cards']['IMPORTED']['type'] = '공격'
        rules['cards']['IMPORTED']['effect_definition'] = build_effect_draft(
            'IMPORTED', '이 기술은 방어할 수 없다.\n①히트 시, 자신은 2FP를 얻는다.',
        )
        rules['characters'] = {
            '2': {'id': 2, 'key': 'opponent'},
            '3': {'id': 3, 'key': 'foreign'},
            '15': {'id': 15, 'key': 'chimera', 'deck_rules': {
                'other_character_cards': {
                    'allowed_types': ['공격'], 'exclude_ultimate': True,
                    'exclude_character_ids': [1], 'max_per_character': 3,
                    'treat_as_own_character': True, 'negate_effects': True,
                    'break_after_use': True,
                },
            }},
        }
        engine = AutomaticGameEngine.initialize(state, rules, seed='chimera-function', run_startup=False)
        live = engine._find_card('imported')
        self.assertTrue(live.get('numbered_effects_negated'))
        self.assertNotEqual(engine._definition_for_card(live), {})

        def act(role, kind, pick=None):
            engine.submit_action(role, next(
                a for a in engine.legal_actions(role)
                if a['type'] == kind and (pick is None or a['payload'].get('card_instance_id') == pick)
            )['action_id'])
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card', 'imported'); act('p2', 'ready_card')
        results = [e['payload'] for e in engine.events if e['type'] == 'battle_judged']
        self.assertTrue(results, [e['type'] for e in engine.events][-30:])
        self.assertEqual((results[-1].get('result') or results[-1]).get('p1'), 'hit')
        self.assertFalse(any(
            e['type'] == 'effect_resolved' and e['payload'].get('ability_id') == 'imported-n1'
            for e in engine.events
        ))
        self.assertEqual(engine.state['players']['p1']['fp'], 0)


class AiWorkerRulesetConnectionTests(SimpleTestCase):
    """AI 워커가 끊긴 MySQL 연결로 새 룰셋을 읽다 실패하면 한 번 다시 연결해 읽는다."""

    def test_retries_once_after_lost_connection(self):
        from unittest import mock

        from django.db.utils import OperationalError

        from . import ai_compute

        calls = []

        def flaky(release_id):
            calls.append(release_id)
            if len(calls) == 1:
                raise OperationalError(2013, 'Lost connection to MySQL server during query')
            return {'version': 'ok'}

        with mock.patch('battlelog.automatic_services._cached_ruleset', side_effect=flaky), \
                mock.patch('django.db.connection.close') as close:
            self.assertEqual(ai_compute._worker_ruleset(6), {'version': 'ok'})
        self.assertEqual(calls, [6, 6])
        self.assertEqual(close.call_count, 2)

    def test_second_failure_is_raised(self):
        from unittest import mock

        from django.db.utils import OperationalError

        from . import ai_compute

        with mock.patch(
            'battlelog.automatic_services._cached_ruleset',
            side_effect=OperationalError(2013, 'lost'),
        ), mock.patch('django.db.connection.close'):
            with self.assertRaises(OperationalError):
                ai_compute._worker_ruleset(6)


    def test_pool_spawns_workers_instead_of_forking(self):
        """fork는 서버의 MySQL 소켓을 워커와 공유해 첫 질의부터 연결이 끊긴다."""
        from unittest import mock

        from . import ai_compute

        with mock.patch.object(ai_compute, '_pool', None),                 mock.patch.object(ai_compute, 'ProcessPoolExecutor') as executor:
            ai_compute._get_pool()
        self.assertEqual(executor.call_args.kwargs['mp_context'].get_start_method(), 'spawn')


class ComboPairFollowupConditionTests(SimpleTestCase):
    """2·3콤보를 함께 낼 때 2번째 카드의 사용 조건은 1번째 카드 처리 후 기준으로 본다."""

    def build(self, first_effect, second_condition, *, filler=False):
        opener = attack('opener', 'p1', frame=8, hit='콤보')
        first = attack('first', 'p1', code='FIRST', frame=5)
        second = attack('second', 'p1', code='SECOND', frame=6)
        extra = [attack('filler', 'p1', code='FILLER', frame=6)] if filler else []
        guard = defense('guard', 'p2', top=None, mid=None, bottom=None)
        rules = ruleset(opener, first, second, guard, *extra)
        rules['cards']['FIRST']['effect_definition'] = {'abilities': [{
            'id': 'first-n1', 'kind': 'effect', 'mode': 'mandatory', 'timing': 'use',
            'visibility': 'public', 'trigger': {'event': 'use'}, 'active_zones': ['battle'],
            'effects': [first_effect],
        }]}
        rules['cards']['SECOND']['effect_definition'] = {
            'abilities': [], 'play_condition': second_condition,
        }
        engine = AutomaticGameEngine.initialize(
            base_state([opener, first, second, *extra], [guard]), rules,
            seed='combo-followup-condition', run_startup=False,
        )

        def act(role, kind, pick=None):
            engine.submit_action(role, next(
                a for a in engine.legal_actions(role)
                if a['type'] == kind and (pick is None or a['payload'].get('card_instance_id') == pick)
            )['action_id'])
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card', 'opener'); act('p2', 'ready_card')
        self.assertEqual(engine.engine_state.get('step'), 'combo')
        return engine

    def pair_offered(self, engine):
        combo = engine.engine_state.get('combo') or {}
        return any(
            action.get('type') == 'play_combo_pair'
            and (action.get('payload') or {}).get('card_instance_ids') == ['first', 'second']
            for action in engine._combo_actions('p1', combo)
        )

    def test_counter_gained_by_first_card_allows_second(self):
        engine = self.build(
            {'op': 'change_counter', 'player': {'controller': True}, 'counter': 'test_charge', 'amount': 1},
            {'op': 'counter_at_least', 'player': {'controller': True}, 'counter': 'test_charge', 'value': 1},
        )
        self.assertTrue(self.pair_offered(engine))

    def test_down_stance_from_first_card_blocks_second(self):
        engine = self.build(
            {'op': 'gain_state', 'player': {'controller': True}, 'state': 'down_stance'},
            {'op': 'not', 'condition': {
                'op': 'has_state', 'player': {'controller': True}, 'state': 'down_stance',
            }},
            filler=True,
        )
        self.assertFalse(self.pair_offered(engine))
        combo = engine.engine_state.get('combo') or {}
        self.assertTrue(any(
            (action.get('payload') or {}).get('card_instance_ids') == ['first', 'filler']
            for action in engine._combo_actions('p1', combo)
        ))
        self.assertFalse(engine.state['players']['p1'].get('passive_state', {}).get('down_stance'))


SAFETY_DISTANCE_TEXT = (
    '게임 시작 시, 사이드 덱에서 루멘 존에 배치한다. '
    '①기술의 사용 시, 상대 기술의 가드 판정이 <-7> 이상이라면 '
    '패에서 수비 기술 1장을 버리고 이 기술을 브레이크할 수 있다. '
    '그 경우, 이번 턴 상대는 추가로 카드를 사용할 수 없다.'
)


class SafetyDistanceLumenTriggerTests(SimpleTestCase):
    """세이프티 디스턴스: 루멘 존에서 자신의 기술 사용 시 유발한다(상대 사용 시에는 아님)."""

    def build(self):
        from .game.drafts import build_effect_draft

        mine = attack('mine', 'p1', code='MINE', frame=5)
        spare = defense('spare', 'p1')
        theirs = attack('theirs', 'p2', code='THEIRS', frame=6)
        theirs['guard'] = '-3'
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
        engine = AutomaticGameEngine.initialize(state, rules, seed='safety-distance', run_startup=False)

        def act(role, kind, pick=None):
            engine.submit_action(role, next(
                a for a in engine.legal_actions(role)
                if a['type'] == kind and (pick is None or a['payload'].get('card_instance_id') == pick)
            )['action_id'])
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card', 'mine'); act('p2', 'ready_card')
        return engine

    def test_own_technique_use_offers_safety_distance_once(self):
        engine = self.build()
        decision = engine.engine_state.get('pending_decision') or {}
        self.assertEqual(decision.get('owner'), 'p1')
        self.assertEqual(decision.get('kind'), 'optional_effect')
        ability = ((decision.get('continuation') or {}).get('item') or {}).get('ability') or {}
        self.assertEqual(ability.get('id'), 'cb03-at-034-n1')
        engine._submit_decision('p1', decision['id'], ['accept'])
        engine._continue()
        choice = engine.engine_state.get('pending_decision') or {}
        self.assertEqual(choice.get('kind'), 'effect_choice')
        engine._submit_decision('p1', choice['id'], ['spare'])
        engine._continue()
        self.assertEqual(engine._find_location('p1-distance')[1], 'break')
        self.assertEqual(engine._find_location('spare')[1], 'list')
        offers = [
            e for e in engine.events
            if e['type'] == 'effect_resolved' and e['payload'].get('ability_id') == 'cb03-at-034-n1'
        ]
        self.assertEqual(len(offers), 1)


class ArmLumenOwnComboOnlyTests(SimpleTestCase):
    """어질리티 핸즈·멧서 슈나이더 ①은 루멘 존에서 자신의 콤보에만 유발한다."""

    TEXTS = {
        'RFS-AT-015': (
            '"L ARM"명을 포함하는 기술은 루멘 존에 1장만 배치할 수 있다.\n'
            '①턴당 1번 콤보 시, 리스트의 <[[character:pinp]]> 기술 '
            '1장을 콤보에 사용할 수 있다.'
        ),
        'RFS-AT-018': (
            '"R ARM"명을 포함하는 기술은 루멘 존에 1장만 배치할 수 있다.\n'
            '①턴당 1번 <[[character:pinp]]> 기술의 콤보 시, 해당 기술에 '
            '이하의 효과를 적용할 수 있다.\n'
            '-해당 기술 데미지+300\n'
            '-사용 후, 해당 기술을 사이드 덱으로 보낸다.'
        ),
    }

    def test_migration_matches_draft_condition(self):
        import importlib

        from .game.drafts import build_effect_draft

        migration = importlib.import_module('card.migrations.0038_arm_lumen_own_combo_only')
        for (code, ability_id), (condition, _old) in migration.CHANGES.items():
            definition = build_effect_draft(code, self.TEXTS[code])
            ability = next(a for a in definition['abilities'] if a['id'] == ability_id)
            self.assertEqual(ability['condition'], condition, code)

    def test_opponent_combo_does_not_offer(self):
        from .game import review

        for runner, code in (
            (review._run_rfs_at_015_combo_scenario, 'RFS-AT-015'),
            (review._run_rfs_at_018_combo_scenario, 'RFS-AT-018'),
        ):
            from .game.drafts import build_effect_draft

            definition = build_effect_draft(code, self.TEXTS[code])
            snapshot = {'code': code, 'name': code, 'type': '특수', 'text': self.TEXTS[code]}
            own = runner(definition, snapshot, 'p1')
            opponent = runner(definition, snapshot, 'p1', event_owner='p2')
            self.assertTrue(own['offered'], code)
            self.assertFalse(opponent['offered'], code)
            self.assertFalse(opponent['resolved'], code)


ENDLESS_BALLARE_TEXT = (
    '이 기술은 자신의 체력이 3000 이하일 경우에만 사용할 수 있다.\n'
    '이 기술은 데미지 보정을 받지 않는다.\n'
    '①사용 시, 이번 턴 리커버리 페이즈 종료 시에 패/리스트/사이드 '
    '덱의 [엔드리스 발라레]를 브레이크한다.\n'
    '②콤보 타임 종료 시, 이하의 효과를 적용한다.\n'
    '-리스트나 배틀 존의 기술을 3장까지 패로 가져올 수 있다.\n'
    '-상대는 리스트에서 기술 1장을 획득할 수 있다.\n\n'
    '-레디 페이즈를 다시 진행한다.'
)


class EndlessBallareReadyRestartFpTests(SimpleTestCase):
    """엔드리스 발라레 ②로 레디를 다시 진행해도 콤보 타임 종료 시 양쪽 FP는 0이 된다(룰 8.4.2)."""

    def test_ready_restart_clears_both_fp(self):
        from .game.drafts import build_effect_draft

        endless = attack('endless', 'p1', code='DFR-AT-020', frame=9, damage=100)
        endless['name'] = '엔드리스 발라레'
        starter = attack('starter', 'p1', code='STARTER')
        opposing = attack('opposing', 'p2', code='OPPOSING')
        state = base_state([], [])
        state['phase'] = 'battle'
        state['players']['p1']['hp'] = 3000
        state['players']['p1']['fp'] = 6
        state['players']['p2']['fp'] = -2
        state['players']['p1']['zones']['battle'] = [starter, endless]
        state['players']['p2']['zones']['battle'] = [opposing]
        release = ruleset(endless, starter, opposing)
        release['cards']['DFR-AT-020']['effect_definition'] = build_effect_draft(
            'DFR-AT-020', ENDLESS_BALLARE_TEXT,
        )
        engine = AutomaticGameEngine(state, release, seed='endless-fp')
        engine.engine_state.update({
            'step': 'combo',
            'combo': {
                'owner': 'p1', 'source': starter['instance_id'],
                'used': [endless['instance_id']], 'next_penalty': 200,
            },
        })
        engine.end_combo()
        engine._continue()
        for _ in range(4):
            decision = engine.engine_state.get('pending_decision')
            if not decision:
                break
            engine._submit_decision(decision['owner'], decision['id'], [])
            engine._continue()

        self.assertEqual(engine.state['phase'], 'ready')
        self.assertEqual(engine.state['players']['p1']['fp'], 0)
        self.assertEqual(engine.state['players']['p2']['fp'], 0)


DIVERTISSEMENT_TEXT = (
    '①콤보 시, [[token:hidden_bond]]카운터 3개가 있을 경우 리스트에서 '
    '사용할 수 있다.\n'
    '②콤보 시, [[token:hidden_bond]]카운터 1개를 소모하고 이 기술 외 '
    '콤보에 사용한 〈발〉 혹은 〈손〉판정 기술 1장을 속도를 무시하고 '
    '이 기술 뒤에 이을 수 있다.\n'
    '그 기술의 사용 후, 콤보 타임을 종료하고 해당 기술을 패로 가져온다.'
)


class DivertissementOwnSpeedTests(SimpleTestCase):
    """디베르티스망 ②의 속도 무시는 뒤에 잇는 기술의 것이다. 자신은 9속 뒤 13속으로 이을 수 없다."""

    def pairs(self, definition):
        one_combo = attack('one', 'p1', frame=3, damage=500, hit='콤보')
        one_combo['body'] = '손'
        diver = attack('diver', 'p1', code='CRS-AT-037', frame=13, damage=400)
        low = attack('low', 'p1', code='LOW', frame=9, damage=400)
        state = base_state([diver, low], [])
        state['phase'] = 'battle'
        state['players']['p1']['zones']['battle'] = [one_combo]
        state['players']['p1']['passive_state']['hidden_bond'] = {'count': 1, 'label': 'hidden_bond'}
        release = ruleset(one_combo, diver, low)
        release['cards']['CRS-AT-037']['effect_definition'] = definition
        engine = AutomaticGameEngine.initialize(state, release, seed='divertissement-speed')
        engine.state['phase'] = 'battle'
        engine.grant_combo('p1', source=one_combo['instance_id'])
        return [
            action['payload']['card_instance_ids']
            for action in engine._combo_actions('p1', engine.engine_state['combo'])
            if action['type'] == 'play_combo_pair'
        ]

    def test_cannot_follow_nine_speed_but_reuse_pair_remains(self):
        from .game.drafts import build_effect_draft

        definition = build_effect_draft('CRS-AT-037', DIVERTISSEMENT_TEXT)
        self.assertFalse(any(rule.get('ignore_speed') for rule in definition['combo_rules']))
        pairs = self.pairs(definition)
        self.assertNotIn(['low', 'diver'], pairs)
        self.assertIn(['diver', 'one'], pairs)  # Q&A 643: 디베르티스망 → 손/발 기술 재사용

    def test_migration_removes_own_ignore_speed(self):
        import importlib

        from .game.drafts import build_effect_draft

        migration = importlib.import_module('card.migrations.0039_divertissement_own_speed')
        definition = build_effect_draft('CRS-AT-037', DIVERTISSEMENT_TEXT)
        legacy = [*definition['combo_rules'], {'ignore_speed': True, 'numbered_effect': True}]
        self.assertEqual(migration.fixed_rules(legacy), definition['combo_rules'])


class MujinActivationAndBreakTests(SimpleTestCase):
    """음양순환극 무진: 3000 이하면 유발 타이밍마다 적용을 고르고, 브레이크는 모든 유발이 끝난 뒤 본다."""

    def build(self, *, yin=0, yang=1, hp=3000):
        from .game.drafts import build_effect_draft
        from .game.review import _cb01_at_025_bagua_definition

        mujin = {
            'instance_id': 'p1-mujin', 'kind': 'card', 'owner': 'p1', 'code': 'CB01-AT-025',
            'name': '음양순환극 무진', 'type': '특수', 'ultimate': True, 'face_up': True,
        }
        bagua = {
            'instance_id': 'p1-bagua', 'kind': 'card', 'owner': 'p1', 'code': 'UNC-PS-001',
            'name': '팔괘엔진', 'type': '특성', 'face_up': True,
        }
        opposing = attack('opposing', 'p2', code='OPPOSING')
        state = base_state([], [opposing])
        state['phase'] = 'battle'
        state['players']['p1']['zones']['ultimate'] = [mujin]
        state['players']['p1']['zones']['passive'] = [bagua]
        state['players']['p1']['hp'] = hp
        state['players']['p1']['passive_state']['yin'] = {'count': yin}
        state['players']['p1']['passive_state']['yang'] = {'count': yang}
        rules = ruleset(opposing)
        rules['cards']['CB01-AT-025'] = {**mujin, 'effect_definition': build_effect_draft('CB01-AT-025', '검토용 원문')}
        rules['cards']['UNC-PS-001'] = {**bagua, 'effect_definition': _cb01_at_025_bagua_definition()}
        engine = AutomaticGameEngine(state, rules, seed='mujin-activation')
        engine.state['phase'] = 'battle'
        return engine

    def tao_hit(self, engine, frame=8):
        tao = attack('tao', 'p1', code='TAO', frame=frame)
        tao['character_key'] = 'tao'
        engine._fire('damage_after', {
            'controller': 'p1', 'player': 'p2', 'amount': 300,
            'source_card_instance_id': 'tao', 'source_card': tao, 'event_card': tao,
        })
        engine._continue()

    def decide(self, engine, pick):
        decision = engine.engine_state['pending_decision']
        option = next(option['id'] for option in decision['options'] if pick(option))
        engine._submit_decision(decision['owner'], decision['id'], [option])
        engine._continue()
        return decision

    def counters(self, engine):
        state = engine.state['players']['p1']['passive_state']
        return state['yin']['count'], state['yang']['count']

    def test_activate_first_then_choose_yin_does_not_break(self):
        engine = self.build()
        self.tao_hit(engine)
        order = self.decide(engine, lambda option: 'cb01' in str(option.get('label')) or '무진' in str(option.get('label')))
        # 순서 선택에서 임의 효과(무진 적용)를 먼저 고르면 그 효과를 발동한 것이다.
        self.assertEqual(order['kind'], 'effect_order')
        self.assertTrue(engine.state['players']['p1']['passive_state']['mujin_active']['value'])
        self.assertIsNotNone(engine._find_card('p1-mujin', owner='p1', zone='ultimate'))  # 적용 직후 브레이크 안 됨
        self.decide(engine, lambda option: option['id'] == 'yin')
        self.assertEqual(self.counters(engine), (1, 1))
        self.assertIsNone(engine.engine_state.get('pending_decision'))
        self.assertIsNotNone(engine._find_card('p1-mujin', owner='p1', zone='ultimate'))

    def test_declining_offers_again_and_accepting_stops_offers(self):
        engine = self.build(yin=1, yang=1)
        engine._fire('phase_start', {'phase': 'battle'})
        engine._continue()
        self.decide(engine, lambda option: option['id'] == 'decline')
        self.assertFalse(engine.state['players']['p1']['passive_state'].get('mujin_active'))
        engine._fire('phase_start', {'phase': 'battle'})
        engine._continue()
        self.decide(engine, lambda option: option['id'] == 'accept')
        self.assertTrue(engine.state['players']['p1']['passive_state']['mujin_active']['value'])
        engine._fire('phase_start', {'phase': 'battle'})
        engine._continue()
        self.assertIsNone(engine.engine_state.get('pending_decision'))

    def test_active_mujin_breaks_after_triggers_when_counter_is_zero(self):
        engine = self.build(yin=1, yang=1)
        engine.state['players']['p1']['passive_state']['mujin_active'] = {'value': True}
        engine.change_counter('p1', 'yin', -1)
        engine._continue()
        self.assertIsNotNone(engine._find_card('p1-mujin', owner='p1', zone='break'))


class NegatedNumberedRootComboRuleTests(SimpleTestCase):
    """번호 효과만 쓰는 루트 combo_rules(라이! 레피! 로켓! ②)는 키메라가 가져와 번호 효과가 무효면 적용하지 않는다."""

    def build(self, negated):
        opener = attack('opener', 'p1', frame=8, hit='콤보')
        first = attack('first', 'p1', code='FIRST', frame=12, damage=600)
        rocket = attack('rocket', 'p1', code='ROCKET', frame=13, damage=1200)
        if negated:
            rocket['numbered_effects_negated'] = True
        guard = defense('guard', 'p2', top=None, mid=None, bottom=None)
        rules = ruleset(opener, first, rocket, guard)
        rules['cards']['ROCKET']['effect_definition'] = {
            'abilities': [{
                'id': 'rocket-n2', 'kind': 'effect', 'mode': 'mandatory', 'timing': 'combo',
                'visibility': 'public', 'trigger': {'event': 'combo'},
                'effects': [{'op': 'static_rule', 'rules': ['combo_rules']}],
            }],
            'combo_rules': [{'min_combo': 4, 'damage_bonus': -400}],
        }
        engine = AutomaticGameEngine.initialize(
            base_state([opener, first, rocket], [guard]), rules,
            seed='negated-root-combo-rule', run_startup=False,
        )
        for role, kind, pick in (('p1', 'pass_phase', None), ('p2', 'pass_phase', None),
                                 ('p1', 'ready_card', 'opener'), ('p2', 'ready_card', None)):
            engine.submit_action(role, next(
                a for a in engine.legal_actions(role)
                if a['type'] == kind and (pick is None or a['payload'].get('card_instance_id') == pick)
            )['action_id'])
        return engine

    def pair_offered(self, engine):
        combo = engine.engine_state.get('combo') or {}
        return any(
            (action.get('payload') or {}).get('card_instance_ids') == ['first', 'rocket']
            for action in engine._combo_actions('p1', combo)
        )

    def test_negated_numbered_restriction_is_ignored(self):
        engine = self.build(negated=True)
        self.assertEqual(engine.engine_state.get('step'), 'combo')
        self.assertTrue(self.pair_offered(engine))

    def test_restriction_applies_without_negation(self):
        engine = self.build(negated=False)
        self.assertFalse(self.pair_offered(engine))


PROVIDENCE_TEXT = (
    '루멘 존의 이 기술은 다른 기술의 효과를 받지 않는다.\n'
    '이 기술을 덱에 편성할 경우, 특수 기술은 [[character:chimera]]의 기술만 편성할 수 있다. \n'
    '게임 시작 시, 사이드 덱에서 루멘 존에 배치한다. \n'
    '①이 기술이 루멘 존에 있는 동안 이하의 효과를 적용한다. \n'
    '- 자신의 기술이 브레이크 될 때마다 리스트에서 1장을 획득할 수 있다. '
    '이 효과는 콤보 타임 중에는 적용하지 않는다. \n'
    '-패  매수 상한이 1장 늘어난다.'
)


class ProvidenceOneComboAfterUseBreakTests(SimpleTestCase):
    """콤보 판정이 난 1콤보 기술의 사용 후 브레이크는 콤보 타임 중이라 섭리의 궤가 유발되지 않는다(8.1.1)."""

    def run_battle(self, hit):
        from .game.drafts import build_effect_draft

        mine = attack('mine', 'p1', code='MINE', frame=5, damage=300, hit=hit)
        mine['break_after_use'] = True
        listed = attack('listed', 'p1', code='LISTED', frame=9)
        guard = defense('guard', 'p2', top=None, mid=None, bottom=None)
        providence = {
            'instance_id': 'p1-providence', 'kind': 'card', 'owner': 'p1',
            'code': 'CB02-AT-002', 'name': '섭리의 궤', 'type': '특수', 'face_up': True,
        }
        state = base_state([mine], [guard])
        state['players']['p1']['zones']['list'] = [listed]
        state['players']['p1']['zones']['lumen'] = [providence]
        rules = ruleset(mine, listed, guard)
        rules['cards']['CB02-AT-002'] = {
            **providence, 'effect_definition': build_effect_draft('CB02-AT-002', PROVIDENCE_TEXT),
        }
        engine = AutomaticGameEngine.initialize(state, rules, seed='providence-one-combo', run_startup=False)
        for role, kind, pick in (('p1', 'pass_phase', None), ('p2', 'pass_phase', None),
                                 ('p1', 'ready_card', 'mine'), ('p2', 'ready_card', None)):
            engine.submit_action(role, next(
                a for a in engine.legal_actions(role)
                if a['type'] == kind and (pick is None or a['payload'].get('card_instance_id') == pick)
            )['action_id'])
        self.assertIsNotNone(engine._find_card('mine', owner='p1', zone='break'))
        return engine

    def providence_offered(self, engine):
        return any(
            event.get('type') == 'decision_requested'
            and (event.get('payload') or {}).get('kind') == 'optional_effect'
            for event in engine.events
        )

    def test_one_combo_after_use_break_does_not_offer(self):
        engine = self.run_battle('콤보')
        self.assertFalse(self.providence_offered(engine))
        self.assertFalse(engine.engine_state.get('combo_time'))

    def test_normal_hit_after_use_break_still_offers(self):
        engine = self.run_battle('2')
        self.assertTrue(self.providence_offered(engine))


TEMPO_DE_DEUX_TEXT = (
    '①1턴에 1번 콤보 시, [[token:hidden_bond]]카운터가 있을 경우 배틀 존의 이 기술을 '
    '다른 <[[character:viola]]> 기술 뒤에 속도를 무시하고 이을 수 있다. \n'
    '②이 기술이 한 턴에 두 번 이상 사용되었을 경우, 이 기술은 데미지 보정을 적용하지 않는다.'
)


class TempoDeDeuxRepeatUseWaiverTests(SimpleTestCase):
    """템포 드 두 ②: 이번 턴 첫 사용이면 콤보 데미지 보정을 그대로 받는다."""

    def combo_damage(self, *, used_before):
        from .game.drafts import build_effect_draft

        opener = attack('opener', 'p1', frame=8, hit='콤보')
        mid = attack('mid', 'p1', code='MID', frame=5, damage=400)
        tempo = attack('tempo', 'p1', code='CB02-AT-026', frame=6, damage=300)
        guard = defense('guard', 'p2', top=None, mid=None, bottom=None)
        rules = ruleset(opener, mid, tempo, guard)
        rules['cards']['CB02-AT-026']['effect_definition'] = build_effect_draft(
            'CB02-AT-026', TEMPO_DE_DEUX_TEXT,
        )
        engine = AutomaticGameEngine.initialize(
            base_state([opener, mid, tempo], [guard]), rules,
            seed='tempo-de-deux-waiver', run_startup=False,
        )

        def act(role, kind, pick=None):
            engine.submit_action(role, next(
                a for a in engine.legal_actions(role)
                if a['type'] == kind and (pick is None or a['payload'].get('card_instance_id') == pick)
            )['action_id'])
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card', 'opener'); act('p2', 'ready_card')
        self.assertEqual(engine.engine_state.get('step'), 'combo')
        if used_before:
            engine._mark_card_used(engine._find_card('tempo'), 'p1', 'ready')
        pair = next(
            a for a in engine._combo_actions('p1', engine.engine_state['combo'])
            if a['type'] == 'play_combo_pair'
            and a['payload']['card_instance_ids'] == ['mid', 'tempo']
        )
        payload = pair['payload']
        first = next(
            a for a in engine.legal_actions('p1')
            if a['type'] == 'select_combo_first'
            and a['payload']['card_instance_id'] == 'mid'
            and a['payload']['combo_speed'] == payload['combo_speeds'][0]
        )
        engine.submit_action('p1', first['action_id'])
        engine.submit_action('p1', next(
            a for a in engine.legal_actions('p1')
            if a['type'] == 'select_combo_followup' and a['payload'].get('proposal') == payload
        )['action_id'])
        damages = [
            e['payload']['amount'] for e in engine.events
            if e['type'] == 'damage_dealt' and e['payload'].get('target') == 'p2'
        ]
        return damages[-1]

    def test_first_use_keeps_three_combo_penalty(self):
        self.assertEqual(self.combo_damage(used_before=False), 100)

    def test_second_use_ignores_penalty(self):
        self.assertEqual(self.combo_damage(used_before=True), 300)


class StateEffectTechniqueFilterTests(SimpleTestCase):
    """「X」 효과가 있는 기술은 효과 번호 바로 뒤에 상태 조건이 붙은 기술(①[[state:x]]:)이다."""

    GRAND_LEGIONS = (
        '①사용 시, 패 4장까지 버리고 해당 기술에 있는 효과에 따라 이하의 효과를 각각 1번씩 적용할 수 있다.\n'
        '-[[state:saintess]]: 사용 후, 리스트에서 기술 2장을 획득한다.\n'
        '-[[state:guardian]]: 이 기술 데미지+200'
    )
    PROMISED_VICTORY = (
        '①[[state:paladin]]: 판정 전, 패에서 [[state:guardian]]효과가 있는 기술을 1장 버린다면 이 기술의 데미지+200\n '
        '②[[state:paladin]]: 콤보 시, 리스트에서 [[state:saintess]]효과가 있는 기술 1장을 사용할 수 있다.'
    )

    def matches(self, text, where):
        from .game.effects import card_matches

        return card_matches({'type': '공격', 'text': text}, {'is_technique': True, **where}, {}, {})

    def test_bullet_branch_is_not_a_state_effect(self):
        self.assertFalse(self.matches(self.GRAND_LEGIONS, {'text_contains': '[[state:saintess]]'}))
        self.assertFalse(self.matches(self.GRAND_LEGIONS, {
            'text_contains_any': ['[[state:paladin]]', '[[state:saintess]]'],
        }))

    def test_mentioned_state_is_not_a_state_effect(self):
        self.assertFalse(self.matches(self.PROMISED_VICTORY, {'text_contains': '[[state:guardian]]'}))
        self.assertTrue(self.matches(self.PROMISED_VICTORY, {'text_contains': '[[state:paladin]]'}))

    def test_numbered_state_effect_matches(self):
        self.assertTrue(self.matches('①[[state:saintess]]: 캐치 시, <5속도>로 사용할 수 있다', {
            'text_contains': '[[state:saintess]]',
        }))
        self.assertTrue(self.matches('① [[state:dark_night]] : 이 기술 데미지+200', {
            'text_contains': '[[state:dark_night]]',
        }))
        self.assertFalse(self.matches('①[[state:saintess]]: 효과', {
            'text_not_contains': '[[state:saintess]]',
        }))

    def test_replacement_line_is_not_a_state_effect(self):
        self.assertFalse(self.matches(
            '①캐치 시, <9속도>로 사용할 수 있다.\n[[state:assassin]] : 대신 1FP를 얻는다.',
            {'text_contains': '[[state:assassin]]'},
        ))

    def test_other_markers_stay_literal(self):
        self.assertTrue(self.matches('[[token:drum]] 카운터', {'text_contains': '[[token:drum]]'}))


class BattleJudgmentVisibleOnBoardTests(SimpleTestCase):
    """인스턴트 스매시 ①: 판정 전 히트 판정 변경이 배틀 존 카드(화면)에도 보이고, 배틀 후 되돌아간다."""

    TEXT = (
        '①[[state:charge]]: 판정 전, 이 기술의 속도를 7로 고정한다, 그 후 이하의 효과를 적용한다.\n'
        '-이 기술의 데미지-100, 히트 판정을 <+3>로 변경한다.\n'
        '②상쇄 시, 자신의 패 1장을 브레이크한다.'
    )

    def test_hit_change_is_on_battle_zone_card_then_restored(self):
        from .game.drafts import build_effect_draft

        smash = attack('smash', 'p1', code='UNC-AT-017', frame=8, damage=400)
        smash.update({'hit': '4', 'counter': '4', 'guard': '-6'})
        foe = defense('foe', 'p2', top=None, bottom='방어')
        state = base_state([smash], [foe])
        state['players']['p1']['passive_state']['charge'] = {'value': True}
        rules = ruleset(smash, foe)
        rules['cards']['UNC-AT-017']['effect_definition'] = build_effect_draft('UNC-AT-017', self.TEXT)
        engine = AutomaticGameEngine.initialize(state, rules, seed='smash-board-hit', run_startup=False)
        seen = []
        fire = engine._fire

        def spy(event, *args, **kwargs):
            if event == 'hit':
                seen.append(engine._find_card('smash', owner='p1', zone='battle').get('hit'))
            return fire(event, *args, **kwargs)
        engine._fire = spy
        act = lambda role, kind: engine.submit_action(role, next(
            a for a in engine.legal_actions(role) if a['type'] == kind)['action_id'])
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card'); act('p2', 'ready_card')
        self.assertEqual(seen, ['+3'])
        self.assertEqual(engine.state['players']['p1']['fp'], 3)
        self.assertEqual(engine._find_card('smash').get('hit'), '4')


class BaguaReconcileQuietTests(SimpleTestCase):
    """팔괘엔진 상태 갱신은 바뀌는 상태가 있을 때만 발동으로 남는다(레디·유발마다 연출 반복 방지)."""

    def build(self, *, yin=0, yang=0):
        bagua = {
            'instance_id': 'p1-bagua', 'kind': 'card', 'owner': 'p1', 'code': 'UNC-PS-001',
            'name': '팔괘엔진', 'type': '특성', 'face_up': True,
        }
        opposing = attack('opposing', 'p2', code='OPPOSING')
        state = base_state([], [opposing])
        state['players']['p1']['zones']['passive'] = [bagua]
        # 게임 시작 때 한 번 갱신된 뒤의 상태(값이 기록된 상태)에서 시작한다.
        state['players']['p1']['passive_state']['yin'] = {'count': yin, 'value': False}
        state['players']['p1']['passive_state']['yang'] = {'count': yang, 'value': False}
        rules = ruleset(opposing)
        rules['cards']['UNC-PS-001'] = {**bagua, 'effect_definition': {
            'schema_version': 1, 'reviewed': True,
            'source_refs': {'rulebook_pages': [], 'qna_ids': []},
            'abilities': [{
                'id': 'unc-ps-001-state-reconcile', 'label': '음·양 카운터에 따른 상태 갱신',
                'kind': 'effect', 'mode': 'mandatory', 'timing': 'result',
                'visibility': 'public', 'active_zones': ['passive'],
                'trigger': {'event': 'counter_changed', 'events': ['game_start', 'card_moved', 'counter_changed']},
                'handler': 'tao_bagua_reconcile',
            }],
        }}
        return AutomaticGameEngine(state, rules, seed='bagua-quiet')

    def resolved(self, engine):
        return [
            event for event in engine.events
            if event.get('type') == 'effect_resolved' and event.get('payload', {}).get('ability_id') == 'unc-ps-001-state-reconcile'
        ]

    def test_counter_change_that_flips_state_resolves_once_then_stays_quiet(self):
        engine = self.build()
        engine.change_counter('p1', 'yin', 1)
        engine._continue()
        self.assertTrue(engine.state['players']['p1']['passive_state']['yin']['value'])
        self.assertEqual(len(self.resolved(engine)), 1)
        # 상태가 그대로인 카드 이동·카운터 변화에서는 발동하지 않는다.
        engine._fire('card_moved', {'controller': 'p1', 'player': 'p1'})
        engine._continue()
        engine.change_counter('p1', 'yin', 1)
        engine._continue()
        self.assertEqual(len(self.resolved(engine)), 1)
        self.assertTrue(engine.state['players']['p1']['passive_state']['yin']['value'])
        # 다시 같아지면 음 상태가 풀리면서 한 번 발동한다.
        engine.change_counter('p1', 'yang', 2)
        engine._continue()
        self.assertFalse(engine.state['players']['p1']['passive_state']['yin']['value'])
        self.assertEqual(len(self.resolved(engine)), 2)

    def test_no_state_change_without_counters(self):
        engine = self.build()
        engine._fire('card_moved', {'controller': 'p1', 'player': 'p1'})
        engine._continue()
        self.assertEqual(self.resolved(engine), [])


class DefenseJudgmentComparisonTests(SimpleTestCase):
    """수비 기술의 히트·가드·카운터 판정은 비교 조건을 항상 만족하지 않는다(인쇄값이 0이어도)."""

    SAFETY_DISTANCE = (
        '게임 시작 시, 사이드 덱에서 루멘 존에 배치한다. ①기술의 사용 시, 상대 기술의 가드 판정이 '
        '<-7> 이상이라면 패에서 수비 기술 1장을 버리고 이 기술을 브레이크할 수 있다. '
        '그 경우, 이번 턴 상대는 추가로 카드를 사용할 수 없다.'
    )
    STEEL_FAITH = (
        '①[[state:guardian]]: 판정 전, 이하의 효과를 적용한다.\n'
        ' -<8속도 이상 중단 상쇄>특수 판정을 추가한다.\n'
        ' -상쇄 시, 상대 기술의 히트 판정이 <콤보>일 경우, 그 판정을 <+4>로 변경한다.\n'
        ' ②상쇄 시, 상대 기술의 히트 판정이 <+6> 이상일 경우 그 판정을 <+4>로 변경한다.'
    )

    def condition(self, code, text, ability_id):
        from .game.drafts import build_effect_draft

        definition = build_effect_draft(code, text)
        return next(a for a in definition['abilities'] if a['id'] == ability_id)['condition']

    def matches(self, condition, opponent_card):
        from .game.effects import condition_matches

        context = {'controller': 'p1', 'event_controller': 'p1', 'opponent_card': opponent_card}
        return condition_matches(condition, {'players': {}}, context)

    def test_safety_distance_ignores_defense_opponent(self):
        condition = self.condition('CB03-AT-034', self.SAFETY_DISTANCE, 'cb03-at-034-n1')
        self.assertTrue(self.matches(condition, {**attack('a', 'p2'), 'guard': '-3'}))
        self.assertFalse(self.matches(condition, {**attack('a', 'p2'), 'guard': '-8'}))
        self.assertFalse(self.matches(condition, defense('d', 'p2')))

    def test_steel_faith_hit_comparison_ignores_defense_opponent(self):
        from .game.effects import condition_matches

        gte = {'op': 'gte', 'left': 'context.opponent_card.hit', 'right': 6}
        self.assertTrue(self.matches(gte, attack('a', 'p2', hit='+6')))
        self.assertFalse(self.matches(gte, {**defense('d', 'p2'), 'hit': '+6'}))
        # 비교 대상이 오른쪽에 있어도, 판정이 아닌 수비 기술 값은 그대로 비교한다.
        right = {'op': 'lte', 'left': -7, 'right': {'path': 'context.opponent_card.guard'}}
        self.assertFalse(condition_matches(right, {}, {'opponent_card': defense('d', 'p2')}))
        self.assertTrue(condition_matches(
            {'op': 'equals', 'left': 'context.opponent_card.type', 'right': '수비'},
            {}, {'opponent_card': defense('d', 'p2')},
        ))
        steel = self.condition('LMI-AT-009', self.STEEL_FAITH, 'lmi-at-009-n2')
        self.assertFalse(self.matches(steel, {**defense('d', 'p2'), 'hit': '+6'}))


class BitterColdContinuousComboTests(SimpleTestCase):
    """혹한: 루멘 존에 있는 동안 콤보에 쓰인 부쿠키 기술 데미지 +100. 콤보마다 유발·중첩하지 않는다."""

    def test_real_combo_adds_100_once_per_card_without_activation(self):
        from .game.drafts import build_effect_draft

        def bukuki(card):
            card['character_key'] = '부쿠키'
            return card

        cold = bukuki(attack('cold', 'p1', code='CB04-AT-012', frame=14, damage=600))
        opener = bukuki(attack('opener', 'p1', frame=8, hit='콤보', damage=400))
        mid = bukuki(attack('mid', 'p1', code='MID', frame=5, damage=400))
        last = bukuki(attack('last', 'p1', code='LAST', frame=6, damage=400))
        guard = defense('guard', 'p2', top=None, mid=None, bottom=None)
        rules = ruleset(cold, opener, mid, last, guard)
        rules['cards']['CB04-AT-012']['effect_definition'] = build_effect_draft('CB04-AT-012', '')
        state = base_state([opener, mid, last], [guard])
        state['players']['p1']['zones']['lumen'] = [cold]
        engine = AutomaticGameEngine.initialize(state, rules, seed='bitter-cold-real-combo', run_startup=False)

        def act(role, kind, pick=None):
            engine.submit_action(role, next(
                a for a in engine.legal_actions(role)
                if a['type'] == kind and (pick is None or a['payload'].get('card_instance_id') == pick)
            )['action_id'])
        act('p1', 'pass_phase'); act('p2', 'pass_phase')
        act('p1', 'ready_card', 'opener'); act('p2', 'ready_card')
        self.assertEqual(engine.engine_state.get('step'), 'combo')
        pair = next(
            a for a in engine._combo_actions('p1', engine.engine_state['combo'])
            if a['type'] == 'play_combo_pair'
            and a['payload']['card_instance_ids'] == ['mid', 'last']
        )
        payload = pair['payload']
        engine.submit_action('p1', next(
            a for a in engine.legal_actions('p1')
            if a['type'] == 'select_combo_first'
            and a['payload']['card_instance_id'] == 'mid'
            and a['payload']['combo_speed'] == payload['combo_speeds'][0]
        )['action_id'])
        engine.submit_action('p1', next(
            a for a in engine.legal_actions('p1')
            if a['type'] == 'select_combo_followup' and a['payload'].get('proposal') == payload
        )['action_id'])
        damages = [
            e['payload']['amount'] for e in engine.events
            if e['type'] == 'damage_dealt' and e['payload'].get('target') == 'p2'
        ]
        # 시동 400+100, 2콤보 400+100-100, 3콤보 400+100-200: 카드마다 한 번씩만 +100.
        self.assertEqual(damages, [500, 400, 300])
        self.assertFalse([
            e for e in engine.events
            if e['type'] in {'effect_resolved', 'decision_requested'}
            and e['payload'].get('card_code') == 'CB04-AT-012'
        ])


def _combo_engine(p1_zones, p2_cards, cards, *, definitions=None, seed='combo-fix'):
    state = base_state([], p2_cards)
    state['players']['p1']['zones'].update(p1_zones)
    rules = ruleset(*cards, *p2_cards)
    for code, definition in (definitions or {}).items():
        rules['cards'][code]['effect_definition'] = definition
    return AutomaticGameEngine.initialize(state, rules, seed=seed, run_startup=False)


def _act(engine, role, kind, pick=None):
    engine.submit_action(role, next(
        a for a in engine.legal_actions(role)
        if a['type'] == kind and (pick is None or a['payload'].get('card_instance_id') == pick)
    )['action_id'])


class AnySpeedComboWindowTests(SimpleTestCase):
    """호신장 ②: 원하는 속도로 사용해도 3콤보 이후에는 직전 속도 +1 연결 규칙을 따른다."""

    def test_any_speed_after_three_combo_keeps_link_window(self):
        guard = attack('guard', 'p1', code='UNC-AT-004', frame=8, damage=200)
        engine = _combo_engine(
            {'hand': [guard]}, [], [guard],
            definitions={'UNC-AT-004': {
                'schema_version': 1, 'abilities': [],
                'combo_rules': [{'any_speed': True, 'numbered_effect': True}],
            }},
        )
        combo = {'owner': 'p1', 'used': ['a', 'b'], 'last_speed': 6}
        self.assertEqual(engine._combo_speed_options('p1', guard, combo), [7])
        # 2콤보 첫 기술은 직전 속도가 없으므로 원하는 속도를 고를 수 있다.
        self.assertIn(3, engine._combo_speed_options('p1', guard, {'owner': 'p1', 'used': []}))


class DownStanceTests(SimpleTestCase):
    """다운 스탠스: "②[[state:down_stance]] :"처럼 콜론 앞에 공백이 있어도 상태 효과가 있는 기술이다."""

    TRAIT = (
        '자신의 <상단 회피> 및 <하단> 위치 판정 기술 사용 후 [[state:down_stance]]상태가 된다.\n'
        '[[state:down_stance]] 상태인 경우 [[state:down_stance]] 상태 효과가 없는 기술을 사용할 때 1속도가 느려진다.\n'
        '<상단 회피> 및 <하단> 위치 판정 이외 기술 사용 후 [[state:down_stance]] 상태가 해제된다.'
    )

    def test_spaced_marker_counts_as_down_stance_effect(self):
        from .game.effects import card_matches

        kick = {'kind': 'card', 'type': '공격', 'text': '①상대 회피 시 3FP\n②[[state:down_stance]] : 이 기술 데미지+200'}
        plain = {'kind': 'card', 'type': '공격', 'text': '①히트 시 1FP'}
        where = {'kind': 'card', 'text_not_contains': '[[state:down_stance]]:'}
        self.assertFalse(card_matches(kick, where))
        self.assertTrue(card_matches(plain, where))

    def test_pair_follow_up_speed_reflects_down_stance_from_first_card(self):
        from .game.drafts import build_effect_draft

        trait = {
            'instance_id': 'ds', 'kind': 'card', 'owner': 'p1', 'code': 'ST3-PS1',
            'name': '다운 스탠스', 'type': '특성', 'face_up': True,
        }
        toss = attack('toss', 'p1', code='TOSS', frame=7, damage=400, position='하단')
        funky = attack('funky', 'p1', code='FUNKY', frame=8, damage=400)
        funky['text'] = '①[[state:down_stance]]: 이 기술의 속도가 2 빨라진다.'
        kick = attack('kick', 'p1', code='KICK', frame=6, damage=400)
        foe = attack('foe', 'p2', code='FOE', frame=14)
        opener = attack('opener', 'p1', code='OPENER', frame=5, hit='콤보', counter='콤보')
        engine = _combo_engine(
            {'hand': [opener, toss, funky, kick], 'passive': [trait]}, [foe],
            [toss, funky, kick, opener],
            definitions={
                'FUNKY': {'schema_version': 1, 'abilities': [{
                    'id': 'funky-n1', 'kind': 'effect', 'mode': 'continuous',
                    'timing': 'function', 'active_zones': ['battle'],
                    'condition': {'op': 'has_state', 'player': {'controller': True}, 'state': 'down_stance'},
                    'effects': [{'op': 'modify_stat', 'player': {'controller': True}, 'stat': 'frame',
                                 'amount': -2, 'duration': 'continuous'}],
                }]},
            },
        )
        engine.ruleset['cards']['ST3-PS1'] = {
            **trait, 'effect_definition': build_effect_draft('ST3-PS1', self.TRAIT),
        }
        engine._refresh_continuous_rules()
        _act(engine, 'p1', 'pass_phase')
        _act(engine, 'p2', 'pass_phase')
        _act(engine, 'p1', 'ready_card', 'opener')
        _act(engine, 'p2', 'ready_card')
        pairs = {
            tuple(a['payload']['card_instance_ids']): a['payload']['combo_speeds']
            for a in engine._combo_actions('p1', engine.engine_state['combo'])
        }
        # Q&A 149: 다운 토스(하단) 뒤의 펑키정키는 다운 스탠스로 6속도가 되어 이을 수 없다.
        self.assertNotIn(('toss', 'funky'), pairs)
        self.assertEqual(pairs.get(('kick', 'toss')), [6, 7])


class SelfBreakingComboCardTests(SimpleTestCase):
    """도펠슈베르터 츠바이: 「콤보 시」 효과로 자신을 브레이크해도 콤보 타임은 끝나지 않는다."""

    def test_combo_continues_after_card_breaks_itself(self):
        opener = attack('opener', 'p1', code='OPENER', frame=5, hit='콤보', counter='콤보')
        first = attack('first', 'p1', code='FIRST', frame=6, damage=300)
        breaker = attack('breaker', 'p1', code='BREAKER', frame=7, damage=300)
        fourth = attack('fourth', 'p1', code='FOURTH', frame=8, damage=400)
        foe = attack('foe', 'p2', code='FOE', frame=14)
        engine = _combo_engine(
            {'hand': [opener, first, breaker, fourth]}, [foe], [opener, first, breaker, fourth],
            definitions={'BREAKER': {'schema_version': 1, 'abilities': [{
                'id': 'breaker-n1', 'kind': 'effect', 'mode': 'mandatory', 'timing': 'combo',
                'active_zones': ['battle'], 'trigger': {'event': 'combo'},
                'effects': [{'op': 'break_card', 'card_instance_id': {'path': 'context.source_card_instance_id'}}],
            }]}},
        )
        _act(engine, 'p1', 'pass_phase')
        _act(engine, 'p2', 'pass_phase')
        _act(engine, 'p1', 'ready_card', 'opener')
        _act(engine, 'p2', 'ready_card')
        _act(engine, 'p1', 'select_combo_first', 'first')
        _act(engine, 'p1', 'select_combo_followup', 'breaker')
        self.assertEqual(engine.engine_state.get('step'), 'combo')
        self.assertEqual(engine._find_location('breaker')[1], 'break')
        self.assertTrue(any(
            a['type'] == 'play_combo_card' and a['payload']['card_instance_id'] == 'fourth'
            for a in engine.legal_actions('p1')
        ))


class LumenComboGrantWithoutLimitTests(SimpleTestCase):
    """블리자드 ③: 루멘 존의 부쿠키 기술 사용 허가에는 장수 제한이 없다."""

    def test_draft_grant_has_no_usage_key(self):
        from .game.drafts import build_effect_draft

        for code in ('CB04-AT-007', 'CB04-AT-005'):
            definition = build_effect_draft(code, '')
            grants = [
                effect for ability in definition['abilities']
                for effect in ability.get('effects') or []
                if effect.get('op') == 'modify_combo' and 'lumen' in (effect.get('allow_zones') or [])
            ]
            self.assertTrue(grants, code)
            self.assertTrue(all('usage_key' not in grant for grant in grants), code)

    def test_two_lumen_cards_can_link(self):
        cards = [
            attack(f'l{frame}', 'p1', code=f'L{frame}', frame=frame) for frame in (5, 6)
        ]
        for card in cards:
            card['character_key'] = '부쿠키'
            card['face_up'] = True
        engine = _combo_engine({'lumen': cards}, [], cards)
        engine.engine_state['modifiers'] = [{
            'op': 'modify_combo', 'player': 'p1', 'controller': 'p1',
            'allow_zones': ['lumen'], 'where': {'character_key': '부쿠키', 'is_technique': True},
            'duration': 'turn', 'source': 'bliz',
        }]
        combo = {'owner': 'p1', 'source': 'bliz', 'used': [], 'next_penalty': 100}
        proposals = [a['payload']['card_instance_ids'] for a in engine._combo_actions('p1', combo)]
        self.assertIn(['l5', 'l6'], proposals)


class BreakZoneOwnSpeedGrantTests(SimpleTestCase):
    """나찰파쇄열권 ②: <8속도 이하> 허가는 자기 효과로 6~8속도로 쓸 수 있는 폭염천뢰도 포함한다."""

    def test_twelve_speed_card_with_six_to_eight_option_is_usable_at_those_speeds(self):
        bakuen = attack('bakuen', 'p1', code='CB04-AT-024', frame=12, damage=500)
        bakuen.update({'character_key': 'rin', 'face_up': True})
        engine = _combo_engine(
            {'break': [bakuen]}, [], [bakuen],
            definitions={'CB04-AT-024': {
                'schema_version': 1, 'abilities': [],
                'combo_rules': [{'speed_options': [6, 7, 8], 'numbered_effect': True}],
            }},
        )
        engine.engine_state['modifiers'] = [{
            'op': 'modify_combo', 'player': 'p1', 'controller': 'p1',
            'allow_zones': ['break'], 'where': {'character_key': 'rin', 'frame_lte': 8},
            'ignore_speed': True, 'duration': 'turn', 'source': 'rasetsu',
        }]
        combo = {'owner': 'p1', 'source': 'rasetsu', 'used': ['a', 'b'], 'last_speed': 9, 'next_penalty': 300}
        self.assertTrue(engine._combo_zone_allowed('p1', bakuen, 'break', combo))
        self.assertEqual(engine._combo_speed_options('p1', bakuen, combo), [6, 7, 8])


class AddedSpecialSpeedLimitTests(SimpleTestCase):
    """호버 부스터: 덧붙인 "9속도 이하 하단 회피"는 10속도 기술을 회피하지 않는다."""

    def test_speed_bound_in_added_special(self):
        from .game.engine import _special_result

        card = {'special': '9속도 이하 하단 회피'}
        self.assertEqual(_special_result(card, '하단', 10), '')
        self.assertEqual(_special_result(card, '하단', 9), 'dodge')
        self.assertEqual(_special_result({'special': '8속도 이상 하단 회피'}, '하단', 7), '')
        # 판정마다 위치를 따로 본다: 상단 회피가 중단 상쇄를 회피로 만들지 않는다.
        self.assertEqual(_special_result({'special': '상단 회피 · 중단 상쇄'}, '중단', 5), 'clash')
        self.assertEqual(_special_result({'special': '상·중·하단 상쇄'}, '하단'), 'clash')


class LumenTechniqueUnguardableScopeTests(SimpleTestCase):
    """니아: 루멘 존의 「상대는 이 기술을 방어할 수 없다」 기술이 다른 기술까지 방어 불가로 만들지 않는다."""

    def test_lumen_technique_prevent_applies_only_to_itself(self):
        rocket = attack('rocket', 'p1', code='ROCKET', frame=13)
        rocket['face_up'] = True
        cats = attack('cats', 'p1', code='CATS', frame=5, position='하단')
        guard = defense('guard', 'p2', top='방어', mid='방어', bottom='방어')
        engine = _combo_engine(
            {'hand': [cats], 'lumen': [rocket]}, [guard], [rocket, cats],
            definitions={'ROCKET': {'schema_version': 1, 'abilities': [{
                'id': 'rocket-function', 'kind': 'function', 'mode': 'continuous', 'timing': 'function',
                'effects': [{'op': 'prevent', 'kind': 'guard', 'player': {'opponent': True}, 'duration': 'continuous'}],
            }]}},
        )
        _act(engine, 'p1', 'pass_phase')
        _act(engine, 'p2', 'pass_phase')
        _act(engine, 'p1', 'ready_card', 'cats')
        _act(engine, 'p2', 'ready_card')
        judged = next(e for e in engine.events if e['type'] == 'battle_judged')
        self.assertEqual(judged['payload']['result'], {'p1': 'guarded', 'p2': 'guard'})


class SpecialComboCapTests(SimpleTestCase):
    """여제의 영역 ②: 효과로 연 콤보 타임도 "3콤보까지"라면 3번째 기술을 이을 수 있다."""

    def build(self, frames):
        cards = [attack(f'c{frame}', 'p1', code=f'C{frame}', frame=frame, damage=400) for frame in frames]
        return _combo_engine({'hand': cards}, [], cards)

    def test_capped_special_combo_offers_third_card(self):
        engine = self.build((5, 6, 7, 8))
        engine.state['phase'] = 'battle'
        engine.engine_state['modifiers'] = [{
            'op': 'modify_combo', 'player': 'p1', 'controller': 'p1', 'max_combo': 3,
            'duration': 'battle', 'source': 'queen',
        }]
        engine.grant_combo('p1', source='queen', special=True, trigger_event=False)
        _act(engine, 'p1', 'select_combo_first', 'c5')
        _act(engine, 'p1', 'select_combo_followup', 'c6')
        self.assertEqual(engine.engine_state['combo']['used'], ['c5', 'c6'])
        _act(engine, 'p1', 'play_combo_card', 'c7')
        self.assertFalse(any(
            a['type'] == 'play_combo_card' for a in engine.legal_actions('p1')
        ))
        damages = [e['payload']['amount'] for e in engine.events if e['type'] == 'damage_dealt']
        self.assertEqual(damages, [400, 300, 200])

    def test_uncapped_special_combo_stops_at_two(self):
        engine = self.build((5, 6, 7))
        engine.state['phase'] = 'battle'
        engine.grant_combo('p1', source='nocturne', special=True, trigger_event=False)
        _act(engine, 'p1', 'select_combo_first', 'c5')
        _act(engine, 'p1', 'select_combo_followup', 'c6')
        self.assertFalse(any(
            a['type'] == 'play_combo_card' for a in engine.legal_actions('p1')
        ))


class ChargeRefreshTests(SimpleTestCase):
    """루트아스트라 ②: 차지를 다음 턴 종료까지 갱신하면 이번 턴 해제 예약은 사라진다(Q&A 509)."""

    def test_refresh_with_expiry_drops_scheduled_loss(self):
        engine = _combo_engine({}, [], [])
        engine.set_passive('p1', 'charge', value=True)
        engine.engine_state['scheduled'] = [{
            'when': {'event': 'phase_end', 'phase': 'recovery'},
            'effect': {'op': 'lose_state', 'player': {'controller': True}, 'state': 'charge'},
            'context': {'controller': 'p1'}, 'duration': 'turn',
        }, {
            'when': {'event': 'phase_end', 'phase': 'recovery'},
            'effect': {'op': 'lose_state', 'player': {'controller': True}, 'state': 'other'},
            'context': {'controller': 'p1'}, 'duration': 'turn',
        }]
        engine.set_passive(
            'p1', 'charge', value=True,
            expires={'event': 'phase_end', 'phase': 'recovery', 'occurrences': 2},
        )
        self.assertEqual(
            [item['effect']['state'] for item in engine.engine_state['scheduled']], ['other'],
        )
        self.assertTrue(engine.state['players']['p1']['passive_state']['charge']['value'])


class CatchGrabNegationTests(SimpleTestCase):
    """8.8.2·8.8.3: 캐치로 사용한 그랩도 패의 그랩을 브레이크해 무효로 할 수 있다."""

    def build(self):
        opener = attack('opener', 'p1', code='OPENER', frame=4, damage=300, counter='6')
        grab = attack('grab', 'p1', code='GRAB', frame=5, damage=500, special='그랩')
        foe = attack('foe', 'p2', code='FOE', frame=10, damage=400)
        hand_grab = attack('hand-grab', 'p2', code='HAND-GRAB', frame=12, special='그랩')
        state = base_state([opener, grab], [foe, hand_grab])
        rules = ruleset(opener, grab, foe, hand_grab)
        engine = AutomaticGameEngine.initialize(state, rules, seed='catch-grab', run_startup=False)
        _act(engine, 'p1', 'pass_phase')
        _act(engine, 'p2', 'pass_phase')
        _act(engine, 'p1', 'ready_card', 'opener')
        _act(engine, 'p2', 'ready_card', 'foe')
        # 카운터로 FP 우위를 얻어 FP 캐치 기회가 열린다.
        self.assertEqual(engine.engine_state.get('step'), 'catch')
        _act(engine, 'p1', 'play_catch_card', 'grab')
        return engine

    def test_defender_can_negate_catch_grab_and_ready_restarts(self):
        engine = self.build()
        decision = engine.engine_state['pending_decision']
        self.assertEqual(decision['owner'], 'p2')
        self.assertEqual(decision['kind'], 'grab_negation')
        self.assertEqual([o['id'] for o in decision['options']], ['hand-grab'])
        hp_before = engine.state['players']['p2']['hp']
        action = next(a for a in engine.legal_actions('p2') if a['type'] == 'submit_decision')
        engine.submit_action('p2', action['action_id'], {'selected': ['hand-grab']})
        self.assertEqual(engine.state['players']['p2']['hp'], hp_before)
        self.assertEqual(engine._find_location('hand-grab')[1], 'break')
        self.assertEqual(engine._find_location('grab')[1], 'hand')
        self.assertEqual(engine.state['phase'], 'ready')
        self.assertEqual(engine.engine_state['step'], 'ready_actions')
        self.assertEqual(engine.state['players']['p1']['zones']['battle'], [])
        self.assertEqual(engine.state['players']['p2']['zones']['battle'], [])
        self.assertFalse(any(e['type'] == 'phase_started' and e['payload'].get('phase') == 'get' for e in engine.events))

    def test_declining_lets_catch_hit(self):
        engine = self.build()
        hp_before = engine.state['players']['p2']['hp']
        action = next(a for a in engine.legal_actions('p2') if a['type'] == 'submit_decision')
        engine.submit_action('p2', action['action_id'], {'selected': []})
        self.assertEqual(engine.state['players']['p2']['hp'], hp_before - 500)


class JetpackOwnCatchTests(SimpleTestCase):
    """제트팩 ①은 자신의 <핀프> 캐치에만 반응하고, 상대의 핀프 캐치에는 반응하지 않는다."""

    TEXT = (
        '"OPTION"명을 포함하는 기술은 루멘 존에 1장만 배치할 수 있다.\n'
        '①턴당 1번 <[[character:pinp]]> 기술로 캐치 시, '
        '배틀 페이즈 종료 시에 1FP를 얻는다.'
    )

    def run_catch(self, jetpack_owner):
        from .game.drafts import build_effect_draft

        opener = attack('opener', 'p1', code='OPENER', frame=4, damage=300, counter='6')
        catcher = attack('catcher', 'p1', code='CATCHER', frame=5, damage=500)
        catcher['character_key'] = 'pinp'
        foe = attack('foe', 'p2', code='FOE', frame=10, damage=400)
        jetpack = {
            'instance_id': 'jetpack', 'owner': jetpack_owner, 'kind': 'card',
            'code': 'RFS-AT-017', 'name': 'OPTION: 제트팩', 'type': '특수',
            'face_up': True,
        }
        state = base_state([opener, catcher], [foe])
        state['players'][jetpack_owner]['zones']['lumen'].append(jetpack)
        rules = ruleset(opener, catcher, foe)
        rules['cards']['CATCHER']['character_key'] = 'pinp'
        rules['cards']['RFS-AT-017'] = {
            **jetpack, 'effect_definition': build_effect_draft('RFS-AT-017', self.TEXT),
        }
        engine = AutomaticGameEngine.initialize(state, rules, seed='jetpack', run_startup=False)
        _act(engine, 'p1', 'pass_phase')
        _act(engine, 'p2', 'pass_phase')
        _act(engine, 'p1', 'ready_card', 'opener')
        _act(engine, 'p2', 'ready_card', 'foe')
        self.assertEqual(engine.engine_state.get('step'), 'catch')
        fp_before = engine.state['players'][jetpack_owner]['fp']
        _act(engine, 'p1', 'play_catch_card', 'catcher')
        self.assertEqual(engine.state['phase'], 'get')
        resolved = any(
            e['type'] == 'effect_resolved' and e['payload'].get('ability_id') == 'rfs-at-017-n1'
            for e in engine.events
        )
        return engine, fp_before, resolved

    def test_own_pinp_catch_gains_fp_at_battle_end(self):
        engine, fp_before, resolved = self.run_catch('p1')
        self.assertTrue(resolved)
        # FP 캐치 비용 6을 낸 뒤 배틀 종료 시 1FP를 얻는다.
        self.assertEqual(engine.state['players']['p1']['fp'], fp_before - 6 + 1)

    def test_opponent_pinp_catch_does_not_trigger(self):
        engine, fp_before, resolved = self.run_catch('p2')
        self.assertFalse(resolved)
        self.assertEqual(engine.state['players']['p2']['fp'], fp_before)


RABBIT_TEXT = (
    '이 기술은 8~11속도만 회피할 수 있다.\n'
    '①[[state:advance_notice]]: 판정 전 회피 속도 제한이 해제되고\n'
    '상대의 기술 데미지만큼 이 기술의 데미지를 올린다.'
)
CHOYEOM_TEXT = (
    '①판정 전, 상대 기술에 <회피> 특수 판정이 있을 경우, 이 기술은 <6속도>로 고정된다. \n'
    '②상대 방어 시, [[token:ember]] 카운터 1개당 1FP를 잃는다. (최대 8) \n'
    '③카운터 시, [[token:ember]] 카운터 1개당 1FP를 얻는다.(최대 9)'
)


class RabbitStampNoticeTests(SimpleTestCase):
    """래빗 스탬프 예고로 회피 속도 제한이 풀려도 없던 상쇄 판정을 얻지는 않는다."""

    def judge(self, notice):
        from .game.drafts import build_effect_draft

        rabbit = attack(
            'rabbit', 'p1', code='ST4-006', frame=10, damage=300,
            special='중단 회피', hit='5', counter='콤보',
        )
        choyeom = attack(
            'choyeom', 'p2', code='CB03-AT-019', frame=9, damage=500,
            position='하단', hit='4',
        )
        state = base_state([rabbit], [choyeom])
        if notice:
            state['players']['p1']['passive_state']['advance_notice'] = {
                'active': True, 'value': True,
            }
        rules = ruleset(rabbit, choyeom)
        rules['cards']['ST4-006']['effect_definition'] = build_effect_draft('ST4-006', RABBIT_TEXT)
        rules['cards']['CB03-AT-019']['effect_definition'] = build_effect_draft(
            'CB03-AT-019', CHOYEOM_TEXT,
        )
        engine = AutomaticGameEngine.initialize(state, rules, seed='rabbit', run_startup=False)
        _act(engine, 'p1', 'pass_phase')
        _act(engine, 'p2', 'pass_phase')
        _act(engine, 'p1', 'ready_card', 'rabbit')
        _act(engine, 'p2', 'ready_card', 'choyeom')
        return next(e['payload'] for e in engine.events if e['type'] == 'battle_judged')

    def test_notice_does_not_turn_counter_into_clash(self):
        judged = self.judge(notice=True)
        self.assertEqual(judged['speed'], {'p1': 10, 'p2': 6})
        self.assertEqual(judged['result'], {'p1': 'countered', 'p2': 'counter'})

    def test_without_notice_is_counter(self):
        self.assertEqual(
            self.judge(notice=False)['result'], {'p1': 'countered', 'p2': 'counter'},
        )


class ShieldAbsorbedDamageTests(SimpleTestCase):
    """보호막이 모두 흡수한 데미지는 체력에 받은 데미지가 아니므로 "데미지를 받았을 때"가 유발되지 않는다."""

    def build(self):
        watcher = {
            'instance_id': 'watcher', 'kind': 'card', 'owner': 'p2', 'code': 'WATCHER',
            'name': 'watcher', 'type': '특수', 'face_up': True,
        }
        state = base_state([], [])
        state['players']['p2']['zones']['lumen'].append(watcher)
        definition = {
            'schema_version': 1, 'abilities': [{
                'id': 'watcher-n1', 'kind': 'effect', 'mode': 'mandatory',
                'timing': 'result', 'active_zones': ['lumen'],
                'trigger': {'event': 'damage_after'},
                'condition': {
                    'op': 'equals', 'left': {'path': 'context.player'},
                    'right': {'path': 'context.controller'},
                },
                'effects': [{'op': 'change_fp', 'player': {'controller': True}, 'amount': 1}],
            }],
        }
        rules = {'version': 'test-v1', 'cards': {
            'WATCHER': {**watcher, 'effect_definition': definition},
        }}
        return AutomaticGameEngine.initialize(state, rules, seed='shield', run_startup=False)

    def resolved(self, engine):
        return [
            e for e in engine.events
            if e['type'] == 'effect_resolved' and e['payload'].get('ability_id') == 'watcher-n1'
        ]

    def test_fully_absorbed_damage_is_not_received(self):
        engine = self.build()
        engine.gain_shield('p2', 500)
        engine.deal_damage('p2', 300, source='effect', context={'controller': 'p1'})
        self.assertEqual(engine.state['players']['p2']['hp'], 5000)
        self.assertEqual(self.resolved(engine), [])
        self.assertEqual(engine.state['players']['p2']['fp'], 0)

    def test_damage_past_shield_is_received(self):
        engine = self.build()
        engine.gain_shield('p2', 100)
        engine.deal_damage('p2', 300, source='effect', context={'controller': 'p1'})
        self.assertEqual(engine.state['players']['p2']['hp'], 4800)
        self.assertEqual(len(self.resolved(engine)), 1)
        self.assertEqual(engine.state['players']['p2']['fp'], 1)


STORMSLAYER_TEXT = (
    '이 기술은 자신의 체력이 2500 이하일 경우에만 사용할 수 있다.\n'
    '이 기술은 효과로 속도가 느려지지 않는다.\n'
    '이 기술은 콤보에 사용할 수 없다.\n'
    '① 사용 시, 패나 리스트의 [[card:LMI-AT-016]]를 브레이크한다.\n'
    '그 후, 이 기술은 상대가 방어 및 상쇄할 수 없으며 이 기술 데미지+500\n'
    '②사용 후, 이 기술을 브레이크한다.\n'
    '그 후, 브레이크 존의 [[card:LMI-AT-016]]를 패로 가져올 수 있다.'
)


class StormslayerSpeedImmunityTests(SimpleTestCase):
    """스톰슬레이어는 효과로 느려지지 않지만, 더 빠르게 하는 효과는 받는다."""

    def judge(self, effect):
        from .game.drafts import build_effect_draft

        storm = attack('storm', 'p1', code='DFR-AT-015', frame=9, damage=500, hit='3', counter='4')
        slower = attack('slower', 'p2', code='SLOWER', frame=13, damage=400)
        state = base_state([storm], [slower], hp=2000)
        rules = ruleset(storm, slower)
        rules['cards']['DFR-AT-015']['effect_definition'] = build_effect_draft(
            'DFR-AT-015', STORMSLAYER_TEXT,
        )
        rules['cards']['SLOWER']['effect_definition'] = {'schema_version': 1, 'abilities': [{
            'id': 'slower-n1', 'kind': 'effect', 'mode': 'mandatory',
            'timing': 'before_judgment', 'active_zones': ['battle'],
            'trigger': {'event': 'before_judgment'},
            'effects': [{
                **effect, 'player': {'opponent': True}, 'stat': 'frame', 'duration': 'battle',
            }],
        }]}
        engine = AutomaticGameEngine.initialize(state, rules, seed='storm', run_startup=False)
        _act(engine, 'p1', 'pass_phase')
        _act(engine, 'p2', 'pass_phase')
        _act(engine, 'p1', 'ready_card', 'storm')
        _act(engine, 'p2', 'ready_card', 'slower')
        while engine.engine_state.get('pending_decision'):
            decision = engine.engine_state['pending_decision']
            action = next(
                a for a in engine.legal_actions(decision['owner'])
                if a['type'] == 'submit_decision'
            )
            engine.submit_action(decision['owner'], action['action_id'], {'selected': []})
        added = next(
            e['payload'] for e in engine.events
            if e['type'] == 'modifier_added' and e['payload']['modifier'].get('source') == 'slower'
        )
        judged = next(e['payload'] for e in engine.events if e['type'] == 'battle_judged')
        return judged['speed']['p1'], added.get('ignored_card_instance_ids')

    def test_slowing_modifier_is_ignored_and_reported(self):
        self.assertEqual(self.judge({'op': 'modify_stat', 'amount': 12}), (9, ['storm']))

    def test_slower_fixed_speed_is_ignored(self):
        self.assertEqual(self.judge({'op': 'fix_speed', 'value': 12}), (9, ['storm']))

    def test_faster_fixed_speed_still_applies(self):
        self.assertEqual(self.judge({'op': 'fix_speed', 'value': 5}), (5, None))
