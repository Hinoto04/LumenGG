"""CB04 추가 공개 카드 2장(2026-11-25)의 번역 배치 테스트."""

from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, TestCase

from card.models import Card, CardTranslation, Character
from common.localization import TOKEN_RE, clear_localization_cache
from common.localization_batches.batch_cb04_20261125 import CARDS, TRANSLATED_FIELDS
from common.models import TranslationSource, TranslationValue


EXPECTED_CODES = ['CB04-AT-040', 'CB04-AT-041']
# 조건 표기 → (영어, 일본어). 기존 번역 카드와 같은 용어를 쓴다.
TERMS = {
    '<7속도>': ('<Speed 7>', '〈速度7〉'),
    '<13속도>': ('<Speed 13>', '〈速度13〉'),
    '특수 기술': ('Special Technique', '特殊技'),
    '데미지 보정': ('damage scaling', 'ダメージ補正'),
}


class CB04SeventhTranslationDataTests(SimpleTestCase):
    def test_all_new_cards_have_both_languages(self):
        self.assertEqual([row['snapshot']['code'] for row in CARDS], EXPECTED_CODES)
        for row in CARDS:
            self.assertEqual(set(row['translations']), {'en', 'ja'})
            for language, fields in row['translations'].items():
                self.assertEqual(set(fields), set(TRANSLATED_FIELDS))
                for field, text in fields.items():
                    with self.subTest(code=row['snapshot']['code'], language=language, field=field):
                        self.assertNotRegex(TOKEN_RE.sub('', text), '[가-힣]')
                        if row['snapshot'][field]:
                            self.assertTrue(text)

    def test_terms_match_existing_translations(self):
        for row in CARDS:
            source = row['snapshot']['text']
            for term, (en, ja) in TERMS.items():
                if term in source:
                    with self.subTest(code=row['snapshot']['code'], term=term):
                        self.assertIn(en, row['translations']['en']['text'])
                        self.assertIn(ja, row['translations']['ja']['text'])

    def test_numbered_lines_are_preserved(self):
        for row in CARDS:
            for marker in '①②③':
                in_source = marker in row['snapshot']['text']
                for language in ('en', 'ja'):
                    with self.subTest(code=row['snapshot']['code'], marker=marker, language=language):
                        self.assertEqual(marker in row['translations'][language]['text'], in_source)


class CB04SeventhTranslationRestoreTests(TestCase):
    def setUp(self):
        self.row = next(row for row in CARDS if row['snapshot']['code'] == 'CB04-AT-040')
        self.character = Character.objects.create(
            name='세츠메이', localization_key='setsumei', description='', group='', datas={}, img='',
        )
        snapshot = {key: value for key, value in self.row['snapshot'].items() if key != 'character_id'}
        self.card = Card.objects.create(character=self.character, **snapshot)
        self.addCleanup(clear_localization_cache)

    def run_migration(self):
        migration = import_module('common.migrations.0030_cb04_seventh_localization')
        migration.forwards(apps, SimpleNamespace(connection=connection))
        clear_localization_cache()

    def test_migration_restores_translations_idempotently(self):
        self.run_migration()
        self.run_migration()
        self.card.refresh_from_db()
        self.assertEqual(self.card.text, self.row['snapshot']['text'])
        for language, fields in self.row['translations'].items():
            legacy = CardTranslation.objects.get(card=self.card, language=language)
            for field in ('name', 'text'):
                with self.subTest(language=language, field=field):
                    self.assertEqual(getattr(legacy, field), fields[field])
                    value = TranslationValue.objects.get(
                        source__key=f'card.{self.card.code}.{field}', language=language,
                    )
                    self.assertEqual(value.text, fields[field])
                    self.assertEqual(value.status, 'translated')
        self.assertTrue(TranslationSource.objects.filter(key=f'card.{self.card.code}.name').exists())

    def test_changed_source_text_is_not_overwritten(self):
        Card.objects.filter(pk=self.card.pk).update(text='수정된 원문')
        self.run_migration()
        legacy = CardTranslation.objects.get(card=self.card, language='ja')
        self.assertEqual(legacy.text, '')
        self.assertEqual(legacy.name, self.row['translations']['ja']['name'])
