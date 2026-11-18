"""Base-stat battle preview for the AI, using only role-filtered observations.

This mirrors the core of ``AutomaticGameEngine._resolve_battle_judgment``
(speed after FP, position keywords, guard/dodge/clash) but deliberately
ignores card effects, continuous rules and rule blocks. It is a heuristic for
choosing cards, never a judgment: the engine still decides every battle.
"""

import math

from .engine import _guard_result, _is_attack, _is_defense, _is_special, _special_result

DAMAGING = {'hit', 'counter'}
# FP 1점의 가치(배틀 1회 승패를 1로 볼 때). FP는 다음 배틀 속도와 캐치 기회로 이어진다.
FP_VALUE_SCALE = 6.0


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _speed(card, fp):
    return max(1.0, _number(card.get('frame'), 99.0) - _number(fp))


def preview_battle(mine, theirs, *, my_fp=0, their_fp=0):
    """Return ``(my_result, their_result)`` for two readied cards."""
    if _is_defense(mine) and _is_defense(theirs):
        return 'none', 'none'
    if _is_attack(mine) and _is_defense(theirs):
        return _attack_vs_defense(mine, theirs)
    if _is_defense(mine) and _is_attack(theirs):
        theirs_result, mine_result = _attack_vs_defense(theirs, mine)
        return mine_result, theirs_result
    if not (_is_attack(mine) and _is_attack(theirs)):
        return 'none', 'none'
    r1 = _special_result(mine, theirs.get('pos'))
    r2 = _special_result(theirs, mine.get('pos'))
    if r1 == 'dodge' and r2 == 'dodge':
        return 'dodge', 'dodge'
    if r1 == 'dodge':
        return 'counter', 'countered'
    if r2 == 'dodge':
        return 'countered', 'counter'
    reference = (_number(mine.get('frame'), 99), _number(theirs.get('frame'), 99))
    final = (_speed(mine, my_fp), _speed(theirs, their_fp))
    if final[0] == final[1]:
        return 'hit', 'hit'
    if (reference[0] > reference[1] and r1 == 'clash') or (reference[1] > reference[0] and r2 == 'clash'):
        return 'clash', 'clash'
    if final[0] < final[1]:
        return 'counter', 'countered'
    return 'countered', 'counter'


def _attack_vs_defense(attack, defense):
    result = _guard_result(defense, attack.get('pos'))
    if result == 'dodge':
        return 'opponent_dodge', 'dodge'
    if result == 'guard':
        return 'guarded', 'guard'
    if result == 'clash':
        return 'clash', 'clash'
    return 'hit', 'failed_defense'


def is_loss(mine, theirs, *, my_fp=0, their_fp=0):
    """I take damage and deal none."""
    mine_result, theirs_result = preview_battle(mine, theirs, my_fp=my_fp, their_fp=their_fp)
    return theirs_result in DAMAGING and mine_result not in DAMAGING


def answers(mine, theirs, *, my_fp=0, their_fp=0):
    """``mine`` is a usable answer to ``theirs``: it does not lose to it."""
    return not is_loss(mine, theirs, my_fp=my_fp, their_fp=their_fp)


def is_ready_candidate(card):
    """Cards a player could plausibly ready (ignores costs and effects)."""
    return (
        isinstance(card, dict)
        and not card.get('hidden')
        and not _is_special(card)
        and (_is_attack(card) or _is_defense(card))
    )


def _players(observation, role):
    players = ((observation.get('state') or {}).get('players') or {})
    rival_role = 'p2' if role == 'p1' else 'p1'
    return players.get(role) or {}, players.get(rival_role) or {}


def _zone(player, zone):
    return list(((player.get('zones') or {}).get(zone)) or [])


def _remembered(observation):
    memory = observation.get('memory') or {}
    return [
        {**card, 'hidden': False, 'remembered': True}
        for card in memory.get('rival_hand') or [] if isinstance(card, dict)
    ]


def rival_hand_view(observation, role):
    """``(known_cards, unknown_count)`` of the opponent's hand.

    Known cards are the visible ones plus those the AI remembers (``memory``
    from ``engine.observe(include_memory=True)``).
    """
    _own, rival = _players(observation, role)
    hand = [card for card in _zone(rival, 'hand') if isinstance(card, dict)]
    visible = [card for card in hand if not card.get('hidden')]
    hidden = len(hand) - len(visible)
    remembered = _remembered(observation)[:hidden]
    return visible + remembered, hidden - len(remembered)


def rival_ready_options(observation, role):
    """Cards the opponent may ready, or ``None`` when any of them is unknown.

    A face-down card already in the opponent's battle zone, or any hand card
    that is neither visible nor remembered, makes the set unknown.
    """
    _own, rival = _players(observation, role)
    battle = [card for card in _zone(rival, 'battle') if isinstance(card, dict)]
    if battle:
        options, coverage = rival_option_view(observation, role)
        return options if coverage >= 1 else None
    known, unknown = rival_hand_view(observation, role)
    if unknown:
        return None
    return [card for card in known if is_ready_candidate(card)]


def rival_option_view(observation, role):
    """``(visible_options, coverage)`` for the opponent's next Ready.

    ``coverage`` is the share of the opponent's possible cards that is
    visible: 1 when the whole hand is known, 0 when nothing is (or when a
    face-down card is already readied, since it may be any former card).
    """
    _own, rival = _players(observation, role)
    battle = [card for card in _zone(rival, 'battle') if isinstance(card, dict)]
    if battle:
        visible = [card for card in battle if not card.get('hidden')]
        if len(visible) == len(battle):
            known = [card for card in visible if is_ready_candidate(card)]
            return (known, 1.0) if known else ([], 0.0)
        # 뒷면 레디: 무엇을 냈는지는 모르고, 레디 전 손패(후보 묶음) 중 하나라는 것만 안다.
        pool = [
            {**card, 'hidden': False, 'remembered': True}
            for card in (observation.get('memory') or {}).get('rival_ready_pool') or []
        ]
        known = [card for card in pool if is_ready_candidate(card)]
        return (known, 1.0) if known else ([], 0.0)
    known, unknown = rival_hand_view(observation, role)
    visible = [card for card in known if is_ready_candidate(card)]
    if not visible:
        return [], 0.0
    return visible, len(visible) / (len(visible) + unknown)


def _fp_gain(card, result):
    field = {'hit': 'hit', 'counter': 'counter', 'guarded': 'guard', 'clash': 'hit'}.get(result)
    if not field:
        return 0.0
    text = str(card.get(field) or '').strip()
    if text.lstrip('+-').isdigit():
        return float(text)
    return 0.0


def battle_value(mine, theirs, *, my_fp=0, their_fp=0):
    """Score one predicted battle for me, about -2..+2.

    +1 when I deal damage, -1 when I take it, plus the FP swing / 6 (a guard
    against a -6 attack is worth +1) and +0.5 when my judgment starts a Combo.
    """
    mine_result, theirs_result = preview_battle(mine, theirs, my_fp=my_fp, their_fp=their_fp)
    value = 0.0
    if mine_result in DAMAGING:
        value += 1.0
        if str(mine.get(mine_result) or '') == '콤보':
            value += 0.5
    if theirs_result in DAMAGING:
        value -= 1.0
    value += (_fp_gain(mine, mine_result) - _fp_gain(theirs, theirs_result)) / FP_VALUE_SCALE
    return value


def battle_outlook(observation, role, card, *, rival_likelihood=None, temperature=2.0):
    """``(expected_value, coverage)`` of readying ``card``.

    The opponent's known options are weighted by
    ``softmax(rival_likelihood(card) / temperature)`` — how likely they are
    to ready each one — or uniformly without a likelihood. ``coverage`` is the
    known share of the opponent's hand (0 = no prediction).
    """
    options, coverage = rival_option_view(observation, role)
    if not options or not coverage or not is_ready_candidate(card):
        return 0.0, 0.0
    my_fp, their_fp = fp_values(observation, role)
    if rival_likelihood is None:
        weights = [1.0] * len(options)
    else:
        scores = [rival_likelihood(other) for other in options]
        top = max(scores)
        weights = [math.exp((score - top) / temperature) for score in scores]
    total = sum(weights)
    value = sum(
        weight * battle_value(card, other, my_fp=my_fp, their_fp=their_fp)
        for weight, other in zip(weights, options)
    ) / total
    return value, coverage


def expected_battle_value(observation, role, card, **kwargs):
    """``battle_outlook`` value scaled by coverage."""
    value, coverage = battle_outlook(observation, role, card, **kwargs)
    return value * coverage


def known_rival_threats(observation, role, *, scope='hand'):
    """Visible opponent cards to prepare answers for."""
    _own, rival = _players(observation, role)
    zones = ['battle', 'hand'] + (['list'] if scope == 'hand_and_list' else [])
    threats = []
    seen = set()
    for zone in zones:
        cards = rival_hand_view(observation, role)[0] if zone == 'hand' else _zone(rival, zone)
        for card in cards:
            key = card.get('instance_id') or id(card)
            if is_ready_candidate(card) and key not in seen:
                seen.add(key)
                threats.append(card)
    return threats


def fp_values(observation, role):
    own, rival = _players(observation, role)
    return _number(own.get('fp')), _number(rival.get('fp'))


def own_card(observation, role, instance_id):
    own, _rival = _players(observation, role)
    for cards in (own.get('zones') or {}).values():
        for card in cards or []:
            if isinstance(card, dict) and card.get('instance_id') == instance_id:
                return card
    return None


def certain_loss(observation, role, card):
    """Every card the opponent can ready beats ``card`` (base stats).

    False whenever the opponent's options are not fully visible or empty.
    """
    options = rival_ready_options(observation, role)
    if not options:
        return False
    my_fp, their_fp = fp_values(observation, role)
    return all(is_loss(card, other, my_fp=my_fp, their_fp=their_fp) for other in options)


def minimum_answer_cards(observation, role, candidates, *, scope='hand', max_size=3):
    """Smallest sets of ``candidates`` that answer every unanswered threat.

    Threats already answered by a card in the AI's hand are skipped. Returns
    ``(threats_left, covers)`` where ``covers`` lists every minimum-size set
    of candidate instance ids (empty when nothing is needed or possible).
    """
    threats = known_rival_threats(observation, role, scope=scope)
    if not threats:
        return [], []
    own, _rival = _players(observation, role)
    my_fp, their_fp = fp_values(observation, role)
    hand = [card for card in _zone(own, 'hand') if is_ready_candidate(card)]
    open_threats = [
        threat for threat in threats
        if not any(answers(card, threat, my_fp=my_fp, their_fp=their_fp) for card in hand)
    ]
    if not open_threats:
        return [], []
    answer_sets = {
        card['instance_id']: {
            index for index, threat in enumerate(open_threats)
            if answers(card, threat, my_fp=my_fp, their_fp=their_fp)
        }
        for card in candidates if card.get('instance_id')
    }
    answer_sets = {key: value for key, value in answer_sets.items() if value}
    reachable = set().union(*answer_sets.values()) if answer_sets else set()
    if not reachable:
        return open_threats, []
    keys = sorted(answer_sets)
    from itertools import combinations
    for size in range(1, max_size + 1):
        covers = [
            set(combo) for combo in combinations(keys, size)
            if set().union(*(answer_sets[key] for key in combo)) >= reachable
        ]
        if covers:
            return open_threats, covers
    # Too many threats for an exact search: greedy cover.
    chosen, covered = set(), set()
    while covered < reachable:
        best = max(keys, key=lambda key: (len(answer_sets[key] - covered), key))
        chosen.add(best)
        covered |= answer_sets[best]
    return open_threats, [chosen]
