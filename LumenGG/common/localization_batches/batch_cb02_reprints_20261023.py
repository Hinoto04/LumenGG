"""Fill empty legacy fields from the reviewed catalog for all CB02 printings.

Keep this module immutable after migration 0022 ships. Reprints retain their
original card codes; resolve pack membership through CollectionCard instead.
"""

from .batch_cb02_20261023 import TRANSLATED_FIELDS, _normalized


def restore_missing_pack_translations(apps, *, using='default'):
    Card = apps.get_model('card', 'Card')
    CardTranslation = apps.get_model('card', 'CardTranslation')
    CollectionCard = apps.get_model('collection', 'CollectionCard')
    TranslationValue = apps.get_model('common', 'TranslationValue')
    card_ids = CollectionCard.objects.using(using).filter(
        pack__code__in=('CB02', 'CB02-PR', 'CB02-CS'), card_id__isnull=False,
    ).values_list('card_id', flat=True)
    cards = list(Card.objects.using(using).filter(pk__in=card_ids))
    if not cards:
        return 0
    keys = [f'card.{card.code}.{field}' for card in cards for field in TRANSLATED_FIELDS]
    values = {
        (value.source.key, value.language): value
        for value in TranslationValue.objects.using(using).filter(
            source__key__in=keys, source__is_active=True,
            language__in=('en', 'ja'), status='translated',
        ).exclude(text='').select_related('source')
    }
    restored = 0
    for card in cards:
        for language in ('en', 'ja'):
            legacy = CardTranslation.objects.using(using).filter(card_id=card.pk, language=language).first()
            updates = {}
            for field in TRANSLATED_FIELDS:
                if legacy and (getattr(legacy, field) or '').strip():
                    continue
                value = values.get((f'card.{card.code}.{field}', language))
                if value and value.text.strip() and (
                    _normalized(value.source.source_text) == _normalized(getattr(card, field))
                ):
                    updates[field] = value.text
            if not updates:
                continue
            if legacy is None:
                CardTranslation.objects.using(using).bulk_create([
                    CardTranslation(card_id=card.pk, language=language, **updates),
                ])
            else:
                CardTranslation.objects.using(using).filter(pk=legacy.pk).update(**updates)
            restored += len(updates)
    return restored
