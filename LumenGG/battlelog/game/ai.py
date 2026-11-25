"""Deterministic policies that consume only the public engine contract."""

import hashlib
import math
import random
from dataclasses import dataclass

from .ai_decisions import decide
from .ai_hand import HandValue, hand_cards
from .ai_matrix import SCORE_PER_VALUE, choose_ready
from .ai_preview import battle_outlook, certain_loss, fp_values, minimum_answer_cards, own_card
from .ai_profile import counter_settings, hand_settings, profile_bonus, profile_weights, safety_settings


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
    'select_combo_first': 1.619503,
    'select_combo_followup': 1.629503,
    'cancel_combo_first': -0.5,
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

# Heuristic features that self-play training does not tune. Policies stored
# before a feature existed fall back to these values; deck profiles may
# override them through ``[weights]``.
HEURISTIC_WEIGHTS = {
    # Expected result of a Ready card against the opponent's known cards,
    # weighted by how likely the opponent readies each one
    # (ai_preview.battle_outlook, about -2..+2), times coverage.
    'battle_preview': 6.0,
    # How much a full prediction replaces the stat proxies (speed, damage,
    # attack/defense): proxies are scaled by 1 - preview_trust * coverage.
    'preview_trust': 0.7,
    # A catch with a card whose hit judgment is a Combo opens Combo Time
    # (8.7.2): worth far more than the catch damage when the hand holds
    # follow-up attacks (``catch_combo`` feature).
    'catch_combo': 6.0,
}
# Stat features that only stand in for "this card wins the battle".
PROXY_FEATURES = (
    'card_damage', 'card_speed', 'card_attack', 'card_defense',
    'zero_damage_attack', 'low_hp_defense', 'hp_advantage_attack',
)

AUTONOMOUS_ACTION_EXCLUSIONS = {'request_rewind', 'pause_clock', 'concede'}

# Actions that put a specific card on the table. Only these are sampled; the
# progress/system buttons (pass, resume clock, decline ...) stay argmax so the
# AI never randomly skips a phase or stalls the clock.
CARD_ACTION_TYPES = {
    'ready_card', 'select_get_card', 'select_ultimate', 'play_catch_card',
    'play_combo_card', 'play_combo_pair', 'play_combo_sequence',
    'select_combo_first', 'select_combo_followup',
}
# Shortlist: at most SHORTLIST_SIZE card actions whose score is within
# SHORTLIST_MARGIN of the best card. One of them is drawn with softmax
# weights exp((score - best) / SAMPLING_TEMPERATURE).
SHORTLIST_SIZE = 3
SHORTLIST_MARGIN = 2.5
SAMPLING_TEMPERATURE = 0.75


@dataclass(frozen=True)
class AIDecision:
    action: dict
    selections: dict
    score: float
    # How a Ready card was chosen (matrix game details), for logs/tests.
    details: dict | None = None


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


def action_features(observation, role, action, *, outlook=None):
    """Return compact numeric features without reading hidden engine state.

    ``outlook``: ``(expected_value, coverage)`` of a Ready card from
    ``ai_preview.battle_outlook``; ``score_action`` supplies it.
    """
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
    value, coverage = outlook or (0.0, 0.0)
    features = {
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
        'battle_preview': value * coverage,
    }
    if action.get('type') == 'play_catch_card':
        features['catch_combo'] = _catch_combo(observation, role, action)
    return features


def _catch_combo(observation, role, action):
    """1 when the catch card's hit judgment is a Combo and another attack in
    hand can follow it, else 0."""
    listed = action.get('card') if isinstance(action.get('card'), dict) else None
    if not listed:
        return 0.0
    card = own_card(observation, role, listed.get('instance_id')) or listed
    if str(card.get('hit') or '') != '콤보':
        return 0.0
    hand = ((((observation.get('state') or {}).get('players') or {}).get(role) or {}).get('zones') or {}).get('hand') or []
    followups = [
        other for other in hand
        if isinstance(other, dict) and other.get('instance_id') != card.get('instance_id')
        and '공격' in str(other.get('type') or '')
    ]
    return 1.0 if followups else 0.0


def score_action(observation, role, action, weights=None, profile=None):
    """Linear policy score plus the optional per-deck profile bonus.

    The profile's style, deck weights and matching situations adjust
    ``weights`` for this action before scoring.
    """
    weights = profile_weights(
        {**HEURISTIC_WEIGHTS, **(weights or DEFAULT_POLICY_WEIGHTS)},
        profile, observation, role, action,
    )
    outlook = _ready_outlook(observation, role, action, weights)
    features = action_features(observation, role, action, outlook=outlook)
    coverage = outlook[1] if outlook else 0.0
    if coverage:
        damping = 1.0 - max(0.0, min(1.0, _number(weights.get('preview_trust')))) * coverage
        for name in PROXY_FEATURES:
            features[name] *= damping
    return sum(
        _number(weights.get(name)) * value
        for name, value in features.items()
    ) + profile_bonus(observation, role, action, profile)


def _ready_outlook(observation, role, action, weights):
    """Predicted battle for a Ready card, or ``None`` for other actions."""
    if action.get('type') != 'ready_card' or not isinstance(action.get('card'), dict):
        return None
    card = own_card(observation, role, action['card'].get('instance_id')) or action['card']
    rival_role = 'p2' if role == 'p1' else 'p1'

    def rival_likelihood(rival_card):
        # 상대도 같은 점수식으로 카드를 고른다고 보고, 그 점수로 낼 확률을 매긴다.
        features = action_features(observation, rival_role, {'type': 'ready_card', 'card': rival_card})
        return sum(_number(weights.get(name)) * value for name, value in features.items())

    return battle_outlook(observation, role, card, rival_likelihood=rival_likelihood)


def _stable_tiebreak(seed, role, action):
    raw = f'{seed}:{role}:{action.get("action_id")}:{action.get("type")}'
    return hashlib.sha256(raw.encode()).hexdigest()


def _engine_default_selections(observation, action):
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


def _decision_selections(observation, action, *, role=None, profile=None):
    """Answer an effect decision: deck/default ``[[effect]]`` rules first,
    then the engine's default (see ``ai_decisions``)."""
    fallback = _engine_default_selections(observation, action)
    if action.get('type') != 'submit_decision':
        return fallback
    fallback = (
        _hand_limit_discard(observation, role, action, profile)
        or _defense_cost_payment(observation, role, action, profile)
        or fallback
    )
    return decide(observation, role, action, profile, fallback=fallback)


def _defense_cost_payment(observation, role, action, profile):
    """Pay an optional defense cost (e.g. Charging Barrier: discard a hand card of the same position).

    The engine's default declines the cost, which turns the defense into a
    failed defense: the attack hits. Paying one card is almost always cheaper,
    so pay with the card whose loss costs the hand least (``ai_hand``).
    """
    if (observation.get('pending_decision') or {}).get('kind') != 'defense_cost':
        return None
    ids = [
        str(option.get('id')) for option in action.get('options') or []
        if isinstance(option, dict) and option.get('id') not in (None, 'decline')
    ]
    count = max(1, int(action.get('minimum') or 0))
    if len(ids) < count:
        return None
    cards = [card for card in hand_cards(observation, role) if str(card.get('instance_id')) in ids]
    if len(cards) >= count:
        settings = hand_settings(profile)
        hand = HandValue(observation, role, keep=settings.get('keep') or 1)
        if hand.known:
            return {'selected': [str(card.get('instance_id')) for card in hand.best_discard(cards, count)]}
    return {'selected': ids[:count]}


def _hand_limit_discard(observation, role, action, profile):
    """Throw back the cards whose loss costs the hand least (``ai_hand``)."""
    if (observation.get('pending_decision') or {}).get('kind') != 'hand_limit_discard' or role is None:
        return None
    settings = hand_settings(profile)
    if not settings.get('enabled'):
        return None
    hand = HandValue(observation, role, keep=settings.get('keep') or 1)
    if not hand.known:
        return None
    ids = {str(option.get('id')) for option in action.get('options') or [] if isinstance(option, dict)}
    cards = [card for card in hand_cards(observation, role) if str(card.get('instance_id')) in ids]
    count = max(0, int(action.get('minimum') or 0))
    if count <= 0 or len(cards) < count:
        return None
    return {'selected': [str(card.get('instance_id')) for card in hand.best_discard(cards, count)]}


def _get_plan(observation, role, candidates, profile):
    """Hand-value bonus for each get action and, with a full hand, the pass.

    ``pass`` is the pass action when the hand is full (passing is legal) and
    no get gains ``hand.swap_margin`` hand value; ``gains`` lists each get's
    gain for logs.
    """
    plan = {'bonus': {}, 'pass': None, 'gains': {}}
    settings = hand_settings(profile)
    gets = [action for action in candidates if action.get('type') == 'select_get_card']
    if not settings.get('enabled') or not gets:
        return plan
    hand = HandValue(observation, role, keep=settings.get('keep') or 1)
    pass_action = next((action for action in candidates if action.get('type') == 'pass_phase'), None)
    full = pass_action is not None
    if not hand.known:
        # 상대 카드를 하나도 모르면 교체가 나은지 판단할 수 없다: 가득 찬 패는 그대로 둔다.
        plan['pass'] = pass_action
        return plan
    cards = hand_cards(observation, role)
    bonus = _number(settings.get('bonus'))
    for action in gets:
        card = _full_card(observation, role, action)
        if not card:
            continue
        gain = hand.get_gain(cards, card, full=full)
        plan['gains'][(card.get('code') or card.get('instance_id'))] = round(gain, 3)
        plan['bonus'][action.get('action_id')] = bonus * gain
    if full and max(plan['gains'].values(), default=0.0) < _number(settings.get('swap_margin')):
        plan['pass'] = pass_action
    return plan


def choose_action(
    observation,
    role,
    *,
    weights=None,
    seed='ai',
    top_k=None,
    margin=None,
    temperature=None,
    profile=None,
    ready_strategy='matrix',
    ready_evaluator=None,
):
    """Choose one legal action from a role-filtered observation.

    Non-card actions are picked greedily. When the best action plays a card,
    the AI shortlists the few strongest card actions and draws one with
    score-weighted randomness so it does not repeat the same line every game.
    ``temperature=0`` restores the fully greedy choice. ``profile`` is a
    normalized AI deck profile (``ai_profile.normalize_profile``).

    Ready cards are chosen as a matrix game against the opponent's known
    cards (``ai_matrix``) when ``ready_strategy='matrix'`` and something of
    their hand is known; ``ready_evaluator(action, rival_card)`` fills the
    cells by engine simulation (``ai_engine_eval``) instead of base stats.

    Before scoring, Ready cards that lose to every card the opponent can
    ready (base stats, all visible) are dropped when another Ready card is
    left, and List cards forming a minimum answer to the opponent's visible
    cards earn the counter bonus (``ai_preview``).
    """
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
    candidates = _drop_certain_losses(observation, role, candidates, profile)
    counter_bonus = _counter_bonus(observation, role, candidates, profile)
    get_plan = _get_plan(observation, role, candidates, profile)
    ranked = sorted(
        (
            (
                score_action(observation, role, action, weights, profile)
                + counter_bonus.get(action.get('action_id'), 0.0)
                + get_plan['bonus'].get(action.get('action_id'), 0.0),
                action,
            )
            for action in candidates
        ),
        key=lambda item: (item[0], _stable_tiebreak(seed, role, item[1])),
        reverse=True,
    )
    score, action = ranked[0]
    if (
        get_plan['pass'] is not None and action.get('type') == 'select_get_card'
        # 상대 위협에 대처할 카드(대처·가드 가산)는 패 가치가 덜 오르더라도 넘기지 않고 가져온다.
        and not counter_bonus.get(action.get('action_id'))
    ):
        # 패가 가득 찼는데 어떤 교체도 패를 낫게 하지 못한다: 가져왔다 되돌려 놓는 대신 넘긴다.
        pass_action = get_plan['pass']
        return AIDecision(
            action=pass_action, selections={},
            score=score_action(observation, role, pass_action, weights, profile),
            details={'get_gains': get_plan['gains']},
        )
    details = None
    matrix_choice = None
    if action.get('type') == 'ready_card' and ready_strategy == 'matrix':
        row_bonus = {
            item.get('action_id'): profile_bonus(observation, role, item, profile) / SCORE_PER_VALUE
            for _score, item in ranked if item.get('type') == 'ready_card'
        } if profile else None
        matrix_choice = choose_ready(
            observation, role, ranked, seed=seed, temperature=temperature,
            evaluator=ready_evaluator, row_bonus=row_bonus,
        )
    if matrix_choice is not None:
        score, action, details = matrix_choice
    elif action.get('type') in CARD_ACTION_TYPES:
        score, action = _sample_card_action(
            ranked,
            seed=seed,
            role=role,
            top_k=SHORTLIST_SIZE if top_k is None else top_k,
            margin=SHORTLIST_MARGIN if margin is None else margin,
            temperature=SAMPLING_TEMPERATURE if temperature is None else temperature,
        )
    return AIDecision(
        action=action,
        selections=_decision_selections(observation, action, role=role, profile=profile),
        score=score,
        details=details,
    )


def _full_card(observation, role, action):
    card = action.get('card') if isinstance(action.get('card'), dict) else None
    if not card:
        return None
    return own_card(observation, role, card.get('instance_id')) or card


def _drop_certain_losses(observation, role, candidates, profile):
    if not safety_settings(profile).get('avoid_certain_loss'):
        return candidates
    ready = [action for action in candidates if action.get('type') == 'ready_card']
    losing = {
        id(action) for action in ready
        if certain_loss(observation, role, _full_card(observation, role, action) or {})
    }
    if not losing or len(losing) == len(ready):
        return candidates
    return [action for action in candidates if id(action) not in losing]


def counter_targets(observation, role, candidates, profile=None):
    """Instance ids of List cards in any minimum answer set (see ai_preview)."""
    settings = counter_settings(profile)
    if not settings.get('enabled'):
        return set()
    gets = [action for action in candidates if action.get('type') == 'select_get_card']
    if not gets:
        return set()
    cards = [card for card in (_full_card(observation, role, action) for action in gets) if card]
    _threats, covers = minimum_answer_cards(
        observation, role, cards, scope=settings.get('scope') or 'hand',
    )
    return set().union(*covers) if covers else set()


def guard_targets(observation, role, candidates, profile=None):
    """List cards in a minimum answer set to threats under the opponent's FP lead.

    Only while the opponent leads in FP (the frame advantage carries into the
    next Ready): threats are judged as if they led by at least
    ``counter.guard_fp`` FP, and the cards to fetch are those that answer what
    the hand cannot (a guard that covers their low or unguardable attacks).
    When the AI is even or ahead, fetching guards only thins its attacks.
    """
    settings = counter_settings(profile)
    if not settings.get('enabled') or not _number(settings.get('guard_bonus')):
        return set()
    my_fp, their_fp = fp_values(observation, role)
    if their_fp <= my_fp:
        return set()
    gets = [action for action in candidates if action.get('type') == 'select_get_card']
    if not gets:
        return set()
    cards = [card for card in (_full_card(observation, role, action) for action in gets) if card]
    _threats, covers = minimum_answer_cards(
        observation, role, cards, scope=settings.get('scope') or 'hand',
        rival_fp_lead=max(their_fp - my_fp, _number(settings.get('guard_fp'))),
    )
    return set().union(*covers) if covers else set()


def _counter_bonus(observation, role, candidates, profile):
    settings = counter_settings(profile)
    bonuses = {}
    for targets, bonus in (
        (counter_targets(observation, role, candidates, profile), _number(settings.get('bonus'))),
        (guard_targets(observation, role, candidates, profile), _number(settings.get('guard_bonus'))),
    ):
        for action in candidates:
            instance_id = (action.get('card') or {}).get('instance_id')
            if action.get('type') == 'select_get_card' and instance_id in targets:
                key = action.get('action_id')
                bonuses[key] = max(bonuses.get(key, 0.0), bonus)
    return bonuses


def card_shortlist(ranked, *, top_k=SHORTLIST_SIZE, margin=SHORTLIST_MARGIN):
    """Return the strongest card actions from a (score, action) ranking."""
    cards = [item for item in ranked if item[1].get('type') in CARD_ACTION_TYPES]
    if not cards:
        return []
    best = cards[0][0]
    return [item for item in cards if item[0] >= best - margin][:max(1, int(top_k))]


def shortlist_weights(shortlist, *, temperature=SAMPLING_TEMPERATURE):
    """Softmax probabilities for a shortlist, highest score first."""
    if not shortlist:
        return []
    if temperature <= 0:
        return [1.0] + [0.0] * (len(shortlist) - 1)
    best = shortlist[0][0]
    raw = [math.exp((score - best) / temperature) for score, _action in shortlist]
    total = sum(raw)
    return [value / total for value in raw]


def _sample_card_action(ranked, *, seed, role, top_k, margin, temperature):
    shortlist = card_shortlist(ranked, top_k=top_k, margin=margin)
    if len(shortlist) <= 1:
        return shortlist[0] if shortlist else ranked[0]
    probabilities = shortlist_weights(shortlist, temperature=temperature)
    # Seeded per decision point: replays of the same seed are reproducible,
    # while each session/version draws independently.
    key = ':'.join(
        [str(seed), role, *sorted(str(item[1].get('action_id')) for item in shortlist)]
    )
    rng = random.Random(hashlib.sha256(key.encode()).hexdigest())
    return rng.choices(shortlist, weights=probabilities, k=1)[0]
