from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.utils import timezone

from card.models import Character
from .party_services import create_room, join_room, perform_party_action, serialize_room, PartyConflict


@override_settings(PARTY_BOARD_VERSION=1, PARTY_EVENT_REVEAL_MS=0, PARTY_ROLL_REVEAL_MS=3200)
class PartyRollTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        character = Character.objects.create(name='주사위', description='', group='', datas={'hand': {'5000': 5}})
        self.room, self.host = create_room({'character_id': character.pk})
        self.room, self.guest = join_room(self.room.code, {'character_id': character.pk})
        self.act(self.host, 'ready'); self.act(self.guest, 'ready'); self.act(self.host, 'start')
        self.host.refresh_from_db()

    def act(self, player, action, after=0, **body):
        self.room.refresh_from_db()
        with patch('battlelog.party_services.timezone.now', return_value=self.now + timedelta(milliseconds=after)):
            self.room = perform_party_action(self.room.code, player.token, {'action': action, 'expected_version': self.room.version, **body})
        return self.room

    def roll(self, *faces):
        with patch('battlelog.party_services.secrets.randbelow', side_effect=[face - 1 for face in faces]):
            self.act(self.host, 'roll')

    def test_roll_keeps_position_and_effects_unchanged_until_reveal_finishes(self):
        self.host.position = 2; self.host.save()
        self.roll(1)
        self.host.refresh_from_db()
        self.assertEqual((self.host.position, self.host.hp), (2, 5000))
        self.assertTrue(self.room.document['move']['reveal_pending'])
        self.assertFalse(serialize_room(self.room, self.host.token)['can_act'])
        self.assertFalse(serialize_room(self.room, self.host.token)['can_use_items'])
        for action in ['roll', 'move', 'use_item', 'end_turn', 'advance']:
            with self.assertRaises(ValueError): self.act(self.host, action, after=3199, node=3, item='heal')
        self.act(self.host, 'advance', after=3200)
        self.host.refresh_from_db()
        self.assertEqual((self.host.position, self.host.hp), (3, 4700))
        self.assertTrue(self.room.document['landed'])

    def test_reveal_ends_at_a_fork_without_choosing_direction(self):
        self.roll(2)
        self.act(self.host, 'advance', after=3300)
        self.host.refresh_from_db(); self.assertEqual(self.host.position, 0)
        self.assertFalse(self.room.document['move'].get('reveal_pending'))
        self.assertTrue(serialize_room(self.room, self.host.token)['can_act'])
        with self.assertRaises(ValueError): self.act(self.host, 'advance', after=3300)
        self.act(self.host, 'move', after=3300, node=1)
        self.host.refresh_from_db(); self.assertEqual(self.host.position, 2)

    def test_two_dice_and_movement_power_are_public_and_cannot_reroll(self):
        self.room.document.update(round=4, double_dice={'0': True}); self.room.save()
        self.roll(2, 5)
        roll = serialize_room(self.room)['dice_roll']
        self.assertEqual((roll['dice_values'], roll['bonus'], roll['total']), ([2, 5], 1, 8))
        self.assertEqual(roll['add_at'] - roll['started_at'], 1700)
        self.assertEqual(roll['end_at'] - roll['started_at'], 3200)
        self.assertEqual([roll[key] - roll['started_at'] for key in ['settle_at', 'number_at', 'count_at', 'total_at']], [900, 1250, 2050, 2500])
        self.assertNotIn(self.host.token, str(roll))
        with self.assertRaises(ValueError): self.act(self.host, 'roll', after=4000)
        self.room.refresh_from_db(); self.assertEqual(self.room.document['dice_roll'], roll)

    def test_reconnect_resumes_pending_roll_once_and_only_owner_can_start(self):
        self.host.position = 2; self.host.save(); self.roll(1)
        state = serialize_room(self.room, self.host.token)
        version = state['version']
        with self.assertRaises(PermissionDenied): self.act(self.guest, 'advance', after=60000)
        self.act(self.host, 'advance', after=60000)
        with self.assertRaises(PartyConflict):
            perform_party_action(self.room.code, self.host.token, {'action': 'advance', 'expected_version': version})
        self.host.refresh_from_db(); self.assertEqual((self.host.hp, self.host.position), (4700, 3))
        self.act(self.host, 'end_turn', after=60000)
        self.assertIsNone(serialize_room(self.room)['dice_roll'])

    def test_dash_gets_a_new_reveal_and_does_not_reuse_old_result(self):
        self.host.position = 3; self.host.save(); self.roll(1)
        first = self.room.document['dice_roll'].copy()
        self.act(self.host, 'advance', after=3300)
        self.assertEqual(self.room.document['arrival'], 'dash')
        with patch('battlelog.party_services.secrets.randbelow', return_value=1): self.act(self.host, 'roll', after=4000)
        second = self.room.document['dice_roll']
        self.assertGreater(second['version'], first['version'])
        self.assertEqual(second['started_at'] - first['started_at'], 4000)
        self.assertTrue(self.room.document['move']['reveal_pending'])
        self.host.refresh_from_db(); self.assertEqual(self.host.position, 4)
