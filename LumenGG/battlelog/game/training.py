"""Small deterministic evolutionary trainer for the linear simulator policy."""

import copy
import random
from dataclasses import dataclass

from .ai import DEFAULT_POLICY_WEIGHTS
from .simulation import run_policy_game


MUTABLE_WEIGHTS = (
    'pass_phase', 'ready_card', 'select_get_card', 'select_ultimate',
    'submit_decision', 'play_combo_card', 'play_combo_pair', 'end_combo',
    'play_catch_card', 'decline_catch', 'card_damage', 'card_speed',
    'card_attack', 'card_defense', 'low_hp_defense', 'hp_advantage_attack',
    'zero_damage_attack',
)


@dataclass(frozen=True)
class TrainingResult:
    weights: dict
    metrics: dict
    games: int


def _paired_game_count(value, *, minimum=2):
    """Return an even game count so every candidate plays both seats."""
    count = max(minimum, int(value))
    return count if count % 2 == 0 else count + 1


def exploration_policies(weights):
    """Deterministic strategic seeds; self-play still decides promotion."""
    speed = copy.deepcopy(weights)
    speed['card_damage'] = 0.05
    speed['card_speed'] = 1.0

    offense = copy.deepcopy(weights)
    offense['card_attack'] = 3.0
    offense['card_defense'] = -2.0

    defense = copy.deepcopy(weights)
    defense['card_attack'] = -2.0
    defense['card_defense'] = 3.0
    defense['low_hp_defense'] = 3.0

    return [speed, offense, defense]


def mutate_policy(weights, rng, *, scale=0.25):
    candidate = copy.deepcopy(weights)
    for name in MUTABLE_WEIGHTS:
        current = float(candidate.get(name, 0.0))
        candidate[name] = round(current + rng.uniform(-scale, scale), 6)
    # Safety/meta actions are fixed invariants, not trainable preferences.
    candidate['concede'] = -1000.0
    candidate['request_rewind'] = -50.0
    candidate['pause_clock'] = -50.0
    return candidate


def _training_corpus(initial_state):
    """Normalize one training state or a non-empty state corpus."""
    if isinstance(initial_state, (list, tuple)):
        states = list(initial_state)
    else:
        states = [initial_state]
    if not states:
        raise ValueError('훈련 상태가 하나 이상 필요합니다.')
    if any(not isinstance(state, dict) for state in states):
        raise TypeError('훈련 상태는 dict여야 합니다.')
    return states


def _evaluate_candidate(initial_state, ruleset, candidate, champion, *, games, seed):
    states = _training_corpus(initial_state)
    reward = 0.0
    wins = losses = draws = incomplete = commands = 0
    for index in range(games):
        candidate_side = 'p1' if index % 2 == 0 else 'p2'
        # Evaluate both candidate seats with the same deterministic shuffle and
        # tie-break seed. Otherwise random seed differences can be mistaken for
        # policy improvement, even when candidate and champion are identical.
        pair_index = index // 2
        state_index = pair_index % len(states)
        state = copy.deepcopy(states[state_index])
        state['priority_player'] = 'p1' if pair_index % 2 == 0 else 'p2'
        policies = {
            candidate_side: candidate,
            'p2' if candidate_side == 'p1' else 'p1': champion,
        }
        game_seed = (
            f'{seed}:pair{pair_index}'
            if len(states) == 1
            else f'{seed}:state{state_index}:pair{pair_index}'
        )
        result = run_policy_game(
            state,
            ruleset,
            policies=policies,
            seed=game_seed,
        )
        commands += result.commands
        if not result.completed:
            incomplete += 1
            reward -= 1.0
        elif result.winner == candidate_side:
            wins += 1
            reward += 1.0
        elif result.winner:
            losses += 1
        else:
            draws += 1
            reward += 0.5
    return {
        'score': reward / max(1, games),
        'wins': wins,
        'losses': losses,
        'draws': draws,
        'incomplete': incomplete,
        'average_commands': round(commands / max(1, games), 3),
        'training_state_count': len(states),
    }


def train_self_play(
    initial_state,
    ruleset,
    *,
    initial_weights=None,
    generations=8,
    candidates_per_generation=4,
    games_per_candidate=8,
    evaluation_games=40,
    seed='lumen-ai-training',
    progress=None,
):
    rng = random.Random(seed)
    states = _training_corpus(initial_state)
    champion = copy.deepcopy(initial_weights or DEFAULT_POLICY_WEIGHTS)
    history = []
    total_games = 0
    generation_count = max(1, generations)
    challenger_count = max(1, candidates_per_generation)
    games_per_matchup = _paired_game_count(games_per_candidate)
    for generation in range(generation_count):
        scale = max(0.04, 0.3 * (1.0 - generation / max(1, generations)))
        if generation == 0:
            challengers = exploration_policies(champion)[:challenger_count]
            challengers.extend(
                mutate_policy(champion, rng, scale=scale)
                for _ in range(challenger_count - len(challengers))
            )
        else:
            challengers = [
                mutate_policy(champion, rng, scale=scale)
                for _ in range(challenger_count)
            ]
        candidates = [champion, *challengers]
        evaluated = []
        for candidate_index, candidate in enumerate(candidates):
            metrics = _evaluate_candidate(
                states,
                ruleset,
                candidate,
                champion,
                games=games_per_matchup,
                seed=f'{seed}:g{generation}:c{candidate_index}',
            )
            total_games += games_per_matchup
            evaluated.append((candidate, metrics))
        champion, best = max(
            evaluated,
            key=lambda item: (
                item[1]['score'],
                -item[1]['incomplete'],
                -item[1]['average_commands'],
            ),
        )
        generation_metrics = {'generation': generation + 1, **best}
        history.append(generation_metrics)
        if progress:
            progress(copy.deepcopy(generation_metrics), total_games)
    evaluation_games = _paired_game_count(evaluation_games, minimum=10)
    evaluation = _evaluate_candidate(
        states,
        ruleset,
        champion,
        initial_weights or DEFAULT_POLICY_WEIGHTS,
        games=evaluation_games,
        seed=f'{seed}:evaluation',
    )
    total_games += evaluation_games
    promoted = evaluation['incomplete'] == 0 and evaluation['score'] > 0.5
    return TrainingResult(
        weights=champion if promoted else copy.deepcopy(initial_weights or DEFAULT_POLICY_WEIGHTS),
        games=total_games,
        metrics={
            'seed': seed,
            'generations': generation_count,
            'candidates_per_generation': challenger_count,
            'games_per_candidate': games_per_matchup,
            'evaluation_games': evaluation_games,
            'evaluation_method': 'paired_seats_same_seed',
            'training_state_count': len(states),
            'evaluation': evaluation,
            'selected': 'evolved' if promoted else 'bootstrap',
            'history': history,
        },
    )
