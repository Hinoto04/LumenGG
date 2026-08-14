from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from card.models import Card, CardTranslation, Character, CharacterTranslation
from card.search import card_matches_search
from common.language import LANGUAGE_COOKIE_NAME, game_term, javascript_translations, translated_card_field, translated_character_field, ui_text
from common.localization import card_translation_key, render_localized_markup
from common.management.commands.convert_localized_references import Command as ConvertLocalizedReferencesCommand
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

        self.assertEqual(translated_card_field(source, 'en', 'text'), 'Use [Reference Card].')
        self.assertEqual(translated_card_field(source, 'ko', 'text'), 'Use [참조 카드].')

        reference_translation.name = 'Renamed Card'
        reference_translation.save()

        self.assertEqual(translated_card_field(source, 'en', 'text'), 'Use [Renamed Card].')

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

        self.assertEqual(translated_character_field(character, 'en', 'description'), 'About [NYA]')

    def test_character_technique_condition_conversion_wraps_angle_outside_square_name(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        CharacterTranslation.objects.create(
            character=character,
            language='ja',
            name='ニア',
        )
        rin = Character.objects.create(
            name='린',
            localization_key='rin',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/rin.webp',
        )
        command = ConvertLocalizedReferencesCommand()
        command.cards = []
        command.card_lookup = {}
        command.characters = [character, rin]
        targets = command.build_targets_for_language('ko')

        converted = command.replace_targets(
            '모든 [니아] 공격 기술과 9속도 이하 니아 기술 및 버린 기술',
            targets,
            'TKN-SRC',
        )

        self.assertEqual(
            converted,
            '모든 <[[character:nya]] 공격> 기술과 <9속도 이하 [[character:nya]]> 기술 및 버린 기술',
        )
        self.assertEqual(
            render_localized_markup(converted, 'ko'),
            '모든 <[니아] 공격> 기술과 <9속도 이하 [니아]> 기술 및 버린 기술',
        )

        ja_targets = command.build_targets_for_language('ja')
        self.assertEqual(
            command.replace_targets('速度9以下のニア技', ja_targets, 'TKN-SRC'),
            '<速度9以下の [[character:nya]]> 技',
        )

    def test_semantic_conversion_distinguishes_yin_yang_states_and_tokens(self):
        command = ConvertLocalizedReferencesCommand()
        command.cards = []
        command.card_lookup = {}
        command.characters = []
        targets = command.build_targets_for_language('ko')

        converted = command.replace_targets(
            '「음」: 상태 / 「음」카운터 / 【양】카운터 / [드럼]',
            targets,
            'TKN-SRC',
        )

        self.assertEqual(
            converted,
            '[[state:yin]]: 상태 / [[token:yin]]카운터 / [[token:yang]]카운터 / [[token:drum]]',
        )
        self.assertEqual(
            render_localized_markup(converted, 'ko'),
            '「음」: 상태 / 【음】카운터 / 【양】카운터 / 【드럼】',
        )

    def test_named_keywords_and_character_states_use_semantic_tokens(self):
        command = ConvertLocalizedReferencesCommand()
        command.cards = []
        command.card_lookup = {}
        command.characters = []
        targets = command.build_targets_for_language('ko')

        converted = command.replace_targets(
            '"라이!"와 "레피!" / 「오버 리밋」 / 「제로 슈트」 / '
            '「예고」 / 라이!명이 / [[state-card:ST1-PS1]] / [[state-card:ST4-PS1]]',
            targets,
            'TKN-SRC',
        )

        self.assertEqual(
            converted,
            '[[keyword:rai]]와 [[keyword:lefi]] / [[state:over_limit]] / '
            '[[state:zero_suit]] / [[state:advance_notice]] / [[keyword:rai]]명이 / '
            '[[state:over_limit]] / [[state:advance_notice]]',
        )

        command.ensure_keyword_sources()
        command.ensure_semantic_sources()
        self.assertEqual(
            render_localized_markup(converted, 'en'),
            '"Rai!"와 "Lefi!" / 「Over Limit」 / 「Zero Suit」 / '
            '「Advance Notice」 / "Rai!"명이 / 「Over Limit」 / 「Advance Notice」',
        )

    def test_semantic_reference_tokens_render_with_standard_marks(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        state_card = Card.objects.create(
            name='「오버 리밋」',
            code='TKN-STATE',
            type='특성',
            character=character,
            img='https://example.com/state.webp',
        )
        token_card = Card.objects.create(
            name='【불씨】',
            code='TKN-COUNTER',
            type='토큰',
            character=character,
            img='https://example.com/token.webp',
        )
        source = Card.objects.create(
            name='표기 테스트',
            code='TKN-MARKUP',
            character=character,
            text=(
                '[[state-card:TKN-STATE]] and [[token-card:TKN-COUNTER]] '
                'and [[keyword:rakshasa]] and [[state:harmony]] and [[token:hidden_bond]]'
            ),
            img='https://example.com/source.webp',
        )
        keyword, _created = TranslationSource.objects.update_or_create(
            key='keyword.rakshasa',
            defaults={
                'category': 'keyword',
                'source_text': '나찰',
                'field_name': 'name',
            },
        )
        TranslationValue.objects.update_or_create(
            source=keyword,
            language='en',
            defaults={'text': 'Rakshasa'},
        )
        harmony, _created = TranslationSource.objects.update_or_create(
            key='term.state.harmony',
            defaults={
                'category': 'state',
                'source_text': '조화',
                'field_name': 'state',
            },
        )
        TranslationValue.objects.update_or_create(
            source=harmony,
            language='en',
            defaults={'text': 'Harmony'},
        )
        hidden_bond, _created = TranslationSource.objects.update_or_create(
            key='term.token.hidden_bond',
            defaults={
                'category': 'token',
                'source_text': '은연',
                'field_name': 'token',
            },
        )
        TranslationValue.objects.update_or_create(
            source=hidden_bond,
            language='en',
            defaults={'text': 'Hidden Bond'},
        )
        CardTranslation.objects.create(
            card=state_card,
            language='en',
            name='Over Limit',
        )
        CardTranslation.objects.create(
            card=token_card,
            language='en',
            name='Ember',
        )

        self.assertEqual(
            translated_card_field(source, 'ko', 'text'),
            '「오버 리밋」 and 【불씨】 and "나찰" and 「조화」 and 【은연】',
        )
        self.assertEqual(
            translated_card_field(source, 'en', 'text'),
            '「Over Limit」 and 【Ember】 and "Rakshasa" and 「Harmony」 and 【Hidden Bond】',
        )

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
