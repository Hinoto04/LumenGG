"""How the AI answers effect decisions (optional effects, passives, choices).

Rules come from the AI deck profile (``[[effect]]``) first and then from the
built-in defaults in ``ai_effect_defaults.toml``. The first rule whose source
(ability id / card code / decision kind) and ``when`` conditions match decides
the aspect it sets (use, choose, pick/avoid/count, amount). Anything left
open falls back to the engine's default answer.
"""

import tomllib
from pathlib import Path

from .ai_profile import condition_matches, normalize_profile

DEFAULTS_PATH = Path(__file__).with_name('ai_effect_defaults.toml')


def _load_defaults():
    raw = tomllib.loads(DEFAULTS_PATH.read_text(encoding='utf-8'))
    return normalize_profile(raw)['effects']


DEFAULT_EFFECT_RULES = _load_defaults()

# 효과로 콤보 타임을 열거나(start_combo) 캐치를 주는(grant_catch) 카드. 관찰에는 카드 효과 정의가 없어
# 엔진을 가진 호출부가 룰셋에서 뽑아 observation['effect_combo_codes']로 넘긴다(rival_combo_threat 조건).
EFFECT_COMBO_OPS = ('start_combo', 'grant_catch')
_effect_code_cache = {}


def _effect_ops(node, found, speeds):
    if isinstance(node, dict):
        if node.get('op') in EFFECT_COMBO_OPS:
            found.add(node['op'])
            if node['op'] == 'grant_catch':
                try:
                    speeds.append(float(node.get('max_speed')))
                except (TypeError, ValueError):
                    speeds.append(99.0)
        for value in node.values():
            _effect_ops(value, found, speeds)
    elif isinstance(node, list):
        for value in node:
            _effect_ops(value, found, speeds)


def effect_combo_codes(ruleset):
    """``{'start_combo': [codes], 'grant_catch': [codes], 'catch_speed': {code: max_speed}}`` (cached per ruleset).

    ``catch_speed`` is the fastest speed limit among a card's granted Catches (99 when unlimited).
    """
    cards = (ruleset or {}).get('cards') or {}
    key = (id(cards), (ruleset or {}).get('version'), len(cards))
    cached = _effect_code_cache.get(key)
    if cached is None:
        cached = {**{op: [] for op in EFFECT_COMBO_OPS}, 'catch_speed': {}}
        for code, card in sorted(cards.items()):
            found, speeds = set(), []
            _effect_ops((card or {}).get('effect_definition'), found, speeds)
            for op in found:
                cached[op].append(code)
            if speeds:
                cached['catch_speed'][code] = max(speeds)
        if len(_effect_code_cache) > 8:
            _effect_code_cache.clear()
        _effect_code_cache[key] = cached
    return cached


def annotate_effect_codes(observation, ruleset):
    """Attach ``effect_combo_codes`` to an observation built from an engine with ``ruleset``."""
    observation['effect_combo_codes'] = effect_combo_codes(ruleset)
    return observation


def _rule_matches(rule, decision, observation, role, action):
    source = decision.get('source') or {}
    kind = decision.get('kind')
    if rule.get('ability') and source.get('ability_id') not in rule['ability']:
        return False
    if rule.get('card') and source.get('card_code') not in rule['card']:
        return False
    if rule.get('decision') and kind not in rule['decision']:
        return False
    return condition_matches(rule.get('when'), observation, role, action)


def matching_rules(observation, role, action, profile=None):
    decision = observation.get('pending_decision') or {}
    rules = [*((profile or {}).get('effects') or []), *DEFAULT_EFFECT_RULES]
    return [rule for rule in rules if _rule_matches(rule, decision, observation, role, action)]


def _first(rules, key):
    return next((rule for rule in rules if key in rule), None)


def _option_codes(observation, role, options):
    """Card code for each option id that names a visible card."""
    players = ((observation.get('state') or {}).get('players') or {})
    cards = {}
    for player in players.values():
        for zone_cards in (player.get('zones') or {}).values():
            for card in zone_cards or []:
                if isinstance(card, dict) and card.get('instance_id') and not card.get('hidden'):
                    cards[card['instance_id']] = card
    codes = {}
    for option in options:
        card = cards.get(option.get('id')) or cards.get(option.get('card_instance_id'))
        code = (card or {}).get('code') or option.get('code') or option.get('card_code')
        if code:
            codes[str(option.get('id'))] = str(code)
    return codes


def _count(value, minimum, maximum, fallback):
    if value == 'max':
        return maximum
    if value == 'min':
        return minimum
    if isinstance(value, int):
        return max(minimum, min(maximum, value))
    return fallback


def decide(observation, role, action, profile=None, fallback=None):
    """Selections for a ``submit_decision`` action, or ``fallback``."""
    decision = observation.get('pending_decision') or {}
    options = [
        option for option in action.get('options') or []
        if isinstance(option, dict) and option.get('id') is not None
    ]
    ids = [str(option.get('id')) for option in options]
    minimum = max(0, int(action.get('minimum') or 0))
    maximum = max(minimum, int(action.get('maximum') or minimum))
    kind = decision.get('kind')
    rules = matching_rules(observation, role, action, profile)

    use_rule = _first(rules, 'use')
    if kind == 'optional_effect':
        if use_rule is not None:
            accept = use_rule['use']
        else:
            accept = ((profile or {}).get('effect_settings') or {}).get('default_use', True)
        choice = 'accept' if accept else 'decline'
        if choice in ids:
            return {'selected': [choice]}
        return fallback
    if use_rule is not None and use_rule['use'] is False:
        if minimum == 0:
            return {'selected': []}
        if 'decline' in ids:
            # 선택형 비용(수비 비용 등)은 "decline" 선택지로 거절한다.
            return {'selected': ['decline']}

    if kind == 'effect_amount':
        amount_rule = _first(rules, 'amount')
        if amount_rule is not None and ids:
            numbers = sorted(ids, key=lambda value: float(value))
            value = amount_rule['amount']
            if value == 'max':
                return {'selected': [numbers[-1]]}
            if value == 'min':
                return {'selected': [numbers[0]]}
            closest = min(numbers, key=lambda item: abs(float(item) - value))
            return {'selected': [closest]}
        return fallback

    choose_rule = _first(rules, 'choose')
    if choose_rule is not None:
        for preferred in choose_rule['choose']:
            if preferred in ids:
                return {'selected': [preferred][:max(1, maximum)]}

    pick_rule = _first(rules, 'pick')
    avoid_rule = _first(rules, 'avoid')
    count_rule = _first(rules, 'count')
    if pick_rule is None and avoid_rule is None and count_rule is None:
        return fallback
    codes = _option_codes(observation, role, options)
    pick = (pick_rule or {}).get('pick') or []
    avoid = set((avoid_rule or {}).get('avoid') or [])
    fallback_ids = list((fallback or {}).get('selected') or [])

    def rank(option_id):
        code = codes.get(option_id)
        if code in pick:
            return (0, pick.index(code), option_id)
        if code in avoid:
            return (2, 0, option_id)
        return (1, 0 if option_id in fallback_ids else 1, option_id)

    ordered = sorted(ids, key=rank)
    count = _count((count_rule or {}).get('count'), minimum, maximum, max(minimum, len(fallback_ids)))
    count = max(minimum, min(maximum, count))
    if count_rule is None and pick_rule is not None:
        # 가져올 카드를 정했다면 그 카드들은 최대 장수 안에서 모두 고른다.
        wanted = sum(1 for option_id in ids if codes.get(option_id) in pick)
        count = max(count, min(maximum, wanted))
    return {'selected': ordered[:count]}
