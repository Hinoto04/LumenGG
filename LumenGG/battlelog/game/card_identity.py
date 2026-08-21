"""Card identity rules shared by manual and automatic simulators."""


PASSIVE_CARD_TYPE = '특성'


def is_passive_card_code(code):
    """Return whether a printed card code identifies a Passive/Trait card.

    Current catalog codes use both ``DFR-PS-001`` and legacy forms such as
    ``ST1-PS1``.  The printed ``PS`` marker is authoritative even if an old
    database row or ruleset snapshot has an incorrect ``type`` value.
    """
    return 'PS' in str(code or '').upper()


def is_passive_card(card):
    if not card:
        return False
    getter = card.get if isinstance(card, dict) else lambda key, default=None: getattr(card, key, default)
    return (
        is_passive_card_code(getter('code', ''))
        or str(getter('type', '') or '') == PASSIVE_CARD_TYPE
    )


def normalize_passive_card(card):
    """Apply the public, face-up Passive-zone representation in place."""
    if not isinstance(card, dict) or not is_passive_card(card):
        return card
    card['type'] = PASSIVE_CARD_TYPE
    card['face_up'] = True
    card['hidden'] = False
    return card
