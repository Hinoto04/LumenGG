"""Deterministic policies that consume only the public engine contract."""

import hashlib
from dataclasses import dataclass


DEFAULT_POLICY_VERSION = 'linear-selfplay-v1.4.0'
DEFAULT_POLICY_WEIGHTS = {
    'bias': 0.0,
    'pass_phase': 0.025854,
    'ready_card': 1.253191,
    'declare_no_response': 0.2,
    'select_get_card': 1.574042,
    'select_ultimate': 2.140599,
    'submit_decision': 0.790517,
    'play_combo_card': 1.599315,
    'play_combo_pair': 1.619503,
    'play_combo_sequence': 1.629503,
    'end_combo': -0.385528,
    'play_catch_card': 1.765078,
    'decline_catch': -0.135896,
    'resume_clock': 5.0,
    'answer_rewind': 0.0,
    'request_rewind': -50.0,
    'pause_clock': -50.0,
    'concede': -1000.0,
    'card_damage': 0.212984,
    'card_speed': 1.106311,
    'card_attack': 1.09275,
    'card_defense': 0.210831,
    'zero_damage_attack': -12.0,
    'low_hp_defense': 1.005251,
    'hp_advantage_attack': 0.318104,
}

AUTONOMOUS_ACTION_EXCLUSIONS = {'request_rewind', 'pause_clock', 'concede'}


@dataclass(frozen=True)
class AIDecision:
    action: dict
    selections: dict
    score: float


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _cards(action):
    values = []
    if isinstance(action.get('card'), dict):
        values.append(action['card'])
    values.extend(item for item in action.get('cards') or [] if isinstance(item, dict))
    return values


def action_features(observation, role, action):
    """Return compact numeric features without reading hidden engine state."""
    state = observation.get('state') or {}
    players = state.get('players') or {}
    own = players.get(role) or {}
    opponent_role = 'p2' if role == 'p1' else 'p1'
    rival = players.get(opponent_role) or {}
    own_hp = _number(own.get('hp'))
    rival_hp = _number(rival.get('hp'))
    cards = _cards(action)
    damage = max((_number(card.get('damage')) for card in cards), default=0.0)
    frames = [_number(card.get('frame'), 20.0) for card in cards if card.get('frame') is not None]
    speed = max(0.0, 12.0 - min(frames, default=12.0))
    card_types = {str(card.get('type') or '') for card in cards}
    return {
        'bias': 1.0,
        str(action.get('type') or ''): 1.0,
        'card_damage': damage / 100.0,
        'card_speed': speed,
        'card_attack': 1.0 if any('공격' in value for value in card_types) else 0.0,
        'card_defense': 1.0 if any('수비' in value for value in card_types) else 0.0,
        'zero_damage_attack': (
            1.0
            if any('공격' in value for value in card_types) and damage <= 0
            else 0.0
        ),
        'low_hp_defense': (
            1.0 if own_hp > 0 and own_hp <= 1500 and any('수비' in value for value in card_types) else 0.0
        ),
        'hp_advantage_attack': (
            max(-1.0, min(1.0, (own_hp - rival_hp) / 5000.0))
            if any('공격' in value for value in card_types) else 0.0
        ),
    }


def score_action(observation, role, action, weights=None):
    weights = weights or DEFAULT_POLICY_WEIGHTS
    return sum(
        _number(weights.get(name)) * value
        for name, value in action_features(observation, role, action).items()
    )


def _stable_tiebreak(seed, role, action):
    raw = f'{seed}:{role}:{action.get("action_id")}:{action.get("type")}'
    return hashlib.sha256(raw.encode()).hexdigest()


def _decision_selections(observation, action):
    if action.get('type') != 'submit_decision':
        return {}
    options = [
        str(option.get('id'))
        for option in action.get('options') or []
        if isinstance(option, dict) and option.get('id') is not None
    ]
    minimum = max(0, int(action.get('minimum') or 0))
    maximum = max(minimum, int(action.get('maximum') or minimum))
    pending = observation.get('pending_decision') or {}
    defaults = [str(value) for value in pending.get('default') or [] if str(value) in options]
    if len(defaults) >= minimum:
        return {'selected': defaults[:maximum]}
    preferred = [value for value in options if value != 'decline']
    if len(preferred) < minimum:
        preferred = options
    return {'selected': preferred[:minimum]}


def choose_action(observation, role, *, weights=None, seed='ai'):
    """Choose one legal action from a role-filtered observation."""
    legal = list(observation.get('legal_actions') or [])
    if not legal:
        return None
    candidates = [
        action for action in legal
        if action.get('type') not in AUTONOMOUS_ACTION_EXCLUSIONS
    ]
    if not candidates:
        return None
    # AI never accepts a rewind of another player's action. This also keeps
    # autonomous matches from oscillating around the rewind protocol.
    rewind_decline = [
        action for action in candidates
        if action.get('type') == 'answer_rewind'
        and not bool((action.get('payload') or {}).get('accept'))
    ]
    if rewind_decline:
        candidates = rewind_decline
    ranked = sorted(
        candidates,
        key=lambda action: (
            score_action(observation, role, action, weights),
            _stable_tiebreak(seed, role, action),
        ),
        reverse=True,
    )
    action = ranked[0]
    return AIDecision(
        action=action,
        selections=_decision_selections(observation, action),
        score=score_action(observation, role, action, weights),
    )
