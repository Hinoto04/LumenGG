import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from card.models import Character
from mobile_api.calculators import perform_mobile_action
from .models import BattleSession, PartyEncounter, PartyRoom
from .party_board import LEGACY_BOARD as BOARD, nearby
from .party_services import PartyConflict, create_room, join_room, perform_party_action, serialize_room, movement_preview, _land
from .services import can_control_session, perform_session_action, serialize_session


# Keep the original-room regression suite on its stored board revision.
from functools import partial
nearby = partial(nearby, board=BOARD)

@override_settings(PARTY_BOARD_VERSION=1, PARTY_EVENT_REVEAL_MS=0, PARTY_ROLL_REVEAL_MS=0)
class PartyTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(name='파티 테스트', description='', group='',
            datas={'hand': {'5000': 5, '3000': 6}}, img='https://example.com/party.png')
        self.room, self.host = create_room({'name': '방장', 'character_id': self.character.pk})
        self.room, self.guest = join_room(self.room.code, {'name': '친구', 'character_id': self.character.pk})

    def act(self, player, action, **data):
        self.room.refresh_from_db()
        self.room = perform_party_action(self.room.code, player.token,
            {'action': action, 'expected_version': self.room.version, **data})
        return self.room

    def start(self):
        self.act(self.host, 'ready')
        self.act(self.guest, 'ready')
        self.act(self.host, 'start')
        self.host.refresh_from_db()
        self.guest.refresh_from_db()

    def battle(self):
        self.start()
        for player, hp in [(self.host, 3400), (self.guest, 2700)]:
            player.refresh_from_db()
            player.hp = hp
            player.position = 1
            player.save()
        self.room.document['landed'] = True
        self.room.save(update_fields=['document'])
        self.act(self.host, 'challenge', target=self.guest.seat)
        return PartyEncounter.objects.get(room=self.room)

    def calc(self, session, action, **data):
        return perform_session_action(session, {'action': action, **data}, control_token=session.control_token)

    def complete(self, session):
        session = self.calc(session, 'party_exchange', expected_exchange=0)
        return self.calc(session, 'party_exchange', expected_exchange=1)

    def land(self, position):
        self.host.refresh_from_db()
        self.host.position = position
        _land(self.room, self.host)
        self.room.save(update_fields=['document'])

    def test_board_is_connected_and_has_four_safe_starting_camps(self):
        self.assertEqual(len(BOARD['nodes']), 32)
        self.assertEqual([n['id'] for n in BOARD['nodes'] if n['kind'] == 'camp'], [0, 6, 12, 18])
        self.assertTrue(all(n['exits'] and all(0 <= end < 32 for end in n['exits']) for n in BOARD['nodes']))
        self.assertTrue(all(n['id'] in BOARD['nodes'][end]['exits'] for n in BOARD['nodes'] for end in n['exits']))
        self.assertEqual({n['kind'] for n in BOARD['nodes']}, {'camp', 'dash', 'charge', 'shop', 'prepare', 'disaster', 'fortune', 'event'})
        self.assertTrue(all(nearby(0, destination, 32) for destination in range(32)))

    def test_four_guest_seats_are_unique_and_fifth_join_is_rejected(self):
        for name in ['3P', '4P']:
            join_room(self.room.code, {'name': name, 'character_id': self.character.pk})
        self.assertEqual(list(self.room.players.values_list('seat', flat=True)), [0, 1, 2, 3])
        with self.assertRaises(ValueError):
            join_room(self.room.code, {'name': '5P', 'character_id': self.character.pk})

    def test_standing_art_is_available_to_web_and_mobile_spectators(self):
        self.character.body_img = 'https://example.com/standing.png'
        self.character.icon_img = 'https://example.com/icon.png'
        self.character.save(update_fields=['body_img', 'icon_img'])
        for url in [reverse('battlelog:partyState', args=[self.room.code]),
                    f'/api/mobile/v1/party/{self.room.code}/state']:
            state = self.client.get(url).json()
            self.assertIsNone(state['me'])
            self.assertEqual(state['players'][1]['character']['body_img'], self.character.body_img)
            self.assertEqual(state['players'][0]['character']['icon_img'], self.character.icon_img)
            self.assertEqual(state['players'][0]['character']['sd_img'], '')
            self.assertEqual(state['board']['shape'], 'octagon')
            self.assertEqual(len(state['board']['nodes']), 32)
            self.assertEqual(state['board']['nodes'][0]['y'], state['board']['nodes'][3]['y'])

    def test_only_host_can_start_and_all_players_must_be_ready(self):
        with self.assertRaises(PermissionDenied):
            self.act(self.guest, 'start')
        with self.assertRaises(ValueError):
            self.act(self.host, 'start')
        self.start()
        self.assertEqual(self.room.status, 'running')
        with self.assertRaises(ValueError):
            join_room(self.room.code, {'character_id': self.character.pk})

    def test_move_is_server_authoritative_and_stale_action_cannot_repeat_roll(self):
        self.start()
        with self.assertRaises(PermissionDenied):
            self.act(self.guest, 'roll')
        self.room.refresh_from_db()
        version = self.room.version
        with patch('battlelog.party_services.secrets.randbelow', return_value=1):
            self.act(self.host, 'roll')
        with self.assertRaises(PartyConflict):
            perform_party_action(self.room.code, self.host.token, {'action': 'roll', 'expected_version': version})
        with self.assertRaises(ValueError):
            self.act(self.host, 'move', node=15)
        self.act(self.host, 'move', node=1)
        version = self.room.version
        with self.assertRaises(ValueError):
            self.act(self.host, 'move', node=2)
        self.host.refresh_from_db()
        self.assertEqual(self.host.position, 2)
        self.assertTrue(self.room.document['landed'])
        self.assertIsNone(self.room.document['move'])
        self.assertEqual(self.room.version, version)
        self.assertEqual(self.room.document['move_path']['nodes'], [0, 1, 2])

    def test_private_items_and_player_tokens_never_leak_into_public_state(self):
        self.host.items = ['heal']
        self.host.save()
        public = serialize_room(self.room)
        self.assertIsNone(public['me'])
        self.assertNotIn(self.host.token, json.dumps(public))
        self.assertNotIn('items', public['players'][0])
        self.assertEqual(serialize_room(self.room, self.host.token)['me']['items'], ['heal'])

    def test_bridge_movement_cannot_reverse_and_direction_survives_turns(self):
        self.start()
        with patch('battlelog.party_services.secrets.randbelow', return_value=0):
            self.act(self.host, 'roll')
        self.act(self.host, 'move', node=24)
        state = serialize_room(self.room, self.host.token)
        self.assertEqual(state['players'][0]['forward_exits'], [25, 31])
        self.act(self.host, 'end_turn')
        self.room.document['landed'] = True
        self.room.save(update_fields=['document'])
        self.act(self.guest, 'end_turn')
        with patch('battlelog.party_services.secrets.randbelow', return_value=2):
            self.act(self.host, 'roll')
        version = self.room.version
        with self.assertRaisesMessage(ValueError, '진행 방향'):
            self.act(self.host, 'move', node=0)
        self.room.refresh_from_db()
        self.assertEqual(self.room.version, version)
        self.assertEqual(self.room.document['move']['remaining'], 3)
        self.act(self.host, 'move', node=31)
        self.assertEqual(self.room.document['move_path']['nodes'], [24, 31, 30])
        self.assertEqual(serialize_room(self.room)['players'][0]['forward_exits'], [29, 18])
        self.assertEqual(self.room.document['headings']['0'], -1)
        self.act(self.host, 'move', node=18)
        self.assertIsNone(self.room.document['move'])

    def test_single_direction_roll_moves_to_destination_and_only_lands_once(self):
        self.start()
        self.host.position = 1
        self.host.save(update_fields=['position'])
        before = self.room.players.get(seat=0).hp
        with patch('battlelog.party_services.secrets.randbelow', return_value=1):
            self.act(self.host, 'roll')
        self.host.refresh_from_db()
        self.assertEqual(self.host.position, 3)
        self.assertEqual(self.host.hp, before - 300)
        self.assertEqual(self.host.prepared_fp, 0)
        self.assertEqual(self.room.document['move_path'],
            {'seat': 0, 'nodes': [1, 2, 3], 'version': self.room.version})
        self.assertIsNone(self.room.document['move'])
        self.assertTrue(self.room.document['landed'])

    def test_automatic_movement_pauses_at_shop_then_stops_at_branch(self):
        self.start()
        self.host.position = 4
        self.host.save(update_fields=['position'])
        self.guest.position = 12
        self.guest.save(update_fields=['position'])
        with patch('battlelog.party_services.secrets.randbelow', return_value=3):
            self.act(self.host, 'roll')
        self.assertEqual(self.room.document['move_path']['nodes'], [4, 5])
        self.assertTrue(self.room.document['move_prompt']['shop'])
        self.act(self.host, 'continue_move')
        self.assertEqual(self.room.document['move_path']['nodes'], [5, 6])
        self.assertEqual(self.room.document['move']['remaining'], 2)
        with self.assertRaisesMessage(ValueError, '지도 화살표'):
            self.act(self.host, 'advance')
        self.act(self.host, 'move', node=7)
        self.assertEqual(self.room.document['move_path']['nodes'], [6, 7, 8])
        self.assertIsNone(self.room.document['move'])

    def test_landing_on_branch_does_not_require_extra_direction_choice(self):
        self.start()
        self.host.position = 5
        self.host.save(update_fields=['position'])
        with patch('battlelog.party_services.secrets.randbelow', return_value=0):
            self.act(self.host, 'roll')
        self.assertEqual(self.room.document['move_path']['nodes'], [5, 6])
        self.assertTrue(self.room.document['landed'])
        self.assertIsNone(self.room.document['move'])

    def test_existing_single_direction_move_can_resume_without_choice(self):
        self.start()
        self.host.position = 1
        self.host.save(update_fields=['position'])
        self.room.document.update({'move': {'dice': 2, 'remaining': 2},
            'previous_positions': {'0': 0}})
        self.room.save(update_fields=['document'])
        self.act(self.host, 'advance')
        self.assertEqual(self.room.document['move_path']['nodes'], [1, 2, 3])
        self.assertIsNone(self.room.document['move'])

    def test_own_camp_can_stop_early_for_reward_and_arrival_purchase(self):
        self.start()
        self.host.position = 24
        self.host.coins = 30
        self.host.save(update_fields=['position', 'coins'])
        with patch('battlelog.party_services.secrets.randbelow', return_value=3):
            self.act(self.host, 'roll')
        self.act(self.host, 'move', node=0)
        self.assertEqual(self.room.document['move_path']['nodes'], [24, 0])
        self.assertTrue(self.room.document['move_prompt']['own_camp'])
        self.assertFalse(serialize_room(self.room, self.host.token)['can_buy_crystal'])
        self.act(self.host, 'stop_home')
        self.host.refresh_from_db()
        self.assertEqual(self.host.coins, 27)
        self.assertEqual(len(self.host.items), 1)
        self.assertFalse(serialize_room(self.room, self.host.token)['can_buy_crystal'])
        self.assertEqual(len(serialize_room(self.room, self.host.token)['camp_gift']['items']), 3)
        self.assertFalse(serialize_room(self.room)['can_buy_crystal'])
        with self.assertRaises(ValueError):
            self.act(self.host, 'buy_crystal')
        self.host.refresh_from_db()
        self.assertEqual(self.host.crystals, 1)
        self.act(self.host, 'skip_camp_gift')
        self.act(self.host, 'end_turn')
        self.assertFalse(serialize_room(self.room, self.host.token)['can_buy_crystal'])

    def test_knockout_rest_preserves_position_and_movement_direction(self):
        self.start()
        self.guest.hp = 0
        self.guest.save(update_fields=['hp'])
        self.room.document.update({'landed': True, 'previous_positions': {'1': 26}})
        self.room.save(update_fields=['document'])
        self.act(self.host, 'end_turn')
        state = serialize_room(self.room)
        self.assertEqual(state['players'][1]['position'], 6)
        self.assertEqual(state['players'][1]['forward_exits'], [7, 5])
        self.assertEqual(state['players'][1]['hp'], 0)

    @override_settings(PARTY_TEST_CONTROLS=False)
    def test_player_switch_is_disabled_outside_test_environment(self):
        for url in [reverse('battlelog:partyTestSeat', args=[self.room.code]),
                    f'/api/mobile/v1/party/{self.room.code}/test-seat']:
            response = self.client.post(url, json.dumps({'seat': 1}), content_type='application/json')
            self.assertEqual(response.status_code, 404)
            self.assertNotIn(self.guest.token, response.content.decode())
        self.assertFalse(serialize_room(self.room)['test_controls'])

    @override_settings(PARTY_TEST_CONTROLS=True)
    def test_web_and_mobile_switch_to_actual_seat_without_changing_game(self):
        self.guest.items = ['prepare']
        self.guest.save(update_fields=['items'])
        version = self.room.version
        for url in [reverse('battlelog:partyTestSeat', args=[self.room.code]),
                    f'/api/mobile/v1/party/{self.room.code}/test-seat']:
            response = self.client.post(url, json.dumps({'seat': 1}), content_type='application/json')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['token'], self.guest.token)
            self.assertEqual(data['state']['me'], {'seat': 1, 'is_host': False, 'items': ['prepare']})
            self.assertEqual(data['state']['version'], version)
            self.assertEqual(data['state']['turn'], 0)
            self.assertEqual(response['Cache-Control'], 'no-store')
            observer = self.client.post(url, json.dumps({'seat': 'spectator'}), content_type='application/json').json()
            self.assertEqual(observer['token'], '')
            self.assertIsNone(observer['state']['me'])
            for invalid in [True, -1, 4, 2, '1']:
                self.assertEqual(self.client.post(url, json.dumps({'seat': invalid}), content_type='application/json').status_code, 400)
        self.room.refresh_from_db()
        self.assertEqual(self.room.version, version)
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(reverse('battlelog:partyTestSeat', args=[self.room.code]),
            json.dumps({'seat': 1}), content_type='application/json').status_code, 403)

    def test_battle_starts_at_current_health_and_only_participants_receive_controls(self):
        third_room, third = join_room(self.room.code, {'name': '관전자', 'character_id': self.character.pk})
        self.act(third, 'ready')
        encounter = self.battle()
        session = encounter.session
        self.assertEqual(session.session_type, BattleSession.SESSION_PARTY)
        self.assertEqual((session.player1_hp, session.player2_hp), (3400, 2700))
        self.assertEqual(session.player1_initial_hp, 5000)
        self.assertIn('control_token', serialize_room(self.room, self.host.token)['battle'])
        self.assertIn('control_token', serialize_room(self.room, self.guest.token)['battle'])
        self.assertNotIn('control_token', serialize_room(self.room, third.token)['battle'])
        self.assertFalse(can_control_session(None, session, ''))

    def test_exactly_two_exchanges_lock_calculator_and_reject_duplicate_completion(self):
        encounter = self.battle()
        session = self.calc(encounter.session, 'party_exchange', expected_exchange=0)
        with self.assertRaises(ValueError):
            self.calc(session, 'party_exchange', expected_exchange=0)
        self.assertTrue(can_control_session(None, session, session.control_token))
        session = self.calc(session, 'hp', target='p1', amount=-300)
        session = self.calc(session, 'party_exchange', expected_exchange=1)
        self.assertFalse(can_control_session(None, session, session.control_token))
        for action, data in [('hp', {'target': 'p1', 'amount': -100}), ('party_exchange', {'expected_exchange': 2})]:
            with self.assertRaises(PermissionDenied):
                self.calc(session, action, **data)
        self.assertEqual(serialize_session(session)['party']['exchanges'], 2)

    def test_party_rejects_character_reset_sudden_death_and_exchange_batches(self):
        session = self.battle().session
        for action in ['character', 'reset_session', 'sudden_death']:
            with self.assertRaises(ValueError):
                self.calc(session, action)
        with self.assertRaises(ValueError):
            self.calc(session, 'batch', actions=[{'action': 'party_exchange', 'expected_exchange': 0}])

    def test_one_submission_applies_hp_once_without_victory_or_coin_transfer(self):
        encounter = self.battle()
        session = self.calc(encounter.session, 'hp', target='p1', amount=-300)
        session = self.calc(session, 'hp', target='p2', amount=-600)
        with self.assertRaises(ValueError):
            self.act(self.host, 'confirm_battle', battle_version=session.version)
        session = self.complete(session)
        self.act(self.host, 'confirm_battle', battle_version=session.version)
        self.host.refresh_from_db(); self.guest.refresh_from_db(); encounter.refresh_from_db()
        self.assertEqual((self.host.hp, self.guest.hp), (3100, 2100))
        self.assertEqual((self.host.coins, self.guest.coins), (3, 0))
        self.assertNotIn('winner', encounter.result)
        self.assertEqual(encounter.status, 'finished')
        self.assertIsNone(serialize_room(self.room)['battle'])
        with self.assertRaises((ValueError, PermissionDenied)):
            self.act(self.guest, 'confirm_battle', battle_version=session.version)
        self.host.refresh_from_db()
        self.assertEqual(self.host.coins, 3)

    def test_defender_can_submit_without_winner_or_attacker_confirmation(self):
        session = self.complete(self.battle().session)
        self.act(self.guest, 'confirm_battle', battle_version=session.version)
        self.assertIsNone(serialize_room(self.room)['battle'])
        self.host.refresh_from_db()
        self.assertEqual(self.host.coins, 1)

    def test_host_can_cancel_without_importing_partial_damage(self):
        encounter = self.battle()
        self.calc(encounter.session, 'hp', target='p1', amount=-1000)
        with self.assertRaises(PermissionDenied):
            self.act(self.guest, 'cancel_battle')
        self.act(self.host, 'cancel_battle')
        self.host.refresh_from_db(); encounter.refresh_from_db()
        self.assertEqual(self.host.hp, 3400)
        self.assertEqual(encounter.status, 'cancelled')

    def test_knocked_out_player_rests_then_revives_and_keeps_crystals(self):
        self.start()
        self.guest.hp = 0; self.guest.crystals = 1; self.guest.save()
        self.room.document['landed'] = True; self.room.save(update_fields=['document'])
        self.act(self.host, 'end_turn')
        self.guest.refresh_from_db()
        self.assertEqual((self.guest.hp, self.guest.position, self.guest.crystals), (0, 6, 1))
        self.act(self.guest, 'end_turn')
        self.room.document['landed'] = True; self.room.save(update_fields=['document'])
        self.act(self.host, 'end_turn')
        self.guest.refresh_from_db()
        self.assertEqual((self.guest.hp, self.guest.position, self.guest.crystals), (2500, 6, 1))

    def test_round_order_uses_fp_then_hp_and_stays_fixed_during_round(self):
        self.room, third = join_room(self.room.code, {'name': '셋째', 'character_id': self.character.pk})
        self.room, fourth = join_room(self.room.code, {'name': '넷째', 'character_id': self.character.pk})
        self.act(third, 'ready'); self.act(fourth, 'ready')
        self.start()
        players = [self.host, self.guest, third, fourth]
        for player, fp, hp in zip(players, [2, 5, 5, -1], [5000, 3000, 4500, 5000]):
            player.prepared_fp = fp; player.hp = hp
            player.save(update_fields=['prepared_fp', 'hp'])
        for player in players:
            self.room.document['landed'] = True; self.room.save(update_fields=['document'])
            self.act(player, 'end_turn')
        state = serialize_room(self.room)
        self.assertEqual((state['round'], state['turn_order'], state['turn']), (2, [2, 1, 0, 3], 2))
        self.assertEqual(state['order_change']['from'], [0, 1, 2, 3])
        self.assertEqual(state['order_change']['to'], [2, 1, 0, 3])
        self.assertNotIn(self.host.token, json.dumps(state))
        self.host.prepared_fp = 99; self.host.save(update_fields=['prepared_fp'])
        for seat in [2, 1, 0, 3]:
            self.assertEqual(self.room.document['turn'], seat)
            self.room.document['landed'] = True; self.room.save(update_fields=['document'])
            self.act(players[seat], 'end_turn')
        self.assertEqual(self.room.document['turn_order'], [0, 2, 1, 3])
        self.assertEqual((self.room.document['round'], self.room.document['turn']), (3, 0))

    def test_round_order_ties_keep_previous_order_and_legacy_rooms_have_seat_order(self):
        self.start()
        self.room.document.pop('turn_order', None)
        self.assertEqual(serialize_room(self.room)['turn_order'], [0, 1])
        self.room.document.update({'turn_order': [1, 0], 'turn': 1, 'landed': True})
        self.room.save(update_fields=['document'])
        self.act(self.guest, 'end_turn')
        self.room.document['landed'] = True; self.room.save(update_fields=['document'])
        self.act(self.host, 'end_turn')
        self.assertEqual(self.room.document['turn_order'], [1, 0])
        self.assertEqual((self.room.document['round'], self.room.document['turn']), (2, 1))
        self.assertIsNone(self.room.document['order_change'])

    def test_reordered_round_finishes_only_after_last_player(self):
        self.start()
        self.room.document.update({'turn_order': [1, 0], 'turn': 1, 'landed': True})
        self.room.save(update_fields=['document'])
        self.guest.crystals = 3; self.guest.save(update_fields=['crystals'])
        self.act(self.guest, 'end_turn')
        self.assertEqual(self.room.status, 'running')
        self.room.document['landed'] = True; self.room.save(update_fields=['document'])
        self.act(self.host, 'end_turn')
        self.assertEqual(self.room.status, 'finished')
        self.assertEqual(self.room.document['winners'], [1])

    def test_rounds_are_unlimited_and_three_crystals_finish_after_all_turns(self):
        self.start()
        self.room.document.update({'round': 12, 'landed': True}); self.room.save(update_fields=['document'])
        self.act(self.host, 'end_turn')
        self.assertEqual(self.room.status, 'running')
        self.room.document['landed'] = True; self.room.save(update_fields=['document'])
        self.act(self.guest, 'end_turn')
        self.assertEqual(self.room.status, 'running')
        self.assertEqual(self.room.document['round'], 13)
        self.host.crystals = 3; self.host.save(update_fields=['crystals'])
        self.room.document['landed'] = True; self.room.save(update_fields=['document'])
        self.act(self.host, 'end_turn')
        self.room.document['landed'] = True; self.room.save(update_fields=['document'])
        self.act(self.guest, 'end_turn')
        self.assertEqual(self.room.status, 'finished')
        self.assertEqual(self.room.document['winners'], [0])

    def test_web_pages_api_reconnect_and_csrf(self):
        response = self.client.get(reverse('battlelog:partyHome'))
        self.assertContains(response, '새 파티 만들기')
        self.assertContains(self.client.get(reverse('battlelog:partyRoom', args=[self.room.code])), 'party-initial-state')
        response = self.client.get(reverse('battlelog:partyState', args=[self.room.code]), HTTP_X_PARTY_PLAYER=self.host.token)
        self.assertEqual(response.json()['me']['seat'], 0)
        response = self.client.post(reverse('battlelog:partyAction', args=[self.room.code]),
            json.dumps({'action': 'ready', 'expected_version': self.room.version}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(reverse('battlelog:partyCreate'), '{}', content_type='application/json').status_code, 403)

    def test_shared_3d_board_page_has_no_participant_credentials(self):
        response = self.client.get(reverse('battlelog:partyBoard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'lumen-party-scene.js')
        self.assertContains(response, 'updatePartyBoard')
        self.assertNotContains(response, self.host.token)
        self.assertNotContains(response, self.guest.token)
        response = self.client.get(reverse('battlelog:partyRoom', args=[self.room.code]))
        self.assertContains(response, 'lumen-party-3d.js')
        self.assertContains(response, 'data-party-map-toggle')

    def test_native_api_and_final_exchange_receipt_replay(self):
        session = self.battle().session
        session = self.calc(session, 'party_exchange', expected_exchange=0)
        payload = {'action': 'party_exchange', 'expected_exchange': 1,
                   'expected_version': session.version, 'action_id': str(uuid.uuid4())}
        completed = perform_mobile_action(session.view_token, payload, session.control_token)
        replay = perform_mobile_action(session.view_token, payload, session.control_token)
        self.assertEqual(replay.version, completed.version)
        response = self.client.get(f'/api/mobile/v1/party/{self.room.code}/state', HTTP_X_PARTY_PLAYER=self.host.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['battle']['exchanges'], 2)
        response = self.client.get(f'/api/mobile/v1/calculators/{session.view_token}/state', HTTP_X_CALCULATOR_CONTROL=session.control_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['party']['code'], self.room.code)

    def test_expired_room_rejects_join_and_mutation(self):
        PartyRoom.objects.filter(pk=self.room.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(ValueError):
            self.act(self.host, 'ready')
        with self.assertRaises(ValueError):
            join_room(self.room.code, {'character_id': self.character.pk})

    def test_initial_direction_and_counterclockwise_route_are_preserved(self):
        self.start()
        state = serialize_room(self.room)
        self.assertEqual(state['players'][0]['forward_exits'], [1, 24])
        self.assertEqual(state['players'][1]['forward_exits'], [7, 26])
        self.room.document['previous_positions'] = {'0': 24}
        self.room.save(update_fields=['document'])
        with patch('battlelog.party_services.secrets.randbelow', return_value=1):
            self.act(self.host, 'roll')
        self.act(self.host, 'move', node=23)
        self.assertEqual(self.room.document['move_path']['nodes'], [0, 23])
        self.assertTrue(self.room.document['move_prompt']['shop'])
        self.act(self.host, 'continue_move')
        self.assertEqual(self.room.document['move_path']['nodes'], [23, 22])
        self.assertEqual(self.room.document['headings']['0'], -1)
        self.assertEqual(serialize_room(self.room)['players'][0]['forward_exits'], [21])
        with patch('battlelog.party_services.secrets.randbelow', return_value=1):
            self.act(self.host, 'roll')
        self.act(self.host, 'end_turn')
        self.room.document['landed'] = True; self.room.save(update_fields=['document'])
        self.act(self.guest, 'end_turn')
        self.assertEqual(serialize_room(self.room)['players'][0]['forward_exits'], [19])

    def test_passing_player_pauses_and_can_be_skipped_without_losing_moves(self):
        self.start()
        self.host.position = 1; self.host.save(update_fields=['position'])
        self.guest.position = 2; self.guest.save(update_fields=['position'])
        with patch('battlelog.party_services.secrets.randbelow', return_value=2):
            self.act(self.host, 'roll')
        state = serialize_room(self.room, self.host.token)
        self.assertEqual(state['move']['remaining'], 2)
        self.assertEqual(state['challenge_targets'], [1])
        self.assertEqual(state['move_prompt'], {'targets': [1], 'own_camp': False})
        with self.assertRaises(ValueError):
            self.act(self.host, 'move', node=3)
        self.act(self.host, 'continue_move')
        self.assertEqual(self.room.document['move_path']['nodes'], [2, 3, 4])
        self.assertIsNone(self.room.document['move'])
        self.assertEqual(self.room.encounters.count(), 0)

    def test_passing_battle_resumes_remaining_moves_after_one_submission(self):
        self.start()
        self.host.position = 1; self.host.prepared_fp = -2; self.host.save()
        self.guest.position = 2; self.guest.prepared_fp = 3; self.guest.save()
        self.room.document['round'] = 6; self.room.save(update_fields=['document'])
        with patch('battlelog.party_services.secrets.randbelow', return_value=1):
            self.act(self.host, 'roll')
        self.act(self.host, 'challenge', target=1)
        encounter = self.room.encounters.get()
        self.assertEqual((encounter.session.player1_fp, encounter.session.player2_fp), (-1, 3))
        self.assertEqual(encounter.snapshot['attacker_bonus'], 1)
        session = self.complete(encounter.session)
        self.act(self.host, 'confirm_battle', battle_version=session.version)
        self.assertIsNone(self.room.document['move_prompt'])
        self.assertIsNone(self.room.document['move'])
        self.assertEqual(self.room.document['move_path']['nodes'], [2, 3, 4])
        self.host.refresh_from_db()
        self.assertEqual(self.host.prepared_fp, 0)

    def test_all_camps_allow_battles_and_no_location_has_immunity(self):
        self.start()
        self.guest.position = 0; self.guest.battle_immune = True; self.guest.save()
        self.land(0)
        self.assertEqual(serialize_room(self.room, self.host.token)['challenge_targets'], [1])
        self.act(self.host, 'challenge', target=1)
        session = self.complete(self.room.encounters.get().session)
        self.act(self.host, 'confirm_battle', battle_version=session.version)
        self.guest.refresh_from_db()
        self.assertFalse(self.guest.battle_immune)

    def test_continue_at_own_camp_does_not_grant_arrival_rewards(self):
        self.start()
        self.host.position = 23; self.host.save(update_fields=['position'])
        before = self.host.coins
        with patch('battlelog.party_services.secrets.randbelow', return_value=1):
            self.act(self.host, 'roll')
        self.assertEqual(self.room.document['move_prompt'], {'targets': [], 'own_camp': True})
        self.assertFalse(serialize_room(self.room, self.host.token)['can_buy_crystal'])
        self.act(self.host, 'continue_move')
        with patch('battlelog.party_services.secrets.randbelow', return_value=0):
            self.act(self.host, 'move', node=1)
        self.host.refresh_from_db()
        self.assertEqual(self.host.items, [])
        self.assertNotEqual(self.host.position, 0)
        self.assertEqual(self.host.coins, before + 1)

    def test_full_home_reward_requires_choice_and_keeps_three_item_limit(self):
        self.start()
        self.host.items = ['heal', 'boost', 'prepare']; self.host.hp = 2000; self.host.coins = 3; self.host.save()
        with patch('battlelog.party_services.secrets.randbelow', return_value=0):
            self.land(0)
        self.assertEqual(serialize_room(self.room, self.host.token)['item_reward'], 'heal')
        with self.assertRaises(ValueError):
            self.act(self.host, 'end_turn')
        self.act(self.host, 'claim_item', index=1)
        self.host.refresh_from_db()
        self.assertEqual(self.host.items, ['heal', 'heal', 'prepare'])
        self.assertEqual(self.host.hp, 2000)
        self.act(self.host, 'skip_camp_gift')
        self.act(self.host, 'end_turn')

    def test_crystal_prices_and_arrival_requirement_apply_at_any_camp(self):
        self.start()
        self.host.coins = 60; self.host.save()
        with self.assertRaises(ValueError):
            self.act(self.host, 'buy_crystal')
        for crystals, cost in enumerate([6, 10, 15]):
            self.host.refresh_from_db()
            self.host.crystals = crystals; self.host.coins = 60; self.host.save()
            self.room.document['turn_number'] += 1
            self.land(12)
            self.host.refresh_from_db()
            self.assertEqual((self.host.coins, self.host.crystals), (60 - cost, crystals + 1))
            with self.assertRaises(ValueError):
                self.act(self.host, 'buy_crystal')

    def test_home_reward_requires_swap_instead_of_item_use_after_arrival(self):
        self.start()
        self.host.items = ['heal', 'boost', 'prepare']; self.host.hp = 2000; self.host.save()
        with patch('battlelog.party_services.secrets.randbelow', return_value=0):
            self.land(0)
        with self.assertRaisesMessage(ValueError, '이동 전에만'):
            self.act(self.host, 'use_item', item='heal')
        self.act(self.host, 'claim_item', index=0)
        state = serialize_room(self.room, self.host.token)
        self.assertIsNone(state['item_reward'])
        self.assertEqual(state['me']['items'], ['heal', 'hurry', 'prepare'])
        self.assertEqual(state['players'][0]['hp'], 2000)

    def test_dash_requires_extra_roll_and_charge_is_optional(self):
        self.start()
        self.land(4)
        self.assertFalse(self.room.document['landed'])
        self.assertEqual(self.room.document['arrival'], 'dash')
        with self.assertRaises(ValueError):
            self.act(self.host, 'end_turn')
        with patch('battlelog.party_services.secrets.randbelow', return_value=0):
            self.act(self.host, 'roll')
        self.host.refresh_from_db()
        self.assertEqual(self.host.position, 5)
        self.land(24)
        self.act(self.host, 'skip_charge')
        self.assertIsNone(self.room.document['arrival'])
        self.act(self.host, 'end_turn')

    def test_charge_teleports_to_target_then_applies_tile_effect_and_offers_battle(self):
        self.start()
        self.guest.position = 2; self.guest.save(update_fields=['position'])
        self.land(24)
        self.act(self.host, 'charge', target=1)
        self.host.refresh_from_db()
        self.assertEqual(self.host.position, 2)
        self.assertEqual(self.host.prepared_fp, 2)
        self.assertEqual(serialize_room(self.room, self.host.token)['challenge_targets'], [1])
        self.act(self.host, 'challenge', target=1)
        self.assertEqual(self.room.encounters.get().session.player1_fp, 2)

    def test_shop_allows_one_purchase_and_preparation_accumulates_until_battle(self):
        self.start()
        self.host.coins = 30; self.host.items = ['prepare']; self.host.save()
        self.act(self.host, 'use_item', item='prepare')
        self.room.document['shop_offer'] = {'turn': self.room.document['turn_number'], 'items': ['prepare', 'heal', 'hurry']}
        self.room.save()
        self.land(5)
        self.act(self.host, 'buy_item', item='prepare')
        with self.assertRaises(ValueError):
            self.act(self.host, 'buy_item', item='boost')
        with self.assertRaisesMessage(ValueError, '이동 전에만'):
            self.act(self.host, 'use_item', item='prepare')
        self.land(2)
        self.host.refresh_from_db()
        self.assertEqual(self.host.prepared_fp, 6)
        self.act(self.host, 'end_turn')
        self.host.refresh_from_db()
        self.assertEqual(self.host.prepared_fp, 6)

    def test_fortune_disaster_and_round_bonus_boundaries(self):
        self.start()
        self.host.coins = 10; self.host.hp = 250; self.host.save()
        with patch('battlelog.party_services.secrets.randbelow', return_value=4):
            self.land(1)
        self.host.refresh_from_db()
        self.assertEqual(self.host.coins, 15)
        self.land(3)
        self.host.refresh_from_db()
        self.assertEqual(self.host.hp, 0)
        for round_number, movement, attack in [(1, 0, 0), (3, 0, 0), (4, 1, 0), (5, 1, 0), (6, 1, 1), (7, 2, 1), (11, 3, 2), (31, 10, 6)]:
            self.room.document['round'] = round_number
            state = serialize_room(self.room)
            self.assertEqual((state['movement_power'], state['attacker_bonus']), (movement, attack))

    def test_all_eight_events_and_offline_hand_instruction(self):
        self.start()
        for event in ['discard', 'rich', 'swamp', 'hurry', 'chance', 'home', 'box', 'poison']:
            with self.subTest(event=event):
                for p in self.room.players.all():
                    p.hp = 4000; p.coins = 10; p.prepared_fp = 0; p.items = []; p.position = 1; p.save()
                with patch('battlelog.party_services.secrets.choice', return_value=event):
                    self.land(25)
                self.host.refresh_from_db(); self.guest.refresh_from_db()
                self.assertEqual(self.room.document['event']['id'], event)
                if event == 'discard':
                    self.assertIn('3장', self.room.document['event']['description'])
                elif event == 'rich':
                    self.assertEqual((self.host.coins, self.guest.coins), (12, 12))
                elif event == 'swamp':
                    self.assertEqual(self.host.prepared_fp, -2)
                elif event == 'chance':
                    self.assertEqual(self.host.prepared_fp, 9)
                elif event == 'hurry':
                    self.assertEqual(self.room.document['double_dice'], {'0': True, '1': True})
                elif event == 'home':
                    self.assertEqual((self.host.position, self.guest.position), (0, 6))
                    self.assertEqual((self.host.coins, self.host.items), (10, []))
                    self.assertFalse(serialize_room(self.room, self.host.token)['can_buy_crystal'])
                elif event == 'box':
                    self.assertEqual(len(self.host.items), 3)
                    self.assertEqual(self.guest.items, [])
                elif event == 'poison':
                    self.assertEqual(self.room.document['poison_turns'], {'0': 3, '1': 3})

    def test_double_dice_is_consumed_individually_and_adds_movement_power(self):
        self.start()
        with patch('battlelog.party_services.secrets.choice', return_value='hurry'):
            self.land(25)
        self.host.position = 0; self.host.items = ['boost']; self.host.save()
        self.room.document.update({'round': 4, 'landed': False}); self.room.save(update_fields=['document'])
        self.act(self.host, 'use_item', item='boost')
        with patch('battlelog.party_services.secrets.randbelow', side_effect=[1, 4]):
            self.act(self.host, 'roll')
        self.assertEqual(self.room.document['move']['dice_values'], [2, 5])
        self.assertEqual(self.room.document['move']['bonus'], 1)
        self.assertEqual(self.room.document['move']['remaining'], 8)
        self.assertNotIn('0', self.room.document['double_dice'])
        self.assertTrue(self.room.document['double_dice']['1'])
        state = serialize_room(self.room)
        self.assertFalse(state['players'][0]['double_dice'])
        self.assertTrue(state['players'][1]['double_dice'])

    def test_poison_ticks_for_exactly_three_personal_turns(self):
        self.start()
        with patch('battlelog.party_services.secrets.choice', return_value='poison'):
            self.land(25)
        for cycle in range(4):
            self.room.document['landed'] = True; self.room.save(update_fields=['document'])
            self.act(self.host, 'end_turn')
            self.guest.refresh_from_db()
            self.assertEqual(self.guest.hp, 5000 - min(cycle + 1, 3) * 500)
            self.room.document['landed'] = True; self.room.save(update_fields=['document'])
            self.act(self.guest, 'end_turn')
            self.host.refresh_from_db()
            self.assertEqual(self.host.hp, 5000 - min(cycle + 1, 3) * 500)
        self.assertEqual(self.room.document['poison_turns'], {'0': 0, '1': 0})

    def test_removed_notes_and_max_round_setting_do_not_return(self):
        state = serialize_room(self.room, self.host.token)
        self.assertNotIn('max_rounds', state)
        self.assertNotIn('public_notes', state['players'][0])
        self.assertNotIn('battle_immune', state['players'][0])
        with self.assertRaises(ValueError):
            self.act(self.host, 'notes', public_notes='unused')
        page = self.client.get(reverse('battlelog:partyRoom', args=[self.room.code]))
        self.assertNotContains(page, 'data-party-notes')
        self.assertNotContains(page, '공개 리스트 · 상태 메모')
        self.assertNotContains(self.client.get(reverse('battlelog:partyHome')), 'name="max_rounds"')

    def test_exact_arrival_does_not_offer_the_same_finished_opponent_again(self):
        self.start()
        self.room.document['round'] = 6; self.room.save(update_fields=['document'])
        self.guest.position = 2; self.guest.hp = 2500; self.guest.save()
        with patch('battlelog.party_services.secrets.randbelow', return_value=0):
            self.act(self.host, 'roll')
        self.act(self.host, 'move', node=1)
        state = serialize_room(self.room, self.host.token)
        self.assertTrue(state['landed'])
        self.assertIsNone(state['move_prompt'])
        self.assertEqual(state['challenge_targets'], [1])
        self.act(self.host, 'challenge', target=1)
        first = self.room.encounters.get().session
        self.assertEqual(first.player1_fp, 4)
        with self.assertRaises(ValueError):
            self.act(self.host, 'challenge', target=1)
        first = self.calc(first, 'hp', target='p1', amount=-200)
        first = self.calc(first, 'hp', target='p2', amount=-100)
        first = self.complete(first)
        self.act(self.host, 'confirm_battle', battle_version=first.version)
        self.assertEqual(serialize_room(self.room, self.host.token)['challenge_targets'], [])
        with self.assertRaises(ValueError):
            self.act(self.host, 'challenge', target=1)
        self.assertEqual(self.room.encounters.filter(status='finished').count(), 1)
        self.host.refresh_from_db(); self.guest.refresh_from_db()
        self.assertEqual((self.host.hp,self.guest.hp),(4800,2400))

    def test_passing_point_offers_another_opponent_after_battle(self):
        room, third = join_room(self.room.code, {'name': '세 번째', 'character_id': self.character.pk})
        self.act(third, 'ready')
        self.start()
        self.host.position = 1; self.host.save(update_fields=['position'])
        for player in [self.guest, third]:
            player.position = 2; player.save(update_fields=['position'])
        with patch('battlelog.party_services.secrets.randbelow', return_value=2):
            self.act(self.host, 'roll')
        self.act(self.host, 'challenge', target=1)
        session = self.complete(self.room.encounters.get().session)
        self.act(self.host, 'confirm_battle', battle_version=session.version)
        self.assertEqual(self.room.document['move']['remaining'], 2)
        self.assertEqual(serialize_room(self.room, self.host.token)['challenge_targets'], [2])
        self.act(self.host, 'challenge', target=2)
        self.assertEqual(self.room.encounters.count(), 2)

    def test_preview_branches_and_target_routes_match_remaining_budget(self):
        self.start()
        with patch('battlelog.party_services.secrets.randbelow', return_value=1):
            self.act(self.host, 'roll')
        preview = serialize_room(self.room, self.host.token)['movement_preview']
        self.assertEqual(preview['nodes'], [1, 2, 24, 25, 31])
        self.assertEqual(set(preview['edges']), {'0-1', '1-2', '0-24', '24-25', '24-31'})
        self.assertEqual(preview['routes']['2'], {'nodes': [0, 1, 2], 'edges': ['0-1', '1-2']})
        self.assertEqual(preview['routes']['25'], {'nodes': [0, 24, 25], 'edges': ['0-24', '24-25']})
        self.assertNotIn('3', preview['routes'])
        self.assertEqual(preview, serialize_room(self.room)['movement_preview'])
        version = self.room.version
        self.act(self.host, 'move', node=1)
        self.assertIsNone(serialize_room(self.room)['movement_preview'])
        self.assertEqual(self.room.version, version + 1)

    def test_preview_respects_counterclockwise_and_does_not_reverse(self):
        self.start()
        self.room.document.update({'previous_positions': {'0': 24}, 'move': {'dice': 2, 'remaining': 2}})
        preview = movement_preview(self.room, self.host)
        self.assertEqual(preview['nodes'], [1, 2, 22, 23])
        self.assertEqual(preview['routes']['22']['edges'], ['0-23', '22-23'])
        self.assertNotIn('24', preview['routes'])
        self.host.position = 24
        self.room.document['previous_positions'] = {'0': 0}
        preview = movement_preview(self.room, self.host)
        self.assertEqual(preview['nodes'], [25, 26, 30, 31])
        self.assertNotIn('0-24', preview['edges'])
        self.assertNotIn('6', preview['routes'])

    def test_preview_handles_large_movement_without_expanding_all_walks(self):
        self.start()
        self.room.document['move'] = {'dice': 6, 'remaining': 10000}
        preview = movement_preview(self.room, self.host)
        self.assertEqual(len(preview['nodes']), 32)
        self.assertEqual(len(preview['edges']), 36)
        self.assertEqual(len(preview['routes']), 32)
        self.assertLess(len(json.dumps(preview)), 25000)
