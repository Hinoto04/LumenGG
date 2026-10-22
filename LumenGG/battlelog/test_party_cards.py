from unittest.mock import patch

from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse
from card.models import Character
from .models import PartyCard
from .party_board import BOARD
from .party_services import create_room, join_room, perform_party_action, serialize_room


class PartyCardCatalogTests(TestCase):
    def setUp(self):
        character = Character.objects.create(name='카드 표시', description='', group='', datas={})
        self.room, self.host = create_room({'character_id': character.pk})

    def test_all_supplied_fronts_have_independent_database_text_and_layout(self):
        self.assertEqual(PartyCard.objects.filter(kind='item').count(), 13)
        self.assertEqual(PartyCard.objects.filter(kind='event').count(), 8)
        for card in PartyCard.objects.all():
            self.assertTrue(card.effect_text.strip())
            self.assertIsNotNone(finders.find(card.image_path), card.code)
            box = card.effect_box
            self.assertAlmostEqual(box['top'], 60 / 88)
            self.assertAlmostEqual(box['height'], 20.2 / 88)
            self.assertLessEqual(box['left'] + box['width'], 1)
            self.assertLessEqual(box['top'] + box['height'], 1)
        self.assertEqual(PartyCard.objects.filter(key='hurry').count(), 2)
        self.assertNotEqual(PartyCard.objects.get(kind='item', key='hurry').image_path,
                            PartyCard.objects.get(kind='event', key='hurry').image_path)

    def test_database_text_is_shared_by_web_and_mobile_without_changing_rules(self):
        text = 'HP 200 회복\n설명란 검증 <b>그대로 표시</b>'
        PartyCard.objects.filter(kind='item', key='heal').update(effect_text=text)
        responses = [self.client.get(reverse('battlelog:partyState', args=[self.room.code])),
                     self.client.get(f'/api/mobile/v1/party/{self.room.code}/state')]
        for response in responses:
            self.assertEqual(response.status_code, 200)
            data = response.json()
            card = data['board']['shop']['heal']
            self.assertEqual(card['description'], text)
            self.assertEqual((card['price'], card['target']), (3, 'self'))
            self.assertTrue(card['image'].endswith('/lp-i01-bandage.png'))
            self.assertEqual(card['card_id'], 'LP-I01')

    def test_edits_refresh_existing_room_and_do_not_mutate_shared_board(self):
        serialize_room(self.room, self.host.token)
        PartyCard.objects.filter(kind='item', key='brick').update(effect_text='수정한 효과 문구')
        state = serialize_room(self.room, self.host.token)
        self.assertEqual(state['board']['shop']['brick']['description'], '수정한 효과 문구')
        self.assertNotEqual(BOARD['shop']['brick']['description'], '수정한 효과 문구')
        self.assertEqual((state['board']['shop']['brick']['damage'], state['board']['shop']['brick']['range']), (500, 4))

    @override_settings(PARTY_BOARD_VERSION=1)
    def test_existing_board_revision_also_gets_the_new_card_catalog(self):
        room, player = create_room({'character_id': self.host.character_id})
        state = serialize_room(room, player.token)
        self.assertEqual(state['board']['version'], 1)
        self.assertTrue(all(card['image'] and card['effect_box'] for card in state['board']['shop'].values()))
        self.assertTrue(all(card['image'] and card['effect_box'] for card in state['board']['events']))

    @override_settings(PARTY_EVENT_REVEAL_MS=0, PARTY_ROLL_REVEAL_MS=0)
    def test_event_card_and_log_use_database_text_while_effect_remains_correct(self):
        PartyCard.objects.filter(kind='event', key='rich').update(effect_text='모두 코인 +2 · DB 문구')
        room, guest = join_room(self.room.code, {'character_id': self.host.character_id})
        for action, player in [('ready', self.host), ('ready', guest), ('start', self.host)]:
            room = perform_party_action(room.code, player.token, {'action': action, 'expected_version': room.version})
        self.host.refresh_from_db(); self.host.position = 41; self.host.save()
        before = self.host.coins
        room.document.update(move={'remaining': 1, 'dice': 1}, landed=False); room.save()
        with patch('battlelog.party_services.secrets.choice', return_value='rich'):
            room = perform_party_action(room.code, self.host.token, {'action':'advance', 'expected_version':room.version})
        state = serialize_room(room, self.host.token)
        self.assertEqual(state['event']['description'], '모두 코인 +2 · DB 문구')
        self.assertTrue(state['event']['image'].endswith('/lp-e02-going-to-be-rich.png'))
        self.assertEqual(state['players'][0]['coins'], before + 2)
        self.assertIn('DB 문구', state['log'][-1]['text'])
