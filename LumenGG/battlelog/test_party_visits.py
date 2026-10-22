from django.test import TestCase, override_settings
from card.models import Character
from .party_services import create_room, join_room, perform_party_action, serialize_room
from .services import perform_session_action


@override_settings(PARTY_ROLL_REVEAL_MS=0)
class PartyBattleVisitTests(TestCase):
    def setUp(self):
        character = Character.objects.create(name='교전 방문', description='', group='', datas={})
        self.room, self.host = create_room({'character_id': character.pk})
        self.room, self.guest = join_room(self.room.code, {'character_id': character.pk})
        self.room, self.third = join_room(self.room.code, {'character_id': character.pk})
        for p in [self.host,self.guest,self.third]: self.act('ready',p)
        self.act('start')
        self.host.position = 3; self.guest.position = 3
        self.host.save(); self.guest.save()
        self.room.document['landed'] = True; self.room.save()

    def act(self, action, player=None, **data):
        self.room.refresh_from_db()
        self.room = perform_party_action(self.room.code,(player or self.host).token,
            {'action':action,'expected_version':self.room.version,**data})

    def state(self):
        self.room.refresh_from_db()
        return serialize_room(self.room,self.host.token)

    def finish(self, target):
        encounter = self.room.encounters.get(status='active')
        session = encounter.session
        for index in range(2):
            session = perform_session_action(session,{'action':'party_exchange','expected_exchange':index},control_token=session.control_token)
        self.act('confirm_battle',battle_version=session.version)

    def test_finished_opponent_is_blocked_after_reconnect_and_server_rejects_retry(self):
        self.act('challenge',target=1); self.finish(self.guest)
        self.assertEqual(self.state()['challenge_targets'],[])
        self.assertTrue(self.state()['can_auto_end_turn'])
        with self.assertRaises(ValueError): self.act('challenge',target=1)
        self.assertEqual(self.room.encounters.count(),1)

    def test_other_opponents_at_same_visit_are_still_available_once_each(self):
        self.third.position = 3; self.third.save()
        self.act('challenge',target=1); self.finish(self.guest)
        self.assertEqual(self.state()['challenge_targets'],[2])
        self.act('challenge',target=2); self.finish(self.third)
        self.assertEqual(self.state()['challenge_targets'],[])
        self.assertEqual(self.room.encounters.filter(status='finished').count(),2)

    def test_cancellation_does_not_consume_the_meeting(self):
        self.act('challenge',target=1); self.act('cancel_battle')
        self.assertEqual(self.state()['challenge_targets'],[1])
        self.act('challenge',target=1)
        self.assertEqual(self.room.encounters.filter(status='active').count(),1)

    def test_remaining_move_resumes_and_new_visit_can_meet_opponent_again(self):
        self.host.position = 2; self.host.save()
        self.room.document.update(landed=False,move={'remaining':41},move_prompt=None)
        self.room.save(); self.act('advance')
        self.assertEqual(self.room.document['move']['remaining'],40)
        self.act('challenge',target=1); self.finish(self.guest)
        self.host.refresh_from_db()
        self.assertEqual(self.host.position,5)
        self.assertEqual(self.room.document['move_prompt']['targets'],[])
        while self.room.document['move']:
            prompt = self.room.document.get('move_prompt') or {}
            self.act('skip_shop' if prompt.get('shop') else 'continue_move' if prompt else 'advance')
        self.host.refresh_from_db()
        self.assertEqual(self.host.position,3)
        self.assertEqual(self.state()['challenge_targets'],[1])
        self.act('challenge',target=1)
        self.assertEqual(self.room.encounters.count(),2)
