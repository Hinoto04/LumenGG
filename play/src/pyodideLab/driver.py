"""AI-vs-AI driver for the Pyodide prototype (also runs under CPython).

Imports the unmodified engine/AI modules as the standalone package
``lumen_game`` (copies of LumenGG/battlelog/game/*.py without the Django
modules). The loop mirrors ``automatic_services.advance_ai_session``: every
seat is an AI, the highest-scoring decision (priority player on ties) is
submitted, and an expired timer is advanced when nobody can act.
"""

import copy
import json
import time
from datetime import datetime, timedelta

from lumen_game.ai import DEFAULT_POLICY_WEIGHTS, choose_action
from lumen_game.ai_engine_eval import EngineReadyEvaluator
from lumen_game.engine import AutomaticGameEngine

SIDES = ('p1', 'p2')
_sample = None


class ImmutableRulesetSnapshot(dict):
    """Same marker as automatic_services.ImmutableRulesetSnapshot.

    Without it the engine deep-copies the whole ruleset (all cards) for every
    engine copy, which makes each Ready simulation about 30x slower.
    """

    _automatic_immutable_ruleset = True


def load_sample(text):
    """Parse the exported sample once; returns a short summary."""
    global _sample
    started = time.perf_counter()
    _sample = json.loads(text)
    _sample['ruleset'] = ImmutableRulesetSnapshot(_sample.get('ruleset') or {})
    return json.dumps({
        'parse_ms': (time.perf_counter() - started) * 1000,
        'meta': _sample.get('meta') or {},
        'cards': len((_sample.get('ruleset') or {}).get('cards') or {}),
    }, ensure_ascii=False)


def _ms(seconds):
    return round(seconds * 1000, 2)


def _summary(values):
    if not values:
        return {'count': 0}
    ordered = sorted(values)
    return {
        'count': len(ordered),
        'mean': _ms(sum(ordered) / len(ordered)),
        'p50': _ms(ordered[len(ordered) // 2]),
        'p90': _ms(ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))]),
        'max': _ms(ordered[-1]),
        'total': _ms(sum(ordered)),
    }


def run_game(engine_eval=True, seed='client-ai', max_commands=2000, progress=None):
    """Play one game to the end. ``progress(dict)`` is called after each command."""
    sample = _sample
    weights = sample.get('weights') or DEFAULT_POLICY_WEIGHTS
    profile = sample.get('profile') or None
    started = time.perf_counter()
    engine = AutomaticGameEngine.initialize(
        copy.deepcopy(sample['initial_state']), sample['ruleset'], seed=seed,
    )
    init_seconds = time.perf_counter() - started
    ready_times, other_times, submit_times = [], [], []
    simulations = []
    commands = 0
    reason = 'command_limit'
    for index in range(max_commands):
        if engine.engine_state.get('status') != 'running':
            reason = engine.engine_state.get('reason') or 'finished'
            break
        decisions = []
        for role in SIDES:
            t0 = time.perf_counter()
            observation = engine.observe(role, include_memory=True)
            has_ready = any(
                action.get('type') == 'ready_card'
                for action in observation.get('legal_actions') or []
            )
            evaluator = EngineReadyEvaluator(engine, role, weights=weights) if engine_eval and has_ready else None
            decision = choose_action(
                observation, role, weights=weights, seed=f'{seed}:{engine.version}',
                profile=profile if role == 'p2' else None,
                ready_evaluator=evaluator,
            )
            elapsed = time.perf_counter() - t0
            if has_ready:
                ready_times.append(elapsed)
                if evaluator is not None:
                    simulations.append(evaluator.simulations)
            else:
                other_times.append(elapsed)
            if decision:
                decisions.append((role, decision))
        if not decisions:
            clock = engine.engine_state.get('clock') or {}
            deadline = clock.get('deadline')
            if deadline and not clock.get('paused'):
                engine.now = datetime.fromisoformat(deadline) + timedelta(milliseconds=1)
                engine.reconcile_clock()
                continue
            reason = 'deadlock'
            break
        priority = engine.state.get('priority_player')
        role, decision = sorted(
            decisions, key=lambda item: (item[1].score, item[0] == priority), reverse=True,
        )[0]
        t0 = time.perf_counter()
        engine.submit_action(
            role, decision.action['action_id'], decision.selections, command_id=f'client-{index}',
        )
        submit_times.append(time.perf_counter() - t0)
        commands += 1
        if progress is not None and commands % 10 == 0:
            progress(json.dumps({
                'commands': commands,
                'turn': engine.state.get('turn'),
                'elapsed_ms': _ms(time.perf_counter() - started),
            }))
    players = engine.state.get('players') or {}
    return json.dumps({
        'engine_eval': bool(engine_eval),
        'seed': seed,
        'completed': engine.engine_state.get('status') != 'running',
        'winner': engine.engine_state.get('winner'),
        'reason': reason,
        'commands': commands,
        'turns': engine.state.get('turn'),
        'hp': {side: (players.get(side) or {}).get('hp') for side in SIDES},
        'game_ms': _ms(time.perf_counter() - started),
        'init_ms': _ms(init_seconds),
        'ready_decision': _summary(ready_times),
        'other_decision': _summary(other_times),
        'submit': _summary(submit_times),
        'simulations_per_ready': (
            round(sum(simulations) / len(simulations), 1) if simulations else 0
        ),
    })


if __name__ == '__main__':  # CPython 기준값: PYTHONPATH=<lumen_game 상위 폴더> python driver.py <sample.json>
    import sys
    with open(sys.argv[1], encoding='utf-8') as handle:
        print(load_sample(handle.read()))
    for flag in (False, True):
        print(run_game(engine_eval=flag))
