from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, TestCase

from card.models import Card, CardTranslation, Character
from common.localization import TOKEN_RE, clear_localization_cache
from common.localization_batches.batch_cb04_20261116 import CARDS, TRANSLATED_FIELDS
from common.models import TranslationValue


EXPECTED_CODES = [
    'CB04-AT-035', 'CB04-AT-036', 'CB04-AT-037', 'CB04-TK-001',
    'CB04-AT-003', 'CB04-AT-004', 'CB04-AT-006', 'CB04-AT-021',
    'CB04-AT-022', 'CB04-AT-010', 'CB04-AT-011', 'CB04-AT-013',
]
# 원문 표기 → (영어, 일본어). 기존 번역 카드와 같은 용어를 쓴다.
TERMS = {
    '[부쿠키]': ('[BUKUKI]', '[ブクキ]'),
    '서리': ('"Frost"', '「霜」'),
    '【보컬】': ('【Vocal】', '【ボーカル】'),
    '【기타】': ('【Guitar】', '【ギター】'),
    '【드럼】': ('【Drum】', '【ドラム】'),
    '[CMYK]': ('[CMYK]', '[CMYK]'),
    '「조화」': ('「Harmony」', '「調和」'),
    '「음」': ('「Yin」', '「陰」'),
    '「양」': ('「Yang」', '「陽」'),
    '[양]': ('[Yang]', '[陽]'),
    '[음]': ('[Yin]', '[陰]'),
    '보호막': ('Shield', 'シールド'),
}


class CB04SecondTranslationDataTests(SimpleTestCase):
    def test_all_new_cards_have_both_languages(self):
        self.assertEqual([row['snapshot']['code'] for row in CARDS], EXPECTED_CODES)
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


class CB04SecondTranslationRestoreTests(TestCase):
    def setUp(self):
        self.row = next(row for row in CARDS if row['snapshot']['code'] == 'CB04-AT-022')
        self.character = Character.objects.create(name='타오', description='', group='', datas={}, img='')
        snapshot = {key: value for key, value in self.row['snapshot'].items() if key != 'character_id'}
        self.card = Card.objects.create(character=self.character, **snapshot)
        self.addCleanup(clear_localization_cache)

    def run_migration(self):
        migration = import_module('common.migrations.0024_cb04_second_localization')
        migration.forwards(apps, SimpleNamespace(connection=connection))

    def test_migration_restores_name_ruby_and_text_idempotently(self):
        self.run_migration()
        self.run_migration()
        for language, fields in self.row['translations'].items():
            legacy = CardTranslation.objects.get(card=self.card, language=language)
            for field in ('name', 'ruby', 'text'):
                with self.subTest(language=language, field=field):
                    self.assertEqual(getattr(legacy, field), fields[field])
                    value = TranslationValue.objects.get(
                        source__key=f'card.{self.card.code}.{field}', language=language,
                    )
                    self.assertEqual(value.text, fields[field])
                    self.assertEqual(value.status, 'translated')

    def test_changed_source_text_is_not_overwritten(self):
        Card.objects.filter(pk=self.card.pk).update(text='수정된 원문')
        self.run_migration()
        legacy = CardTranslation.objects.get(card=self.card, language='ja')
        self.assertEqual(legacy.text, '')
        self.assertEqual(legacy.name, self.row['translations']['ja']['name'])
