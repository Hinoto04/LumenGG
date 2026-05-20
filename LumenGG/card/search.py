from common.text_search import search_contains, search_equals


BASE_CARD_SEARCH_FIELDS = ('code', 'name', 'ruby')
CARD_KEYWORD_SEARCH_FIELDS = ('keyword', 'hiddenKeyword', 'search')
CARD_TRANSLATION_SEARCH_FIELDS = ('name', 'ruby', 'keyword', 'hiddenKeyword', 'search')


def _card_translations(card):
    try:
        return card.translations.all()
    except Exception:
        return []


def card_search_values(card, include_keywords=True):
    values = [getattr(card, field, '') for field in BASE_CARD_SEARCH_FIELDS]
    if include_keywords:
        values.extend(getattr(card, field, '') for field in CARD_KEYWORD_SEARCH_FIELDS)

    for translation in _card_translations(card):
        for field in CARD_TRANSLATION_SEARCH_FIELDS:
            if include_keywords or field not in CARD_KEYWORD_SEARCH_FIELDS:
                values.append(getattr(translation, field, ''))
    return values


def card_matches_search(card, query, include_keywords=True):
    return search_contains(query, card_search_values(card, include_keywords=include_keywords))


def card_matches_search_exact(card, query, include_keywords=False):
    return search_equals(query, card_search_values(card, include_keywords=include_keywords))
