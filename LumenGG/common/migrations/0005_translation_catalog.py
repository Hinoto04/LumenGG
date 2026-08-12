import hashlib
import re
import unicodedata

import django.db.models.deletion
from django.db import migrations, models


CARD_FIELDS = ('name', 'ruby', 'text', 'detail_text', 'keyword', 'hiddenKeyword', 'search')
CHARACTER_FIELDS = ('name', 'description', 'group', 'datas')
LANGUAGES = ('en', 'ja')


def slug(value, fallback='item'):
    value = str(value or '').strip()
    normalized = unicodedata.normalize('NFKD', value)
    ascii_value = normalized.encode('ascii', 'ignore').decode('ascii').lower()
    ascii_value = re.sub(r'[^a-z0-9]+', '_', ascii_value).strip('_')
    if ascii_value:
        return ascii_value[:80]
    digest = hashlib.sha1(value.encode('utf-8')).hexdigest()[:10]
    return f'{fallback}_{digest}'


def unique_key(prefix, value, used, fallback='item'):
    base_slug = slug(value, fallback=fallback)
    candidate = f'{prefix}{base_slug}'
    index = 2
    while candidate in used:
        candidate = f'{prefix}{base_slug}_{index}'
        index += 1
    used.add(candidate)
    return candidate


def content_type(ContentType, app_label, model):
    content_type_obj, _created = ContentType.objects.get_or_create(
        app_label=app_label,
        model=model,
    )
    return content_type_obj


def upsert_source(TranslationSource, key, category, source_text='', source_data=None, content_type=None, object_id=None, field_name='', note=''):
    defaults = {
        'category': category,
        'source_text': source_text or '',
        'source_data': source_data or {},
        'content_type': content_type,
        'object_id': object_id,
        'field_name': field_name or '',
        'note': note or '',
        'is_active': True,
    }
    source, _created = TranslationSource.objects.update_or_create(
        key=key,
        defaults=defaults,
    )
    return source


def upsert_value(TranslationValue, source, language, text='', data=None, overwrite=True):
    data = data or {}
    status = 'translated' if (text or data) else 'missing'
    value, created = TranslationValue.objects.get_or_create(
        source=source,
        language=language,
        defaults={'text': text or '', 'data': data, 'status': status},
    )
    if not created and overwrite:
        value.text = text or ''
        value.data = data
        value.status = status
        value.save(update_fields=['text', 'data', 'status', 'updated_at'])
    return value


def fill_value_if_missing(TranslationValue, source, language, text='', data=None):
    value, _created = TranslationValue.objects.get_or_create(
        source=source,
        language=language,
        defaults={
            'text': text or '',
            'data': data or {},
            'status': 'translated' if (text or data) else 'missing',
        },
    )
    if text and not value.text:
        value.text = text
        value.status = 'translated'
        value.save(update_fields=['text', 'status', 'updated_at'])
    if data and not value.data:
        value.data = data
        value.status = 'translated'
        value.save(update_fields=['data', 'status', 'updated_at'])


def seed_translation_catalog(apps, schema_editor):
    Card = apps.get_model('card', 'Card')
    CardTranslation = apps.get_model('card', 'CardTranslation')
    Character = apps.get_model('card', 'Character')
    CharacterTranslation = apps.get_model('card', 'CharacterTranslation')
    TermTranslation = apps.get_model('common', 'TermTranslation')
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationValue = apps.get_model('common', 'TranslationValue')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    card_ct = content_type(ContentType, 'card', 'card')
    character_ct = content_type(ContentType, 'card', 'character')
    used_keys = set(TranslationSource.objects.values_list('key', flat=True))
    card_name_sources = {}
    character_name_sources = {}

    for card in Card.objects.order_by('id'):
        if not card.code:
            continue
        translations = {
            translation.language: translation
            for translation in CardTranslation.objects.filter(card_id=card.id)
        }
        for field_name in CARD_FIELDS:
            source_text = getattr(card, field_name, '') or ''
            translated_values = {
                language: getattr(translation, field_name, '') or ''
                for language, translation in translations.items()
            }
            if not source_text and not any(translated_values.values()):
                continue
            key = f'card.{card.code}.{field_name}'
            used_keys.add(key)
            source = upsert_source(
                TranslationSource,
                key,
                'card',
                source_text=source_text,
                content_type=card_ct,
                object_id=card.id,
                field_name=field_name,
            )
            if field_name == 'name' and source_text:
                card_name_sources[source_text] = source
            for language in LANGUAGES:
                upsert_value(
                    TranslationValue,
                    source,
                    language,
                    text=translated_values.get(language, ''),
                )

    for character in Character.objects.order_by('id'):
        translations = {
            translation.language: translation
            for translation in CharacterTranslation.objects.filter(character_id=character.id)
        }
        if not character.localization_key:
            continue
        for field_name in CHARACTER_FIELDS:
            source_text = '' if field_name == 'datas' else getattr(character, field_name, '') or ''
            source_data = character.datas or {} if field_name == 'datas' else {}
            translated_values = {}
            translated_data = {}
            for language, translation in translations.items():
                if field_name == 'datas':
                    translated_data[language] = translation.datas or {}
                else:
                    translated_values[language] = getattr(translation, field_name, '') or ''
            if not source_text and not source_data and not any(translated_values.values()) and not any(translated_data.values()):
                continue
            key = f'character.{character.localization_key}.{field_name}'
            used_keys.add(key)
            source = upsert_source(
                TranslationSource,
                key,
                'character',
                source_text=source_text,
                source_data=source_data,
                content_type=character_ct,
                object_id=character.id,
                field_name=field_name,
            )
            if field_name == 'name' and source_text:
                character_name_sources[source_text] = source
            for language in LANGUAGES:
                upsert_value(
                    TranslationValue,
                    source,
                    language,
                    text=translated_values.get(language, ''),
                    data=translated_data.get(language, {}),
                )

    # Import static dictionaries first. Existing DB TermTranslation rows are applied afterwards.
    try:
        from common import language as language_module

        static_groups = []
        for source, english in language_module.UI_TRANSLATIONS.get('en', {}).items():
            static_groups.append(('ui', source, {'en': english, 'ja': language_module.UI_TRANSLATIONS.get('ja', {}).get(source, '')}))
        for source, english in language_module.GAME_TERM_TRANSLATIONS.get('en', {}).items():
            static_groups.append(('general', source, {'en': english, 'ja': language_module.GAME_TERM_TRANSLATIONS.get('ja', {}).get(source, '')}))
        for source, english in language_module.PACK_TERM_TRANSLATIONS.get('en', {}).items():
            static_groups.append(('pack', source, {'en': english, 'ja': language_module.PACK_TERM_TRANSLATIONS.get('ja', {}).get(source, '')}))
    except Exception:
        static_groups = []

    for category, source_text, translations in static_groups:
        duplicate_source = card_name_sources.get(source_text) or character_name_sources.get(source_text)
        if duplicate_source is not None:
            for language, text in translations.items():
                fill_value_if_missing(TranslationValue, duplicate_source, language, text=text)
            continue
        prefix = 'ui.' if category == 'ui' else f'term.{category}.'
        key = unique_key(prefix, translations.get('en') or source_text, used_keys, fallback=category)
        source = upsert_source(
            TranslationSource,
            key,
            category,
            source_text=source_text,
            field_name=category,
        )
        for language, text in translations.items():
            upsert_value(TranslationValue, source, language, text=text)

    term_groups = {}
    for term in TermTranslation.objects.order_by('category', 'source', 'language'):
        term_groups.setdefault((term.category, term.source), {})[term.language] = term.text

    for (category, source_text), translations in term_groups.items():
        duplicate_source = card_name_sources.get(source_text) or character_name_sources.get(source_text)
        if duplicate_source is not None:
            for language, text in translations.items():
                fill_value_if_missing(TranslationValue, duplicate_source, language, text=text)
            continue
        existing = TranslationSource.objects.filter(category=category, source_text=source_text).first()
        source = existing
        if source is None:
            key = unique_key(
                f'term.{category}.',
                translations.get('en') or source_text,
                used_keys,
                fallback=category,
            )
            source = upsert_source(
                TranslationSource,
                key,
                category,
                source_text=source_text,
                field_name=category,
            )
        for language, text in translations.items():
            upsert_value(TranslationValue, source, language, text=text)


def unseed_translation_catalog(apps, schema_editor):
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationSource.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('card', '0025_localization_keys'),
        ('common', '0004_termtranslation'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='TranslationSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=160, unique=True)),
                ('category', models.CharField(choices=[('card', 'Card'), ('character', 'Character'), ('general', 'General'), ('card_type', 'Card type'), ('position', 'Position'), ('body', 'Body'), ('special', 'Special'), ('result', 'Result'), ('tag', 'Tag'), ('ui', 'UI'), ('pack', 'Pack')], default='general', max_length=32)),
                ('source_text', models.TextField(blank=True)),
                ('source_data', models.JSONField(blank=True, default=dict)),
                ('object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('field_name', models.CharField(blank=True, max_length=60)),
                ('note', models.CharField(blank=True, max_length=200)),
                ('is_active', models.BooleanField(default=True)),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='contenttypes.contenttype')),
            ],
            options={
                'ordering': ['category', 'key'],
                'indexes': [
                    models.Index(fields=['category'], name='common_tran_categor_69d6ac_idx'),
                    models.Index(fields=['content_type', 'object_id'], name='common_tran_content_36a9e8_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='TranslationValue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(choices=[('en', 'English'), ('ja', '日本語')], max_length=5)),
                ('text', models.TextField(blank=True)),
                ('data', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('translated', 'Translated'), ('missing', 'Missing'), ('needs_review', 'Needs review')], default='translated', max_length=20)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='values', to='common.translationsource')),
            ],
            options={
                'ordering': ['source__key', 'language'],
                'constraints': [models.UniqueConstraint(fields=('source', 'language'), name='unique_translation_value_language')],
            },
        ),
        migrations.RunPython(seed_translation_catalog, unseed_translation_catalog),
    ]
