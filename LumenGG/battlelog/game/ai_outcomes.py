"""Ready matrix cells from per-card outcome numbers instead of full simulation.

A player rarely plays a whole Combo out in their head. They judge the clash
of the two readied cards and then think in rough, well-known numbers: "this
card's Combo deals about 2000", "a hit here gives three counters", "being
guarded costs me 6 FP". This module does the same:

* the judgment comes from ``ai_preview.preview_battle`` (printed stats, FP);
* what follows the judgment comes from an *outcome table*: for each card code
  and judgment result, the average resources its owner gained in that battle
  (damage dealt, FP at the end, passive counters, hand cards);
* a cell is ``my gains - rival gains`` weighted by resource rates, in the same
  units as ``ai_engine_eval`` (400 damage = 1, 6 FP = 1, a lethal hit ±20).

The table is measured by self-play (``OutcomeRecorder``, command
``build_ai_outcome_table``) and stored in ``ai_outcome_table.json``. AI deck
profiles may override entries (``[outcome."CODE".hit]``) and the resource
rates (``[resources]``). Cards whose effects often change the judgment itself
(high *drift*: the printed-stat preview disagreed with the real judgment)
can be handed to the engine evaluator for just those cells (``refine``).
"""

import json
from functools import lru_cache
from pathlib import Path

from .ai_preview import (
    DAMAGING, _fp_gain, _is_attack, _number, _players, _zone, catch_after, fp_values, is_ready_candidate,
    own_card, preview_battle, rival_hand_view,
)

TABLE_PATH = Path(__file__).with_name('ai_outcome_table.json')
RESOURCES = ('damage', 'fp', 'counter', 'card')
# 자원 1단위의 가치. 배틀 한 번 승패(엔진 평가의 데미지 400)를 1로 본다.
DEFAULT_RATES = {'damage': 1 / 400.0, 'fp': 1 / 6.0, 'counter': 0.5, 'card': 0.75}
# 표본이 이보다 적은 칸은 기본 수치(인쇄 데미지·FP)와 섞어 쓴다.
MIN_SAMPLES = 3
# 인쇄 수치 예측이 실제 판정과 이 비율 넘게 달랐던 카드는 효과가 판정을 바꾸는 카드로 본다.
DRIFT_LIMIT = 0.2
WIN_VALUE = 20.0
# 수비 카드가 공격을 막거나 피하거나 상쇄한 판정(효과 캐치가 나는 때)
DEFENDED = {'guard', 'dodge', 'clash'}


def _same_card(a, b):
    if a is b:
        return True
    ida, idb = a.get('instance_id'), b.get('instance_id')
    return bool(ida) and ida == idb


def _code(card):
    return str((card or {}).get('code') or '')


def _empty_gain():
    return {key: 0.0 for key in RESOURCES}


class OutcomeTable:
    """Average resource gains per ``(card code, judgment result)``."""

    def __init__(self, cards=None, overrides=None, state_speed=None):
        self.cards = cards or {}
        self.overrides = overrides or {}
        self.state_speed = state_speed or {}
        self._combo_extra = None

    def speed_offset(self, code, states=''):
        """Measured speed change (frames, + = slower) of ``code`` under ``states``.

        Effects that fire on use or before judgment (Charge's "2 speed slower",
        a passive state's speed-up) never show in printed stats. Self-play
        recorded the real final speed, keyed by card and by the owner's active
        states; a card without samples for these states borrows the state's
        average over all cards.
        """
        rows = self.entry(code).get('speed') or {}

        def measured(row):
            row = row or {}
            return float(row.get('offset') or 0) if int(row.get('n') or 0) >= MIN_SAMPLES else None

        base = measured(rows.get('')) or 0.0
        if not states:
            return base
        own = measured(rows.get(states))
        if own is not None:
            return own
        overall = measured(self.state_speed.get(states))
        if overall is None:
            return base
        return base + overall - (measured(self.state_speed.get('')) or 0.0)

    def entry(self, code):
        return self.cards.get(code) or {}

    def samples(self, code, result):
        return int(((self.entry(code).get('results') or {}).get(result) or {}).get('n') or 0)

    def drift_rate(self, code):
        entry = self.entry(code)
        judged = int(entry.get('judged') or 0)
        if judged < MIN_SAMPLES:
            return None
        return float(entry.get('drift') or 0) / judged

    def drifts(self, card, limit=DRIFT_LIMIT):
        rate = self.drift_rate(_code(card))
        return rate is not None and rate > limit

    def combo_extra(self, character_id):
        """Measured damage beyond the printed value when a Combo starts."""
        if self._combo_extra is None:
            totals = {}
            for entry in self.cards.values():
                printed = _number(entry.get('printed_damage'))
                for result, row in (entry.get('results') or {}).items():
                    if result not in DAMAGING or not entry.get('combo', {}).get(result):
                        continue
                    n = int(row.get('n') or 0)
                    bucket = totals.setdefault(entry.get('character_id'), [0.0, 0])
                    bucket[0] += (_number(row.get('damage')) - printed) * n
                    bucket[1] += n
            self._combo_extra = {key: total / n for key, (total, n) in totals.items() if n}
        return self._combo_extra.get(character_id, 0.0)

    def default_gain(self, card, result):
        gain = _empty_gain()
        if result in DAMAGING:
            gain['damage'] = _number(card.get('damage'))
            if str(card.get(result) or '') == '콤보':
                gain['damage'] += self.combo_extra(self.entry(_code(card)).get('character_id', card.get('character_id')))
        gain['fp'] = _fp_gain(card, result)
        return gain

    def gain(self, card, result):
        """Resources the card's owner is expected to gain with ``result``."""
        code = _code(card)
        default = self.default_gain(card, result)
        row = ((self.entry(code).get('results') or {}).get(result)) or {}
        n = int(row.get('n') or 0)
        if n:
            weight = n / float(max(n, MIN_SAMPLES))
            gain = {
                key: weight * _number(row.get(key)) + (1 - weight) * default[key]
                for key in RESOURCES
            }
        else:
            gain = default
        manual = (self.overrides.get(code) or {}).get(result) or {}
        return {key: _number(manual[key]) if key in manual else gain[key] for key in RESOURCES}

    def with_overrides(self, overrides):
        if not overrides:
            return self
        merged = {code: dict(rows) for code, rows in self.overrides.items()}
        for code, rows in overrides.items():
            merged.setdefault(code, {}).update(rows)
        return OutcomeTable(self.cards, merged, self.state_speed)


@lru_cache(maxsize=4)
def _load_table(path):
    try:
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return OutcomeTable()
    return OutcomeTable(payload.get('cards') or {}, state_speed=payload.get('state_speed') or {})


def default_table():
    return _load_table(str(TABLE_PATH))


def table_for_profile(profile=None, table=None):
    """``(table, rates)`` with the profile's overrides applied."""
    table = table or default_table()
    profile = profile or {}
    rates = {**DEFAULT_RATES, **(profile.get('resources') or {})}
    return table.with_overrides(profile.get('outcome') or {}), rates


class TableReadyEvaluator:
    """``evaluator(my_ready_action, rival_card) -> value`` from the outcome table.

    ``refine(action, rival_card)`` hands a cell to ``refiner`` (normally an
    ``EngineReadyEvaluator``) when either card's effects often change the
    judgment; ``ai_matrix`` calls it only for columns left after pruning.
    """

    def __init__(self, observation, role, *, table=None, rates=None, refiner=None, drift_limit=DRIFT_LIMIT):
        self.observation = observation
        self.role = role
        self.table = table or default_table()
        self.rates = {**DEFAULT_RATES, **(rates or {})}
        self.refiner = refiner
        self.drift_limit = drift_limit
        self.my_fp, self.their_fp = fp_values(observation, role)
        players = (observation.get('state') or {}).get('players') or {}
        rival_role = 'p2' if role == 'p1' else 'p1'
        engine_state = (observation.get('state') or {}).get('engine') or {}
        self.my_states = state_key(players.get(role), engine_state, role)
        self.rival_states = state_key(players.get(rival_role), engine_state, rival_role)
        self.my_hp = _number((players.get(role) or {}).get('hp'), 0)
        self.rival_hp = _number((players.get(rival_role) or {}).get('hp'), 0)
        own, _rival = _players(observation, role)
        self.my_hand = [card for card in _zone(own, 'hand') if isinstance(card, dict) and not card.get('hidden')]
        self.rival_hand = rival_hand_view(observation, role)[0]
        # 효과로 캐치를 주는 카드와 그 캐치의 속도 상한(ai_decisions.annotate_effect_codes가 붙인 값).
        self.effect_catch = dict((observation.get('effect_combo_codes') or {}).get('catch_speed') or {})
        self.refined = 0

    def _catch_damage(self, hand, readied, max_speed):
        """Most damage a Catch from ``hand`` deals (the readied card is in battle), or ``None``."""
        damages = [
            self.table.gain(card, 'hit')['damage']
            for card in hand
            if not _same_card(card, readied) and _is_attack(card)
            and _number(card.get('frame'), 99.0) <= max_speed
        ]
        return max(damages) if damages else None

    def _with_catch(self, mine, rival_card, mine_result, theirs_result, mine_gain, theirs_gain):
        """Settle the Catch the judgment FP opens instead of the measured averages.

        The table measures a battle up to its end, so a Catch that followed is
        averaged into the row (being guarded looks cheap: the FP was reset by the
        opponent's Catch and its damage went to the guard card's row, shared by
        every attacker). Here the printed FP decides who may Catch and the known
        hand decides with what; without a card the FP lead simply remains.
        """
        my_fp, their_fp = _fp_gain(mine, mine_result), _fp_gain(rival_card, theirs_result)
        catch = catch_after(my_fp, their_fp)
        # 효과 캐치: 수비 카드가 막거나 피한 뒤 효과로 캐치하는 경우(리타 「나의 영혼은 성녀를 위해」 등).
        # FP와 상관없이 캐치가 생긴다. 효과의 다른 조건(루멘 존 카드 등)은 보지 않고 늘 캐치한다고 본다.
        effect_catch = None
        if theirs_result in DEFENDED and _code(rival_card) in self.effect_catch:
            effect_catch = ('theirs', self.effect_catch[_code(rival_card)])
        elif mine_result in DEFENDED and _code(mine) in self.effect_catch:
            effect_catch = ('mine', self.effect_catch[_code(mine)])
        if catch is None and effect_catch is None:
            return mine_gain, theirs_gain
        defaults = (self.table.default_gain(mine, mine_result), self.table.default_gain(rival_card, theirs_result))
        mine_gain, theirs_gain = (
            {**gain, 'damage': default['damage'], 'fp': default['fp']}
            for gain, default in zip((mine_gain, theirs_gain), defaults)
        )
        if effect_catch is not None:
            owner, max_speed = effect_catch
            if owner == 'mine':
                damage, gain = self._catch_damage(self.my_hand, mine, max_speed), mine_gain
            else:
                damage, gain = self._catch_damage(self.rival_hand, rival_card, max_speed), theirs_gain
            if damage is not None:
                gain['damage'] += damage
                mine_gain['fp'] = theirs_gain['fp'] = 0.0
                return mine_gain, theirs_gain
            if catch is None:
                return mine_gain, theirs_gain
        owner, max_speed = catch
        if owner == 'mine':
            damage, gain, target_hp = self._catch_damage(self.my_hand, mine, max_speed), mine_gain, self.rival_hp
        else:
            damage, gain, target_hp = self._catch_damage(self.rival_hand, rival_card, max_speed), theirs_gain, self.my_hp
        # 캐치하지 않으면 FP 우위(max_speed)가 남는다. 더 큰 쪽을 고른다고 본다.
        if damage is not None and (
            self.rates['damage'] * damage >= self.rates['fp'] * max_speed
            or 0 < target_hp <= gain['damage'] + damage
        ):
            gain['damage'] += damage
            mine_gain['fp'] = theirs_gain['fp'] = 0.0
        return mine_gain, theirs_gain

    def _mine(self, action):
        card = action.get('card') or {}
        return own_card(self.observation, self.role, card.get('instance_id')) or card

    def __call__(self, action, rival_card):
        mine = self._mine(action)
        if not (is_ready_candidate(mine) and is_ready_candidate(rival_card)):
            return None
        # 속도 보정은 FP처럼 최종 속도에만 반영한다(상쇄 판단용 기준 속도는 인쇄 수치).
        mine_result, theirs_result = preview_battle(
            mine, rival_card,
            my_fp=self.my_fp - self.table.speed_offset(_code(mine), self.my_states),
            their_fp=self.their_fp - self.table.speed_offset(_code(rival_card), self.rival_states),
        )
        mine_gain = self.table.gain(mine, mine_result)
        theirs_gain = self.table.gain(rival_card, theirs_result)
        mine_gain, theirs_gain = self._with_catch(mine, rival_card, mine_result, theirs_result, mine_gain, theirs_gain)
        value = sum(self.rates[key] * (mine_gain[key] - theirs_gain[key]) for key in RESOURCES)
        if self.rival_hp > 0 and mine_gain['damage'] >= self.rival_hp:
            value += WIN_VALUE
        if self.my_hp > 0 and theirs_gain['damage'] >= self.my_hp:
            value -= WIN_VALUE
        return value

    def protect_column(self, rival_card):
        """Keep this column when pruning: its table values may be wrong."""
        return self.refiner is not None and self.table.drifts(rival_card, self.drift_limit)

    def needs_refine(self, action, rival_card):
        return (
            self.table.drifts(self._mine(action), self.drift_limit)
            or self.table.drifts(rival_card, self.drift_limit)
        )

    def refine(self, action, rival_card):
        if self.refiner is None or not self.needs_refine(action, rival_card):
            return None
        value = self.refiner(action, rival_card)
        if value is not None:
            self.refined += 1
        return value


# --- measuring the table -------------------------------------------------

def state_key(player, engine_state, side):
    """Sorted names of a player's active on/off states, e.g. ``'charge'``.

    Counters (numeric ``count``) are left out: they change every battle.
    """
    names = set()
    for name, entry in ((player or {}).get('passive_state') or {}).items():
        if isinstance(entry, dict):
            if entry.get('value') and 'count' not in entry:
                names.add(str(name))
        elif entry is True:
            names.add(str(name))
    for name, sources in (((engine_state or {}).get('continuous_states') or {}).get(side) or {}).items():
        if sources:
            names.add(str(name))
    return '+'.join(sorted(names))


def _side_snapshot(engine, side):
    player = (engine.state.get('players') or {}).get(side) or {}
    zones = player.get('zones') or {}
    counters = 0.0
    for entry in (player.get('passive_state') or {}).values():
        counters += _number(entry.get('count') if isinstance(entry, dict) else entry)
    return {
        'hp': _number(player.get('hp')),
        'fp': _number(player.get('fp')),
        'counter': counters,
        'cards': len(zones.get('hand') or []) + len(zones.get('battle') or []),
        'states': state_key(player, engine.engine_state, side),
    }


class OutcomeRecorder:
    """Collect outcome-table samples while a game is played.

    Call ``step(engine)`` before every command and ``finish(engine)`` after
    the game. A battle runs from the last Ready-phase snapshot of a turn to
    the moment the turn leaves the Ready/Battle phases.
    """

    def __init__(self, ruleset):
        self.cards = (ruleset or {}).get('cards') or {}
        self.stats = {}
        self.state_speed = {}
        self.battles = 0
        self._start = None
        self._pending = None
        self._seen = 0
        self._events_seen = 0
        self._speeds = {}

    def step(self, engine):
        state, engine_state = engine.state, engine.engine_state
        turn, phase = state.get('turn'), state.get('phase')
        if self._pending and (
            engine_state.get('status') != 'running'
            or turn != self._pending['turn']
            or phase not in ('ready', 'battle')
        ):
            self._finish_battle(engine)
        history = engine_state.get('battle_result_history') or []
        if len(history) < self._seen:
            self._seen = 0
        fresh = history[self._seen:]
        self._seen = len(history)
        events = engine.events or []
        if len(events) < self._events_seen:
            self._events_seen = 0
        for event in events[self._events_seen:]:
            if event.get('type') == 'battle_judged':
                self._speeds.setdefault(turn, (event.get('payload') or {}).get('speed'))
        self._events_seen = len(events)
        if phase == 'ready' and engine_state.get('status') == 'running':
            self._start = {
                'turn': turn,
                'sides': {side: _side_snapshot(engine, side) for side in ('p1', 'p2')},
            }
        if self._pending or not self._start or self._start['turn'] != turn:
            return
        judged = {}
        for entry in fresh:
            if entry.get('turn') == turn and entry.get('player') in ('p1', 'p2'):
                judged.setdefault(entry['player'], entry)
        if len(judged) == 2:
            self._pending = {
                'turn': turn, 'start': self._start, 'judged': judged, 'speed': self._speeds.get(turn),
            }

    def finish(self, engine):
        self.step(engine)
        if self._pending:
            self._finish_battle(engine)

    def _finish_battle(self, engine):
        pending, self._pending = self._pending, None
        start = pending['start']['sides']
        end = {side: _side_snapshot(engine, side) for side in ('p1', 'p2')}
        self.battles += 1
        for side, rival in (('p1', 'p2'), ('p2', 'p1')):
            entry, other = pending['judged'][side], pending['judged'][rival]
            code = _code(entry.get('card'))
            result = str(entry.get('result') or 'none')
            if not code:
                continue
            printed = self.cards.get(code) or {}
            stats = self.stats.setdefault(code, {
                'character_id': printed.get('character_id'),
                'printed_damage': _number(printed.get('damage')),
                'judged': 0, 'drift': 0, 'results': {}, 'combo': {},
            })
            stats['judged'] += 1
            other_printed = self.cards.get(_code(other.get('card'))) or {}
            if printed and other_printed:
                predicted, _ = preview_battle(
                    printed, other_printed,
                    my_fp=start[side]['fp'], their_fp=start[rival]['fp'],
                )
                if predicted != result:
                    stats['drift'] += 1
            if str(printed.get(result) or '') == '콤보':
                stats['combo'][result] = True
            speed = (pending.get('speed') or {}).get(side)
            frame = str(printed.get('frame') or '').strip()
            # 속도가 인쇄된 카드(공격 기술)만 잰다. 수비 기술은 속도가 없다.
            if frame.lstrip('-').isdigit() and isinstance(speed, (int, float)):
                expected = max(1.0, float(frame) - start[side]['fp'])
                key = start[side]['states']
                for bucket in (
                    stats.setdefault('speed', {}).setdefault(key, {'n': 0, 'offset': 0.0}),
                    self.state_speed.setdefault(key, {'n': 0, 'offset': 0.0}),
                ):
                    bucket['n'] += 1
                    bucket['offset'] += speed - expected
            row = stats['results'].setdefault(result, {'n': 0, **_empty_gain()})
            row['n'] += 1
            row['damage'] += start[rival]['hp'] - end[rival]['hp']
            row['fp'] += end[side]['fp']
            row['counter'] += end[side]['counter'] - start[side]['counter']
            row['card'] += end[side]['cards'] - (start[side]['cards'] - 1)

    def merge(self, other):
        for code, theirs in other.stats.items():
            mine = self.stats.setdefault(code, {**theirs, 'results': {}, 'combo': {}, 'judged': 0, 'drift': 0})
            mine['judged'] += theirs['judged']
            mine['drift'] += theirs['drift']
            mine['combo'].update(theirs.get('combo') or {})
            for key, row in (theirs.get('speed') or {}).items():
                target = mine.setdefault('speed', {}).setdefault(key, {'n': 0, 'offset': 0.0})
                target['n'] += row['n']
                target['offset'] += row['offset']
            for result, row in theirs['results'].items():
                target = mine['results'].setdefault(result, {'n': 0, **_empty_gain()})
                for key, value in row.items():
                    target[key] += value
        for key, row in other.state_speed.items():
            target = self.state_speed.setdefault(key, {'n': 0, 'offset': 0.0})
            target['n'] += row['n']
            target['offset'] += row['offset']
        self.battles += other.battles

    def table_payload(self, **meta):
        """JSON-ready table: sums become averages."""
        cards = {}
        for code, stats in sorted(self.stats.items()):
            results = {}
            for result, row in sorted(stats['results'].items()):
                n = row['n']
                results[result] = {'n': n, **{key: round(row[key] / n, 2) for key in RESOURCES}}
            cards[code] = {
                'character_id': stats['character_id'],
                'printed_damage': stats['printed_damage'],
                'judged': stats['judged'],
                'drift': stats['drift'],
                'combo': stats.get('combo') or {},
                'results': results,
                'speed': _averaged(stats.get('speed') or {}),
            }
        return {
            'version': 1, **meta, 'battles': self.battles, 'cards': cards,
            'state_speed': _averaged(self.state_speed),
        }


def _averaged(rows):
    return {
        key: {'n': row['n'], 'offset': round(row['offset'] / row['n'], 2)}
        for key, row in sorted(rows.items()) if row['n']
    }


READY_EVAL_MODES = ('table', 'engine', 'base')


def build_ready_evaluator(engine, observation, role, *, mode='table', weights=None, profile=None, engine_cells=True):
    """Ready-matrix evaluator for one decision, or ``None`` (printed stats only).

    ``table``: outcome table, with engine simulation only for cells whose
    cards change the judgment (when ``engine_cells``). ``engine``: every cell
    by simulation. ``base``: printed-stat preview.
    """
    if not any(action.get('type') == 'ready_card' for action in observation.get('legal_actions') or []):
        return None
    if mode not in READY_EVAL_MODES or mode == 'base':
        return None
    from .ai_engine_eval import EngineReadyEvaluator

    if mode == 'engine':
        return EngineReadyEvaluator(engine, role, weights=weights) if engine_cells else None
    table, rates = table_for_profile(profile)
    refiner = EngineReadyEvaluator(engine, role, weights=weights) if engine_cells else None
    return TableReadyEvaluator(observation, role, table=table, rates=rates, refiner=refiner)
