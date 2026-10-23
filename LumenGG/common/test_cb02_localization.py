from importlib import import_module
from io import StringIO
from types import SimpleNamespace

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, TestCase

from card.models import Card, CardTranslation, Character
from collection.models import CollectionCard, Pack
from common.localization import TOKEN_RE, clear_localization_cache, translate_card_field
from common.localization_batches.batch_cb02_20261023 import (
    CARDS, TRANSLATED_FIELDS, restore_missing_translations,
)
from common.localization_batches.batch_cb02_reprints_20261023 import restore_missing_pack_translations
from common.models import TranslationSource, TranslationValue


class CB02TranslationDataTests(SimpleTestCase):
    def test_all_29_cards_have_both_languages_and_preserve_references(self):
        self.assertEqual(len(CARDS), 29)
        self.assertEqual(len({row['snapshot']['code'] for row in CARDS}), 29)
        for row in CARDS:
            self.assertTrue(row['snapshot']['code'].startswith('CB02-'))
            self.assertEqual(set(row['translations']), {'en', 'ja'})
            for language, fields in row['translations'].items():
                self.assertEqual(set(fields), set(TRANSLATED_FIELDS))
                for field, text in fields.items():
                    with self.subTest(code=row['snapshot']['code'], language=language, field=field):
                        self.assertNotRegex(text, '[가-힣]')
                        if row['snapshot'][field] and field != 'hiddenKeyword':
                            self.assertTrue(text)
                        self.assertEqual(
                            TOKEN_RE.findall(row['snapshot'][field]), TOKEN_RE.findall(text),
                        )


class CB02TranslationRestoreTests(TestCase):
    def setUp(self):
        self.row = CARDS[0]
        self.character = Character.objects.create(name='키메라', description='', group='', datas={}, img='')
        snapshot = {key: value for key, value in self.row['snapshot'].items() if key != 'character_id'}
        self.card = Card.objects.create(character=self.character, **snapshot)
        self.addCleanup(clear_localization_cache)

    def test_migration_restores_both_stores_and_is_idempotent(self):
        migration = import_module('common.migrations.0021_cb02_localization')
        migration.forwards(apps, SimpleNamespace(connection=connection))
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
        values = list(TranslationValue.objects.order_by('pk').values())
        self.assertEqual(restore_missing_translations(apps), 0)
        self.assertEqual(list(TranslationValue.objects.order_by('pk').values()), values)

    def test_catalog_edits_are_preserved_and_copied_to_empty_legacy_fields(self):
        source = TranslationSource.objects.get(key=f'card.{self.card.code}.name')
        TranslationValue.objects.create(source=source, language='en', text='Edited name', status='translated')
        restore_missing_translations(apps)
        source.refresh_from_db()
        self.assertEqual(source.values.get(language='en').text, 'Edited name')
        self.assertEqual(CardTranslation.objects.get(card=self.card, language='en').name, 'Edited name')

    def test_legacy_edits_are_preserved_when_catalog_translation_is_missing(self):
        legacy = CardTranslation.objects.create(card=self.card, language='en', name='Legacy edit')
        TranslationValue.objects.filter(source__key=f'card.{self.card.code}.name', language='en').delete()
        restore_missing_translations(apps)
        legacy.refresh_from_db()
        self.assertEqual(legacy.name, 'Legacy edit')
        self.assertEqual(translate_card_field(self.card, 'en', 'name'), 'Legacy edit')

    def test_changed_card_text_is_not_given_a_stale_translation(self):
        self.card.text += '\n새로 개정된 효과'
        self.card.save(update_fields=['text'])
        restore_missing_translations(apps)
        self.assertFalse(TranslationValue.objects.filter(
            source__key=f'card.{self.card.code}.text', language='en',
        ).exists())
        self.assertEqual(CardTranslation.objects.get(card=self.card, language='en').text, '')

    def test_newer_catalog_source_and_inactive_sources_are_preserved(self):
        source = TranslationSource.objects.get(key=f'card.{self.card.code}.text')
        source.source_text = '카탈로그에서 개정된 효과'
        source.save(update_fields=['source_text'])
        name = TranslationSource.objects.get(key=f'card.{self.card.code}.name')
        name.is_active = False
        name.save(update_fields=['is_active'])
        restore_missing_translations(apps)
        source.refresh_from_db()
        name.refresh_from_db()
        self.assertEqual(source.source_text, '카탈로그에서 개정된 효과')
        self.assertFalse(source.values.exists())
        self.assertFalse(name.is_active)
        self.assertFalse(name.values.exists())

    def test_korean_placeholder_does_not_override_the_translation_batch(self):
        CardTranslation.objects.create(card=self.card, language='en', text=self.card.text)
        TranslationValue.objects.filter(
            source__key=f'card.{self.card.code}.text', language='en',
        ).update(status='missing')
        restore_missing_translations(apps)
        clear_localization_cache()
        value = TranslationValue.objects.get(source__key=f'card.{self.card.code}.text', language='en')
        self.assertEqual(value.text, self.row['translations']['en']['text'])
        self.assertEqual(CardTranslation.objects.get(card=self.card, language='en').text, value.text)

    def test_fill_command_restores_missing_cb02_and_dry_run_rolls_back(self):
        call_command('fill_missing_localization', '--dry-run', stdout=StringIO())
        self.assertFalse(CardTranslation.objects.filter(card=self.card).exists())
        call_command('fill_missing_localization', stdout=StringIO())
        clear_localization_cache()
        self.assertEqual(translate_card_field(self.card, 'en', 'name'), self.row['translations']['en']['name'])
        self.assertEqual(CardTranslation.objects.get(card=self.card, language='ja').text,
                         self.row['translations']['ja']['text'])

    def test_other_packs_are_not_modified(self):
        other = Card.objects.create(code='CB03-TEST', name='다른 카드', character=self.character)
        restore_missing_translations(apps)
        self.assertFalse(CardTranslation.objects.filter(card=other).exists())


class CB02ReprintTranslationRestoreTests(TestCase):
    def setUp(self):
        character = Character.objects.create(name='세츠', description='', group='', datas={}, img='')
        self.card = Card.objects.create(code='ST1-013', name='구르기', keyword='회피/', character=character)
        self.pack = Pack.objects.create(code='CB02', name='잔칫날의 초담')
        CollectionCard.objects.create(card=self.card, pack=self.pack, code='CB02-PR-001')
        source = TranslationSource.objects.get(key=f'card.{self.card.code}.keyword')
        self.value = TranslationValue.objects.create(source=source, language='en', text='Dodge/', status='translated')
        self.addCleanup(clear_localization_cache)

    def test_migration_resolves_original_card_code_and_is_idempotent(self):
        migration = import_module('common.migrations.0022_cb02_reprint_localization')
        migration.forwards(apps, SimpleNamespace(connection=connection))
        self.assertEqual(CardTranslation.objects.get(card=self.card, language='en').keyword, 'Dodge/')
        self.assertEqual(restore_missing_pack_translations(apps), 0)

    def test_preserves_existing_legacy_and_catalog_edits(self):
        legacy = CardTranslation.objects.create(card=self.card, language='en', keyword='Edited keyword/')
        self.value.refresh_from_db()
        self.value.text = 'Catalog edit/'
        self.value.save(update_fields=['text'])
        self.assertEqual(restore_missing_pack_translations(apps), 0)
        legacy.refresh_from_db()
        self.value.refresh_from_db()
        self.assertEqual(legacy.keyword, 'Edited keyword/')
        self.assertEqual(self.value.text, 'Catalog edit/')

    def test_skips_a_card_not_printed_in_cb02(self):
        CollectionCard.objects.filter(card=self.card).delete()
        self.assertEqual(restore_missing_pack_translations(apps), 0)
        self.assertFalse(CardTranslation.objects.filter(card=self.card).exists())

    def test_does_not_copy_a_stale_or_unreviewed_catalog_translation(self):
        self.value.status = 'needs_review'
        self.value.save(update_fields=['status'])
        self.assertEqual(restore_missing_pack_translations(apps), 0)
        self.value.status = 'translated'
        self.value.save(update_fields=['status'])
        self.card.keyword = '다른 키워드/'
        self.card.save(update_fields=['keyword'])
        self.value.source.refresh_from_db()
        self.value.source.source_text = '이전 원문'
        self.value.source.save(update_fields=['source_text'])
        self.assertEqual(restore_missing_pack_translations(apps), 0)
        self.assertFalse(CardTranslation.objects.filter(card=self.card).exists())

    def test_fill_command_covers_reprints_and_dry_run_rolls_back(self):
        call_command('fill_missing_localization', '--dry-run', stdout=StringIO())
        self.assertFalse(CardTranslation.objects.filter(card=self.card).exists())
        call_command('fill_missing_localization', stdout=StringIO())
        self.assertEqual(CardTranslation.objects.get(card=self.card, language='en').keyword, 'Dodge/')
