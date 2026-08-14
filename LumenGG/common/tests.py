from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from card.models import Card, CardTranslation, Character, CharacterTranslation
from card.search import card_matches_search
from common.language import LANGUAGE_COOKIE_NAME, game_term, javascript_translations, translated_card_field, translated_character_field, ui_text
from common.localization import card_translation_key
from common.models import TermTranslation, TranslationSource, TranslationValue


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
        self.assertEqual(game_term('개러지 토큰', 'en'), 'Garage Token')
        self.assertEqual(game_term('개러지 토큰', 'ja'), 'ガレージトークン')

    def test_yohan_passive_short_labels_are_translated(self):
        self.assertEqual(ui_text('홀', 'en'), 'Odd')
        self.assertEqual(ui_text('짝', 'en'), 'Even')
        self.assertEqual(ui_text('공', 'ja'), '攻')
        self.assertEqual(ui_text('수', 'ja'), '防')
        self.assertEqual(javascript_translations('en')['선언'], 'Declare')
        self.assertEqual(javascript_translations('ja')['예지'], '予知')

    def test_game_term_uses_custom_term_translation(self):
        TermTranslation.objects.create(
            source='잔향',
            language='en',
            text='Afterimage',
            category='body',
        )

        self.assertEqual(game_term('잔향', 'en'), 'Afterimage')

    def test_card_reference_token_renders_current_translated_name(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        referenced = Card.objects.create(
            name='참조 카드',
            code='TKN-REF',
            character=character,
            img='https://example.com/ref.webp',
        )
        reference_translation = CardTranslation.objects.create(
            card=referenced,
            language='en',
            name='Reference Card',
        )
        source = Card.objects.create(
            name='토큰 테스트',
            code='TKN-SRC',
            character=character,
            text='Use [[card:TKN-REF]].',
            img='https://example.com/source.webp',
        )

        self.assertEqual(translated_card_field(source, 'en', 'text'), 'Use Reference Card.')
        self.assertEqual(translated_card_field(source, 'ko', 'text'), 'Use 참조 카드.')

        reference_translation.name = 'Renamed Card'
        reference_translation.save()

        self.assertEqual(translated_card_field(source, 'en', 'text'), 'Use Renamed Card.')

    def test_single_bracket_card_reference_token_is_supported(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        referenced = Card.objects.create(
            name='참조 카드',
            code='TKN-SINGLE-REF',
            character=character,
            img='https://example.com/ref.webp',
        )
        CardTranslation.objects.create(
            card=referenced,
            language='en',
            name='Single Reference',
        )
        source = Card.objects.create(
            name='단일 괄호 테스트',
            code='TKN-SINGLE-SRC',
            character=character,
            text='Use [card:TKN-SINGLE-REF].',
            img='https://example.com/source.webp',
        )

        self.assertEqual(translated_card_field(source, 'en', 'text'), 'Use Single Reference.')
        self.assertEqual(translated_card_field(source, 'ko', 'text'), 'Use 참조 카드.')

    def test_character_reference_token_renders_current_translated_name(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='[[character:nya]] 소개',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        CharacterTranslation.objects.create(
            character=character,
            language='en',
            name='NYA',
            description='About [[character:nya]]',
        )

        self.assertEqual(translated_character_field(character, 'en', 'description'), 'About NYA')

    def test_search_uses_translation_catalog_values(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        card = Card.objects.create(
            name='검색 원본',
            code='TKN-SEARCH',
            character=character,
            img='https://example.com/card.webp',
        )
        source = TranslationSource.objects.get(key=card_translation_key(card, 'name'))
        TranslationValue.objects.create(
            source=source,
            language='en',
            text='Catalog Search Name',
        )

        self.assertTrue(card_matches_search(card, 'catalog search'))

    def test_fill_missing_localization_generates_hidden_keywords_from_translated_name(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        card = Card.objects.create(
            name='퀵 알레',
            code='TKN-HIDDEN',
            character=character,
            hiddenKeyword='퀵알레/퀵알래/',
            img='https://example.com/card.webp',
        )
        CardTranslation.objects.create(
            card=card,
            language='en',
            name='Quick Allez',
            hiddenKeyword='퀵알레/',
        )
        CardTranslation.objects.create(
            card=card,
            language='ja',
            name='クイック・アレ',
            hiddenKeyword='퀵알레/',
        )

        call_command('fill_missing_localization', verbosity=0)

        en_hidden = translated_card_field(card, 'en', 'hiddenKeyword')
        ja_hidden = translated_card_field(card, 'ja', 'hiddenKeyword')

        self.assertIn('QuickAllez/', en_hidden)
        self.assertIn('quickallez/', en_hidden)
        self.assertNotIn('퀵알레', en_hidden)
        self.assertIn('クイックアレ/', ja_hidden)
        self.assertNotIn('퀵알레', ja_hidden)
        self.assertTrue(card_matches_search(card, 'quickallez'))
        self.assertTrue(card_matches_search(card, 'クイックアレ'))
