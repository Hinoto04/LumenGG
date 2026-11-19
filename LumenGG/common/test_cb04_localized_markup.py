"""CB04 카드 원문·번역의 용어 변환 표기(0028) 테스트."""

from collections import defaultdict
from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, TestCase

from card.models import Card, CardTranslation, Character
from common.localization import TOKEN_RE, clear_localization_cache, render_localized_markup
from common.localization_batches.batch_cb04_20261119 import CARDS as FIFTH_CARDS
from common.localization_batches.batch_cb04_markup_20261119 import DATA
from common.models import TranslationSource, TranslationValue


class CB04MarkupDataTests(SimpleTestCase):
    def test_every_language_uses_the_same_tokens(self):
        tokens = defaultdict(dict)
        for change in DATA['changes']:
            tokens[(change['code'], change['field'])][change['language']] = sorted(
                TOKEN_RE.findall(change['new']),
            )
        for (code, field), by_language in tokens.items():
            with self.subTest(code=code, field=field):
                self.assertIn('ko', by_language)
                for language, found in by_language.items():
                    self.assertTrue(found, language)
                    self.assertEqual(found, by_language['ko'], language)

    def test_known_keywords_are_no_longer_plain_brackets(self):
        plain = {
            'ko': ['[부쿠키]', '[불씨]', '[거미]', '「서리', '[귀섬]', '[핀프]', '[CMYK]', '「청염」', '【개러지】'],
            'en': ['[BUKUKI]', '[Ember]', '[Spider]', '"Frost"', '[Oni Flash]', '[PINP]', '[CMYK]', '【Garage】'],
            'ja': ['[ブクキ]', '[火種]', '[蜘蛛]', '「霜」', '[鬼閃]', '[ピンプ]', '[CMYK]', '【ガレージ】'],
        }
        for change in DATA['changes']:
            for term in plain[change['language']]:
                with self.subTest(code=change['code'], language=change['language'], term=term):
                    self.assertNotIn(term, change['new'])

    def test_expected_references(self):
        expected = {
            ('CB04-AT-024', 'ko'): '[[token:ember]]',
            ('CB04-AT-027', 'en'): '[[token:spider]]',
            ('CB04-AT-007', 'ja'): '[[state:frost]]',
            ('CB04-AT-007', 'en'): '[[state:frost]]',
            ('CB04-AT-002', 'ko'): '<[[character:부쿠키]]>',
            ('CB04-AT-004', 'ko'): '<[[character:부쿠키]]>',
            ('CB04-AT-031', 'ja'): '[[card:RFS-AT-002]]',
            ('DFR-AT-017', 'en'): '[[token:garage]]',
        }
        texts = {(change['code'], change['language']): change['new'] for change in DATA['changes']
                 if change['field'] == 'text'}
        for key, token in expected.items():
            with self.subTest(key=key):
                self.assertIn(token, texts[key])


class CB04MarkupMigrationTests(TestCase):
    def setUp(self):
        self.row = next(row for row in FIFTH_CARDS if row['snapshot']['code'] == 'CB04-AT-027')
        character = Character.objects.create(
            name='이제벨', localization_key='ezebel', description='', group='', datas={}, img='',
        )
        snapshot = {key: value for key, value in self.row['snapshot'].items() if key != 'character_id'}
        self.card = Card.objects.create(character=character, **snapshot)
        self.addCleanup(clear_localization_cache)

    def run_migrations(self):
        for name in ('0027_cb04_fifth_localization', '0028_cb04_localized_markup'):
            import_module(f'common.migrations.{name}').forwards(apps, SimpleNamespace(connection=connection))
        clear_localization_cache()

    def test_converts_source_and_translations_idempotently(self):
        self.run_migrations()
        self.run_migrations()
        changes = {
            change['language']: change['new'] for change in DATA['changes']
            if change['code'] == self.card.code and change['field'] == 'text'
        }
        self.card.refresh_from_db()
        self.assertEqual(self.card.text, changes['ko'])
        self.assertEqual(
            TranslationSource.objects.get(key=f'card.{self.card.code}.text').source_text, changes['ko'],
        )
        for language in ('en', 'ja'):
            with self.subTest(language=language):
                self.assertEqual(
                    CardTranslation.objects.get(card=self.card, language=language).text, changes[language],
                )
                self.assertEqual(
                    TranslationValue.objects.get(
                        source__key=f'card.{self.card.code}.text', language=language,
                    ).text,
                    changes[language],
                )

    def test_rendered_text_uses_localized_token_names(self):
        self.run_migrations()
        self.card.refresh_from_db()
        en = CardTranslation.objects.get(card=self.card, language='en').text
        ja = CardTranslation.objects.get(card=self.card, language='ja').text
        self.assertIn('【Spider】', render_localized_markup(en, 'en'))
        self.assertIn('【蜘蛛】', render_localized_markup(ja, 'ja'))
        self.assertIn('【거미】', render_localized_markup(self.card.text, 'ko'))

    def test_new_terms_are_seeded(self):
        self.run_migrations()
        self.assertEqual(
            render_localized_markup('[[state:frost]] [[token:garage]]', 'en'), '「Frost」 【Garage】',
        )
        self.assertEqual(
            render_localized_markup('[[state:frost]] [[token:garage]]', 'ja'), '「霜」 【ガレージ】',
        )

    def test_edited_text_is_not_replaced(self):
        Card.objects.filter(pk=self.card.pk).update(text='수정된 원문')
        self.run_migrations()
        self.card.refresh_from_db()
        self.assertEqual(self.card.text, '수정된 원문')
