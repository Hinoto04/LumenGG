"""Finf's manually cleared, one-turn temporary HP; stored in existing session JSON."""
import copy

SHIELD_KEY = 'finf_shield'
MAX_SHIELD_DELTA = 50000


def shield_enabled(character):
    """보호막 조작은 캐릭터가 정해진 모든 플레이어가 쓸 수 있다."""
    return bool(character)


def supports_shield(character):
    """패시브로 보호막을 쓰는 특성(핀프 등). 처음 상태에 보호막 0을 넣고 앱·웹에서 보호막 줄을 우선한다."""
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
