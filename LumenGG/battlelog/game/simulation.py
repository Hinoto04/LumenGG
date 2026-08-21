"""Headless policies used to detect deadlocks and runaway resolution loops."""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from .engine import AutomaticGameEngine
from .ai import DEFAULT_POLICY_WEIGHTS, choose_action
from .spec import PLAYER_SIDES


@dataclass
class SimulationResult:
    completed: bool
    commands: int
    winner: str | None
    reason: str
    error: str = ''


def _command_limit_error(engine):
    recent_events = [
        str(event.get('type') or '') for event in engine.events[-12:]
    ]
    legal = {
        side: [action.get('type') for action in engine.list_legal_actions(side)]
        for side in PLAYER_SIDES
    }
    battle_events = [
        {
            'type': event.get('type'),
            'payload': event.get('payload'),
        }
        for event in engine.events
        if event.get('type') in {'battle_revealed', 'battle_judged', 'damage_dealt'}
    ][-8:]
    hp = {
        side: (engine.state.get('players', {}).get(side) or {}).get('hp')
        for side in PLAYER_SIDES
    }
    return (
        f'turn={engine.state.get("turn")}, phase={engine.state.get("phase")}, '
        f'step={engine.engine_state.get("step")}, hp={hp}, legal={legal}, '
        f'recent_events={recent_events}, recent_battles={battle_events}'
    )


def run_random_game(initial_state, ruleset, *, seed='headless', max_commands=2000):
    engine = AutomaticGameEngine.initialize(initial_state, ruleset, seed=seed)
    policy = random.Random(seed)
    excluded = {'request_rewind', 'concede', 'pause_clock'}
    for command_index in range(max_commands):
        status = engine.engine_state.get('status')
        if status != 'running':
            return SimulationResult(
                completed=True, commands=command_index,
                winner=engine.engine_state.get('winner'), reason=engine.engine_state.get('reason') or '',
            )
        candidates = []
        for side in PLAYER_SIDES:
            candidates.extend((side, action) for action in engine.list_legal_actions(side) if action['type'] not in excluded)
        if not candidates:
            clock = engine.engine_state.get('clock') or {}
            deadline = clock.get('deadline')
            if deadline and not clock.get('paused'):
                engine.now = datetime.fromisoformat(deadline) + timedelta(milliseconds=1)
                engine.reconcile_clock()
                continue
            return SimulationResult(False, command_index, None, 'deadlock', '합법 행동과 진행 가능한 타이머가 없습니다.')
        side, action = policy.choice(candidates)
        selections = {}
        if action['type'] == 'submit_decision':
            options = [str(item.get('id')) for item in action.get('options') or []]
            minimum = int(action.get('minimum') or 0)
            selections['selected'] = sorted(options)[:minimum]
        engine.submit_action(side, action['action_id'], selections, command_id=f'headless-{command_index}')
    return SimulationResult(
        False, max_commands, None, 'command_limit', _command_limit_error(engine),
    )


def run_policy_game(
    initial_state,
    ruleset,
    *,
    policies=None,
    seed='self-play',
    max_commands=2000,
):
    """Run AI-vs-AI through the same observe/list/submit API used online."""
    try:
        engine = AutomaticGameEngine.initialize(initial_state, ruleset, seed=seed)
    except Exception as exc:  # Treat a bad effect as one incomplete sample.
        return SimulationResult(
            False, 0, None, 'engine_error', f'{type(exc).__name__}: {exc}',
        )
    policies = policies or {side: DEFAULT_POLICY_WEIGHTS for side in PLAYER_SIDES}
    for command_index in range(max_commands):
        status = engine.engine_state.get('status')
        if status != 'running':
            return SimulationResult(
                completed=True,
                commands=command_index,
                winner=engine.engine_state.get('winner'),
                reason=engine.engine_state.get('reason') or '',
            )
        decisions = []
        for side in PLAYER_SIDES:
            observation = engine.observe(side)
            decision = choose_action(
                observation,
                side,
                weights=policies.get(side) or DEFAULT_POLICY_WEIGHTS,
                seed=f'{seed}:{command_index}',
            )
            if decision:
                decisions.append((side, decision))
        if not decisions:
            clock = engine.engine_state.get('clock') or {}
            deadline = clock.get('deadline')
            if deadline and not clock.get('paused'):
                engine.now = datetime.fromisoformat(deadline) + timedelta(milliseconds=1)
                engine.reconcile_clock()
                continue
            return SimulationResult(False, command_index, None, 'deadlock', '합법 행동과 진행 가능한 타이머가 없습니다.')
        side, decision = sorted(
            decisions,
            key=lambda item: (item[1].score, item[0] == engine.state.get('priority_player')),
            reverse=True,
        )[0]
        try:
            engine.submit_action(
                side,
                decision.action['action_id'],
                decision.selections,
                command_id=f'self-play-{command_index}',
            )
        except Exception as exc:  # Headless training must quarantine one bad game.
            return SimulationResult(
                False, command_index, None, 'engine_error',
                f'{type(exc).__name__}: {exc}',
            )
    return SimulationResult(
        False, max_commands, None, 'command_limit', _command_limit_error(engine),
    )
