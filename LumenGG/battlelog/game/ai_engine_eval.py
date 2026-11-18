"""Fill the Ready matrix by simulating each pairing on a copy of the engine.

For a Ready candidate of the AI and one card the opponent may ready, the
copy readies both cards and plays the battle out (catches, Combos, effect
choices) with the plain policy for both sides, then scores the change:
damage dealt minus damage taken (per ``DAMAGE_UNIT``), the FP lead after the
battle and a large bonus for winning the game. Card effects, passives and
continuous rules are therefore all included, which base stats cannot see.

Only cards the AI knows are hypothesized for the opponent. The copy still
holds the opponent's real hidden cards, so effects that look at them can
leak a little information; the AI never reads them directly.
"""

import copy

from .engine import AutomaticGameEngine, EngineError

DAMAGE_UNIT = 400.0
FP_UNIT = 6.0
WIN_VALUE = 20.0
MAX_STEPS = 120
# 레디 한 번에 할 시뮬레이션 상한. 넘는 칸은 기본 수치 예측을 쓴다(ai_matrix).
MAX_SIMULATIONS = 36


def _opponent(role):
    return 'p2' if role == 'p1' else 'p1'


def _snapshot(engine, role):
    players = engine.state.get('players') or {}
    return {
        'my_hp': float((players.get(role) or {}).get('hp') or 0),
        'rival_hp': float((players.get(_opponent(role)) or {}).get('hp') or 0),
    }


class EngineReadyEvaluator:
    """``evaluator(my_ready_action, rival_card) -> value or None``."""

    def __init__(self, engine, role, *, weights=None, max_steps=MAX_STEPS, max_simulations=MAX_SIMULATIONS):
        self.state = copy.deepcopy(engine.state)
        self.ruleset = engine.ruleset
        self.version = engine.version
        self.now = engine.now
        self.role = role
        self.weights = weights
        self.max_steps = max_steps
        self.max_simulations = max_simulations
        self.cache = {}
        self.simulations = 0

    def __call__(self, my_action, rival_card):
        my_id = (my_action.get('card') or {}).get('instance_id')
        rival_id = (rival_card or {}).get('instance_id')
        if not my_id or not rival_id:
            return None
        key = (my_id, rival_id)
        if key not in self.cache:
            if self.max_simulations is not None and self.simulations >= self.max_simulations:
                return None
            self.cache[key] = self._simulate(my_id, rival_id)
        return self.cache[key]

    def _ready(self, engine, side, instance_id):
        action = next((
            item for item in engine.legal_actions(side)
            if item.get('type') == 'ready_card'
            and (item.get('payload') or {}).get('card_instance_id') == instance_id
        ), None)
        if action is None:
            return False
        engine.submit_action(side, action['action_id'], {}, command_id=f'eval-ready-{side}')
        return True

    @staticmethod
    def _swap_ready(engine, side, actual_id, hypothesis_id):
        """Make the copy's face-down Ready card the hypothesized one.

        The AI does not know which card the opponent readied, so each column
        replaces the real one with a candidate from the same pool.
        """
        zones = engine.state['players'][side]['zones']
        battle, hand = zones.get('battle') or [], zones.get('hand') or []
        b = next((i for i, card in enumerate(battle) if card.get('instance_id') == actual_id), None)
        h = next((i for i, card in enumerate(hand) if card.get('instance_id') == hypothesis_id), None)
        if b is None or h is None:
            return False
        battle[b], hand[h] = hand[h], battle[b]
        battle[b]['face_up'] = False
        engine.engine_state['ready_cards'][side] = hypothesis_id
        return True

    def _simulate(self, my_id, rival_id):
        from .ai import choose_action  # 순환 import 방지

        self.simulations += 1
        role, rival = self.role, _opponent(self.role)
        engine = AutomaticGameEngine(
            copy.deepcopy(self.state), self.ruleset, version=self.version,
            now=self.now, events=[], seed='ready-eval',
        )
        before = _snapshot(engine, role)
        turn = engine.state.get('turn')
        try:
            already = (engine.engine_state.get('ready_cards') or {}).get(rival)
            if already and already != rival_id and not self._swap_ready(engine, rival, already, rival_id):
                return None
            pending = [(role, my_id)] + ([] if already else [(rival, rival_id)])
            # 먼저 레디해야 하는 쪽(예: 서드아이)이 있으면 가능한 쪽부터 낸다.
            for _attempt in range(2):
                for side, instance_id in list(pending):
                    if self._ready(engine, side, instance_id):
                        pending.remove((side, instance_id))
            if pending:
                return None
            for step in range(self.max_steps):
                if (
                    engine.engine_state.get('status') != 'running'
                    or engine.state.get('turn') != turn
                    or engine.state.get('phase') not in ('ready', 'battle')
                ):
                    break
                decisions = []
                for side in (role, rival):
                    observation = engine.observe(side, include_memory=True)
                    decision = choose_action(
                        observation, side, weights=self.weights, seed=f'eval:{step}',
                        temperature=0, ready_strategy='policy',
                    )
                    if decision:
                        decisions.append((side, decision))
                if not decisions:
                    break
                side, decision = sorted(
                    decisions,
                    key=lambda item: (item[1].score, item[0] == engine.state.get('priority_player')),
                    reverse=True,
                )[0]
                engine.submit_action(
                    side, decision.action['action_id'], decision.selections,
                    command_id=f'eval-{step}',
                )
        except (EngineError, KeyError, TypeError, ValueError):
            return None
        after = _snapshot(engine, role)
        dealt = before['rival_hp'] - after['rival_hp']
        taken = before['my_hp'] - after['my_hp']
        players = engine.state.get('players') or {}
        fp_lead = float((players.get(role) or {}).get('fp') or 0) - float((players.get(rival) or {}).get('fp') or 0)
        value = (dealt - taken) / DAMAGE_UNIT + fp_lead / FP_UNIT
        winner = engine.engine_state.get('winner')
        if winner == role:
            value += WIN_VALUE
        elif winner == rival:
            value -= WIN_VALUE
        return value
