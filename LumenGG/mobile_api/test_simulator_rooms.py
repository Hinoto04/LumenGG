"""앱(JWT)용 방 · 퀵 매치: 웹 로비와 같은 play_rooms를 쓰고, 각자 자기 덱만 고른다."""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from battlelog import test_automatic_engine as engine_tests
from battlelog.models import SimulatorRoom
from deck.models import Deck

BASE = '/api/mobile/v1/simulator'


def jwt_client(user=None):
    client = APIClient()
    if user is not None:
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + str(RefreshToken.for_user(user).access_token))
    return client


class MobileSimulatorRoomTests(TestCase):
    # 검증된 릴리스, AI 정책, 공개 덱 두 개(self.decks)
    setUp = engine_tests.SimulatorAIHTTPTests.setUp

    def post(self, client, path, body=None):
        return client.post(f'{BASE}/{path}', body or {}, format='json')

    def private_deck(self, owner):
        return Deck.objects.create(
            name='앱 비공개 덱', author=owner, character=self.decks[0].character,
            visibility=Deck.VISIBILITY_PRIVATE,
        )

    def test_room_with_own_private_deck_starts_and_returns_absolute_seat_url(self):
        host_user = User.objects.create_user(username='app-host', password='pw')
        host, guest = jwt_client(host_user), jwt_client()
        created = self.post(host, 'rooms', {'deck_id': self.decks[0].id, 'mode': 'automatic'})
        self.assertEqual(created.status_code, 201, created.data)
        code, host_token = created.data['room']['code'], created.data['token']
        self.assertEqual(created.data['room']['seat'], 'host')
        self.assertTrue(created.data['room']['invite_url'].endswith(f'/battlelog/simulator/?room={code}'))
        self.assertTrue(created.data['room']['invite_url'].startswith('http'))

        # 방장이 자기 비공개 덱으로 바꾼다(JWT 계정으로 권한 확인).
        private = self.decks[1]
        Deck.objects.filter(pk=private.pk).update(author=host_user, visibility=Deck.VISIBILITY_PRIVATE)
        changed = self.post(host, f'rooms/{code}/deck', {'token': host_token, 'deck_id': private.id})
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(changed.data['room']['seats']['host']['deck']['id'], private.id)

        joined = self.post(guest, f'rooms/{code.lower()}/join', {'deck_id': self.decks[0].id})
        guest_token = joined.data['token']
        self.assertEqual(joined.data['room']['seat'], 'guest')
        # 상대 덱은 캐릭터만 보인다.
        self.assertNotIn('id', joined.data['room']['seats']['host']['deck'])

        self.post(host, f'rooms/{code}/ready', {'token': host_token, 'ready': True})
        started = self.post(guest, f'rooms/{code}/ready', {'token': guest_token, 'ready': True})
        self.assertEqual(started.data['room']['status'], 'started', started.data)
        session = SimulatorRoom.objects.get(code=code).session
        self.assertTrue(started.data['room']['play_url'].startswith('http'))
        self.assertIn(f'seat=p2&token={session.player2_token}', started.data['room']['play_url'])

        host_view = self.post(host, f'rooms/{code}/state', {'token': host_token})
        self.assertIn(f'seat=p1&token={session.player1_token}', host_view.data['room']['play_url'])
        stranger = self.post(jwt_client(), f'rooms/{code}/state', {'token': 'nope'})
        self.assertNotIn('play_url', stranger.data['room'])

    def test_private_deck_of_another_user_is_rejected_with_message(self):
        other = User.objects.create_user(username='app-other', password='pw')
        me = User.objects.create_user(username='app-me', password='pw')
        response = self.post(jwt_client(me), 'rooms', {'deck_id': self.private_deck(other).id})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['ok'])
        self.assertIn('권한', response.data['error'])
        missing = self.post(jwt_client(), 'rooms/ZZZZZZ/join', {})
        self.assertEqual(missing.status_code, 400)
        self.assertIn('방을 찾을 수 없습니다', missing.data['error'])

    def test_leaving_closes_host_room(self):
        client = jwt_client()
        created = self.post(client, 'rooms', {'deck_id': self.decks[0].id})
        code, token = created.data['room']['code'], created.data['token']
        left = self.post(client, f'rooms/{code}/leave', {'token': token})
        self.assertEqual(left.data['room']['status'], 'closed')

    def test_quick_match_pairs_app_player_with_waiting_player(self):
        first = jwt_client(User.objects.create_user(username='app-quick-1', password='pw'))
        second = jwt_client(User.objects.create_user(username='app-quick-2', password='pw'))
        waiting = self.post(first, 'quick', {'deck_id': self.decks[0].id})
        self.assertEqual(waiting.status_code, 201, waiting.data)
        self.assertEqual(waiting.data['room']['status'], 'waiting')
        self.assertEqual(waiting.data['room']['kind'], 'quick')
        self.assertNotIn('invite_url', waiting.data['room'])

        matched = self.post(second, 'quick', {'deck_id': self.decks[1].id})
        self.assertEqual(matched.data['room']['code'], waiting.data['room']['code'])
        self.assertEqual(matched.data['room']['status'], 'started')
        self.assertIn('seat=p2', matched.data['room']['play_url'])

        code = waiting.data['room']['code']
        polled = self.post(first, f'rooms/{code}/state', {'token': waiting.data['token']})
        self.assertIn('seat=p1', polled.data['room']['play_url'])
        self.assertTrue(polled.data['room']['play_url'].startswith('http'))
