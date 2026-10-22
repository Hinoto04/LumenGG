from unittest.mock import patch

from django.test import TestCase, override_settings

from card.models import Character
from .party_services import create_room, join_room, perform_party_action, serialize_room


@override_settings(PARTY_BOARD_VERSION=1, PARTY_EVENT_REVEAL_MS=0, PARTY_ROLL_REVEAL_MS=0)
class PartyArrivalTests(TestCase):
    def setUp(self):
        character = Character.objects.create(name='도착 규칙', description='', group='', datas={'hand': {'5000': 5}})
        self.room, self.host = create_room({'character_id': character.pk})
        self.room, self.guest = join_room(self.room.code, {'character_id': character.pk})
        self.act('ready'); self.act('ready', player=self.guest); self.act('start')
        self.guest.position = 18; self.guest.save()

    def act(self, action, player=None, **body):
        self.room.refresh_from_db()
        self.room = perform_party_action(self.room.code, (player or self.host).token,
            {'action': action, 'expected_version': self.room.version, **body})

    def moving(self, origin, remaining):
        self.host.refresh_from_db()
        self.host.position = origin; self.host.hp = 5000; self.host.coins = 10
        self.host.prepared_fp = 0; self.host.items = []; self.host.save()
        self.room.refresh_from_db()
        self.room.document.update(move={'remaining': remaining, 'dice': remaining}, landed=False,
            move_prompt=None, arrival=None, event=None, previous_positions={}, headings={}, log=[])
        self.room.save()

    def state(self):
        return serialize_room(self.room, self.host.token)

    def test_outer_passes_have_no_effect_and_shop_preserves_remaining_movement(self):
        self.moving(0, 6)
        with patch('battlelog.party_services.secrets.randbelow', side_effect=AssertionError('fortune rolled while passing')):
            self.act('move', node=1)
        self.host.refresh_from_db()
        self.assertEqual((self.host.position, self.host.hp, self.host.prepared_fp, self.host.coins, self.host.items), (5, 5000, 0, 10, []))
        self.assertFalse(self.room.document['landed'])
        self.assertIsNone(self.room.document['arrival'])
        self.assertTrue(self.room.document['move_prompt']['shop'])
        self.assertEqual(self.room.document['move']['remaining'], 1)
        self.assertTrue(self.room.document['move_prompt']['shop_open'])
        self.assertTrue(self.state()['can_buy_item'])
        offered = self.state()['shop_offers'][0]
        self.act('buy_item', item=offered)
        self.assertIsNone(self.room.document['move'])
        with self.assertRaises(ValueError): self.act('buy_item', item='heal')
        self.host.refresh_from_db()
        self.assertEqual((self.host.position, self.host.hp, self.host.prepared_fp, self.host.coins, self.host.items), (6, 5000, 0, 1, [offered]))
        self.assertEqual(self.host.crystals, 1)
        self.assertTrue(self.room.document['landed'])
        self.assertEqual(sum('도착.' in entry['text'] for entry in self.room.document['log']), 1)

    def test_cancelling_auto_opened_shop_does_not_allow_later_purchase(self):
        self.moving(4, 3); self.act('advance')
        self.assertTrue(self.room.document['move_prompt']['shop_open'])
        self.act('skip_shop')
        self.host.refresh_from_db()
        self.assertEqual((self.host.position, self.host.coins), (6, 10))
        self.assertEqual(self.room.document['move']['remaining'], 1)
        self.assertFalse(self.state()['can_buy_item'])
        self.assertFalse(self.state()['can_buy_crystal'])
        self.assertIsNone(self.room.document['move_prompt'])
        with self.assertRaises(ValueError): self.act('open_shop')
        with self.assertRaises(ValueError): self.act('buy_item', item='heal')

    def test_inner_event_prepare_disaster_and_charge_passes_have_no_effect(self):
        self.moving(31, 5)
        self.act('advance')
        self.assertEqual(self.room.players.get(seat=0).position, 24)
        self.assertFalse(self.state()['can_charge'])
        with patch('battlelog.party_services.secrets.choice', side_effect=AssertionError('event on pass')):
            self.act('move', node=25)
            self.assertIsNone(self.room.document['event'])
            self.act('move', node=27)
        self.host.refresh_from_db()
        self.assertEqual((self.host.position, self.host.hp, self.host.prepared_fp, self.host.coins), (28, 5000, 0, 10))
        self.assertTrue(self.state()['can_charge'])

    def test_meeting_someone_on_preparation_does_not_apply_arrival_effect(self):
        self.moving(1, 3); self.guest.position = 2; self.guest.save()
        self.act('advance')
        self.assertEqual(self.room.document['move_prompt']['targets'], [1])
        self.host.refresh_from_db(); self.assertEqual(self.host.prepared_fp, 0)
        self.act('continue_move')
        self.host.refresh_from_db()
        self.assertEqual((self.host.position, self.host.hp, self.host.prepared_fp), (4, 5000, 0))
        self.assertEqual(self.room.document['arrival'], 'dash')

    def test_own_camp_reward_waits_for_stop_choice(self):
        self.moving(23, 3); self.act('advance')
        self.assertTrue(self.room.document['move_prompt']['own_camp'])
        self.host.refresh_from_db(); self.assertEqual((self.host.coins, self.host.items), (10, []))
        self.assertFalse(self.state()['can_buy_crystal'])
        with patch('battlelog.party_services._random_item', return_value='heal'): self.act('stop_home')
        self.host.refresh_from_db(); self.assertEqual((self.host.coins, self.host.items), (7, ['heal']))
        self.assertEqual(self.host.crystals, 1)
        self.assertEqual(len(self.state()['camp_gift']['items']), 3)

    def test_continuing_past_own_camp_does_not_grant_rewards(self):
        self.moving(23, 3); self.act('advance'); self.act('continue_move')
        self.act('move', node=1)
        self.host.refresh_from_db()
        self.assertEqual((self.host.position, self.host.coins, self.host.items, self.host.prepared_fp), (2, 10, [], 2))

    def test_shop_and_remaining_movement_survive_cancelled_battle(self):
        self.moving(4, 3); self.guest.position = 5; self.guest.save()
        self.act('advance'); self.act('open_shop'); self.act('challenge', target=1)
        self.act('cancel_battle')
        self.assertTrue(self.room.document['move_prompt']['shop_open'])
        self.assertTrue(self.state()['can_buy_item'])
        self.assertEqual(self.room.document['move']['remaining'], 2)

    def test_exact_landings_apply_each_tile_effect_once(self):
        cases = [(0, 1, 5000, 0, 12, None), (1, 2, 5000, 2, 10, None),
                 (2, 3, 4700, 0, 10, None), (3, 4, 5000, 0, 10, 'dash'),
                 (24, 25, 5000, 0, 12, None), (31, 24, 5000, 0, 10, 'charge')]
        for origin, destination, hp, fp, coins, arrival in cases:
            with self.subTest(destination=destination):
                self.moving(origin, 1)
                with patch('battlelog.party_services.secrets.randbelow', return_value=1), patch('battlelog.party_services.secrets.choice', return_value='rich'):
                    self.act('move', node=destination)
                self.host.refresh_from_db()
                self.assertEqual((self.host.hp, self.host.prepared_fp, self.host.coins), (hp, fp, coins))
                self.assertEqual(self.room.document['arrival'], arrival)
                with self.assertRaises(ValueError): self.act('advance')
                self.host.refresh_from_db()
                self.assertEqual((self.host.hp, self.host.prepared_fp, self.host.coins), (hp, fp, coins))
