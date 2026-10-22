import uuid
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from LumenGG.asgi import application
from card.models import Character
from deck.models import Deck
from tournament.models import Tournament, TournamentParticipant, TournamentRound, TournamentMatch
from battlelog.models import BattleSession
from battlelog.services import get_or_create_tournament_session, perform_session_action


def fixture():
    host, a, b, outsider = [User.objects.create_user(username=n) for n in ['organizer', 'alice', 'bob', 'outsider']]
    c = Character.objects.create(name='A', description='', group='', datas={'hand': {'5000': 5}})
    other = Character.objects.create(name='B', description='', group='', datas={'hand': {'4000': 4}})
    t = Tournament.objects.create(name='모바일 테스트 대회', organizer=host, status='running', visibility='unlisted')
    participants = []
    for user in [a, b]:
        deck = Deck.objects.create(name=user.username, author=user, character=c, visibility='private')
        participants.append(TournamentParticipant.objects.create(tournament=t, user=user, deck=deck))
    r = TournamentRound.objects.create(tournament=t, number=1, set_count=1)
    m = TournamentMatch.objects.create(round=r, table_no=1, player1=participants[0], player2=participants[1])
    return host, a, b, outsider, c, other, t, r, m, get_or_create_tournament_session(m)


class MobileTournamentTests(TestCase):
    def setUp(self):
        self.host, self.a, self.b, self.outsider, self.c, self.other, self.t, self.r, self.m, self.s = fixture()
        self.client = APIClient()
        self.client.force_authenticate(self.a)
        self.base = f'/api/mobile/v1/tournaments/{self.t.pk}'
        self.calc = f'/api/mobile/v1/calculators/{self.s.view_token}'
        self.report = self.base + f'/matches/{self.m.pk}/report'
        self.result = dict(winner='p1', player1_score=1, player2_score=0)

    def action(self, action='hp', **values):
        self.s.refresh_from_db()
        body = dict(action=action, action_id=str(uuid.uuid4()), expected_version=self.s.version, **values)
        return self.client.post(self.calc + '/action', body, format='json')

    def test_my_tournaments_and_matches_are_private_to_participants(self):
        other_round = TournamentRound.objects.create(tournament=self.t, number=2)
        TournamentMatch.objects.create(round=other_round, table_no=1, player1=self.m.player2, player2=self.m.player2)
        self.assertEqual([t['id'] for t in self.client.get('/api/mobile/v1/tournaments').data['tournaments']], [self.t.pk])
        self.assertEqual([m['id'] for m in self.client.get(self.base).data['matches']], [self.m.pk])
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.base).status_code, 404)
        self.assertEqual(self.client.get('/api/mobile/v1/tournaments').data['tournaments'], [])
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/mobile/v1/tournaments').status_code, 401)

    def test_calculator_entry_reuses_web_session_without_control_token(self):
        path = self.base + f'/matches/{self.m.pk}/calculator'
        response = self.client.post(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['view_token'], self.s.view_token)
        self.assertNotIn('control_token', response.data)
        self.assertNotIn('control_url', response.data['state'])
        self.assertTrue(response.data['state']['can_control'])
        self.assertTrue(response.data['state']['set']['can_report'])
        self.assertEqual(BattleSession.objects.filter(tournament_match=self.m).count(), 1)
        self.client.force_authenticate(self.host)
        self.assertEqual(self.client.post(path).status_code, 404)

    def test_token_does_not_replace_account_authentication(self):
        self.client.force_authenticate(None)
        for suffix in ['/state', '/events']:
            self.assertEqual(self.client.get(self.calc + suffix, HTTP_X_CALCULATOR_CONTROL=self.s.control_token).status_code, 403)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.action(target='p1', amount=-100).status_code, 403)
        self.client.force_authenticate(self.a)
        self.assertEqual(self.action(target='p1', amount=-100).data['state']['players']['p1']['hp'], 4900)

    def test_character_is_own_side_and_submitted_deck_only(self):
        self.assertEqual(self.action('character', target='p2', character_id=self.c.pk).status_code, 403)
        self.assertEqual(self.action('character', target='p1', character_id=self.other.pk).status_code, 403)
        self.assertEqual(self.action('character', target='p1', character_id=self.c.pk).status_code, 200)

    def test_both_set_confirmations_finalize_match_and_replay_safely(self):
        self.assertEqual(self.action(target='p2', amount=-5000).status_code, 200)
        response = self.action('report_set')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['state']['set']['player1_confirmed'])
        self.m.refresh_from_db()
        self.assertEqual(self.m.status, 'pending')
        self.client.force_authenticate(self.b)
        self.s.refresh_from_db()
        body = dict(action='report_set', action_id=str(uuid.uuid4()), expected_version=self.s.version)
        response = self.client.post(self.calc + '/action', body, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['state']['can_control'])
        self.m.refresh_from_db()
        self.r.refresh_from_db()
        self.assertEqual((self.m.status, self.m.winner_id, self.m.player1_score, self.r.status), ('reported', self.m.player1_id, 1, 'finished'))
        self.assertEqual(self.client.post(self.calc + '/action', body, format='json').status_code, 200)
        self.assertEqual(self.action(target='p1', amount=-100).status_code, 403)

    def test_expired_round_blocks_hp_but_allows_set_confirmation(self):
        self.s = perform_session_action(self.s, dict(action='hp', target='p2', amount=-5000), self.a)
        self.r.started_at = timezone.now() - timedelta(hours=2)
        self.r.save()
        self.assertEqual(self.action(target='p1', amount=-100).status_code, 403)
        self.assertEqual(self.action('report_set').status_code, 200)

    def test_direct_result_validation_idempotency_and_no_edits_after_submission(self):
        for body in [dict(winner='p1', player1_score=0, player2_score=1), dict(winner='p1', player1_score=2, player2_score=0),
                     dict(winner='draw', player1_score=1, player2_score=0), dict(winner='p1', player1_score=True, player2_score=0),
                     dict(winner='p1', player1_score='1', player2_score=0)]:
            self.assertEqual(self.client.post(self.report, body, format='json').status_code, 400)
        response = self.client.post(self.report, self.result, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['already_reported'])
        self.assertTrue(self.client.post(self.report, self.result, format='json').data['already_reported'])
        self.assertEqual(self.client.post(self.report, dict(winner='p2', player1_score=0, player2_score=1), format='json').status_code, 409)
        self.assertFalse(self.client.get(self.calc + '/state').data['can_control'])

    def test_bye_closed_round_and_nonparticipant_are_rejected(self):
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.post(self.report, self.result, format='json').status_code, 404)
        self.client.force_authenticate(self.a)
        self.r.status = 'finished'
        self.r.save()
        self.assertEqual(self.client.post(self.report, self.result, format='json').status_code, 400)
        self.r.status = 'running'
        self.r.save()
        self.m.player2 = None
        self.m.save()
        self.assertEqual(self.client.post(self.report, self.result, format='json').status_code, 400)
        self.assertEqual(self.client.post(self.base + f'/matches/{self.m.pk}/calculator').status_code, 400)

    def test_elimination_draw_stale_version_and_batched_confirmations_are_rejected(self):
        self.r.stage = 'elimination'
        self.r.save()
        self.assertEqual(self.client.post(self.report, dict(winner='draw', player1_score=0, player2_score=0), format='json').status_code, 400)
        self.assertEqual(self.client.post(self.calc + '/action', dict(action='hp', target='p1', amount=-100, action_id=str(uuid.uuid4()), expected_version=999), format='json').status_code, 409)
        self.assertEqual(self.action('batch', actions=[{'action': 'report_set'}]).status_code, 400)


@override_settings(CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
class MobileTournamentRealtimeTests(TransactionTestCase):
    def setUp(self):
        self.host, self.a, self.b, self.outsider, self.c, self.other, self.t, self.r, self.m, self.s = fixture()

    def test_jwt_authentication_and_live_web_updates(self):
        access = str(RefreshToken.for_user(self.a).access_token)
        outsider = str(RefreshToken.for_user(self.outsider).access_token)

        async def scenario():
            path = f'/ws/mobile/v1/calculators/{self.s.view_token}/'
            denied = WebsocketCommunicator(application, path)
            self.assertTrue((await denied.connect())[0])
            self.assertEqual((await denied.receive_json_from())['type'], 'authentication_required')
            await denied.send_json_to({'type': 'authenticate', 'access_token': outsider})
            self.assertEqual((await denied.receive_output())['code'], 4403)
            await denied.disconnect()
            controller = WebsocketCommunicator(application, path)
            await controller.connect()
            await controller.receive_json_from()
            await controller.send_json_to({'type': 'authenticate', 'request_id': 'auth', 'access_token': access})
            state = (await controller.receive_json_from())['state']
            self.assertTrue(state['can_control'])
            self.assertNotIn('control_url', state)
            body = dict(action='hp', target='p1', amount=-100, expected_version=state['version'], action_id=str(uuid.uuid4()))
            await controller.send_json_to({'type': 'action', 'request_id': 'one', 'payload': body})
            for _ in range(5):
                result = await controller.receive_json_from()
                if result.get('request_id') == 'one':
                    break
            self.assertTrue(result['ok'])
            self.assertEqual(result['state']['players']['p1']['hp'], 4900)
            await database_sync_to_async(perform_session_action)(self.s, dict(action='hp', target='p1', amount=-100), self.a)
            from battlelog.realtime import broadcast_battle_session
            await database_sync_to_async(broadcast_battle_session)(self.s)
            for _ in range(6):
                result = await controller.receive_json_from()
                if result.get('state', {}).get('players', {}).get('p1', {}).get('hp') == 4800:
                    break
            self.assertEqual(result['state']['players']['p1']['hp'], 4800)
            await controller.disconnect()
        async_to_sync(scenario)()

    def test_expired_jwt_is_rejected(self):
        token = RefreshToken.for_user(self.a).access_token
        token.set_exp(lifetime=timedelta(seconds=-1))

        async def scenario():
            socket = WebsocketCommunicator(application, f'/ws/mobile/v1/calculators/{self.s.view_token}/')
            await socket.connect()
            await socket.receive_json_from()
            await socket.send_json_to({'type': 'authenticate', 'access_token': str(token)})
            self.assertEqual((await socket.receive_output())['code'], 4401)
            await socket.disconnect()
        async_to_sync(scenario)()
