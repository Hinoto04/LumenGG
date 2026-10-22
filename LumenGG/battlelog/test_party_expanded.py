from collections import deque
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from card.models import Character
from .party_board import BOARD, range_exits
from .party_services import create_room, join_room, perform_party_action, serialize_room, forward_exits


@override_settings(PARTY_ROLL_REVEAL_MS=0)
class ExpandedPartyTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(name='확장 지도', description='', group='', datas={})
        self.room, self.host = create_room({'character_id': self.character.pk})
        self.room, self.guest = join_room(self.room.code, {'character_id': self.character.pk})
        self.act('ready'); self.act('ready', self.guest); self.act('start')

    def act(self, action, player=None, **data):
        self.room.refresh_from_db()
        self.room = perform_party_action(self.room.code, (player or self.host).token,
            {'action': action, 'expected_version': self.room.version, **data})

    def moving(self, position, remaining):
        self.host.refresh_from_db(); self.host.position = position; self.host.coins = 20; self.host.save()
        self.room.refresh_from_db()
        self.room.document.update(move={'dice': remaining, 'remaining': remaining}, landed=False,
            move_prompt=None, arrival=None, previous_positions={}, headings={})
        self.room.save()

    def test_two_disconnected_walking_rings_and_balanced_shared_camps(self):
        self.assertEqual(len(BOARD['nodes']), 64)
        self.assertEqual(BOARD['homes'], [5, 15, 25, 35])
        for tile in BOARD['nodes']:
            self.assertEqual(len(tile['exits']), 2)
            self.assertTrue(all(BOARD['nodes'][n]['ring'] == tile['ring'] for n in tile['exits']))
            if tile['kind'] == 'transfer':
                self.assertEqual(BOARD['nodes'][tile['transfer_to']]['transfer_to'], tile['id'])
        camps = [n['id'] for n in BOARD['nodes'] if n.get('shared')]
        self.assertEqual(camps, [45, 57])
        for camp in camps:
            distances, queue = {camp: 0}, deque([camp])
            while queue:
                node = queue.popleft()
                for other in range_exits(BOARD['nodes'][node]):
                    if other not in distances:
                        distances[other] = distances[node] + 1; queue.append(other)
            nearest = sorted(distances[n] for n in BOARD['homes'])
            self.assertEqual(nearest[:2], [7, 7])
        self.assertEqual([p['home'] for p in serialize_room(self.room)['players']], [5, 15])

    def test_transfer_only_on_arrival_and_preserves_heading(self):
        self.moving(39, 2); self.act('advance')
        self.assertEqual(self.room.players.get(seat=0).position, 1)
        self.assertFalse(serialize_room(self.room)['can_transfer'])
        self.moving(39, 1); self.act('advance')
        state = serialize_room(self.room, self.host.token)
        self.assertTrue(state['can_transfer']); self.assertEqual(state['transfer_to'], 40)
        with self.assertRaises(ValueError): self.act('end_turn')
        self.act('transfer')
        self.host.refresh_from_db()
        self.assertEqual(self.host.position, 40)
        self.assertEqual(forward_exits(self.room, self.host), [41])
        self.assertTrue(self.room.document['move_path']['teleport'])
        self.assertFalse(serialize_room(self.room)['can_transfer'])
        with self.assertRaises(ValueError): self.act('transfer')

    def test_transfer_can_be_declined(self):
        self.moving(39, 1); self.act('advance'); self.act('skip_transfer')
        self.assertEqual(self.room.players.get(seat=0).position, 0)
        self.assertIsNone(self.room.document['arrival'])
        self.act('end_turn')

    def test_shared_camp_stops_any_player_and_only_sells_crystals(self):
        self.moving(44, 3); self.act('advance')
        self.assertTrue(self.room.document['move_prompt']['shared_camp'])
        self.assertEqual(self.room.document['move']['remaining'], 2)
        self.act('stop_home')
        self.host.refresh_from_db()
        self.assertEqual((self.host.coins, self.host.items), (14, []))
        self.assertFalse(serialize_room(self.room, self.host.token)['can_buy_crystal'])
        self.assertEqual(len(serialize_room(self.room, self.host.token)['camp_gift']['items']), 3)
        self.assertEqual((self.host.coins, self.host.crystals), (14, 1))

    def test_item_range_crosses_transfer_but_preview_does_not(self):
        self.moving(39, 2)
        self.guest.position = 41; self.guest.save()
        state = serialize_room(self.room, self.host.token)
        self.assertIn(self.guest.seat, state['item_targets']['brick'])
        self.assertTrue(all(node < 40 for node in state['movement_preview']['nodes']))
        self.assertEqual(len(state['movement_preview']['edges']), 2)

    def test_roadblock_can_be_installed_on_the_new_high_numbered_tiles(self):
        self.host.position = 62; self.host.items = ['roadblock']; self.host.save()
        self.act('use_item', item='roadblock', node=63)
        self.assertEqual(self.room.document['roadblocks'][0]['node'], 63)
        self.moving(62, 3)
        self.act('advance')
        self.assertEqual(self.room.players.get(seat=0).position, 63)
        self.assertTrue(self.room.document['landed'])
        self.assertEqual(self.room.document['roadblocks'], [])

    @override_settings(PARTY_EVENT_REVEAL_MS=0)
    def test_go_home_event_uses_relocated_personal_camps_without_arrival_rewards(self):
        self.moving(41, 1)
        self.guest.position = 50; self.guest.save()
        with patch('battlelog.party_services.secrets.choice', return_value='home'):
            self.act('advance')
        self.assertEqual(list(self.room.players.values_list('position', flat=True)), [5, 15])
        self.assertEqual(self.room.players.get(seat=0).coins, 20)
        self.assertFalse(serialize_room(self.room, self.host.token)['can_buy_crystal'])

    def test_legacy_upgrade_preserves_resources_and_remaining_move(self):
        with override_settings(PARTY_BOARD_VERSION=1):
            room, player = create_room({'character_id': self.character.pk})
            player.hp = 1230; player.coins = 8; player.items = ['heal']; player.save()
            room.document.update(move={'remaining': 3, 'dice': 4}, roadblocks=[{'node': 24, 'owner': 0}])
            room.save()
        state = serialize_room(room, player.token)
        self.assertEqual(state['board']['version'], 2)
        self.assertEqual((state['players'][0]['position'], state['players'][0]['hp'], state['players'][0]['coins']), (5, 1230, 8))
        self.assertEqual(state['me']['items'], ['heal']); self.assertEqual(state['move']['remaining'], 3)
        self.assertEqual(state['roadblocks'][0]['node'], 40)
        version = room.version
        serialize_room(room)
        self.assertEqual(room.version, version)

    @override_settings(PARTY_EVENT_REVEAL_MS=2400)
    def test_event_card_precedes_effect_and_effect_is_logged_exactly_once(self):
        now = timezone.now()
        self.moving(41, 1)
        with patch('battlelog.party_services.timezone.now', return_value=now), patch('battlelog.party_services.secrets.choice', return_value='rich'):
            self.act('advance')
        event = self.room.document['event']
        self.assertTrue(event['pending']); self.assertIn('going-to-be-rich.png', event['image'])
        self.assertEqual(self.room.players.get(seat=0).coins, 20)
        self.assertFalse(serialize_room(self.room, self.host.token)['can_act'])
        with self.assertRaises(ValueError): self.act('end_turn')
        with patch('battlelog.party_services.timezone.now', return_value=now + timedelta(milliseconds=2899)):
            with self.assertRaises(ValueError): self.act('resolve_event', event_version=event['version'])
        with patch('battlelog.party_services.timezone.now', return_value=now + timedelta(milliseconds=2900)):
            self.act('resolve_event', event_version=event['version'])
        self.assertEqual(self.room.players.get(seat=0).coins, 22)
        self.assertFalse(self.room.document['event']['pending'])
        self.assertEqual(sum('이벤트 · 부자가 될거야' in e['text'] for e in self.room.document['log']), 1)
        with self.assertRaises(ValueError): self.act('resolve_event', event_version=event['version'])
