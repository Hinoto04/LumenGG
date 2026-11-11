"""방 · 퀵 매치(play_rooms.py): 각 플레이어가 자기 덱만 골라 사람끼리 대전을 만든다."""

import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from deck.models import Deck

from .models import LumenSimulatorSession, SimulatorRoom
from . import test_automatic_engine as engine_tests


class PlayRoomTests(TestCase):
    # 검증된 릴리스, AI 정책, 공개 덱 두 개(self.decks)
    setUp = engine_tests.SimulatorAIHTTPTests.setUp

    def post(self, client, name, body=None, **kwargs):
        return client.post(
            reverse(f'battlelog:{name}', kwargs=kwargs or None),
            data=json.dumps(body or {}), content_type='application/json',
        )

    def test_room_starts_when_both_players_choose_their_own_deck_and_ready(self):
        host, guest = Client(), Client()
        created = self.post(host, 'playRoomCreate', {'deck_id': self.decks[0].id}).json()
        code, host_token = created['room']['code'], created['token']
        self.assertEqual(created['room']['seat'], 'host')
        self.assertFalse(created['room']['seats']['guest']['present'])

        joined = self.post(guest, 'playRoomJoin', {'deck_id': self.decks[1].id}, code=code).json()
        guest_token = joined['token']
        self.assertEqual(joined['room']['seat'], 'guest')
        # 상대 덱은 캐릭터만 보인다.
        self.assertNotIn('id', joined['room']['seats']['host']['deck'])
        self.assertEqual(joined['room']['seats']['guest']['deck']['id'], self.decks[1].id)

        self.post(host, 'playRoomReady', {'token': host_token, 'ready': True}, code=code)
        started = self.post(guest, 'playRoomReady', {'token': guest_token, 'ready': True}, code=code).json()

        self.assertEqual(started['room']['status'], 'started', started)
        room = SimulatorRoom.objects.get(code=code)
        session = room.session
        self.assertEqual(session.player1_controller, LumenSimulatorSession.CONTROLLER_HUMAN)
        self.assertEqual(session.player2_controller, LumenSimulatorSession.CONTROLLER_HUMAN)
        # 각자 자기 좌석 주소만 받는다.
        self.assertIn(f'seat=p2&token={session.player2_token}', started['room']['play_url'])
        host_view = self.post(host, 'playRoomState', {'token': host_token}, code=code).json()
        self.assertIn(f'seat=p1&token={session.player1_token}', host_view['room']['play_url'])
        stranger = self.post(Client(), 'playRoomState', {'token': 'nope'}, code=code).json()
        self.assertNotIn('play_url', stranger['room'])

    def test_changing_deck_clears_ready_and_full_room_rejects_third_player(self):
        host = Client()
        created = self.post(host, 'playRoomCreate', {'deck_id': self.decks[0].id}).json()
        code, token = created['room']['code'], created['token']
        self.post(host, 'playRoomReady', {'token': token, 'ready': True}, code=code)
        changed = self.post(host, 'playRoomDeck', {'token': token, 'deck_id': self.decks[1].id}, code=code).json()
        self.assertFalse(changed['room']['seats']['host']['ready'])

        self.post(Client(), 'playRoomJoin', {}, code=code)
        third = self.post(Client(), 'playRoomJoin', {}, code=code)
        self.assertEqual(third.status_code, 400)
        self.assertIn('이미 상대가', third.json()['error'])

    def test_private_deck_of_another_user_cannot_be_used_in_a_room(self):
        other = User.objects.create_user(username='room-other', password='pw')
        private = Deck.objects.create(
            name='private', author=other, character=self.decks[0].character,
            visibility=Deck.VISIBILITY_PRIVATE,
        )
        response = self.post(Client(), 'playRoomCreate', {'deck_id': private.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn('권한', response.json()['error'])

    def test_quick_match_pairs_two_waiting_players(self):
        first, second = Client(), Client()
        waiting = self.post(first, 'playQuick', {'deck_id': self.decks[0].id}).json()
        self.assertEqual(waiting['room']['status'], 'waiting')
        self.assertEqual(waiting['room']['kind'], 'quick')

        matched = self.post(second, 'playQuick', {'deck_id': self.decks[1].id}).json()
        self.assertEqual(matched['room']['code'], waiting['room']['code'])
        self.assertEqual(matched['room']['status'], 'started')
        self.assertIn('seat=p2', matched['room']['play_url'])

        polled = self.post(first, 'playRoomState', {'token': waiting['token']}, code=waiting['room']['code']).json()
        self.assertIn('seat=p1', polled['room']['play_url'])

    def test_quick_match_skips_players_who_stopped_waiting(self):
        stale = self.post(Client(), 'playQuick', {'deck_id': self.decks[0].id}).json()
        SimulatorRoom.objects.filter(code=stale['room']['code']).update(
            host_seen_at=timezone.now() - timedelta(minutes=5),
        )
        fresh = self.post(Client(), 'playQuick', {'deck_id': self.decks[1].id}).json()
        self.assertNotEqual(fresh['room']['code'], stale['room']['code'])
        self.assertEqual(fresh['room']['status'], 'waiting')

    def test_site_start_page_is_the_game_client_lobby(self):
        response = self.client.get(reverse('battlelog:simulatorStart'))
        self.assertContains(response, 'play/play.js')
        legacy = self.client.get(reverse('battlelog:simulatorStart') + '?legacy=1')
        self.assertNotContains(legacy, 'play/play.js')

    def test_lobby_has_site_navbar_but_game_screen_is_full_screen(self):
        for name in ('simulatorStart', 'play'):
            lobby = self.client.get(reverse(f'battlelog:{name}'))
            self.assertContains(lobby, 'data-v2-header')
            self.assertContains(lobby, 'play-lobby-page')
        game = self.client.get(reverse('battlelog:play') + '?game=abc&seat=p1&token=x')
        self.assertContains(game, 'play/play.js')
        self.assertNotContains(game, 'data-v2-header')
