from django.db.models import F

from collection.models import CollectionCard


def _normalize_card_id_list(card_ids):
    normalized = []
    for card_id in card_ids:
        if not card_id:
            continue
        try:
            normalized.append(int(card_id))
        except (TypeError, ValueError):
            continue
    return list(dict.fromkeys(normalized))


def _version_from_collection_card(collection_card):
    if collection_card and collection_card.pack and collection_card.pack.code:
        return collection_card.pack.code
    return 'N/A'


def get_deck_version_from_card_ids(card_ids):
    card_ids = _normalize_card_id_list(card_ids)
    if not card_ids:
        return 'N/A'

    base_query = CollectionCard.objects.filter(
        card_id__in=card_ids,
        pack__isnull=False,
        pack__released__isnull=False,
    ).select_related('pack')

    latest_original_print = base_query.filter(
        code=F('card__code')
    ).order_by(
        '-pack__released',
        '-pack_id',
        '-id',
    ).first()

    if latest_original_print:
        return _version_from_collection_card(latest_original_print)

    latest_available_print = base_query.order_by(
        '-pack__released',
        '-pack_id',
        '-id',
    ).first()
    return _version_from_collection_card(latest_available_print)


def get_deck_version_from_entries(deck_entries):
    return get_deck_version_from_card_ids(card_id for card_id, *_ in deck_entries)


def get_deck_version_from_cards(cards):
    return get_deck_version_from_card_ids(card.id for card in cards)
