from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from card.models import Character
from .party_board import SHOP
from .party_services import PartyConflict, create_room, join_room, perform_party_action, serialize_room, _land


@override_settings(PARTY_ROLL_REVEAL_MS=0)
class PartyTurnFlowTests(TestCase):
    def setUp(self):
        character = Character.objects.create(name='턴 진행', description='', group='', datas={})
        self.room, self.host = create_room({'character_id': character.pk})
        self.room, self.guest = join_room(self.room.code, {'character_id': character.pk})
        self.act('ready'); self.act('ready', self.guest); self.act('start')
        self.host.items = ['heal']; self.host.coins = 20; self.host.save()

    def act(self, action, player=None, **data):
        self.room.refresh_from_db()
        self.room = perform_party_action(self.room.code, (player or self.host).token,
            {'action': action, 'expected_version': self.room.version, **data})

    def state(self, player=None):
        self.room.refresh_from_db()
        return serialize_room(self.room, (player or self.host).token)

    def arrive(self, position=3, arrival=None):
        self.host.position = position; self.host.save()
        self.room.document.update(move=None, landed=True, arrival=arrival, movement_started=True)
        self.room.save()

    def test_items_only_before_the_first_roll_including_dash(self):
        self.assertTrue(self.state()['can_use_items'])
        with patch('battlelog.party_services.secrets.randbelow', return_value=1): self.act('roll')
        self.assertFalse(self.state()['can_use_items'])
        with self.assertRaisesMessage(ValueError, '이동 전에만'): self.act('use_item', item='heal')
        self.arrive(7, 'dash'); self.room.document['landed'] = False; self.room.save()
        self.assertFalse(self.state()['can_use_items'])
        with self.assertRaisesMessage(ValueError, '이동 전에만'): self.act('use_item', item='heal')

    def test_auto_end_requires_no_move_and_resets_items_for_next_turn(self):
        self.assertFalse(self.state()['can_auto_end_turn'])
        self.arrive()
        self.assertTrue(self.state()['can_auto_end_turn'])
        with self.assertRaises(PermissionDenied): self.act('auto_end_turn', self.guest)
        self.act('auto_end_turn')
        self.assertEqual(self.state(self.guest)['turn'], self.guest.seat)
        self.assertTrue(self.state(self.guest)['can_use_items'])

    def test_choices_block_automatic_end(self):
        for position, arrival in [(2, 'charge'), (0, 'transfer'), (8, None)]:
            self.arrive(position, arrival)
            self.assertFalse(self.state()['can_auto_end_turn'])
            with self.assertRaises(ValueError): self.act('auto_end_turn')
        self.arrive(5)
        self.room.document['camp_arrival_turn'] = self.room.document['turn_number']; self.room.save()
        self.assertFalse(self.state()['can_auto_end_turn'])
        self.act('buy_crystal')
        self.assertFalse(self.state()['can_auto_end_turn'])
        self.act('skip_camp_gift')
        self.assertTrue(self.state()['can_auto_end_turn'])
        for field, value in [('hand_tasks', {'reason': '부활', 'count': 5, 'version': 1}), ('item_rewards', 'heal')]:
            self.room.document[field] = {'0': value}; self.room.save()
            self.assertFalse(self.state()['can_auto_end_turn'])
            self.room.document.pop(field); self.room.save()
        self.room.document['event'] = {'id': 'rich', 'pending': True}; self.room.save()
        self.assertFalse(self.state()['can_auto_end_turn'])

    def test_arrival_battle_remains_optional_and_can_repeat(self):
        self.arrive()
        self.guest.position = self.host.position; self.guest.save()
        self.assertFalse(self.state()['can_auto_end_turn'])
        self.act('skip_challenge')
        self.assertTrue(self.state()['can_auto_end_turn'])
        self.act('challenge', target=self.guest.seat)
        self.assertFalse(self.state()['can_auto_end_turn'])
        self.act('cancel_battle')
        self.assertFalse(self.state()['can_auto_end_turn'])
        self.act('skip_challenge'); self.act('auto_end_turn')
        self.assertEqual(self.room.document['turn'], self.guest.seat)

    def test_shop_offers_three_stable_items_and_rejects_other_purchases(self):
        self.arrive(8)
        offers = self.state()['shop_offers']
        self.assertEqual(len(set(offers)), 3)
        self.assertEqual(self.state(self.guest)['shop_offers'], offers)
        other = next(key for key in SHOP if key not in offers)
        with self.assertRaises(ValueError): self.act('buy_item', item=other)
        self.assertEqual(self.state()['shop_offers'], offers)
        self.act('buy_item', item=offers[0]); self.host.refresh_from_db()
        self.assertEqual(self.host.coins, 17)
        self.assertIn(offers[0], self.host.items)
        self.assertTrue(self.state()['can_auto_end_turn'])

    def test_shop_cancel_leaves_inventory_unchanged_and_resumes_passing_move(self):
        self.arrive(8)
        self.act('skip_shop'); self.host.refresh_from_db()
        self.assertEqual((self.host.items, self.host.coins), (['heal'], 20))
        self.assertTrue(self.state()['can_auto_end_turn'])
        self.room.document.pop('shop_closed_turn')
        self.room.document.update(move={'remaining': 2}, landed=False, move_prompt={'shop': True, 'shop_open': True, 'targets': []})
        self.room.save()
        self.act('skip_shop'); self.host.refresh_from_db()
        self.assertEqual(self.host.position, 10)
        self.assertEqual(self.room.document['arrival'], 'transfer')

    def test_shop_full_bag_or_insufficient_coins_keeps_cancel_choice(self):
        self.arrive(8)
        self.host.coins = 0; self.host.items = ['heal'] * 3; self.host.save()
        self.assertFalse(self.state()['can_auto_end_turn'])
        with self.assertRaises(ValueError): self.act('buy_item', item=self.state()['shop_offers'][0])
        self.act('skip_shop')
        self.assertTrue(self.state()['can_auto_end_turn'])

    def test_camp_auto_purchase_prices_and_stable_free_reward(self):
        for crystals, cost in enumerate([6, 10, 15]):
            self.room.refresh_from_db(); self.room.document['turn_number'] += 1
            self.host.refresh_from_db(); self.host.position = 45; self.host.coins = cost; self.host.crystals = crystals
            _land(self.room, self.host); self.room.save()
            self.host.refresh_from_db()
            self.assertEqual((self.host.coins, self.host.crystals), (0, crystals + 1))
            state = self.state(); offers = state['camp_gift']['items']
            self.assertEqual(len(set(offers)), 3)
            self.assertEqual(self.state()['camp_gift']['items'], offers)
            self.assertIsNone(self.state(self.guest)['camp_gift'])
            with self.assertRaises(ValueError): self.act('buy_crystal')
            invalid = next(key for key in SHOP if key not in offers)
            with self.assertRaises(ValueError): self.act('choose_camp_gift', item=invalid)
            self.act('choose_camp_gift', item=offers[0])
            self.host.refresh_from_db()
            if self.state()['item_reward']: self.act('claim_item', discard=True)
            self.assertEqual(self.host.coins, 0)
            self.assertIsNone(self.state()['camp_gift'])

    def test_home_bonus_and_full_bag_rewards_do_not_overwrite_each_other(self):
        self.host.position = 5; self.host.coins = 3; self.host.items = ['heal', 'gun', 'prepare']
        with patch('battlelog.party_services._random_item', return_value='brick'):
            _land(self.room, self.host); self.room.save()
        state = self.state(); offers = state['camp_gift']['items']
        self.assertEqual((state['players'][0]['coins'], state['players'][0]['crystals']), (0, 1))
        self.assertEqual(state['item_reward'], 'brick')
        with self.assertRaises(ValueError): self.act('choose_camp_gift', item=offers[0])
        self.assertEqual(self.state()['item_reward'], 'brick')
        self.act('claim_item', discard=True)
        version = self.room.version
        self.act('choose_camp_gift', item=offers[0])
        self.assertEqual(self.state()['item_reward'], offers[0])
        with self.assertRaises(PartyConflict):
            perform_party_action(self.room.code, self.host.token, {'action':'choose_camp_gift','item':offers[0],'expected_version':version})
        self.act('claim_item', index=1)
        self.host.refresh_from_db()
        self.assertEqual(len(self.host.items), 3)
        self.assertEqual(self.host.items[1], offers[0])
        self.assertTrue(self.state()['can_auto_end_turn'])

    def test_passing_home_shortfall_includes_home_bonus_without_buying(self):
        self.host.position = 5; self.host.coins = 1; self.host.save()
        self.room.document.update(move={'remaining':3}, landed=False, move_prompt={'own_camp':True,'targets':[]})
        self.room.save()
        self.assertEqual(self.state()['camp_stop_shortfall'], 2)
        self.assertIsNone(self.state()['camp_gift'])
        self.act('continue_move'); self.host.refresh_from_db()
        self.assertEqual((self.host.coins, self.host.crystals), (1, 0))

    def test_unaffordable_camp_does_not_buy_or_hold_turn_open(self):
        self.host.position = 45; self.host.coins = 5
        _land(self.room, self.host); self.room.save()
        self.host.refresh_from_db()
        self.assertEqual((self.host.coins,self.host.crystals), (5,0))
        self.assertIsNone(self.state()['camp_gift'])
        self.assertTrue(self.state()['can_auto_end_turn'])
