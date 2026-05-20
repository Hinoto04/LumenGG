import unicodedata


def normalize_search_text(value):
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    return ''.join(character for character in text if character.isalnum())


def search_contains(query, values):
    needle = normalize_search_text(query)
    if not needle:
        return False
    return any(needle in normalize_search_text(value) for value in values)


def search_equals(query, values):
    needle = normalize_search_text(query)
    if not needle:
        return False
    return any(needle == normalize_search_text(value) for value in values)
