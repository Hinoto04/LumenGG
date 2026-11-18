"""Ready selection as a two-player zero-sum matrix game.

Rows are the AI's Ready candidates, columns the cards the opponent may ready
(visible, remembered or deduced — see ``ai_preview.rival_option_view``). A
cell is the predicted result for the AI: ``ai_preview.battle_value`` from
base stats, or an engine simulation when an evaluator is supplied
(``ai_engine_eval``). The AI then plays the equilibrium mixed strategy,
blended with the policy ranking by how much of the opponent's hand is known.
Mixing keeps the whole deck in use and makes the AI hard to read.
"""

import hashlib
import math
import random

from .ai_preview import battle_value, fp_values, is_ready_candidate, own_card, rival_option_view

# Profile/score bonuses are in policy score units; one battle result is
# about ``SCORE_PER_VALUE`` of those (``HEURISTIC_WEIGHTS['battle_preview']``).
SCORE_PER_VALUE = 6.0
POLICY_TEMPERATURE = 0.75
ITERATIONS = 400


def solve_zero_sum(matrix, iterations=ITERATIONS):
    """Row player's equilibrium strategy by fictitious play (rows maximize)."""
    rows, cols = len(matrix), len(matrix[0])
    row_counts = [0] * rows
    row_payoff = [0.0] * rows
    col_payoff = [0.0] * cols
    i = max(range(rows), key=lambda r: min(matrix[r]))
    for _ in range(iterations):
        row_counts[i] += 1
        for j in range(cols):
            col_payoff[j] += matrix[i][j]
        j = min(range(cols), key=lambda c: (col_payoff[c], c))
        for r in range(rows):
            row_payoff[r] += matrix[r][j]
        i = max(range(rows), key=lambda r: (row_payoff[r], -r))
    total = float(sum(row_counts))
    return [count / total for count in row_counts]


def _softmax(scores, temperature):
    if not scores:
        return []
    if temperature <= 0:
        best = max(scores)
        hits = [1.0 if score == best else 0.0 for score in scores]
        return [hit / sum(hits) for hit in hits]
    top = max(scores)
    raw = [math.exp((score - top) / temperature) for score in scores]
    total = sum(raw)
    return [value / total for value in raw]


def ready_matrix(observation, role, ready_actions, *, evaluator=None, row_bonus=None):
    """``(matrix, options, coverage)`` or ``None`` when nothing is known."""
    options, coverage = rival_option_view(observation, role)
    if not options or not coverage:
        return None
    my_fp, their_fp = fp_values(observation, role)
    matrix = []
    for action in ready_actions:
        card = own_card(observation, role, (action.get('card') or {}).get('instance_id')) or action.get('card') or {}
        bonus = (row_bonus or {}).get(action.get('action_id'), 0.0)
        row = []
        for other in options:
            value = evaluator(action, other) if evaluator else None
            if value is None:
                value = (
                    battle_value(card, other, my_fp=my_fp, their_fp=their_fp)
                    if is_ready_candidate(card) else -2.0
                )
            row.append(value + bonus)
        matrix.append(row)
    refine = getattr(evaluator, 'refine', None)
    if refine is not None:
        # 수치표 평가: 상대가 굳이 낼 이유가 없는 카드(다른 카드보다 항상 나쁜 열)는 빼고,
        # 남은 칸 중 효과가 판정을 자주 바꾸는 카드만 엔진으로 다시 계산한다.
        protect = getattr(evaluator, 'protect_column', None)
        margin = getattr(evaluator, 'prune_margin', 0.0)
        keep = list(range(len(options))) if margin is None else dominated_free_columns(
            matrix, protected={j for j, other in enumerate(options) if protect and protect(other)},
            margin=margin,
        )
        evaluator.pruned = [options[j].get('code') for j in range(len(options)) if j not in keep]
        matrix = [[row[j] for j in keep] for row in matrix]
        options = [options[j] for j in keep]
        for i, action in enumerate(ready_actions):
            bonus = (row_bonus or {}).get(action.get('action_id'), 0.0)
            for j, other in enumerate(options):
                value = refine(action, other)
                if value is not None:
                    matrix[i][j] = value + bonus
    return matrix, options, coverage


def dominated_free_columns(matrix, *, protected=(), tolerance=1e-9, margin=0.0):
    """Column indexes left after removing columns the opponent never prefers.

    The opponent minimizes. Column ``j`` goes when another column ``k`` is at
    most as good for the AI in every row and better in one (or identical with
    a lower index). Removing such columns keeps the game's value, and it is
    what a player does when they ignore cards the opponent would lose with.
    """
    columns = list(range(len(matrix[0]))) if matrix else []
    keep = []
    for j in columns:
        if j in protected:
            keep.append(j)
            continue
        dominated = False
        for k in columns:
            if k == j:
                continue
            if margin > 0:
                # 추정치가 조금 틀려도 버티도록, 모든 행에서 margin 넘게 나쁠 때만 뺀다.
                if all(row[k] < row[j] - margin for row in matrix):
                    dominated = True
                    break
                continue
            le = all(row[k] <= row[j] + tolerance for row in matrix)
            if not le:
                continue
            strict = any(row[k] < row[j] - tolerance for row in matrix)
            if strict or k < j:
                dominated = True
                break
        if not dominated:
            keep.append(j)
    return keep or columns


def choose_ready(observation, role, ranked, *, seed, temperature, evaluator=None, row_bonus=None):
    """Pick a Ready action from ``ranked`` (score, action) pairs, or ``None``.

    Returns ``(score, action, details)``.
    """
    ready = [(score, action) for score, action in ranked if action.get('type') == 'ready_card']
    if len(ready) < 2:
        return None
    actions = [action for _score, action in ready]
    built = ready_matrix(observation, role, actions, evaluator=evaluator, row_bonus=row_bonus)
    if built is None:
        return None
    matrix, options, coverage = built
    equilibrium = solve_zero_sum(matrix)
    policy = _softmax([score for score, _action in ready], POLICY_TEMPERATURE)
    mixed = [coverage * e + (1.0 - coverage) * p for e, p in zip(equilibrium, policy)]
    if temperature is not None and temperature <= 0:
        index = max(range(len(mixed)), key=lambda i: (mixed[i], ready[i][0]))
    else:
        key = ':'.join([str(seed), role, 'ready-matrix', *sorted(str(a.get('action_id')) for a in actions)])
        rng = random.Random(hashlib.sha256(key.encode()).hexdigest())
        index = rng.choices(range(len(ready)), weights=[p + 1e-12 for p in mixed], k=1)[0]
    score, action = ready[index]
    details = {
        'coverage': coverage,
        'options': [card.get('code') for card in options],
        'probabilities': {a['card'].get('code'): round(p, 3) for a, p in zip(actions, mixed)},
        'matrix': matrix,
        'engine_evaluated': evaluator is not None and not hasattr(evaluator, 'refine'),
    }
    if hasattr(evaluator, 'refine'):
        details['table_evaluated'] = True
        details['engine_cells'] = getattr(evaluator, 'refined', 0)
        details['pruned'] = getattr(evaluator, 'pruned', [])
    return score, action, details
