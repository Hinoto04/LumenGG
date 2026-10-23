"""Finf's manually cleared, one-turn temporary HP; stored in existing session JSON."""
import copy

SHIELD_KEY = 'finf_shield'
MAX_SHIELD_DELTA = 50000


def supports_shield(character):
    if character and hasattr(character, 'trait_card_id'):
        return bool(character.trait_config.get('supports_shield'))
    return bool(character and character.name == '핀프')


def shield_amount(state):
    entry = (state or {}).get(SHIELD_KEY) or {}
    try:
        return max(0, int(entry.get('value', entry.get('count', 0))))
    except (TypeError, ValueError, OverflowError, AttributeError):
        return 0


def with_shield(state, amount):
    result = copy.deepcopy(state or {})
    result[SHIELD_KEY] = {'value': max(0, amount), 'label': '보호막'}
    return result
