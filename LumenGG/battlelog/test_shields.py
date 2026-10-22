import json
import uuid
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from card.models import Character
from battlelog.models import BattleSession
from battlelog.services import create_standalone_session, perform_session_action, serialize_session, undo_last_hp_event
from battlelog.shields import shield_amount, SHIELD_KEY
from mobile_api.calculators import perform_mobile_action, mobile_state


class FinfShieldTests(TestCase):
    def setUp(self):
        self.finf = Character.objects.create(name='핀프', datas={'hand': {'5000': 6}}, description='', group='', img='https://example.com/finf.png')
        self.other = Character.objects.create(name='루트', datas={'hand': {'5000': 6}}, description='', group='', img='https://example.com/root.png')
        self.session = create_standalone_session('A', 'B', self.finf, self.other)

    def act(self, action, amount=0, target='p1', **kwargs):
        self.session = perform_session_action(self.session, {'action': action, 'target': target, 'amount': amount, **kwargs}, control_token=self.session.control_token)
        return self.session

    def test_full_equal_and_overflow_damage(self):
        for damage, hp, shield in [(100, 5000, 200), (300, 5000, 0), (500, 4800, 0)]:
            with self.subTest(damage=damage):
                self.act('reset_session'); self.act('shield', 300); self.act('hp', -damage)
                self.assertEqual(self.session.player1_hp, hp)
                self.assertEqual(shield_amount(self.session.player1_passive_state), shield)
                self.assertEqual(self.session.events.filter(event_type='hp').latest('id').payload['shield_absorbed'], min(300, damage))
                self.act('undo')
                self.assertEqual(self.session.player1_hp, 5000)
                self.assertEqual(shield_amount(self.session.player1_passive_state), 300)

    def test_shield_subtraction_healing_and_manual_expiry(self):
        self.act('shield', 30000); self.act('shield', 30000)
        self.assertEqual(shield_amount(self.session.player1_passive_state), 60000)
        self.act('shield_reset')
        self.act('shield', 300); self.act('hp', 100); self.act('fp_reset')
        self.assertEqual(self.session.player1_hp, 5100)
        self.assertEqual(shield_amount(self.session.player1_passive_state), 300)
        self.act('shield', -500)
        self.assertEqual(shield_amount(self.session.player1_passive_state), 0)
        self.act('shield', 300); self.act('shield_reset')
        self.assertEqual(shield_amount(self.session.player1_passive_state), 0)
        self.assertEqual(self.session.player1_hp, 5100)

    def test_undo_restores_hp_and_shield_without_erasing_later_gain(self):
        self.act('shield', 300); self.act('hp', -500); self.act('shield', 200); self.act('undo')
        self.assertEqual(self.session.player1_hp, 5000)
        self.assertEqual(shield_amount(self.session.player1_passive_state), 500)

    def test_pending_redis_hp_event_can_restore_shield(self):
        self.act('shield', 100)
        self.session.player1_hp = 4800
        self.session.save(update_fields=['player1_hp'])
        record = {'event_uid': str(uuid.uuid4()), 'target': 'p1', 'hp_before': 5000, 'amount': -500,
                  'created_at': timezone.now().isoformat(), 'payload': {'shield_absorbed': 300}}
        with patch('battlelog.services.latest_pending_event', return_value=record), patch('battlelog.services.mark_pending_event_undone', return_value=record):
            self.session = undo_last_hp_event(self.session)
        self.assertEqual(self.session.player1_hp, 5000)
        self.assertEqual(shield_amount(self.session.player1_passive_state), 400)

    def test_both_players_legacy_state_and_non_finf(self):
        self.session = create_standalone_session('A', 'B', self.finf, self.finf)
        self.session.player2_passive_state = {} # Old save without the shield field.
        self.session.save(update_fields=['player2_passive_state'])
        self.act('shield', 300, target='p2'); self.act('hp', -500, target='p2')
        self.assertEqual(self.session.player2_hp, 4800)
        self.assertEqual(self.session.player1_hp, 5000)
        other = create_standalone_session('A', 'B', self.other, self.other)
        other.player1_passive_state = {SHIELD_KEY: {'value': 300}}
        other.save(update_fields=['player1_passive_state'])
        other = perform_session_action(other, {'action': 'hp', 'target': 'p1', 'amount': -500}, control_token=other.control_token)
        self.assertEqual(other.player1_hp, 4500)

    def test_reset_and_sudden_death_clear_shield(self):
        self.act('shield', 300); self.act('reset_session')
        self.assertEqual(shield_amount(self.session.player1_passive_state), 0)
        self.act('shield', 300); self.act('sudden_death', enabled=True)
        self.assertEqual(shield_amount(self.session.player1_passive_state), 0)
        self.assertEqual(self.session.player1_hp, 1000)

    def test_invalid_and_unauthorized_actions(self):
        for body in [{'action': 'shield', 'amount': 0}, {'action': 'shield', 'amount': 0.5}, {'action': 'shield', 'amount': True}, {'action': 'shield', 'amount': 50001}, {'action': 'shield', 'amount': 100, 'target': 'p2'}, {'action': 'shield_reset', 'target': 'bad'}, {'action': 'passive', 'key': SHIELD_KEY, 'value': -100}]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.act(**body)
        with self.assertRaises(PermissionDenied):
            perform_session_action(self.session, {'action': 'shield', 'target': 'p1', 'amount': 100})

    def test_mobile_batch_receipt_idempotency_and_shared_web_state(self):
        body = {'action_id': str(uuid.uuid4()), 'expected_version': self.session.version, 'action': 'batch',
                'actions': [{'action': 'shield', 'target': 'p1', 'amount': 300}, {'action': 'hp', 'target': 'p1', 'amount': -500}]}
        self.session = perform_mobile_action(self.session.view_token, body, self.session.control_token)
        perform_mobile_action(self.session.view_token, body, self.session.control_token)
        self.session.refresh_from_db()
        self.assertEqual(self.session.player1_hp, 4800)
        web = serialize_session(self.session, control_token=self.session.control_token)
        mobile = mobile_state(self.session, self.session.control_token)
        self.assertEqual(web['players']['p1']['passive_state'], mobile['players']['p1']['passive_state'])
        self.assertEqual(shield_amount(web['players']['p1']['passive_state']), 0)

    def test_web_endpoint_and_spectator_permissions(self):
        url = reverse('battlelog:sessionAction', args=[self.session.view_token])
        body = {'action': 'shield', 'target': 'p1', 'amount': 300}
        self.assertEqual(self.client.post(url, json.dumps(body), content_type='application/json').status_code, 403)
        body['control_token'] = self.session.control_token
        self.assertEqual(self.client.post(url, json.dumps(body), content_type='application/json').status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(shield_amount(self.session.player1_passive_state), 300)

    def test_party_battle_accepts_shield_actions(self):
        from battlelog.party_services import create_room, join_room
        from battlelog.models import PartyEncounter
        room, host = create_room({'character_id': self.finf.pk})
        room, guest = join_room(room.code, {'character_id': self.other.pk})
        self.session.session_type = BattleSession.SESSION_PARTY
        self.session.save(update_fields=['session_type'])
        PartyEncounter.objects.create(room=room, session=self.session, player1=host, player2=guest, snapshot={'exchanges': 0})
        self.act('shield', 300); self.act('hp', -500)
        self.assertEqual(self.session.player1_hp, 4800)
