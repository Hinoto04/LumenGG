import json
from django.test import TestCase
from django.urls import reverse
from card.models import Character
from battlelog.calculator_ui import calculator_url
from battlelog.models import BattleSession
from battlelog.services import create_standalone_session, serialize_session
from mobile_api.calculators import mobile_state


class CalculatorUiTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(name='루트', description='', group='', datas={'hand': {'5000': 6}}, img='https://example.com/root.png')
        self.session = create_standalone_session('A', 'B', self.character, self.character)
        self.view_url = reverse('battlelog:sessionDetail', args=[self.session.view_token])
        self.control_url = reverse('battlelog:sessionControl', args=[self.session.view_token, self.session.control_token])

    def test_every_legacy_ui_link_opens_the_single_calculator(self):
        for query in ('', '?ui=classic', '?ui=character', '?ui=invalid', '?choose_ui=1'):
            response = self.client.get(self.control_url + query)
            self.assertTemplateUsed(response, 'battlelog/session_v2.html')
            self.assertContains(response, 'src="/static/v2/calculator-hud.js')
            self.assertContains(response, 'src="/static/v2/calculator-passive-tray.js')
            self.assertNotContains(response, 'calculator-character.js')
            self.assertNotIn('ui=', response.context['view_url'])
            self.assertNotIn('ui=', response.context['control_url'])
            self.assertNotIn('ui=', response.context['current_url'])

    def test_legacy_ui_links_keep_the_same_session_and_role(self):
        before = (self.session.version, self.session.player1_hp, self.session.player1_fp)
        spectator = self.client.get(self.view_url + '?choose_ui=1&ui=character')
        self.assertFalse(spectator.context['state']['can_control'])
        self.session.refresh_from_db()
        self.assertEqual((self.session.version, self.session.player1_hp, self.session.player1_fp), before)
        self.assertEqual(BattleSession.objects.count(), 1)

    def test_spectators_cannot_control_and_controllers_share_one_state(self):
        action_url = reverse('battlelog:sessionAction', args=[self.session.view_token])
        forbidden = self.client.post(action_url, json.dumps({'action': 'hp', 'target': 'p1', 'amount': -100}), content_type='application/json')
        self.assertEqual(forbidden.status_code, 403)
        response = self.client.post(action_url, json.dumps({'action': 'hp', 'target': 'p1', 'amount': -300, 'control_token': self.session.control_token}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(self.control_url).context['state']['players']['p1']['hp'], 4700)

    def test_start_redirect_ignores_retired_ui_choice(self):
        start = reverse('battlelog:sim')
        for ui in ('character', 'classic', ''):
            response = self.client.post(start, {'player1_name': 'A', 'player2_name': 'B', 'player1_character': self.character.id, 'player2_character': self.character.id, 'ui': ui})
            self.assertEqual(response.status_code, 302)
            self.assertNotIn('ui=', response.url)
        self.assertNotContains(self.client.get(start), 'name="ui"')

    def test_web_and_app_share_theme_and_declarative_passive(self):
        web = serialize_session(self.session, control_token=self.session.control_token, include_events=False)
        mobile = mobile_state(self.session, self.session.control_token)
        self.assertEqual(web['players']['p1']['character']['calculator_ui'], mobile['players']['p1']['character']['calculator_ui'])
        self.assertEqual(web['players']['p1']['character']['calculator_ui']['theme_key'], 'root')
        self.assertEqual(web['players']['p1']['character']['passive'], mobile['players']['p1']['character']['passive'])
        self.assertIn('controls', web['players']['p1']['character']['passive'])
        self.assertNotIn('ui=', web['view_url'])
        self.character.name = 'Unknown'
        self.character.save(update_fields=['name'])
        self.session.player1_character = self.character
        self.assertIsNone(serialize_session(self.session, include_events=False)['players']['p1']['character']['calculator_ui'])

    def test_url_cleanup_preserves_other_parameters_tokens_and_fragment(self):
        self.assertEqual(calculator_url('/session/token/control/secret/?lang=ja&ui=classic#log'), '/session/token/control/secret/?lang=ja#log')
        self.assertEqual(calculator_url('/session/token/?choose_ui=1&ui=character'), '/session/token/')
