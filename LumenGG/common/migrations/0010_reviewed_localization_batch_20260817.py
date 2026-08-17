from django.core.management import call_command
from django.db import migrations

from common.localization_batches.batch_20260817 import (
    SEMANTIC_REFERENCES,
    TRANSLATIONS,
    normalize_semantic_card_tokens,
)


def seed_semantic_references(apps):
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationValue = apps.get_model('common', 'TranslationValue')
    for reference in SEMANTIC_REFERENCES.values():
        kind = reference['kind']
        source, _created = TranslationSource.objects.update_or_create(
            key=f'term.{kind}.{reference["slug"]}',
            defaults={
                'category': kind,
                'source_text': reference['ko'],
                'source_data': {},
                'field_name': kind,
                'note': f'Semantic {kind} reference; rendered with standard marks.',
                'is_active': True,
            },
        )
        for language in ('en', 'ja'):
            TranslationValue.objects.update_or_create(
                source_id=source.id,
                language=language,
                defaults={
                    'text': reference[language],
                    'data': {},
                    'status': 'translated',
                },
            )


def apply_translations(apps):
    Card = apps.get_model('card', 'Card')
    CardTranslation = apps.get_model('card', 'CardTranslation')
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationValue = apps.get_model('common', 'TranslationValue')

    sources = {
        source.key: source
        for source in TranslationSource.objects.filter(key__in=TRANSLATIONS)
    }
    for source_key, translations in TRANSLATIONS.items():
        source = sources.get(source_key)
        if source is None:
            continue
        for language, text in translations.items():
            TranslationValue.objects.update_or_create(
                source_id=source.id,
                language=language,
                defaults={
                    'text': normalize_semantic_card_tokens(text),
                    'data': {},
                    'status': 'translated',
                },
            )

    card_payload = {}
    for source_key, translations in TRANSLATIONS.items():
        parts = source_key.split('.')
        if len(parts) != 3 or parts[0] != 'card':
            continue
        _prefix, code, field_name = parts
        for language, text in translations.items():
            card_payload.setdefault((code, language), {})[field_name] = (
                normalize_semantic_card_tokens(text)
            )

    cards = {
        card.code: card
        for card in Card.objects.filter(code__in={code for code, _language in card_payload})
    }
    existing = {
        (translation.card_id, translation.language): translation
        for translation in CardTranslation.objects.filter(
            card_id__in=[card.id for card in cards.values()],
            language__in=('en', 'ja'),
        )
    }
    creates = []
    updates = []
    update_fields = set()
    for (code, language), fields in card_payload.items():
        card = cards.get(code)
        if card is None:
            continue
        translation = existing.get((card.id, language))
        if translation is None:
            translation = CardTranslation(card_id=card.id, language=language)
            creates.append(translation)
        else:
            updates.append(translation)
        for field_name, text in fields.items():
            setattr(translation, field_name, text)
            update_fields.add(field_name)
    if creates:
        CardTranslation.objects.bulk_create(creates)
    if updates and update_fields:
        CardTranslation.objects.bulk_update(updates, sorted(update_fields))


def forwards(apps, schema_editor):
    seed_semantic_references(apps)
    apply_translations(apps)
    call_command('convert_localized_references', '--apply', '--samples', '0', verbosity=0)


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0009_named_keywords_and_states'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
