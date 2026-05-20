from django.test import TestCase
from django.urls import reverse

from card.models import Card, CardTranslation, Character
from common.language import LANGUAGE_COOKIE_NAME, game_term, translated_card_field
from common.models import TermTranslation


class LanguageSettingTests(TestCase):
    def test_set_language_stores_session_and_cookie(self):
        response = self.client.post(
            reverse('common:setLanguage'),
            {'language': 'en', 'next': '/'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['lumengg_language'], 'en')
        self.assertEqual(response.cookies[LANGUAGE_COOKIE_NAME].value, 'en')


class TranslationLookupTests(TestCase):
    def test_card_translation_falls_back_to_korean_when_missing(self):
        character = Character.objects.create(
            name='니아',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        card = Card.objects.create(
            name='라이! 촙!',
            code='ST1-005',
            character=character,
            img='https://example.com/card.webp',
        )

        self.assertEqual(translated_card_field(card, 'en', 'name'), '라이! 촙!')

    def test_card_translation_uses_selected_language(self):
        character = Character.objects.create(
            name='니아',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        card = Card.objects.create(
            name='라이! 촙!',
            code='ST1-005',
            character=character,
            img='https://example.com/card.webp',
        )
        CardTranslation.objects.create(
            card=card,
            language='en',
            name='Rai! Chop!',
        )

        self.assertEqual(translated_card_field(card, 'en', 'name'), 'Rai! Chop!')

    def test_game_term_translates_builtin_judgment_terms(self):
        self.assertEqual(game_term('방어', 'en'), 'Guard')
        self.assertEqual(game_term('상단·중단 상쇄', 'en'), 'High/Mid Clash')
        self.assertEqual(game_term('하단 회피/그랩', 'ja'), '下段 回避/投げ')

    def test_game_term_uses_custom_term_translation(self):
        TermTranslation.objects.create(
            source='잔향',
            language='en',
            text='Afterimage',
            category='body',
        )

        self.assertEqual(game_term('잔향', 'en'), 'Afterimage')
