import uuid

from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings

from card.models import Character
from mobile_api.calculators import perform_mobile_action
from .party_services import PartyConflict, create_room, join_room, perform_party_action, serialize_room
from .services import can_control_session, perform_session_action, serialize_session


@override_settings(PARTY_ROLL_REVEAL_MS=0)
class PartyBattleCompletionTests(TestCase):
    def setUp(self):
        character = Character.objects.create(name='전투 종료 테스트', description='', group='', datas={})
        self.room, self.host = create_room({'character_id': character.pk})
        self.room, self.guest = join_room(self.room.code, {'character_id': character.pk})
        self.room, self.third = join_room(self.room.code, {'character_id': character.pk})
        for player in (self.host, self.guest, self.third):
            self.act(player, 'ready')
        self.act(self.host, 'start')
        for player in (self.host, self.guest):
            player.refresh_from_db()
            player.position = 3
            player.save()
        self.room.document['landed'] = True
        self.room.save()
        self.act(self.host, 'challenge', target=self.guest.seat)
        self.encounter = self.room.encounters.get(status='active')
        self.session = self.encounter.session

    def act(self, player, action, **data):
        self.room.refresh_from_db()
        self.room = perform_party_action(self.room.code, player.token,
            {'action': action, 'expected_version': self.room.version, **data})

    def calc(self, action, **data):
        self.session = perform_session_action(self.session, {'action': action, **data},
            control_token=self.session.control_token)

    def complete(self):
        self.calc('party_exchange', expected_exchange=0)
        self.calc('party_exchange', expected_exchange=1)

    def submit(self, player=None, **extra):
        self.act(player or self.host, 'confirm_battle', battle_version=self.session.version, **extra)

    def test_non_participant_cannot_submit_and_stale_calculator_version_is_rejected(self):
        self.complete()
        with self.assertRaises(PermissionDenied):
            self.submit(self.third)
        with self.assertRaises(PartyConflict):
            self.act(self.guest, 'confirm_battle', battle_version=self.session.version - 1)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.status, 'active')
        self.submit(self.guest)
        self.assertIsNone(serialize_room(self.room)['battle'])

    def test_first_exchange_knockout_locks_calculator_and_one_defender_submission_scores_once(self):
        self.calc('hp', target='p2', amount=-self.session.player2_hp)
        # HP entry can still be corrected until the exchange is marked complete.
        self.assertTrue(can_control_session(None, self.session, self.session.control_token))
        self.assertFalse(serialize_session(self.session)['party']['completed'])
        self.calc('party_exchange', expected_exchange=0)
        state = serialize_session(self.session)
        self.assertEqual(state['party']['exchanges'], 1)
        self.assertTrue(state['party']['completed'])
        self.assertFalse(can_control_session(None, self.session, self.session.control_token))
        for action, data in [('hp', {'target': 'p2', 'amount': 100}),
                             ('party_exchange', {'expected_exchange': 1})]:
            with self.assertRaises(PermissionDenied):
                self.calc(action, **data)
        for participant in (self.host, self.guest):
            battle = serialize_room(self.room, participant.token)['battle']
            self.assertTrue(battle['completed'])
            self.assertTrue(battle['can_confirm'])
        self.assertFalse(serialize_room(self.room, self.third.token)['battle']['can_confirm'])
        self.submit(self.guest)
        self.host.refresh_from_db()
        self.guest.refresh_from_db()
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.status, 'finished')
        self.assertEqual(self.encounter.result['confirmed'], [self.guest.seat])
        self.assertNotIn('winner', self.encounter.result)
        self.assertEqual(self.guest.hp, 0)
        self.assertEqual(self.host.crystals, 1)
        coins = (self.host.coins, self.guest.coins)
        self.assertEqual(coins, (26, 0))
        with self.assertRaises(ValueError):
            self.submit(self.host)
        self.host.refresh_from_db()
        self.guest.refresh_from_db()
        self.assertEqual(self.host.crystals, 1)
        self.assertEqual((self.host.coins, self.guest.coins), coins)

    def test_attacker_knockout_ends_first_exchange_and_awards_damage_and_knockout_rewards(self):
        self.calc('hp', target='p1', amount=-self.session.player1_hp)
        self.calc('party_exchange', expected_exchange=0)
        self.submit()
        self.host.refresh_from_db()
        self.guest.refresh_from_db()
        self.assertEqual(self.host.hp, 0)
        self.assertEqual(self.guest.crystals, 1)
        self.assertEqual((self.host.coins, self.guest.coins), (1, 25))
        self.assertTrue(self.room.document['landed'])

    def test_both_knocked_out_in_first_exchange_need_no_result_choice(self):
        self.calc('hp', target='p1', amount=-self.session.player1_hp)
        self.calc('hp', target='p2', amount=-self.session.player2_hp)
        self.calc('party_exchange', expected_exchange=0)
        coins = (self.host.coins, self.guest.coins)
        self.submit()
        self.host.refresh_from_db()
        self.guest.refresh_from_db()
        self.assertEqual((self.host.hp, self.guest.hp), (0, 0))
        self.assertEqual((self.host.coins, self.guest.coins), (coins[0] + 25, coins[1] + 25))
        self.assertEqual((self.host.crystals, self.guest.crystals), (1, 1))

    def test_surviving_first_exchange_stays_open_and_second_exchange_uses_explicit_completion(self):
        self.calc('party_exchange', expected_exchange=0)
        self.assertFalse(serialize_session(self.session)['party']['completed'])
        self.assertFalse(serialize_room(self.room, self.host.token)['battle']['can_confirm'])
        with self.assertRaises(ValueError):
            self.submit()
        self.calc('hp', target='p2', amount=-self.session.player2_hp)
        # Damage entered during exchange two must not be mistaken for a first-exchange KO.
        self.assertTrue(can_control_session(None, self.session, self.session.control_token))
        self.calc('party_exchange', expected_exchange=1)
        self.assertEqual(serialize_session(self.session)['party']['exchanges'], 2)
        self.assertTrue(serialize_session(self.session)['party']['completed'])
        self.submit()

    def test_hp_correction_before_first_completion_keeps_second_exchange_available(self):
        self.calc('hp', target='p1', amount=-self.session.player1_hp)
        self.calc('undo')
        self.calc('party_exchange', expected_exchange=0)
        self.assertFalse(serialize_session(self.session)['party']['completed'])
        self.assertTrue(can_control_session(None, self.session, self.session.control_token))
        self.calc('party_exchange', expected_exchange=1)
        self.submit()

    def test_mobile_first_exchange_knockout_receipt_can_replay_after_calculator_locks(self):
        self.calc('hp', target='p2', amount=-self.session.player2_hp)
        payload = {'action': 'party_exchange', 'expected_exchange': 0,
                   'expected_version': self.session.version, 'action_id': str(uuid.uuid4())}
        self.session = perform_mobile_action(self.session.view_token, payload, self.session.control_token)
        replay = perform_mobile_action(self.session.view_token, payload, self.session.control_token)
        self.assertEqual(replay.version, self.session.version)
        self.assertEqual(serialize_session(replay)['party']['exchanges'], 1)
        self.assertTrue(serialize_session(replay)['party']['completed'])
        self.submit()

    def test_existing_two_exchange_battle_and_pending_old_confirmation_need_only_one_submission(self):
        self.complete()
        self.encounter.refresh_from_db()
        self.encounter.snapshot.pop('completed')
        self.encounter.result = {'version': self.session.version, 'winner': '0', 'confirmed': [0]}
        self.encounter.save()
        self.session.refresh_from_db()
        self.assertTrue(serialize_session(self.session)['party']['completed'])
        self.assertFalse(can_control_session(None, self.session, self.session.control_token))
        self.assertNotIn('winner', serialize_room(self.room, self.guest.token)['battle']['result'])
        self.submit(self.guest)
        self.encounter.refresh_from_db()
        self.assertNotIn('winner', self.encounter.result)
        self.assertEqual(self.encounter.status, 'finished')

    def test_legacy_winner_field_is_ignored_without_recording_victory_or_transferring_coins(self):
        self.complete()
        self.submit(winner=str(self.third.seat))
        self.host.refresh_from_db()
        self.guest.refresh_from_db()
        self.encounter.refresh_from_db()
        self.assertNotIn('winner', self.encounter.result)
        self.assertEqual((self.host.coins, self.guest.coins), (1, 0))
        self.assertEqual((self.host.crystals, self.guest.crystals), (0, 0))
