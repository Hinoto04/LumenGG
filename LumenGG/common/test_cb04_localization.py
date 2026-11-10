from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, TestCase

from card.models import Card, CardTranslation, Character
from common.localization import TOKEN_RE, clear_localization_cache
from common.localization_batches.batch_cb04_20261110 import CARDS, TRANSLATED_FIELDS
from common.models import TranslationValue


class CB04TranslationDataTests(SimpleTestCase):
    def test_new_bukuki_cards_have_both_languages(self):
        self.assertEqual(
            [row['snapshot']['code'] for row in CARDS],
            ['CB04-AT-001', 'CB04-AT-002', 'CB04-AT-007'],
        )
        for row in CARDS:
            self.assertEqual(set(row['translations']), {'en', 'ja'})
            for language, fields in row['translations'].items():
                self.assertEqual(set(fields), set(TRANSLATED_FIELDS))
                for field, text in fields.items():
                    with self.subTest(code=row['snapshot']['code'], language=language, field=field):
                        self.assertNotRegex(text, '[가-힣]')
                        if row['snapshot'][field]:
                            self.assertTrue(text)
                        self.assertEqual(
                            TOKEN_RE.findall(row['snapshot'][field]), TOKEN_RE.findall(text),
                        )

    def test_terms_match_already_published_bukuki_cards(self):
        # CB04-PS-001/AT-012 were translated with these names before this batch.
        for row in CARDS:
            text = row['snapshot']['text']
            en = row['translations']['en']['text']
            ja = row['translations']['ja']['text']
            if '[부쿠키]' in text:
                self.assertIn('[BUKUKI]', en)
                self.assertIn('[ブクキ]', ja)
            if '서리' in text:
                self.assertIn('"Frost"', en)
                self.assertIn('「霜」', ja)


class CB04TranslationRestoreTests(TestCase):
    def setUp(self):
        self.row = CARDS[0]
        self.character = Character.objects.create(name='부쿠키', description='', group='', datas={}, img='')
        snapshot = {key: value for key, value in self.row['snapshot'].items() if key != 'character_id'}
        self.card = Card.objects.create(character=self.character, **snapshot)
        self.addCleanup(clear_localization_cache)

    def run_migration(self):
        migration = import_module('common.migrations.0023_cb04_localization')
        migration.forwards(apps, SimpleNamespace(connection=connection))

    def test_migration_restores_both_stores_and_is_idempotent(self):
        self.run_migration()
        self.run_migration()
        for language, fields in self.row['translations'].items():
            legacy = CardTranslation.objects.get(card=self.card, language=language)
            for field, text in fields.items():
                with self.subTest(language=language, field=field):
                    self.assertEqual(getattr(legacy, field), text)
                    if text:
                        value = TranslationValue.objects.get(
                            source__key=f'card.{self.card.code}.{field}', language=language,
                        )
                        self.assertEqual(value.text, text)
                        self.assertEqual(value.status, 'translated')

    def test_changed_source_text_is_not_overwritten_with_stale_translation(self):
        Card.objects.filter(pk=self.card.pk).update(text='수정된 원문')
        self.run_migration()
        legacy = CardTranslation.objects.get(card=self.card, language='en')
        self.assertEqual(legacy.text, '')
        self.assertEqual(legacy.name, self.row['translations']['en']['name'])

    def test_existing_editorial_translation_is_kept(self):
        CardTranslation.objects.create(card=self.card, language='en', name='Edited Name')
        self.run_migration()
        self.assertEqual(CardTranslation.objects.get(card=self.card, language='en').name, 'Edited Name')
