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

    def test_legacy_and_invalid_values_keep_classic_and_new_assets_are_opt_in(self):
        for query in ('', '?ui=classic', '?ui=invalid'):
            response = self.client.get(self.control_url + query)
            self.assertTemplateUsed(response, 'battlelog/session_v2.html')
            self.assertNotContains(response, 'src="/static/v2/calculator-character.js"')
            self.assertNotContains(response, 'href="/static/v2/calculator-character.css"')
        response = self.client.get(self.control_url + '?ui=character')
        self.assertTemplateUsed(response, 'battlelog/session_character.html')
        self.assertContains(response, 'src="/static/v2/calculator-character.js"')
        self.assertContains(response, 'v2-character-calculator')
        self.assertTrue(response.context['view_url'].endswith('?ui=character'))
        self.assertTrue(response.context['control_url'].endswith('?ui=character'))

    def test_entry_choice_keeps_the_same_session_and_role(self):
        before = (self.session.version, self.session.player1_hp, self.session.player1_fp)
        for path in (self.view_url, self.control_url):
            response = self.client.get(path + '?choose_ui=1')
            self.assertTemplateUsed(response, 'battlelog/calculator_entry.html')
            self.assertContains(response, 'data-calculator-style="clean"')
            self.assertEqual(response.context['classic_url'], path)
            self.assertEqual(response.context['character_url'], path+'?ui=character')
        response = self.client.get(self.control_url + '?choose_ui=1&lang=ja')
        self.assertEqual(response.context['classic_url'], self.control_url + '?lang=ja')
        self.assertEqual(response.context['character_url'], self.control_url + '?lang=ja&ui=character')
        self.session.refresh_from_db()
        self.assertEqual((self.session.version,self.session.player1_hp,self.session.player1_fp),before)
        self.assertEqual(BattleSession.objects.count(),1)

    def test_ui_does_not_fork_data_or_grant_spectator_control(self):
        action_url = reverse('battlelog:sessionAction', args=[self.session.view_token])
        forbidden = self.client.post(action_url, json.dumps({'action':'hp','target':'p1','amount':-100,'ui':'character'}),content_type='application/json')
        self.assertEqual(forbidden.status_code,403)
        response = self.client.post(action_url,json.dumps({'action':'hp','target':'p1','amount':-300,'control_token':self.session.control_token}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        for query in ('', '?ui=character'):
            page=self.client.get(self.control_url+query)
            self.assertEqual(page.context['state']['players']['p1']['hp'],4700)
        spectator=self.client.get(self.view_url+'?ui=character')
        self.assertFalse(spectator.context['state']['can_control'])
        self.assertEqual(BattleSession.objects.count(),1)

    def test_start_redirect_preserves_selected_ui(self):
        start=reverse('battlelog:sim')
        for ui in ('character','classic','invalid'):
            response=self.client.post(start,{'player1_name':'A','player2_name':'B','player1_character':self.character.id,'player2_character':self.character.id,'ui':ui})
            self.assertEqual(response.status_code,302)
            self.assertEqual('?ui=character' in response.url,ui=='character')

    def test_optional_metadata_is_shared_and_urls_remain_canonical(self):
        web=serialize_session(self.session,control_token=self.session.control_token,include_events=False)
        mobile=mobile_state(self.session,self.session.control_token)
        self.assertEqual(web['players']['p1']['character']['calculator_ui'],mobile['players']['p1']['character']['calculator_ui'])
        self.assertEqual(web['players']['p1']['character']['calculator_ui']['theme_key'],'root')
        self.assertNotIn('ui=',web['view_url'])
        self.character.name='Unknown';self.character.save(update_fields=['name'])
        self.session.player1_character=self.character
        self.assertIsNone(serialize_session(self.session,include_events=False)['players']['p1']['character']['calculator_ui'])

    def test_url_selection_preserves_other_parameters_tokens_and_fragment(self):
        self.assertEqual(calculator_url('/session/token/control/secret/?lang=ja&ui=classic#log','character'),'/session/token/control/secret/?lang=ja&ui=character#log')
        self.assertEqual(calculator_url('/session/token/?choose_ui=1&ui=character','classic'),'/session/token/')
