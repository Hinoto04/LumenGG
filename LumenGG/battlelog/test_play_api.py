"""Game client (play/) page, lobby API, deck preparation check and the app endpoint."""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from card.models import Card
from deck.models import Deck

from .models import LumenSimulatorSession
from . import test_automatic_engine as engine_tests


class PlayApiTests(TestCase):
    # A validated full-card release, an active AI policy and two schema-1 decks.
    setUp = engine_tests.SimulatorAIHTTPTests.setUp

    def new_game(self, client=None, **body):
        payload = {'p1_deck': self.decks[0].id, 'p2_deck': self.decks[1].id, 'opponent': 'ai', **body}
        return (client or self.client).post(
            reverse('battlelog:playNew'), data=json.dumps(payload), content_type='application/json',
        )

    def test_page_sets_csrf_cookie_and_loads_the_bundle(self):
        response = self.client.get(reverse('battlelog:play'))

        self.assertContains(response, 'play/play.js')
        self.assertContains(response, 'play/play.css')
        self.assertIn('csrftoken', response.cookies)

    def test_new_ai_game_returns_only_the_creators_seat(self):
        response = self.new_game()

        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        session = LumenSimulatorSession.objects.get(view_token=data['view_token'])
        self.assertEqual(session.mode, LumenSimulatorSession.MODE_AUTOMATIC)
        self.assertEqual(session.player2_controller, LumenSimulatorSession.CONTROLLER_AI)
        self.assertEqual(data['seats'], {'p1': session.player1_token})
        self.assertEqual(
            data['urls']['p1'],
            f'/battlelog/play/?game={session.view_token}&seat=p1&token={session.player1_token}',
        )
        self.assertNotIn('p2', data['urls'])

    def test_new_human_game_returns_the_opponent_seat_and_timers(self):
        response = self.new_game(opponent='human', ready_timeout_seconds=30, effect_timeout_seconds=60)

        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        session = LumenSimulatorSession.objects.get(view_token=data['view_token'])
        self.assertEqual(data['seats']['p2'], session.player2_token)
        settings = session.document['state']['engine']['settings']
        self.assertEqual(settings['ready_timeout_seconds'], 30)
        self.assertEqual(settings['effect_timeout_seconds'], 60)

    def test_private_deck_of_another_user_is_refused(self):
        stranger = User.objects.create_user(username='play-stranger', password='pw')
        self.decks[1].author = stranger
        self.decks[1].visibility = Deck.VISIBILITY_PRIVATE
        self.decks[1].save()

        response = self.new_game()

        self.assertEqual(response.status_code, 403)
        self.assertIn('플레이어2 덱을 볼 권한이 없습니다.', response.json()['error'])
        self.assertFalse(LumenSimulatorSession.objects.exists())

    def test_invalid_input_is_a_readable_error(self):
        self.assertEqual(self.new_game(p1_deck='nope').json()['error'], '덱 ID를 확인해주세요.')
        self.assertEqual(self.new_game(opponent='robot').status_code, 400)

    def test_my_decks_need_login(self):
        url = reverse('battlelog:playDecks')
        self.assertTrue(self.client.get(url, {'mine': 1}).json()['login_required'])

        self.client.force_login(self.user)
        rows = self.client.get(url, {'mine': 1}).json()['decks']
        self.assertEqual({row['id'] for row in rows}, {deck.id for deck in self.decks})
        self.assertIn('character_id', rows[0])

        searched = self.client.get(url, {'q': 'AI HTTP'}).json()['decks']
        self.assertEqual(len(searched), 2)

    def test_app_endpoint_returns_absolute_urls_for_the_webview(self):
        client = APIClient()
        client.force_authenticate(self.user)
        self.decks[0].visibility = Deck.VISIBILITY_PRIVATE
        self.decks[0].save()

        response = client.post('/api/mobile/v1/simulator/sessions', {
            'p1_deck': self.decks[0].id, 'p2_deck': self.decks[1].id, 'opponent': 'ai',
        }, format='json')

        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()['urls']['p1'].startswith('http://testserver/battlelog/play/?game='))
        anonymous = APIClient().post('/api/mobile/v1/simulator/sessions', {
            'p1_deck': self.decks[0].id, 'p2_deck': self.decks[1].id,
        }, format='json')
        self.assertEqual(anonymous.status_code, 403)


class PlayPreparationCheckTests(TestCase):
    setUp_base = engine_tests.SimulatorAIHTTPTests.setUp

    def setUp(self):
        self.setUp_base()
        trait = Card.objects.create(
            name='AI HTTP Trait', code='AIH-PS-001', character=self.character, type='특성',
            effect_definition={'schema_version': 1, 'reviewed': True, 'abilities': []},
        )
        for deck in self.decks:
            deck.trait_card = trait
            deck.schema_version = 2
            deck.save()
        response = self.client.post(reverse('battlelog:playNew'), data=json.dumps({
            'p1_deck': self.decks[0].id, 'p2_deck': self.decks[1].id, 'opponent': 'human',
        }), content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.session = LumenSimulatorSession.objects.get(view_token=response.json()['view_token'])

    def check(self, active, seat='p1', token=None):
        return self.client.post(
            reverse('battlelog:simulatorPreparationCheck', args=[self.session.view_token]),
            data=json.dumps({
                'seat': seat, 'seat_token': token or self.session.player1_token, 'active': active,
            }),
            content_type='application/json',
        )

    def test_check_reports_problems_without_saving(self):
        preparation = self.session.document['preparation']
        self.assertEqual(preparation['status'], 'editing')
        active = preparation['players']['p1']['active']
        broken = {**active, 'cards': active['cards'][1:]}

        response = self.check(broken)

        self.assertEqual(response.status_code, 200, response.content)
        report = response.json()['report']
        self.assertFalse(report['is_valid'])
        self.assertTrue(any(issue['severity'] == 'error' for issue in report['issues']))
        self.session.refresh_from_db()
        self.assertEqual(self.session.document['preparation']['version'], preparation['version'])
        self.assertEqual(self.session.document['preparation']['players']['p1']['active'], active)

    def test_check_requires_the_seat_token(self):
        active = self.session.document['preparation']['players']['p1']['active']
        self.assertEqual(self.check(active, token='wrong').status_code, 403)


class PlayManualModeTests(TestCase):
    """Manual (sandbox) sessions open in the game client unless a passive panel needs the legacy page."""

    setUp = engine_tests.SimulatorAIHTTPTests.setUp

    def new_game(self, **body):
        payload = {'p1_deck': self.decks[0].id, 'p2_deck': self.decks[1].id, 'opponent': 'human', 'mode': 'manual', **body}
        return self.client.post(reverse('battlelog:playNew'), data=json.dumps(payload), content_type='application/json')

    def seat_page(self, session, **query):
        return self.client.get(reverse('battlelog:simulatorSeat', kwargs={
            'view_token': session.view_token, 'seat': 'p1', 'seat_token': session.player1_token,
        }), query)

    def test_manual_game_opens_in_the_game_client(self):
        response = self.new_game()

        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()
        self.assertEqual(data['mode'], 'manual')
        self.assertNotIn('legacy', data)
        session = LumenSimulatorSession.objects.get(view_token=data['view_token'])
        self.assertTrue(data['urls']['p1'].startswith('/battlelog/play/?game='))
        self.assertEqual(self.seat_page(session).status_code, 302)
        # The legacy page stays reachable on request.
        legacy = self.seat_page(session, legacy=1)
        self.assertEqual(legacy.status_code, 200)
        self.assertContains(legacy, 'v2/lumen-simulator.js')

    def test_manual_game_against_ai_is_refused(self):
        response = self.new_game(opponent='ai')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], '수동 대전은 사람끼리만 할 수 있습니다.')

    def use_passive_panel(self, template, js):
        self.character.datas = {
            **self.character.datas,
            'simulator_passive_ui': {'template': template, 'js': js},
        }
        self.character.save(update_fields=['datas'])

    def test_ported_character_panels_open_in_the_game_client(self):
        for name, template in (
            ('nia', 'battlelog/passive_ui/nia_simulator.html'),
            ('cmyk', 'battlelog/passive_ui/cmyk_simulator.html'),
            ('yohan', 'battlelog/passive_ui/yohan_simulator.html'),
            ('tao', 'battlelog/passive_ui/tao.html'),
        ):
            with self.subTest(name):
                self.use_passive_panel(template, f'battlelog/passive_ui/{name}_simulator.js')
                data = self.new_game().json()
                self.assertNotIn('legacy', data)
                self.assertTrue(data['urls']['p1'].startswith('/battlelog/play/'))

    def test_unported_character_panel_keeps_the_legacy_page(self):
        # A character-specific template the game client does not know yet.
        self.use_passive_panel('battlelog/passive_ui/root.html', 'battlelog/passive_ui/root.js')

        data = self.new_game().json()

        self.assertTrue(data['legacy'])
        session = LumenSimulatorSession.objects.get(view_token=data['view_token'])
        self.assertEqual(data['urls']['p1'], reverse('battlelog:simulatorSeat', kwargs={
            'view_token': session.view_token, 'seat': 'p1', 'seat_token': session.player1_token,
        }))
        self.assertEqual(self.seat_page(session).status_code, 200)

    def test_configurable_passive_controls_work_in_the_game_client(self):
        self.character.datas = {
            **self.character.datas,
            'simulator_passive_ui': {'options': {'controls': [{'type': 'toggle', 'key': 'charge', 'label': '차지'}]}},
        }
        self.character.save(update_fields=['datas'])

        data = self.new_game().json()

        self.assertNotIn('legacy', data)
