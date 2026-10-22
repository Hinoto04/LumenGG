from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings

from card.models import Character
from .models import PartyEncounter
from .party_board import LEGACY_BOARD as BOARD, SHOP, nearby
from .party_services import create_room, join_room, perform_party_action, serialize_room, _land, forward_exits, PartyConflict
from .services import perform_session_action


# Keep the original-room regression suite on its stored board revision.
from functools import partial
nearby = partial(nearby, board=BOARD)

@override_settings(PARTY_BOARD_VERSION=1, PARTY_EVENT_REVEAL_MS=0, PARTY_ROLL_REVEAL_MS=0)
class PartyRulesTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(name='규칙 테스트', description='', group='',
            datas={'hand': {'4450': 5, '3000': 7, '2000': 8}, 'initial_passive_state': {'focus': {'count': 3}}}, img='https://example.com/card.png')
        self.room, self.host = create_room({'name': '방장', 'character_id': self.character.pk})
        self.room, self.guest = join_room(self.room.code, {'name': '친구', 'character_id': self.character.pk})
        self.act(self.host, 'ready'); self.act(self.guest, 'ready'); self.act(self.host, 'start')
        self.host.refresh_from_db(); self.guest.refresh_from_db()

    def act(self, player, action, **data):
        self.room.refresh_from_db()
        self.room = perform_party_action(self.room.code, player.token,
            {'action': action, 'expected_version': self.room.version, **data})
        return self.room

    def stock(self, player, *items):
        player.refresh_from_db(); player.items = list(items); player.save(update_fields=['items'])
        self.room.refresh_from_db(); self.room.document.pop('item_turn', None); self.room.save(update_fields=['document'])

    def end(self, player):
        self.room.refresh_from_db(); self.room.document['landed'] = True; self.room.save(update_fields=['document'])
        self.act(player, 'end_turn')

    def confirm(self, hp1=None, hp2=None):
        encounter = self.room.encounters.get(status='active')
        session = encounter.session
        if hp1 is not None: session.player1_hp = hp1
        if hp2 is not None: session.player2_hp = hp2
        session.save()
        for index in range(2):
            session = perform_session_action(session, {'action': 'party_exchange', 'expected_exchange': index}, control_token=session.control_token)
            if serialize_room(self.room, encounter.player1.token)['battle']['completed']:
                break
        self.act(encounter.player1, 'confirm_battle', battle_version=session.version)
        return session

    def meet(self):
        self.host.position = 1; self.guest.position = 1
        self.host.save(update_fields=['position']); self.guest.save(update_fields=['position'])
        self.room.document['landed'] = True; self.room.save(update_fields=['document'])

    def test_catalog_and_short_tile_descriptions(self):
        self.assertEqual(len(SHOP), 13)
        self.assertTrue(all(item['price'] == 3 and item['image'] == '' for item in SHOP.values()))
        self.assertEqual(BOARD['nodes'][0]['description'], '도착 시, 코인을 지불하고 승점을 구매 가능')
        self.assertEqual(BOARD['nodes'][2]['description'], '도착 시, FP 획득')

    def test_preparation_adds_attacker_bonus_without_drawing_a_card(self):
        for round_number, amount in [(1, 2), (6, 3), (11, 4)]:
            self.room.document['round'] = round_number
            self.host.prepared_fp = 0
            self.host.position = 2
            _land(self.room, self.host)
            self.assertEqual(self.host.prepared_fp, amount)
            self.assertFalse(self.room.document.get('hand_tasks'))

    def test_heals_fixed_hp_and_preparation_item_is_four_fp(self):
        self.host.hp = 4000; self.host.save(update_fields=['hp'])
        self.stock(self.host, 'heal'); self.act(self.host, 'use_item', item='heal')
        self.host.refresh_from_db(); self.assertEqual(self.host.hp, 4200)
        self.stock(self.host, 'heal_kit'); self.act(self.host, 'use_item', item='heal_kit')
        self.host.refresh_from_db(); self.assertEqual(self.host.hp, 4450)
        self.stock(self.host, 'prepare'); self.act(self.host, 'use_item', item='prepare')
        self.host.refresh_from_db(); self.assertEqual(self.host.prepared_fp, 4)

    def test_damage_range_and_invalid_targets_do_not_consume_item(self):
        self.stock(self.host, 'brick', 'gun')
        self.guest.position = next(n for n in range(32) if nearby(0, n, 6) and not nearby(0, n, 4)); self.guest.save()
        version = self.room.version
        with self.assertRaises(ValueError): self.act(self.host, 'use_item', item='brick', target=1)
        self.host.refresh_from_db(); self.assertEqual(self.host.items, ['brick', 'gun'])
        self.room.refresh_from_db(); self.assertEqual(self.room.version, version)
        self.act(self.host, 'use_item', item='gun', target=1)
        self.guest.refresh_from_db(); self.assertEqual(self.guest.hp, 4150)

    def test_shield_blocks_one_item_damage_and_does_not_award_score(self):
        self.guest.position = 1; self.guest.hp = 100; self.guest.save()
        self.room.document['shields'] = {'1': True}; self.room.save(update_fields=['document'])
        self.stock(self.host, 'brick'); self.act(self.host, 'use_item', item='brick', target=1)
        self.guest.refresh_from_db(); self.host.refresh_from_db()
        self.assertEqual((self.guest.hp, self.host.crystals), (100, 0))
        self.assertFalse(self.room.document['shields'])
        self.stock(self.host, 'gun'); self.act(self.host, 'use_item', item='gun', target=1)
        self.guest.refresh_from_db(); self.host.refresh_from_db()
        self.assertEqual((self.guest.hp, self.host.crystals), (0, 1))

    def test_double_dice_and_smart_die_are_consumed_by_one_movement_roll(self):
        self.stock(self.host, 'hurry'); self.act(self.host, 'use_item', item='hurry')
        self.stock(self.host, 'smart_dice'); self.act(self.host, 'use_item', item='smart_dice', value=4)
        with patch('battlelog.party_services.secrets.randbelow', return_value=5) as random:
            self.act(self.host, 'roll')
        self.assertEqual(self.room.document['move']['dice_values'], [4, 6])
        self.assertEqual(self.room.document['move']['remaining'], 10)
        self.assertEqual(random.call_count, 1)
        self.assertFalse(self.room.document['double_dice'])
        self.assertFalse(self.room.document['smart_dice'])

    def test_smart_die_rejects_non_integer_and_out_of_range_without_consuming(self):
        self.stock(self.host, 'smart_dice')
        for value in [0, 7, True, '3', 3.5]:
            with self.assertRaises(ValueError): self.act(self.host, 'use_item', item='smart_dice', value=value)
        self.host.refresh_from_db(); self.assertEqual(self.host.items, ['smart_dice'])

    def test_free_initial_direction_allows_reversal_once_then_preserves_heading(self):
        self.stock(self.host, 'redirect'); self.act(self.host, 'use_item', item='redirect')
        with patch('battlelog.party_services.secrets.randbelow', return_value=0): self.act(self.host, 'roll')
        self.assertEqual(forward_exits(self.room, self.host), [1, 23, 24])
        self.act(self.host, 'move', node=23)
        self.host.refresh_from_db()
        self.assertEqual(self.host.position, 23)
        self.assertEqual(forward_exits(self.room, self.host), [22])
        self.assertFalse(self.room.document['free_direction'])

    def test_barrier_stops_on_entry_removes_itself_and_applies_arrival(self):
        self.stock(self.host, 'roadblock'); self.act(self.host, 'use_item', item='roadblock', node=2)
        self.assertEqual(self.room.document['roadblocks'], [{'node': 2, 'owner': 0}])
        with patch('battlelog.party_services.secrets.randbelow', return_value=5): self.act(self.host, 'roll')
        preview = serialize_room(self.room, self.host.token)['movement_preview']
        self.assertNotIn('2-3', preview['edges'])
        self.act(self.host, 'move', node=1)
        self.host.refresh_from_db()
        self.assertEqual((self.host.position, self.host.prepared_fp), (2, 2))
        self.assertIsNone(self.room.document['move'])
        self.assertTrue(self.room.document['landed'])
        self.assertEqual(self.room.document['roadblocks'], [])

    def test_barrier_validates_range_and_duplicate_installation(self):
        self.stock(self.host, 'roadblock')
        with self.assertRaises(ValueError): self.act(self.host, 'use_item', item='roadblock', node=32)
        self.act(self.host, 'use_item', item='roadblock', node=1)
        self.stock(self.host, 'roadblock')
        with self.assertRaises(ValueError): self.act(self.host, 'use_item', item='roadblock', node=1)
        self.host.refresh_from_db(); self.assertEqual(self.host.items, ['roadblock'])

    def test_cloak_blocks_battle_charge_and_items_until_next_own_turn(self):
        self.stock(self.host, 'cloak'); self.act(self.host, 'use_item', item='cloak'); self.meet()
        self.end(self.host)
        state = serialize_room(self.room, self.guest.token)
        self.assertTrue(state['players'][0]['cloaked'])
        self.room.document['landed'] = True; self.room.save(update_fields=['document'])
        self.assertEqual(serialize_room(self.room, self.guest.token)['challenge_targets'], [])
        self.stock(self.guest, 'brick')
        with self.assertRaises(ValueError): self.act(self.guest, 'use_item', item='brick', target=0)
        with self.assertRaises(ValueError): self.act(self.guest, 'challenge', target=0)
        self.room.document['arrival'] = 'charge'; self.room.save(update_fields=['document'])
        with self.assertRaises(ValueError): self.act(self.guest, 'charge', target=0)
        self.end(self.guest)
        self.assertFalse(serialize_room(self.room)['players'][0]['cloaked'])

    def test_training_requires_offline_hand_confirmation_and_uses_current_hp_limit(self):
        self.host.hp = 2300; self.host.save(update_fields=['hp'])
        self.stock(self.host, 'training'); self.act(self.host, 'use_item', item='training')
        task = serialize_room(self.room, self.host.token)['hand_task']
        self.assertEqual(task['count'], 7)
        with self.assertRaises(ValueError): self.act(self.host, 'roll')
        with self.assertRaises(PartyConflict): self.act(self.host, 'ack_hand', task_version=task['version'] - 1)
        self.act(self.host, 'ack_hand', task_version=task['version'])
        self.assertIsNone(serialize_room(self.room, self.host.token)['hand_task'])

    def test_ko_rest_one_personal_turn_revive_in_place_and_reset_passive(self):
        self.guest.position = 4; self.guest.hp = 300; self.guest.save()
        self.room.document['passive_states'] = {'1': {'focus': {'count': 9}}}; self.room.save(update_fields=['document'])
        self.stock(self.host, 'brick'); self.act(self.host, 'use_item', item='brick', target=1)
        self.host.refresh_from_db(); self.assertEqual(self.host.crystals, 1)
        self.end(self.host)
        state = serialize_room(self.room, self.guest.token)
        self.assertEqual((state['players'][1]['hp'], state['players'][1]['position'], state['players'][1]['ko_status']), (0, 4, 'resting'))
        for action in ['roll', 'use_item', 'buy_item', 'claim_item', 'challenge', 'ack_hand']:
            with self.assertRaises(ValueError): self.act(self.guest, action, item='heal', target=0)
        self.end(self.guest); self.end(self.host)
        self.guest.refresh_from_db()
        self.assertEqual((self.guest.hp, self.guest.position), (2300, 4))
        self.assertEqual(self.room.document['passive_states']['1'], {'focus': {'count': 3}})
        task = serialize_room(self.room, self.guest.token)['hand_task']
        self.assertEqual((task['reason'], task['count']), ('부활', 7))
        self.assertFalse(serialize_room(self.room, self.guest.token)['can_use_items'])

    def test_environmental_ko_has_no_player_score_and_does_not_move_home(self):
        self.host.hp = 100; self.host.position = 3; self.host.save()
        _land(self.room, self.host)
        self.assertEqual(self.host.hp, 0)
        self.host.refresh_from_db(); self.guest.refresh_from_db()
        self.assertEqual((self.host.crystals, self.guest.crystals), (0, 0))
        self.room.save(update_fields=['document']); self.end(self.host); self.end(self.guest)
        self.host.refresh_from_db(); self.assertEqual((self.host.hp, self.host.position), (0, 3))

    def test_battle_ko_scores_once_after_one_submission(self):
        self.meet(); self.act(self.host, 'challenge', target=1)
        self.confirm(hp2=0)
        self.host.refresh_from_db(); self.assertEqual(self.host.crystals, 1)
        self.assertEqual(serialize_room(self.room)['players'][1]['ko_status'], 'knocked_out')
        with self.assertRaises(ValueError): self.act(self.host, 'challenge', target=1)
        self.host.refresh_from_db(); self.assertEqual(self.host.crystals, 1)

    def test_passive_persists_across_battles_until_revive(self):
        self.meet(); self.act(self.host, 'challenge', target=1)
        first = self.room.encounters.get(status='active').session
        first.player1_passive_state = {'focus': {'count': 9}}; first.save()
        self.confirm()
        self.end(self.host); self.end(self.guest); self.meet()
        self.act(self.host, 'challenge', target=1)
        self.assertEqual(self.room.encounters.get(status='active').session.player1_passive_state, {'focus': {'count': 9}})

    def test_smart_die_waits_for_movement_and_shield_does_not_block_disaster(self):
        self.stock(self.host, 'smart_dice'); self.act(self.host, 'use_item', item='smart_dice', value=2)
        self.host.position = 1
        with patch('battlelog.party_services.secrets.randbelow', return_value=5): _land(self.room, self.host)
        self.assertEqual(self.room.document['smart_dice']['0'], 2)
        self.room.document['shields'] = {'0': True}
        self.host.position = 3; _land(self.room, self.host)
        self.assertEqual(self.host.hp, 4150)
        self.assertTrue(self.room.document['shields']['0'])

    def test_counter_ko_ends_original_movement_and_awards_defender_score(self):
        self.guest.position = 1; self.guest.save(update_fields=['position'])
        self.room.document['revenge'] = {'1': True}; self.room.save(update_fields=['document'])
        with patch('battlelog.party_services.secrets.randbelow', return_value=2): self.act(self.host, 'roll')
        self.act(self.host, 'move', node=1); self.act(self.host, 'challenge', target=1)
        self.confirm(); self.act(self.guest, 'counterattack'); self.confirm(hp2=0)
        self.host.refresh_from_db(); self.guest.refresh_from_db()
        self.assertEqual((self.host.hp, self.guest.crystals), (0, 1))
        self.assertIsNone(self.room.document['move'])
        self.assertTrue(self.room.document['landed'])
        self.assertFalse(self.room.document.get('counter_prompt'))

    def test_counter_is_optional_owned_by_defender_and_preserves_original_movement(self):
        self.guest.position = 1; self.guest.save(update_fields=['position'])
        self.room.document['revenge'] = {'1': True}; self.room.save(update_fields=['document'])
        with patch('battlelog.party_services.secrets.randbelow', return_value=2): self.act(self.host, 'roll')
        self.act(self.host, 'move', node=1); self.act(self.host, 'challenge', target=1)
        self.confirm(hp1=4000, hp2=3500)
        self.assertEqual(self.room.document['counter_prompt']['seat'], 1)
        with self.assertRaises(ValueError): self.act(self.host, 'continue_move')
        with self.assertRaises(PermissionDenied): self.act(self.host, 'counterattack')
        self.act(self.guest, 'counterattack')
        counter = self.room.encounters.get(status='active')
        self.assertTrue(counter.snapshot['counter'])
        self.assertEqual((counter.player1.seat, counter.session.player1_hp, counter.session.player2_hp), (1, 3500, 4000))
        self.confirm()
        self.assertEqual(self.room.document['turn'], 0)
        self.assertIsNone(self.room.document['move'])
        self.host.refresh_from_db()
        self.assertEqual((self.host.position, self.host.hp), (3, 3700))

    def test_counter_decline_and_cancel_do_not_consume_original_turn(self):
        self.stock(self.host, 'revenge'); self.act(self.host, 'use_item', item='revenge'); self.meet()
        self.end(self.host)
        self.room.document['landed'] = True; self.room.save(update_fields=['document'])
        self.act(self.guest, 'challenge', target=0); self.confirm()
        self.act(self.host, 'counterattack')
        self.act(self.host, 'cancel_battle')
        self.assertEqual(self.room.document['counter_prompt']['seat'], 0)
        self.act(self.host, 'skip_counter')
        self.assertFalse(self.room.document.get('counter_prompt'))
        self.assertEqual(self.room.document['turn'], 1)

    def test_legacy_boost_is_mapped_to_double_dice_without_exposing_inventory(self):
        self.stock(self.host, 'boost')
        self.assertEqual(serialize_room(self.room, self.host.token)['me']['items'], ['hurry'])
        self.assertIsNone(serialize_room(self.room)['me'])
        self.act(self.host, 'use_item', item='boost')
        self.assertTrue(self.room.document['double_dice']['0'])
