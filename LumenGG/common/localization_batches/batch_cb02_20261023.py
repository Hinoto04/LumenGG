"""CB02 source texts and English/Japanese translations captured on 2026-10-23.

Keep this module and its JSON immutable after migration 0021 ships. The source
snapshots also exercise the effect compiler independently of the live database.
Only missing translations of unchanged source fields are restored.
"""

import json
from pathlib import Path


CARDS = json.loads(Path(__file__).with_name('cb02_20261023.json').read_text(encoding='utf-8'))
TRANSLATED_FIELDS = ('name', 'ruby', 'text', 'detail_text', 'keyword', 'hiddenKeyword', 'search')


def _normalized(text):
    return (text or '').replace('\r\n', '\n').strip()


def restore_missing_translations(apps, *, using='default'):
    """Restore both translation stores without replacing existing editorial work."""
    Card = apps.get_model('card', 'Card')
    CardTranslation = apps.get_model('card', 'CardTranslation')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationValue = apps.get_model('common', 'TranslationValue')
    cards = {
        card.code: card
        for card in Card.objects.using(using).filter(
            code__in=[row['snapshot']['code'] for row in CARDS],
        )
    }
    restored = 0
    if not cards:
        return restored
    content_type, _ = ContentType.objects.using(using).get_or_create(app_label='card', model='card')
    for row in CARDS:
        snapshot = row['snapshot']
        card = cards.get(snapshot['code'])
        if card is None:
            continue
        for language, fields in row['translations'].items():
            legacy = CardTranslation.objects.using(using).filter(
                card_id=card.pk, language=language,
            ).first()
            if legacy is None:
                legacy = CardTranslation(card_id=card.pk, language=language)
                CardTranslation.objects.using(using).bulk_create([legacy])
            legacy_updates = {}
            for field in TRANSLATED_FIELDS:
                original = getattr(card, field) or ''
                text = fields[field]
                if not text or _normalized(original) != _normalized(snapshot[field]):
                    continue
                source, _ = TranslationSource.objects.using(using).get_or_create(
                    key=f'card.{card.code}.{field}',
                    defaults={
                        'category': 'card', 'source_text': original,
                        'content_type_id': content_type.pk, 'object_id': card.pk,
                        'field_name': field, 'is_active': True,
                    },
                )
                # A catalog source can have newer text than the legacy Card row.
                if not source.is_active or _normalized(source.source_text) != _normalized(original):
                    continue
                value, _ = TranslationValue.objects.using(using).get_or_create(
                    source_id=source.pk, language=language,
                    defaults={'status': 'missing'},
                )
                missing_value = not value.text.strip() or value.status == 'missing'
                if missing_value:
                    legacy_text = getattr(legacy, field) or ''
                    value.text = (
                        legacy_text if legacy_text.strip()
                        and _normalized(legacy_text) != _normalized(original) else text
                    )
                    value.data = {}
                    value.status = 'translated'
                    value.save(using=using, update_fields=['text', 'data', 'status', 'updated_at'])
                    restored += 1
                legacy_text = getattr(legacy, field) or ''
                if value.text != legacy_text and (
                    not legacy_text.strip() or _normalized(legacy_text) == _normalized(original)
                ):
                    legacy_updates[field] = value.text
                    if not missing_value:
                        restored += 1
            if legacy_updates:
                # QuerySet.update avoids post_save copying other stale legacy
                # fields over translations edited directly in the catalog.
                CardTranslation.objects.using(using).filter(pk=legacy.pk).update(**legacy_updates)
    return restored
