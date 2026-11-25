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

# 카드 효과 정의에서 뽑는 AI 힌트. 관찰에는 효과 정의가 없어 엔진을 가진 호출부가 룰셋에서 뽑아
# observation['effect_combo_codes']로 넘긴다.
#   start_combo / grant_catch: 효과로 콤보 타임을 열거나 캐치를 주는 카드(rival_combo_threat, 효과 캐치)
#   catch_speed: 효과 캐치의 속도 상한
#   speed_boost: 효과로 자기 속도를 가장 많이 빠르게 하는 값(음수, 조건은 보지 않음. 예: 페인 프리즌 -8)
#   play_counter: 이 카운터가 1개 이상 있어야 쓸 수 있는 카드(예: 페인 프리즌 → hidden_bond 「은연」)
#   defense_costs: 비용을 치러야 하는 수비 판정 [{judgment, where}] (예: 차징 배리어 상쇄)
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


def _speed_boost(node):
    """Most negative own-speed change (``modify_stat`` frame/speed for the controller) in a definition."""
    best = 0.0
    if isinstance(node, dict):
        if (
            node.get('op') == 'modify_stat' and node.get('stat') in ('frame', 'speed')
            and (node.get('player') in (None, {'controller': True}))
        ):
            try:
                best = min(best, float(node.get('amount')))
            except (TypeError, ValueError):
                pass
        for value in node.values():
            best = min(best, _speed_boost(value))
    elif isinstance(node, list):
        for value in node:
            best = min(best, _speed_boost(value))
    return best


def effect_combo_codes(ruleset):
    """AI hints from a ruleset's effect definitions (cached per ruleset); see the comment above.

    ``{'start_combo': [codes], 'grant_catch': [codes], 'catch_speed': {code: max_speed},
    'speed_boost': {code: frames}, 'play_counter': {code: counter}, 'defense_costs': {code: [rules]}}``
    """
    cards = (ruleset or {}).get('cards') or {}
    key = (id(cards), (ruleset or {}).get('version'), len(cards))
    cached = _effect_code_cache.get(key)
    if cached is None:
        cached = {
            **{op: [] for op in EFFECT_COMBO_OPS},
            'catch_speed': {}, 'speed_boost': {}, 'play_counter': {}, 'defense_costs': {},
        }
        for code, card in sorted(cards.items()):
            definition = (card or {}).get('effect_definition') or {}
            found, speeds = set(), []
            _effect_ops(definition, found, speeds)
            for op in found:
                cached[op].append(code)
            if speeds:
                cached['catch_speed'][code] = max(speeds)
            boost = _speed_boost(definition.get('abilities'))
            if boost < 0:
                cached['speed_boost'][code] = boost
            condition = definition.get('play_condition') if isinstance(definition, dict) else None
            if isinstance(condition, dict) and condition.get('op') == 'counter_at_least' and condition.get('counter'):
                cached['play_counter'][code] = str(condition['counter'])
            costs = [
                {'judgment': rule.get('judgment'), 'where': ((rule.get('cost') or {}).get('selector') or {}).get('where') or {}}
                for rule in (definition.get('defense_rules') or []) if isinstance(rule, dict) and rule.get('cost')
            ]
            if costs:
                cached['defense_costs'][code] = costs
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
