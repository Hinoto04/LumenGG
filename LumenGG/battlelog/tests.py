import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from card.models import Character
from deck.models import Deck
from tournament.models import Tournament, TournamentMatch, TournamentParticipant, TournamentRound

from .models import BattleEvent, BattleSession
from .event_buffer import flush_session_events
from .services import cleanup_expired_sessions, get_or_create_tournament_session


class BattleCalculatorTests(TestCase):
    def setUp(self):
        self.char_a = Character.objects.create(
            name='니아',
            description='',
            group='',
            datas={'hand': {'5000': 6, '4000': 7, '3000': 8}},
            img='https://example.com/nia.png',
        )
        self.char_b = Character.objects.create(
            name='루트',
            description='',
            group='',
            datas={'hand': {'4500': 6, '3000': 8}},
            img='https://example.com/root.png',
        )

    def post_json(self, url, payload):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_anonymous_user_can_create_standalone_session_and_control_by_token(self):
        response = self.client.post(reverse('battlelog:sim'), {
            'player1_name': 'A',
            'player2_name': 'B',
            'player1_character': self.char_a.id,
            'player2_character': self.char_b.id,
        })

        self.assertEqual(response.status_code, 302)
        session = BattleSession.objects.get()
        self.assertEqual(session.session_type, BattleSession.SESSION_STANDALONE)
        self.assertEqual(session.player1_hp, 5000)
        self.assertEqual(session.player2_hp, 4500)
        self.assertIsNotNone(session.expires_at)

        action_url = reverse('battlelog:sessionAction', kwargs={'view_token': session.view_token})
        forbidden = self.post_json(action_url, {'action': 'hp', 'target': 'p1', 'amount': -100})
        self.assertEqual(forbidden.status_code, 403)

        allowed = self.post_json(action_url, {
            'action': 'hp',
            'target': 'p1',
            'amount': -300,
            'control_token': session.control_token,
        })
        self.assertEqual(allowed.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.player1_hp, 4700)
        flush_session_events(session.id)
        self.assertEqual(BattleEvent.objects.filter(event_type=BattleEvent.EVENT_HP).count(), 1)

    def test_undo_reverts_last_hp_event(self):
        session = BattleSession.objects.create(
            session_type=BattleSession.SESSION_STANDALONE,
            view_token='view',
            control_token='control',
            player1_character=self.char_a,
            player2_character=self.char_b,
            player1_initial_hp=5000,
            player2_initial_hp=4500,
            player1_hp=5000,
            player2_hp=4500,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        action_url = reverse('battlelog:sessionAction', kwargs={'view_token': session.view_token})
        self.post_json(action_url, {
            'action': 'hp',
            'target': 'p2',
            'amount': -500,
            'control_token': session.control_token,
        })
        response = self.post_json(action_url, {'action': 'undo', 'control_token': session.control_token})

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.player2_hp, 4500)
        flush_session_events(session.id)
        self.assertTrue(BattleEvent.objects.get(event_type=BattleEvent.EVENT_HP).undone)

    def test_tournament_player_can_control_match_session_without_control_token(self):
        owner = User.objects.create_user(username='owner', password='pw')
        p1_user = User.objects.create_user(username='p1', password='pw')
        p2_user = User.objects.create_user(username='p2', password='pw')
        tournament = Tournament.objects.create(name='테스트 대회', organizer=owner)
        deck1 = Deck.objects.create(name='D1', author=p1_user, character=self.char_a)
        deck2 = Deck.objects.create(name='D2', author=p2_user, character=self.char_b)
        participant1 = TournamentParticipant.objects.create(tournament=tournament, user=p1_user, deck=deck1)
        participant2 = TournamentParticipant.objects.create(tournament=tournament, user=p2_user, deck=deck2)
        round_obj = TournamentRound.objects.create(tournament=tournament, number=1)
        match = TournamentMatch.objects.create(round=round_obj, table_no=1, player1=participant1, player2=participant2)
        session = get_or_create_tournament_session(match)

        self.client.login(username='p1', password='pw')
        response = self.post_json(reverse('battlelog:sessionAction', kwargs={'view_token': session.view_token}), {
            'action': 'hp',
            'target': 'p2',
            'amount': -100,
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.player2_hp, 4400)

    def test_cleanup_deletes_expired_standalone_sessions(self):
        BattleSession.objects.create(
            session_type=BattleSession.SESSION_STANDALONE,
            view_token='expired',
            control_token='expired-control',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        BattleSession.objects.create(
            session_type=BattleSession.SESSION_STANDALONE,
            view_token='active',
            control_token='active-control',
            expires_at=timezone.now() + timedelta(minutes=30),
        )

        cleanup_expired_sessions()

        self.assertFalse(BattleSession.objects.filter(view_token='expired').exists())
        self.assertTrue(BattleSession.objects.filter(view_token='active').exists())
