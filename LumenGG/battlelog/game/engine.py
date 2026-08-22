"""Pure, deterministic automatic-game state machine.

The engine owns no database objects.  A caller supplies a copied state and an
immutable ruleset snapshot, then persists the returned state and events in one
transaction.  Browser clients and future AI players use the same legal-action
contract.
"""

import copy
import hashlib
import json
import random
from datetime import datetime, timedelta, timezone as datetime_timezone

from .effects import EffectResolver, EffectResolutionError, card_matches, condition_matches, resolve_value
from .card_identity import PASSIVE_CARD_TYPE, is_passive_card, normalize_passive_card
from .spec import (
    ALL_ZONES,
    DEFAULT_EFFECT_CHOICE_SECONDS,
    DEFAULT_READY_SECONDS,
    ENGINE_SCHEMA_VERSION,
    MAX_RESOLUTION_STEPS,
    PHASES,
    PLAYER_SIDES,
)


class EngineError(ValueError):
    """Base class for automatic engine failures."""


class IllegalAction(EngineError):
    """The submitted action is not in the current legal-action set."""


class StaleState(EngineError):
    """The command was created for an older session version."""


PASSIVE_STATE_KEY_ALIASES = {
    # The manual calculator predates the automatic engine's semantic keys.
    # Normalize its stored keys so both modes update the same state value.
    'root_charge': 'charge',
    'notice': 'advance_notice',
    'silver_counter': 'hidden_bond',
    'yang_counter': 'yang',
    'yin_counter': 'yin',
    'foresight_counter': 'foresight',
    'ember_token': 'ember',
    'howling_counter': 'howling',
}


def opponent(side):
    return 'p2' if side == 'p1' else 'p1'


def _utc_now():
    return datetime.now(datetime_timezone.utc)


def _as_datetime(value):
    if isinstance(value, datetime):
        result = value
    elif value:
        try:
            result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except (TypeError, ValueError):
            return None
    else:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=datetime_timezone.utc)
    return result.astimezone(datetime_timezone.utc)


def _number(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_special(card):
    return (
        not (card or {}).get('non_technique_while_face_down')
        and '특수' in str((card or {}).get('type') or '')
    )


def _is_attack(card):
    return (
        not (card or {}).get('non_technique_while_face_down')
        and '공격' in str((card or {}).get('type') or '')
    )


def _is_defense(card):
    return (
        not (card or {}).get('non_technique_while_face_down')
        and '수비' in str((card or {}).get('type') or '')
    )


def _has_grab(card):
    return '그랩' in str((card or {}).get('special') or '')


def _special_result(card, position):
    """Return an attack card's dodge/clash keyword against a position."""
    text = (
        str((card or {}).get('special') or '')
        .replace('•', '·').replace('ㆍ', '·')
    )
    if not position:
        return ''
    covers_all_positions = '상·중·하단' in text
    if (position in text or covers_all_positions) and '회피' in text:
        return 'dodge'
    if (position in text or covers_all_positions) and '상쇄' in text:
        return 'clash'
    return ''


def _guard_result(card, position):
    key = {'상단': 'g_top', '중단': 'g_mid', '하단': 'g_bot'}.get(position)
    value = str((card or {}).get(key) or '') if key else ''
    if '회피' in value:
        return 'dodge'
    if '방어' in value:
        return 'guard'
    if '상쇄' in value:
        return 'clash'
    return 'hit'


def _fp_value(value):
    text = str(value or '').strip()
    if text.lstrip('+-').isdigit():
        return int(text)
    return 0


class AutomaticGameEngine:
    """Ruleset-pinned automatic simulator engine."""

    def __init__(self, state, ruleset, *, version=1, now=None, events=None, seed=''):
        self.state = copy.deepcopy(state or {})
        # Published cached rulesets are immutable snapshots. Ad-hoc rulesets
        # remain defensively copied because tests/editors may mutate them.
        self.ruleset = (
            ruleset
            if getattr(ruleset, '_automatic_immutable_ruleset', False)
            else copy.deepcopy(ruleset or {})
        )
        self.version = int(version or 1)
        self.now = _as_datetime(now) or _utc_now()
        self.events = copy.deepcopy(events or [])
        self.seed = str(self.state.get('random_seed') or seed or 'lumen-automatic')
        self._ensure_state()
        self.resolver = EffectResolver(self)

    @classmethod
    def initialize(cls, base_state, ruleset, *, now=None, seed='', settings=None):
        """Turn the existing simulator zones/HP/FP payload into automatic state."""
        state = copy.deepcopy(base_state or {})
        state['turn'] = max(1, _number(state.get('turn'), 1))
        state['phase'] = 'lumen'
        first = state.get('priority_player')
        if first not in PLAYER_SIDES:
            digest = hashlib.sha256(str(seed or 'lumen-automatic').encode()).digest()
            first = PLAYER_SIDES[digest[0] % 2]
        state['priority_player'] = first
        state['random_seed'] = str(seed or 'lumen-automatic')
        state['engine'] = {
            'schema_version': ENGINE_SCHEMA_VERSION,
            'status': 'running',
            'step': 'phase_actions',
            'phase_passes': [],
            'ready_cards': {},
            'resolution_queue': [],
            'resolution_order_groups': {},
            'deferred_effects': [],
            'domain_queue': [],
            'resolution_steps': 0,
            'modifiers': [],
            'replacements': [],
            'shields': {side: [] for side in PLAYER_SIDES},
            'scheduled': [],
            'state_expirations': [],
            'usage': {},
            'card_use_history': [],
            'ability_resolution_history': [],
            'battle_result_history': [],
            'turn_damage_received': {side: 0 for side in PLAYER_SIDES},
            'effect_damage_counts': {},
            'skip_phases': {},
            'no_response': {side: 0 for side in PLAYER_SIDES},
            'hand_adjustment_queue': [],
            'deferred_hand_adjustments': [],
            'pending_decision': None,
            'clock': None,
            'rewind_request': None,
            'pipeline': None,
            'battle': {},
            'combo': None,
            'catch': None,
            'winner': None,
            'reason': '',
            'settings': copy.deepcopy(settings or {}),
            'initial_passive_states': {
                side: copy.deepcopy(((state.get('players') or {}).get(side) or {}).get('passive_state') or {})
                for side in PLAYER_SIDES
            },
            'command_count': 0,
            'random_counter': 0,
            'id_counter': 0,
            # Game-start, turn-start, and the first Lumen phase are distinct
            # timing windows.  Keep the latter two behind this small startup
            # pipeline so a choice in an earlier window cannot cause a later
            # trigger to be collected against stale state.
            'startup_stage': 'after_game_start',
        }
        engine = cls(state, ruleset, version=1, now=now, seed=seed)
        engine._reconcile_trait_states()
        engine.emit('setup_completed', 'system', {
            side: {
                'character': [card.get('character_id') for card in engine._zone(side, 'character')],
                'passives': [card.get('code') for card in engine._zone(side, 'passive')],
                'ultimate': [card.get('code') for card in engine._zone(side, 'ultimate')],
                # The rulebook requires the final five-card hand to be shown
                # after exchange; the live zone becomes private immediately.
                'revealed_hand': [card.get('code') for card in engine._zone(side, 'hand')],
                'list': [card.get('code') for card in engine._zone(side, 'list')],
            }
            for side in PLAYER_SIDES
        })
        engine.emit('automatic_game_started', 'system', {
            'ruleset_version': ruleset.get('version') or ruleset.get('content_hash'),
            'priority_player': first,
        })
        engine._fire('game_start', {'turn': 1})
        engine._continue()
        return engine

    def _ensure_state(self):
        self.state.setdefault('players', {})
        for side in PLAYER_SIDES:
            player = self.state['players'].setdefault(side, {})
            player['hp'] = _number(player.get('hp'))
            player['fp'] = _number(player.get('fp'))
            player.setdefault('passive_state', {})
            self._normalize_passive_state_keys(player['passive_state'])
            zones = player.setdefault('zones', {})
            for zone in ('character', 'passive', 'battle', 'list', 'hand', 'side', 'break', 'lumen', 'ultimate'):
                zones.setdefault(zone, [])
                for card in zones[zone]:
                    released_card = (
                        (self.ruleset.get('cards') or {}).get(str(card.get('code') or '')) or {}
                    )
                    definition = (
                        released_card.get('effect_definition') or {}
                    )
                    if definition.get('token_key'):
                        card['token_key'] = definition['token_key']
                    if definition.get('token_usage'):
                        card['token_usage'] = copy.deepcopy(
                            definition['token_usage']
                        )
                    self._apply_card_form(card, zone, definition=definition)
                    character_id = card.get('character_id', released_card.get('character_id'))
                    released_character = (
                        (self.ruleset.get('characters') or {}).get(str(character_id)) or {}
                    )
                    if released_character.get('key'):
                        card['character_key'] = released_character['key']
        self._normalize_passive_zone_cards()
        for side in PLAYER_SIDES:
            for cards in (self.state['players'][side].get('zones') or {}).values():
                for card in cards:
                    self._apply_owner_deck_rules(card)
        engine = self.state.setdefault('engine', {})
        defaults = {
            'schema_version': ENGINE_SCHEMA_VERSION,
            'status': 'running',
            'step': 'phase_actions',
            'phase_passes': [],
            'ready_cards': {},
            'resolution_queue': [],
            'resolution_order_groups': {},
            'deferred_effects': [],
            'domain_queue': [],
            'resolution_steps': 0,
            'modifiers': [],
            'replacements': [],
            'shields': {side: [] for side in PLAYER_SIDES},
            'scheduled': [],
            'state_expirations': [],
            'usage': {},
            'card_use_history': [],
            'ability_resolution_history': [],
            'battle_result_history': [],
            'turn_damage_received': {side: 0 for side in PLAYER_SIDES},
            'effect_damage_counts': {},
            'skip_phases': {},
            'no_response': {side: 0 for side in PLAYER_SIDES},
            'hand_adjustment_queue': [],
            'deferred_hand_adjustments': [],
            'pending_decision': None,
            'clock': None,
            'rewind_request': None,
            'pipeline': None,
            'battle': {},
            'combo': None,
            'catch': None,
            'winner': None,
            'reason': '',
            'settings': {},
            # Older automatic documents did not persist the initial passive
            # snapshot. Their current state is the safest recovery baseline.
            'initial_passive_states': {
                side: copy.deepcopy((self.state['players'].get(side) or {}).get('passive_state') or {})
                for side in PLAYER_SIDES
            },
            'command_count': 0,
            'random_counter': 0,
            'id_counter': 0,
        }
        for key, value in defaults.items():
            engine.setdefault(key, copy.deepcopy(value))
        for passive_state in (engine.get('initial_passive_states') or {}).values():
            self._normalize_passive_state_keys(passive_state)
        for side in PLAYER_SIDES:
            engine['shields'].setdefault(side, [])
            engine['turn_damage_received'].setdefault(side, 0)
        if self.state.get('priority_player') not in PLAYER_SIDES:
            self.state['priority_player'] = 'p1'

    @staticmethod
    def _normalize_passive_state_keys(passive_state):
        if not isinstance(passive_state, dict):
            return
        for legacy_key, canonical_key in PASSIVE_STATE_KEY_ALIASES.items():
            legacy = passive_state.pop(legacy_key, None)
            if not isinstance(legacy, dict):
                continue
            current = passive_state.get(canonical_key)
            if not isinstance(current, dict):
                passive_state[canonical_key] = legacy
                continue
            if not current.get('label') and legacy.get('label'):
                current['label'] = legacy['label']

    @property
    def engine_state(self):
        return self.state['engine']

    def _normalize_passive_zone_cards(self):
        """Keep PS/Trait cards in their owner's public Passive Zone."""
        relocated = {side: [] for side in PLAYER_SIDES}
        for container_side in PLAYER_SIDES:
            zones = self.state['players'][container_side]['zones']
            for zone_name, cards in zones.items():
                retained = []
                for card in cards:
                    if is_passive_card(card):
                        owner = (
                            card.get('owner')
                            if card.get('owner') in PLAYER_SIDES
                            else container_side
                        )
                        card['owner'] = owner
                        normalize_passive_card(card)
                        if zone_name == 'passive' and owner == container_side:
                            retained.append(card)
                        else:
                            relocated[owner].append(card)
                    else:
                        retained.append(card)
                zones[zone_name] = retained
        for side in PLAYER_SIDES:
            passive_zone = self.state['players'][side]['zones']['passive']
            for card in passive_zone:
                normalize_passive_card(card)
            known_ids = {
                str(card.get('instance_id')) for card in passive_zone
                if card.get('instance_id')
            }
            for card in relocated[side]:
                instance_id = str(card.get('instance_id') or '')
                if instance_id and instance_id in known_ids:
                    continue
                passive_zone.append(card)
                if instance_id:
                    known_ids.add(instance_id)

    @property
    def is_waiting(self):
        clock = self.engine_state.get('clock') or {}
        return bool(
            self.engine_state.get('pending_decision')
            or clock.get('paused')
            or self.engine_state.get('rewind_request')
        )

    def emit(self, event_type, actor, payload=None, *, visibility='public'):
        event = {
            'id': self._next_id('event'),
            'type': str(event_type),
            'actor': actor,
            'payload': copy.deepcopy(payload or {}),
            'visibility': visibility,
            'created_at': self.now.isoformat(),
        }
        self.events.append(event)
        return event

    def _next_id(self, kind):
        counter = _number(self.engine_state.get('id_counter'))
        self.engine_state['id_counter'] = counter + 1
        return hashlib.sha256(f'{self.seed}:{kind}:{counter}'.encode()).hexdigest()[:32]

    # ------------------------------------------------------------------
    # Legal actions and command dispatch

    def _action(self, action_type, *, label='', payload=None, **extra):
        core = {'type': action_type, 'payload': copy.deepcopy(payload or {})}
        encoded = json.dumps(
            {'state': self._action_revision(), **core},
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        )
        action = {
            'action_id': hashlib.sha256(encoded.encode()).hexdigest()[:32],
            'type': action_type,
            'label': label or action_type,
            **core,
        }
        action.update(extra)
        return action

    def _action_revision(self):
        engine = self.engine_state
        return {
            'turn': self.state.get('turn'),
            'phase': self.state.get('phase'),
            'step': engine.get('step'),
            'decision': (engine.get('pending_decision') or {}).get('id'),
        }

    def legal_actions(self, role):
        if role not in PLAYER_SIDES or self.engine_state.get('status') != 'running':
            return []
        self._refresh_continuous_rules()
        engine = self.engine_state
        actions = []
        rewind = engine.get('rewind_request')
        if rewind:
            if rewind.get('requested_by') != role:
                actions.extend([
                    self._action('answer_rewind', label='되감기 수락', payload={'accept': True}),
                    self._action('answer_rewind', label='되감기 거절', payload={'accept': False}),
                ])
            return actions
        clock = engine.get('clock') or {}
        if clock.get('paused'):
            actions.append(self._action('resume_clock', label='타이머 재개'))
            return actions
        decision = engine.get('pending_decision')
        if decision:
            if decision.get('owner') == role:
                actions.append(self._action(
                    'submit_decision',
                    label=decision.get('prompt') or '선택 확정',
                    payload={'decision_id': decision.get('id')},
                    options=self._decision_options_for(role, decision),
                    minimum=decision.get('minimum', 1),
                    maximum=decision.get('maximum', 1),
                ))
            elif clock.get('owner') == decision.get('owner'):
                actions.append(self._action('pause_clock', label='선택 타이머 일시정지'))
            return actions

        phase = self.state.get('phase')
        step = engine.get('step')
        if phase == 'ready' and step == 'ready_actions':
            ready = engine.get('ready_cards') or {}
            forced_first = engine.get('forced_ready_first')
            if forced_first in PLAYER_SIDES and forced_first not in ready and role != forced_first:
                return actions
            if role not in ready:
                ready_cards = [card for card in self._zone(role, 'hand') if self._legal_ready_card(card)]
                forced_id = (engine.get('forced_ready_cards') or {}).get(role)
                if forced_id:
                    ready_cards = [
                        card for card in ready_cards
                        if card.get('instance_id') == forced_id
                    ]
                for card in ready_cards:
                    actions.append(self._action(
                        'ready_card', label=card.get('name') or '카드 레디',
                        payload={'card_instance_id': card.get('instance_id')},
                        card=self._public_action_card(card),
                    ))
                if not ready_cards:
                    actions.append(self._action('declare_no_response', label='사용 가능한 카드 없음'))
            if clock.get('owner') and clock.get('owner') != role:
                actions.append(self._action('pause_clock', label='레디 타이머 일시정지'))
        elif phase in {'lumen', 'recovery'} and step == 'phase_actions':
            if role not in (engine.get('phase_passes') or []):
                actions.append(self._action('pass_phase', label='페이즈 종료'))
        elif phase == 'get' and step == 'get_actions':
            if role == engine.get('current_actor'):
                if role in (engine.get('forced_get_designators') or {}):
                    return actions
                for card in self._zone(role, 'list'):
                    if not _is_special(card) and not self._rule_blocked('get_card', role, card):
                        actions.append(self._action(
                            'select_get_card', label=card.get('name') or '카드 획득',
                            payload={'card_instance_id': card.get('instance_id')},
                            card=self._public_action_card(card),
                        ))
                for card in self._zone(role, 'ultimate'):
                    if _is_special(card) or self._rule_blocked('get_card', role, card):
                        continue
                    actions.append(self._action(
                        'select_ultimate', label=card.get('name') or '얼티밋 획득',
                        payload={'card_instance_id': card.get('instance_id')},
                        card=self._public_action_card(card),
                    ))
                actions.append(self._action('pass_phase', label='획득하지 않음'))
        elif phase == 'battle' and step == 'combo':
            combo = engine.get('combo') or {}
            if combo.get('owner') == role and not combo.get('proposal_submitted'):
                combo_actions = self._combo_actions(role, combo, staged=True)
                actions.extend(combo_actions)
                initial_pair_pending = not (combo.get('used') or [])
                if not initial_pair_pending and not (
                    combo_actions
                    and self._required_combo_followup_rules(role, combo)
                ):
                    actions.append(self._action('end_combo', label='콤보 종료'))
        elif phase == 'battle' and step == 'catch':
            catch = engine.get('catch') or {}
            if catch.get('owner') == role:
                for option in self._legal_catch_options(role, catch):
                    card = option['card']
                    optional_speed = option.get('optional_fixed_speed')
                    cost = option.get('counter_cost') or {}
                    suffix = ''
                    if optional_speed is not None:
                        suffix = f' ({optional_speed}속도'
                        if cost:
                            suffix += f'·{cost.get("counter")} {cost.get("amount")}개'
                        suffix += ')'
                    payload = {'card_instance_id': card.get('instance_id')}
                    choice_speed = (
                        option.get('fixed_speed')
                        if option.get('fixed_speed') is not None
                        else self.card_stat(card, 'frame', role, include_fp=False)
                    )
                    payload['choice_speed'] = choice_speed
                    if option.get('catch_rule_index') is not None:
                        payload['catch_rule_index'] = option['catch_rule_index']
                    actions.append(self._action(
                        'play_catch_card',
                        label=(card.get('name') or '캐치 사용') + suffix,
                        payload=payload,
                        card=self._private_action_card(card),
                        choice_speed=choice_speed,
                    ))
                exemption = self._catch_source_break_exemption(role, catch)
                if exemption:
                    counter_key = exemption['counter']
                    for option in self._legal_catch_options(
                        role, catch, counter_exemptions={counter_key},
                    ):
                        card = option['card']
                        optional_speed = option.get('optional_fixed_speed')
                        suffix = ' (원본 브레이크'
                        if optional_speed is not None:
                            suffix += f'·{optional_speed}속도'
                        suffix += f'·{counter_key} 미소모)'
                        payload = {
                            'card_instance_id': card.get('instance_id'),
                            'source_break_counter_exemption': counter_key,
                        }
                        choice_speed = (
                            option.get('fixed_speed')
                            if option.get('fixed_speed') is not None
                            else self.card_stat(
                                card, 'frame', role, include_fp=False,
                            )
                        )
                        payload['choice_speed'] = choice_speed
                        if option.get('catch_rule_index') is not None:
                            payload['catch_rule_index'] = option['catch_rule_index']
                        actions.append(self._action(
                            'play_catch_card',
                            label=(card.get('name') or '캐치 사용') + suffix,
                            payload=payload,
                            card=self._private_action_card(card),
                            choice_speed=choice_speed,
                        ))
                actions.append(self._action('decline_catch', label='캐치 종료'))
        if not decision and not rewind:
            if (
                (engine.get('settings') or {}).get('rewind_enabled', False)
                and engine.get('last_rewindable_command_id')
            ):
                actions.append(self._action('request_rewind', label='직전 명령 되감기 요청'))
            actions.append(self._action('concede', label='기권'))
        return actions

    def list_legal_actions(self, role):
        """Stable AI-facing alias for the human legal-action contract."""
        return self.legal_actions(role)

    def submit_action(self, role, action_id, selections=None, *, command_id=''):
        if role not in PLAYER_SIDES:
            raise IllegalAction('플레이어 역할만 명령을 실행할 수 있습니다.')
        legal = {action['action_id']: action for action in self.legal_actions(role)}
        action = legal.get(str(action_id or ''))
        if not action:
            raise IllegalAction('현재 합법 행동이 아니거나 만료된 action_id입니다.')
        selections = copy.deepcopy(selections or {})
        self.engine_state['command_count'] = _number(self.engine_state.get('command_count')) + 1
        self.engine_state['resolution_steps'] = 0
        self.emit('command', role, {
            'command_id': str(command_id or ''),
            'action_type': action['type'],
        })
        self._dispatch(role, action, selections)
        self._continue()
        return self.state, self.events

    def _dispatch(self, role, action, selections):
        action_type = action['type']
        payload = action.get('payload') or {}
        if action_type == 'pass_phase':
            self._pass_phase(role)
        elif action_type == 'ready_card':
            self._ready_card(role, payload['card_instance_id'])
        elif action_type == 'declare_no_response':
            self._declare_no_response(role)
        elif action_type in {'select_get_card', 'select_ultimate'}:
            self._get_card(role, payload['card_instance_id'])
        elif action_type == 'submit_decision':
            self._submit_decision(role, payload['decision_id'], selections.get('selected') or [])
        elif action_type == 'select_combo_first':
            combo = self.engine_state.get('combo') or {}
            if combo.get('owner') != role or combo.get('used'):
                raise IllegalAction('첫 콤보 카드를 선택할 수 있는 시점이 아닙니다.')
            combo['initial_selection'] = {
                'card_instance_id': payload.get('card_instance_id'),
                'combo_speed': payload.get('combo_speed'),
                'ignore_damage_penalty': bool(payload.get('ignore_damage_penalty')),
                'ignore_speed': bool(payload.get('ignore_speed')),
            }
            self.emit('combo_first_selected', role, copy.deepcopy(combo['initial_selection']))
        elif action_type == 'cancel_combo_first':
            combo = self.engine_state.get('combo') or {}
            if combo.get('owner') != role or not combo.get('initial_selection'):
                raise IllegalAction('취소할 첫 콤보 선택이 없습니다.')
            combo.pop('initial_selection', None)
            self.emit('combo_first_selection_cancelled', role, {})
        elif action_type == 'select_combo_followup':
            proposal = payload.get('proposal') or {}
            card_ids = proposal.get('card_instance_ids') or []
            combo_speeds = proposal.get('combo_speeds') or []
            ignore_damage_penalty = proposal.get('ignore_damage_penalty') or [False] * len(card_ids)
            ignore_speed = proposal.get('ignore_speed') or [False] * len(card_ids)
            self._play_combo(
                role, list(card_ids), list(combo_speeds),
                list(ignore_damage_penalty), list(ignore_speed),
            )
        elif action_type in {'play_combo_sequence', 'play_combo_pair', 'play_combo_card'}:
            card_ids = payload.get('card_instance_ids') or [payload.get('card_instance_id')]
            combo_speeds = payload.get('combo_speeds') or [payload.get('combo_speed')]
            ignore_damage_penalty = payload.get('ignore_damage_penalty') or [False] * len(card_ids)
            ignore_speed = payload.get('ignore_speed') or [False] * len(card_ids)
            self._play_combo(
                role, [item for item in card_ids if item],
                [item for item in combo_speeds if item is not None],
                list(ignore_damage_penalty),
                list(ignore_speed),
            )
        elif action_type == 'end_combo':
            self.end_combo()
        elif action_type == 'play_catch_card':
            self._play_catch(
                role, payload['card_instance_id'],
                catch_rule_index=payload.get('catch_rule_index'),
                source_break_counter_exemption=payload.get(
                    'source_break_counter_exemption',
                ),
            )
        elif action_type == 'decline_catch':
            self.end_catch()
        elif action_type == 'pause_clock':
            self._pause_clock(role, str(selections.get('reason') or '').strip())
        elif action_type == 'resume_clock':
            self._resume_clock(role)
        elif action_type == 'request_rewind':
            if not (self.engine_state.get('settings') or {}).get('rewind_enabled', False):
                raise IllegalAction('이 자동 대전에서는 되감기를 사용하지 않습니다.')
            self._request_rewind(role)
        elif action_type == 'answer_rewind':
            self._answer_rewind(role, bool(payload.get('accept')))
        elif action_type == 'concede':
            self._finish(opponent(role), 'concede')
        else:
            raise IllegalAction('지원하지 않는 자동 행동입니다.')

    # ------------------------------------------------------------------
    # Phase machine and battle pipeline

    def _continue(self):
        for _ in range(MAX_RESOLUTION_STEPS):
            if self.engine_state.get('status') != 'running' or self.is_waiting:
                return
            hand_adjustments = self.engine_state.get(
                'hand_adjustment_queue',
            ) or []
            if hand_adjustments:
                side = hand_adjustments.pop(0)
                self._start_hand_limit_adjustment(side)
                if self.is_waiting:
                    return
                continue
            if self.engine_state.get('resolution_queue'):
                if not self.resolver.drain():
                    return
                continue
            restarted_phase = self.engine_state.pop('phase_restart_pending_start', None)
            if restarted_phase in PHASES:
                self._refresh_continuous_rules()
                self._fire('phase_start', {
                    'phase': restarted_phase,
                    'restarted': True,
                })
                continue
            domain_queue = self.engine_state.get('domain_queue') or []
            if domain_queue:
                item = domain_queue.pop(0)
                if item.get('kind') == 'damage':
                    self._advance_damage(item)
                elif item.get('kind') == 'victory_check':
                    self._check_victory()
                elif item.get('kind') == 'play_resume':
                    play = item.get('play') or {}
                    role = item.get('role')
                    if play.get('kind') == 'ready':
                        self._ready_card(role, play.get('card_instance_id'), cost_paid=True)
                    elif play.get('kind') == 'combo':
                        self._start_combo_card(
                            role, play.get('card_ids') or [], play.get('combo_speeds') or [],
                            play.get('ignore_damage_penalty') or [],
                            play.get('ignore_speed') or [],
                            cost_paid_for=play.get('card_instance_id'),
                        )
                    elif play.get('kind') == 'catch':
                        self._play_catch(
                            role, play.get('card_instance_id'),
                            cost_paid=bool(play.get('cost_paid', True)),
                            catch_rule_index=play.get('catch_rule_index'),
                            source_break_counter_exemption=play.get(
                                'source_break_counter_exemption',
                            ),
                            source_break_paid=bool(
                                play.get('source_break_paid'),
                            ),
                        )
                elif item.get('kind') == 'combo_speed_resume':
                    play = item.get('play') or {}
                    role = item.get('role')
                    self._start_combo_card(
                        role, play.get('card_ids') or [],
                        play.get('combo_speeds') or [],
                        play.get('ignore_damage_penalty') or [],
                        play.get('ignore_speed') or [],
                        cost_paid_for=play.get('cost_paid_for'),
                        speed_cost_paid_for=play.get(
                            'speed_cost_paid_for'
                        ),
                    )
                continue
            deferred = self.engine_state.get('deferred_effects') or []
            if deferred:
                item = deferred.pop(0)
                self.resolver.execute_effects(item.get('effects'), item.get('context') or {})
                continue
            replenishments = self.engine_state.get('break_replenishment_queue') or []
            if replenishments:
                owner = replenishments.pop(0)
                self._start_break_replenishment(owner)
                if self.is_waiting:
                    return
                continue
            pipeline = self.engine_state.get('pipeline')
            if pipeline:
                if not self._advance_pipeline(pipeline):
                    return
                continue
            if self._advance_startup_stage():
                continue
            if self._settle_replaced_get_action():
                continue
            if self._auto_advance_actionless_phase():
                continue
            return
        raise EngineError('자동 진행 단계 제한을 초과했습니다.')

    def _advance_startup_stage(self):
        """Open initial timing windows only after the previous one settles."""
        stage = self.engine_state.get('startup_stage')
        if stage == 'after_game_start':
            self.engine_state['startup_stage'] = 'after_turn_start'
            self._fire('turn_start', {'turn': self.state.get('turn', 1)})
            return True
        if stage == 'after_turn_start':
            self.engine_state.pop('startup_stage', None)
            self._refresh_continuous_rules()
            self._fire('phase_start', {
                'phase': 'lumen', 'turn': self.state.get('turn', 1),
                'first_turn': True,
            })
            return True
        return False

    def _auto_advance_actionless_phase(self):
        settings = self.engine_state.get('settings') or {}
        if not settings.get('auto_advance_empty_phases', False):
            return False
        phase = self.state.get('phase')
        step = self.engine_state.get('step')
        if phase in {'lumen', 'recovery'} and step == 'phase_actions':
            self.emit('phase_auto_advanced', 'system', {
                'phase': phase, 'reason': 'no_player_action',
            })
            self._advance_phase()
            return True
        if phase != 'get' or step != 'get_actions':
            return False
        role = self.engine_state.get('current_actor')
        if role not in PLAYER_SIDES:
            return False
        if role in (self.engine_state.get('forced_get_designators') or {}):
            return False
        has_get = any(
            not _is_special(card)
            and not self._rule_blocked('get_card', role, card)
            for card in self._zone(role, 'list')
        ) or any(
            not self._rule_blocked('get_card', role, card)
            for card in self._zone(role, 'ultimate')
        )
        if has_get:
            return False
        self.emit('phase_auto_advanced', 'system', {
            'phase': phase, 'player': role, 'reason': 'no_get_action',
        })
        self._finish_get_action(role, None)
        return True

    def _pass_phase(self, role):
        phase = self.state.get('phase')
        if phase == 'get':
            if role != self.engine_state.get('current_actor'):
                raise IllegalAction('현재 우선권 플레이어의 Get 차례입니다.')
            self._finish_get_action(role, None)
            return
        passed = self.engine_state.setdefault('phase_passes', [])
        if role in passed:
            raise IllegalAction('이미 이 페이즈를 종료했습니다.')
        passed.append(role)
        self.emit('phase_passed', role, {'phase': phase})
        if all(side in passed for side in PLAYER_SIDES):
            self._advance_phase()

    def restart_phase_without_ending_battle(self, phase):
        """Restart a phase while preserving battle-scoped effects and usage."""
        if phase != 'ready' or self.state.get('phase') != 'battle':
            self.engine_state['repeat_phase'] = phase
            return
        engine = self.engine_state
        previous = self.state.get('phase')
        # Returning to Ready is part of the resolving effect. Remaining effects
        # at the old timing miss their window, and no battle-end expiration is
        # performed because the same battle phase continues (Q&A 67/404/626).
        engine['resolution_queue'] = []
        engine['resolution_order_groups'] = {}
        engine['deferred_effects'] = []
        engine['domain_queue'] = []
        engine['pending_decision'] = None
        engine['pipeline'] = None
        engine['ready_cards'] = {}
        engine['battle'] = {}
        engine['combo'] = None
        engine['catch'] = None
        engine['granted_catches'] = []
        engine['current_actor'] = None
        engine['phase_passes'] = []
        engine['phase_skipped_players'] = []
        engine['step'] = 'ready_actions'
        engine['defense_over_count'] = 0
        engine.pop('catch_fp_history', None)
        engine.pop('combo_source_ids', None)
        engine.pop('end_battle_requested', None)
        self._clear_clock()
        self.state['phase'] = 'ready'
        self.emit('phase_restarted', 'system', {
            'from_phase': previous,
            'phase': 'ready',
            'turn': self.state.get('turn'),
            'battle_continues': True,
        })
        self.emit('phase_started', 'system', {
            'phase': 'ready',
            'turn': self.state.get('turn'),
            'restarted': True,
        })
        engine['phase_restart_pending_start'] = 'ready'

    def _advance_phase(
        self, explicit=None, *, phase_end_resolved=False,
        state_expiration_resolved=False,
    ):
        current = self.state.get('phase')
        engine = self.engine_state
        if not phase_end_resolved:
            phase_end_context = {'phase': current}
            skipped_controllers = list(engine.get('phase_skipped_players') or [])
            if current == 'get':
                skipped_controllers = list(dict.fromkeys([
                    *skipped_controllers,
                    *(engine.get('get_skipped_players') or []),
                ]))
            if skipped_controllers:
                phase_end_context['excluded_controllers'] = skipped_controllers
            self._fire('phase_end', phase_end_context)
            if self.is_waiting:
                self.engine_state['pipeline'] = {'kind': 'phase_advance', 'explicit': explicit}
                return
        if not state_expiration_resolved:
            self._expire_state_durations('phase_end', phase=current)
            if self.is_waiting:
                self.engine_state['pipeline'] = {
                    'kind': 'phase_advance', 'explicit': explicit,
                    'state_expiration_resolved': True,
                }
                return
        self._expire_modifiers('phase')
        self._reset_usage('phase')
        if current == 'get':
            engine.pop('get_skipped_players', None)
            for side in PLAYER_SIDES:
                for card in self._zone(side, 'hand'):
                    if card.pop('hide_after_get', False):
                        card['face_up'] = False
        end_turn_requested = bool(engine.pop('end_turn_requested', False))
        repeated = engine.pop('repeat_phase', None)
        if end_turn_requested:
            next_phase = 'lumen'
            if not self._complete_turn():
                return
        elif repeated in PHASES:
            next_phase = repeated
        elif explicit:
            next_phase = explicit
        elif current == 'recovery':
            next_phase = 'lumen'
            if not self._complete_turn():
                return
        else:
            next_phase = PHASES[min(PHASES.index(current) + 1, len(PHASES) - 1)]
        while next_phase != 'lumen' and self._phase_skipped(next_phase):
            self.emit('phase_skipped', 'system', {'phase': next_phase})
            if next_phase == 'recovery':
                if not self._complete_turn():
                    return
                next_phase = 'lumen'
            else:
                next_phase = PHASES[PHASES.index(next_phase) + 1]
        skipped_players = self._consume_phase_skip_players(next_phase) if next_phase == 'lumen' else []
        if next_phase == 'get':
            self._recalculate_priority()
        self.state['phase'] = next_phase
        engine['phase_passes'] = list(skipped_players)
        engine['phase_skipped_players'] = list(skipped_players)
        engine['step'] = {
            'ready': 'ready_actions', 'get': 'get_actions',
        }.get(next_phase, 'phase_actions')
        engine['current_actor'] = None
        if next_phase == 'ready':
            engine['ready_cards'] = {}
            self._clear_clock()
            forced_first = engine.get('forced_ready_first')
            if forced_first in PLAYER_SIDES:
                # Third Eye treats its controller as already Ready for timer
                # purposes: the designated opponent receives the first
                # configured Ready window immediately (Q&A 228).
                self._start_clock(
                    'ready', owner=forced_first,
                    seconds=self._timeout_seconds(
                        'ready_timeout_seconds', DEFAULT_READY_SECONDS,
                    ),
                )
        elif next_phase == 'battle':
            engine['step'] = 'battle_pipeline'
            engine['pipeline'] = {'kind': 'battle', 'stage': 'start'}
        elif next_phase == 'get':
            engine['replaced_get'] = {}
            skip_get = engine.get('skip_get') or {}
            ordered_players = [
                self.state['priority_player'],
                opponent(self.state['priority_player']),
            ]
            engine['get_skipped_players'] = [
                side for side in ordered_players if skip_get.get(side, False)
            ]
            engine['get_order'] = [
                side for side in ordered_players
                if not skip_get.pop(side, False)
            ]
            engine['get_done'] = []
            engine['current_actor'] = engine['get_order'][0] if engine['get_order'] else None
        elif next_phase == 'recovery':
            self._recovery_core()
        self.emit('phase_started', 'system', {'phase': next_phase, 'turn': self.state.get('turn')})
        for side in skipped_players:
            self.emit('phase_skipped', side, {'phase': next_phase, 'player': side})
        self._refresh_continuous_rules()
        phase_start_context = {'phase': next_phase}
        if skipped_players:
            phase_start_context['excluded_controllers'] = list(skipped_players)
        self._fire('phase_start', phase_start_context)
        if next_phase == 'get' and not self.is_waiting:
            self._open_forced_get_decision()
        if next_phase == 'get' and not engine.get('get_order') and not self.is_waiting:
            self._advance_phase('recovery')
        if (
            next_phase == 'lumen'
            and all(side in (engine.get('phase_passes') or []) for side in PLAYER_SIDES)
            and not self.is_waiting
        ):
            self._advance_phase()

    def _complete_turn(self):
        previous_turn = _number(self.state.get('turn'), 1)
        self.state['turn'] = previous_turn + 1
        if self.engine_state.get('sudden_death'):
            remaining = _number(self.engine_state.get('sudden_death_turns_remaining'), 3) - 1
            self.engine_state['sudden_death_turns_remaining'] = remaining
            if remaining <= 0:
                self._resolve_sudden_death()
                if self.engine_state.get('status') != 'running':
                    return False
        self._fire('turn_end', {'turn': previous_turn})
        forced_get = self.engine_state.setdefault(
            'forced_get_designators', {},
        )
        forced_get_turns = self.engine_state.setdefault(
            'forced_get_turns', {},
        )
        for beneficiary in list(forced_get):
            scheduled_turn = _number(
                forced_get_turns.get(beneficiary), previous_turn,
            )
            if scheduled_turn > previous_turn:
                continue
            chooser = forced_get.pop(beneficiary, None)
            forced_get_turns.pop(beneficiary, None)
            self.emit('forced_get_expired', chooser or 'system', {
                'beneficiary': beneficiary, 'turn': previous_turn,
            })
        self.engine_state.pop('forced_ready_first', None)
        self.engine_state.pop('forced_ready_first_source', None)
        self.engine_state.pop('forced_ready_cards', None)
        self.engine_state.pop('forced_ready_card_sources', None)
        self._expire_modifiers('turn')
        for side in PLAYER_SIDES:
            for cards in self.state['players'][side]['zones'].values():
                for card in cards:
                    if card.get('move_to_hand_blocked_until') == 'turn':
                        card.pop('move_to_hand_blocked_until', None)
                    blocked_through = card.get('move_to_hand_blocked_through_turn')
                    if (
                        blocked_through is not None
                        and _number(blocked_through) < _number(self.state.get('turn'), 1)
                    ):
                        card.pop('move_to_hand_blocked_through_turn', None)
        self._reset_usage('turn')
        self.engine_state['turn_damage_received'] = {side: 0 for side in PLAYER_SIDES}
        self._fire('turn_start', {'turn': self.state['turn']})
        return self.engine_state.get('status') == 'running'

    def _advance_pipeline(self, pipeline):
        if pipeline.get('kind') == 'phase_advance':
            self.engine_state['pipeline'] = None
            self._advance_phase(
                pipeline.get('explicit'), phase_end_resolved=True,
                state_expiration_resolved=bool(
                    pipeline.get('state_expiration_resolved'),
                ),
            )
            return True
        if pipeline.get('kind') == 'battle':
            return self._advance_battle_pipeline(pipeline)
        if pipeline.get('kind') == 'catch_resolution':
            return self._advance_catch_pipeline(pipeline)
        if pipeline.get('kind') == 'catch_end':
            return self._advance_catch_end_pipeline(pipeline)
        if pipeline.get('kind') == 'combo_resolution':
            return self._advance_combo_pipeline(pipeline)
        if pipeline.get('kind') == 'combo_end':
            return self._advance_combo_end_pipeline(pipeline)
        if pipeline.get('kind') == 'mutual_combo_end':
            return self._advance_mutual_combo_end_pipeline(pipeline)
        if pipeline.get('kind') == 'battle_cleanup':
            return self._advance_cleanup_pipeline(pipeline)
        if pipeline.get('kind') == 'no_response':
            return self._advance_no_response_pipeline(pipeline)
        return False

    def _ready_card(self, role, instance_id, *, cost_paid=False):
        if role in self.engine_state.get('ready_cards', {}):
            raise IllegalAction('이미 카드를 레디했습니다.')
        forced_first = self.engine_state.get('forced_ready_first')
        if (
            forced_first in PLAYER_SIDES and forced_first != role
            and forced_first not in self.engine_state.get('ready_cards', {})
        ):
            raise IllegalAction('상대가 지정된 기술을 먼저 레디해야 합니다.')
        forced_id = (self.engine_state.get('forced_ready_cards') or {}).get(role)
        if forced_id and forced_id != instance_id:
            raise IllegalAction('공개된 지정 기술을 레디해야 합니다.')
        card = self._find_card(instance_id, owner=role, zone='hand')
        if not card or not self._legal_ready_card(card, ignore_cost=cost_paid):
            raise IllegalAction('레디할 수 없는 카드입니다.')
        if not cost_paid and self._begin_play_cost(
            role, card, 'ready', {'kind': 'ready', 'card_instance_id': instance_id},
        ):
            return
        self.move_card(instance_id, 'battle', reason='ready')
        card['face_up'] = False
        self._mark_card_used(card, role, 'ready')
        self.engine_state['ready_cards'][role] = instance_id
        if forced_id == instance_id:
            self.engine_state.setdefault('forced_ready_cards', {}).pop(role, None)
            self.engine_state.setdefault('forced_ready_card_sources', {}).pop(role, None)
        if forced_first == role:
            self.engine_state.pop('forced_ready_first', None)
            self.engine_state.pop('forced_ready_first_source', None)
        self.emit('card_readied', role, {
            'card_instance_id': instance_id,
            'card_id': card.get('card_id'),
            'card_code': card.get('code'),
            'card_label': card.get('name') or card.get('code') or '카드',
        }, visibility='private')
        self._fire('ready', {'controller': role, 'source_card_instance_id': instance_id, 'source_card': card})
        other = opponent(role)
        if other not in self.engine_state['ready_cards']:
            self._start_clock(
                'ready', owner=other,
                seconds=self._timeout_seconds(
                    'ready_timeout_seconds', DEFAULT_READY_SECONDS,
                ),
            )
        else:
            self._clear_clock()
            other_card = self._find_card(self.engine_state['ready_cards'][other])
            if other_card and other_card.get('virtual'):
                self._request_virtual_result(other, role)
            else:
                self._advance_phase('battle')

    def _advance_battle_pipeline(self, pipeline):
        stage = pipeline.get('stage')
        if stage == 'start':
            battle = {}
            for side in PLAYER_SIDES:
                instance_id = (self.engine_state.get('ready_cards') or {}).get(side)
                card = self._find_card(instance_id, owner=side, zone='battle')
                if not card:
                    raise EngineError('배틀 카드가 없습니다.')
                card['face_up'] = True
                for set_card in self._zone(side, 'battle'):
                    if set_card.get('attached_to') == instance_id:
                        set_card['face_up'] = True
                battle[side] = {'card': copy.deepcopy(card), 'instance_id': instance_id}
            self.engine_state['battle'] = battle
            battle['starting_fp'] = {
                side: _number(self.state['players'][side].get('fp')) for side in PLAYER_SIDES
            }
            battle['effect_count_before'] = sum(1 for event in self.events if event.get('type') == 'effect_resolved')
            battle['fp_event_count_before'] = sum(1 for event in self.events if event.get('type') == 'fp_changed')
            battle['damage_event_count_before'] = sum(1 for event in self.events if event.get('type') == 'damage_dealt')
            battle['actual_damage_received'] = {side: 0 for side in PLAYER_SIDES}
            self.emit('battle_revealed', 'system', {
                side: {
                    'card_instance_id': battle[side]['instance_id'],
                    'card_id': battle[side]['card'].get('card_id'),
                    'card_code': battle[side]['card'].get('code'),
                    'card_type': battle[side]['card'].get('type'),
                    'card_label': (
                        battle[side]['card'].get('name')
                        or battle[side]['card'].get('code')
                        or '카드'
                    ),
                }
                for side in PLAYER_SIDES
            })
            pipeline['stage'] = 'reveal_cost'
            return True
        if stage == 'reveal_cost':
            # Some printed use requirements (for example LMI-AT-027, Q&A
            # 434/480) are paid after both Techniques are revealed but before
            # the normal ``use`` timing window. Card-selection costs use the
            # same window so the opponent cannot learn the payment during
            # Ready (LMI-AT-010, Q&A 222/526).
            if self._offer_next_battle_reveal_play_cost(pipeline):
                return False
            pipeline['stage'] = 'use'
            self._battle_trigger('battle_reveal')
            return not self.is_waiting
        if stage == 'use':
            self._battle_trigger('use')
            if self.engine_state.pop('end_battle_requested', False):
                return self._cleanup_battle()
            pipeline['stage'] = 'before_judgment'
            return not self.is_waiting
        if stage == 'before_judgment':
            self._battle_trigger('before_judgment')
            if self.engine_state.pop('end_battle_requested', False):
                return self._cleanup_battle()
            pipeline['stage'] = 'defense_cost'
            return not self.is_waiting
        if stage == 'defense_cost':
            if self._offer_next_defense_cost(pipeline):
                return False
            pipeline['stage'] = 'speed_capture'
            return True
        if stage == 'speed_capture':
            self._capture_battle_speed()
            pipeline['speed_reset_index'] = 0
            pipeline['stage'] = 'speed_reset'
            return True
        if stage == 'speed_reset':
            index = _number(pipeline.get('speed_reset_index'))
            order = self._priority_order()
            if index < len(order):
                side = order[index]
                pipeline['speed_reset_index'] = index + 1
                entry = self.engine_state['battle'][side]
                self.set_fp(side, 0, source='battle_speed', context={
                    'controller': side, 'source_card_instance_id': entry['instance_id'],
                    'source_card': entry['card'],
                })
                return not self.is_waiting
            pipeline['stage'] = 'grab_negation'
            return True
        if stage == 'grab_negation':
            pipeline['stage'] = 'judgment'
            if self._offer_grab_negation():
                return False
            return True
        if stage == 'judgment':
            self._resolve_battle_judgment()
            pipeline['trigger_index'] = 0
            pipeline['stage'] = 'result_triggers'
            return True
        if stage == 'result_triggers':
            triggers = self.engine_state['battle'].get('trigger_sequence') or []
            index = _number(pipeline.get('trigger_index'))
            if index < len(triggers):
                event_type, context = triggers[index]
                pipeline['trigger_index'] = index + 1
                self._fire(event_type, context)
                return not self.is_waiting
            late_combo_triggers = self._late_combo_result_triggers()
            if late_combo_triggers:
                triggers.extend(late_combo_triggers)
                return True
            pipeline['stage'] = 'damage'
            return True
        if stage == 'damage':
            self._prepare_battle_outcomes()
            pipeline['stage'] = 'outcomes'
            return True
        if stage == 'outcomes':
            outcomes = self.engine_state['battle'].get('outcome_queue') or []
            if outcomes:
                outcome = outcomes.pop(0)
                self._apply_battle_outcome(outcome)
                return not self.is_waiting
            if not self.engine_state['battle'].get('damage_prepared'):
                self._prepare_battle_damage_outcomes()
                return True
            self._check_victory()
            pipeline['stage'] = 'after_judgment'
            return True
        if stage == 'after_judgment':
            self._battle_trigger('after_judgment')
            pipeline['stage'] = 'after_use'
            return not self.is_waiting
        if stage == 'after_use':
            self._battle_trigger('after_use')
            if self.engine_state.pop('end_battle_requested', False):
                return self._cleanup_battle()
            pipeline['stage'] = 'combo'
            return not self.is_waiting
        if stage == 'combo':
            self.engine_state['pipeline'] = None
            combo_result = self._open_combo_from_battle()
            if combo_result == 'mutual':
                return not self.is_waiting
            if combo_result:
                return False
            self._open_catch_or_cleanup()
            return not self.is_waiting
        return False

    def _battle_trigger(self, event_type):
        # Re-evaluate numberless/continuous effects at every battle timing
        # boundary.  A state gained during ``use`` can immediately change the
        # cards which a ``before_judgment`` condition observes (for example
        # Dark Night removing the opposing Technique's special judgments,
        # Q&A 584).
        self._refresh_continuous_rules()
        for side in self._priority_order():
            if (
                self.state.get('phase') != 'battle'
                or side not in (self.engine_state.get('battle') or {})
            ):
                break
            entry = self.engine_state['battle'][side]
            other_entry = self.engine_state['battle'][opponent(side)]
            # A revealed Technique whose mandatory use cost could not be paid
            # is adjudicated as invalid. It still participates in the later
            # core judgment as a failed Technique, but owns no battle-timing
            # effect windows of its own (LMI-AT-010, Q&A 222/526/588).
            if (entry.get('card') or {}).get('technique_invalidated'):
                continue
            battle_result = (
                (self.engine_state['battle'].get('result') or {}).get(side)
            )
            judgment_field = (
                'hit' if battle_result == 'clash' else battle_result
            )
            combo_judgment = bool(
                battle_result in {'hit', 'counter', 'clash'}
                and str((entry.get('card') or {}).get(judgment_field) or '')
                == '콤보'
            )
            self._fire(event_type, {
                'controller': side,
                'source_card_instance_id': entry['instance_id'],
                'source_card': entry['card'],
                'opponent_card': other_entry['card'],
                'result': battle_result,
                'combo_judgment': combo_judgment,
                'combo_number': 1 if combo_judgment else None,
                'use_context': 'ready',
                'controller_speed': self.card_stat(entry['card'], 'frame', side, include_fp=False),
                'opponent_speed': self.card_stat(
                    other_entry['card'], 'frame', opponent(side), include_fp=False,
                ),
                'controller_damage': self.card_stat(
                    entry['card'], 'damage', side, include_fp=False,
                ),
                'opponent_damage': self.card_stat(
                    other_entry['card'], 'damage', opponent(side),
                    include_fp=False,
                ),
                'controller_damage_received': _number(
                    (self.engine_state['battle'].get('actual_damage_received') or {}).get(side),
                ),
                'opponent_damage_received': _number(
                    (self.engine_state['battle'].get('actual_damage_received') or {}).get(opponent(side)),
                ),
                # Only this side's Battle Technique owns this timing slot.
                # Passive/Lumen/Ultimate reactions remain globally active.
                'source_battle_card_only': True,
            })
            if self.state.get('phase') != 'battle':
                break

    def _capture_battle_speed(self):
        battle = self.engine_state['battle']
        self._refresh_continuous_rules()
        reference_speed = {}
        final_speed = {}
        for side in PLAYER_SIDES:
            card = battle[side]['card']
            reference_speed[side] = self.card_stat(card, 'frame', side, include_fp=False)
            fixed = self._fixed_stat(card, 'frame', side)
            final_speed[side] = fixed if fixed is not None else max(1, reference_speed[side] - self.state['players'][side]['fp'])
        battle['reference_speed'] = reference_speed
        battle['speed'] = final_speed

    def _resolve_battle_judgment(self):
        battle = self.engine_state['battle']
        reference_speed = battle['reference_speed']
        final_speed = battle['speed']

        c1, c2 = battle['p1']['card'], battle['p2']['card']
        result = {'p1': 'none', 'p2': 'none'}
        invalidated = {
            'p1': bool(c1.get('technique_invalidated')),
            'p2': bool(c2.get('technique_invalidated')),
        }
        if invalidated['p1'] or invalidated['p2']:
            for side in PLAYER_SIDES:
                other = opponent(side)
                if invalidated[side]:
                    result[side] = 'failed_defense'
                elif invalidated[other] and _is_attack(battle[side]['card']):
                    result[side] = 'hit'
        elif _is_defense(c1) and _is_defense(c2):
            pass
        elif _is_attack(c1) and _is_defense(c2):
            result['p1'], result['p2'] = self._attack_vs_defense(c1, c2, 'p1', 'p2')
        elif _is_defense(c1) and _is_attack(c2):
            defender_result, attacker_result = self._attack_vs_defense(c2, c1, 'p2', 'p1')
            result['p1'], result['p2'] = attacker_result, defender_result
        elif _is_attack(c1) and _is_attack(c2):
            r1 = _special_result(c1, c2.get('pos'))
            r2 = _special_result(c2, c1.get('pos'))
            if not r1 and self._defense_judgment_allowed(
                c1, c2, 'clash', 'p2', grant_only=True,
            ):
                r1 = 'clash'
            if not r2 and self._defense_judgment_allowed(
                c2, c1, 'clash', 'p1', grant_only=True,
            ):
                r2 = 'clash'
            if r1 and not self._defense_judgment_allowed(c1, c2, r1, 'p2'):
                r1 = ''
            if r2 and not self._defense_judgment_allowed(c2, c1, r2, 'p1'):
                r2 = ''
            if r1 and self._rule_blocked(r1, 'p1', c1, c2):
                r1 = ''
            if r2 and self._rule_blocked(r2, 'p2', c2, c1):
                r2 = ''
            battle['pre_result_triggers'] = []
            if r1 == 'dodge' and r2 == 'dodge':
                result = {'p1': 'dodge', 'p2': 'dodge'}
            elif r1 == 'dodge':
                result = {'p1': 'counter', 'p2': 'countered'}
                battle['pre_result_triggers'] = [('dodge', 'p1'), ('opponent_dodge', 'p2')]
            elif r2 == 'dodge':
                result = {'p1': 'countered', 'p2': 'counter'}
                battle['pre_result_triggers'] = [('opponent_dodge', 'p1'), ('dodge', 'p2')]
            elif final_speed['p1'] == final_speed['p2']:
                result = {'p1': 'hit', 'p2': 'hit'}
            elif (
                reference_speed['p1'] > reference_speed['p2'] and r1 == 'clash'
            ) or (
                reference_speed['p2'] > reference_speed['p1'] and r2 == 'clash'
            ):
                result = {'p1': 'clash', 'p2': 'clash'}
            elif final_speed['p1'] < final_speed['p2']:
                result = {'p1': 'counter', 'p2': 'countered'}
            else:
                result = {'p1': 'countered', 'p2': 'counter'}
        forced = self.engine_state.pop('forced_no_response_result', None) or {}
        missing = forced.get('missing')
        if missing in PLAYER_SIDES:
            chooser = opponent(missing)
            result[chooser] = forced.get('result') if forced.get('result') in {'hit', 'counter'} else 'hit'
            result[missing] = 'failed_defense'
        battle['result'] = result
        for side in PLAYER_SIDES:
            self.engine_state.setdefault('battle_result_history', []).append({
                'turn': int(self.state.get('turn') or 1),
                'player': side,
                'result': result.get(side),
                'card': copy.deepcopy(battle[side]['card']),
                'opponent_card': copy.deepcopy(battle[opponent(side)]['card']),
            })
        battle['trigger_sequence'] = self._result_trigger_sequence(result, battle.get('pre_result_triggers'))
        self.emit('battle_judged', 'system', {
            'reference_speed': reference_speed,
            'speed': final_speed,
            'result': result,
            'cards': {
                side: {
                    'card_instance_id': battle[side]['instance_id'],
                    'card_id': battle[side]['card'].get('card_id'),
                    'card_code': battle[side]['card'].get('code'),
                    'card_type': battle[side]['card'].get('type'),
                    'card_label': (
                        battle[side]['card'].get('name')
                        or battle[side]['card'].get('code')
                        or '카드'
                    ),
                }
                for side in PLAYER_SIDES
            },
        })

    def _attack_vs_defense(self, attack, defense, attacker_side, defender_side):
        defense_result = _guard_result(defense, attack.get('pos'))
        if defense_result in {'dodge', 'clash'} and not self._defense_judgment_allowed(
            defense, attack, defense_result, attacker_side,
        ):
            defense_result = 'hit'
        if defense_result in {'dodge', 'guard', 'clash'} and self._rule_blocked(
            defense_result,
            defender_side,
            defense,
            attack,
        ):
            defense_result = 'hit'
        if defense_result == 'dodge':
            return 'opponent_dodge', 'dodge'
        if defense_result == 'guard':
            return 'guarded', 'guard'
        if defense_result == 'clash':
            return 'clash', 'clash'
        return 'hit', 'grabbed' if _has_grab(attack) else 'failed_defense'

    def _defense_judgment_allowed(
        self, defense, attack, judgment, attacker_side, *, grant_only=False,
    ):
        defender_side = opponent(attacker_side)
        if self._rule_blocked('defense_rule', defender_side, defense, attack):
            return True
        definition = self._definition_for_card(defense)
        rules = [
            (index, rule)
            for index, rule in enumerate(definition.get('defense_rules') or [])
            if isinstance(rule, dict)
            and not (
                rule.get('numbered_effect')
                and (defense or {}).get('numbered_effects_negated')
            )
            and rule.get('judgment', 'dodge') == judgment
            and rule.get('position') in {None, attack.get('pos')}
            and (not grant_only or rule.get('grant') is True)
        ]
        if not rules:
            return not grant_only
        speed = self.card_stat(attack, 'frame', attacker_side, include_fp=False)
        damage = self.card_stat(attack, 'damage', attacker_side, include_fp=False)
        for rule_index, rule in rules:
            rule_controller = defense.get('owner')
            context = {
                'controller': rule_controller,
                'opponent': opponent(rule_controller) if rule_controller in PLAYER_SIDES else attacker_side,
                'source_card': defense, 'opponent_card': attack,
                'controller_hp': self.state['players'][rule_controller].get('hp')
                if rule_controller in PLAYER_SIDES else None,
                'controller_fp': self.state['players'][rule_controller].get('fp')
                if rule_controller in PLAYER_SIDES else None,
                'opponent_hp': self.state['players'][attacker_side].get('hp')
                if attacker_side in PLAYER_SIDES else None,
                'opponent_fp': self.state['players'][attacker_side].get('fp')
                if attacker_side in PLAYER_SIDES else None,
                'controller_speed': self.card_stat(
                    defense, 'frame', rule_controller, include_fp=False,
                ) if rule_controller in PLAYER_SIDES else None,
                'opponent_speed': speed,
            }
            if not condition_matches(rule.get('condition'), self.state, context):
                continue
            if rule.get('min_speed') is not None and speed < _number(rule.get('min_speed')):
                continue
            if rule.get('max_speed') is not None and speed > _number(rule.get('max_speed')):
                continue
            if rule.get('min_damage') is not None and damage < _number(rule.get('min_damage')):
                continue
            if rule.get('max_damage') is not None and damage > _number(rule.get('max_damage')):
                continue
            if rule.get('min_hit') is not None and _fp_value(attack.get('hit')) < _number(rule.get('min_hit')):
                continue
            if rule.get('hit_values') and attack.get('hit') not in rule.get('hit_values'):
                continue
            if rule.get('where') and not card_matches(attack, rule.get('where')):
                continue
            if rule.get('cost') and not self._defense_cost_was_paid(
                defender_side, defense, rule_index,
            ):
                continue
            return True
        return False

    @staticmethod
    def _defense_cost_key(side, defense, rule_index):
        return ':'.join((
            str(side or ''), str((defense or {}).get('instance_id') or ''),
            str(int(rule_index)),
        ))

    def _defense_cost_was_paid(self, side, defense, rule_index):
        paid = (self.engine_state.get('battle') or {}).get(
            'defense_costs_paid', [],
        ) or []
        return self._defense_cost_key(side, defense, rule_index) in paid

    def _defense_cost_rule_applies(self, side, rule_index, rule):
        """Return the live context when a revealed defense can pay ``rule``.

        Costs are offered after every ``before_judgment`` effect, so dynamic
        speed requirements observe effect-modified reference Speed but never
        FP.  A cost is not charged when the printed judgment cannot apply in
        the first place (wrong position, a rule prohibition, or another rule
        boundary).  Grab itself does not prohibit Guard or another printed
        defense judgment (Q&A 460).
        """
        battle = self.engine_state.get('battle') or {}
        entry = battle.get(side) or {}
        other_side = opponent(side)
        other_entry = battle.get(other_side) or {}
        defense = entry.get('card') or {}
        attack = other_entry.get('card') or {}
        judgment = str(rule.get('judgment') or 'dodge')
        if (
            not defense or not attack
            or defense.get('technique_invalidated')
            or self._rule_blocked('defense_rule', side, defense, attack)
            or self._rule_blocked(judgment, side, defense, attack)
        ):
            return None
        printed = _guard_result(defense, attack.get('pos'))
        if printed != judgment:
            return None
        attacker_side = other_side
        speed = self.card_stat(attack, 'frame', attacker_side, include_fp=False)
        damage = self.card_stat(attack, 'damage', attacker_side, include_fp=False)
        context = {
            'controller': side, 'opponent': other_side,
            'source_card': defense,
            'source_card_instance_id': defense.get('instance_id'),
            'opponent_card': attack,
            'controller_hp': self.state['players'][side].get('hp'),
            'controller_fp': self.state['players'][side].get('fp'),
            'opponent_hp': self.state['players'][other_side].get('hp'),
            'opponent_fp': self.state['players'][other_side].get('fp'),
            'controller_speed': self.card_stat(
                defense, 'frame', side, include_fp=False,
            ),
            'opponent_speed': speed,
        }
        if not condition_matches(rule.get('condition'), self.state, context):
            return None
        if rule.get('min_speed') is not None and speed < _number(rule.get('min_speed')):
            return None
        if rule.get('max_speed') is not None and speed > _number(rule.get('max_speed')):
            return None
        if rule.get('min_damage') is not None and damage < _number(rule.get('min_damage')):
            return None
        if rule.get('max_damage') is not None and damage > _number(rule.get('max_damage')):
            return None
        if rule.get('min_hit') is not None and _fp_value(attack.get('hit')) < _number(rule.get('min_hit')):
            return None
        if rule.get('hit_values') and attack.get('hit') not in rule.get('hit_values'):
            return None
        if rule.get('where') and not card_matches(
            attack, rule.get('where'), self.state, context,
        ):
            return None
        return context

    def _offer_next_defense_cost(self, pipeline):
        entries = pipeline.get('defense_cost_entries')
        if entries is None:
            entries = []
            battle = self.engine_state.get('battle') or {}
            for side in self._priority_order():
                card = (battle.get(side) or {}).get('card') or {}
                definition = self._definition_for_card(card)
                for rule_index, rule in enumerate(
                    definition.get('defense_rules') or [],
                ):
                    if isinstance(rule, dict) and isinstance(
                        rule.get('cost'), dict,
                    ) and not (
                        rule.get('numbered_effect')
                        and card.get('numbered_effects_negated')
                    ):
                        entries.append({
                            'side': side, 'rule_index': rule_index,
                        })
            pipeline['defense_cost_entries'] = entries
            pipeline['defense_cost_index'] = 0
        while _number(pipeline.get('defense_cost_index')) < len(entries):
            entry_index = _number(pipeline.get('defense_cost_index'))
            pipeline['defense_cost_index'] = entry_index + 1
            entry = entries[entry_index]
            side = entry.get('side')
            rule_index = _number(entry.get('rule_index'))
            battle = self.engine_state.get('battle') or {}
            defense = (battle.get(side) or {}).get('card') or {}
            definition = self._definition_for_card(defense)
            rules = definition.get('defense_rules') or []
            if rule_index >= len(rules) or not isinstance(rules[rule_index], dict):
                continue
            rule = rules[rule_index]
            if self._defense_cost_was_paid(side, defense, rule_index):
                continue
            context = self._defense_cost_rule_applies(side, rule_index, rule)
            if context is None:
                continue
            cost = rule.get('cost') or {}
            operation = cost.get('operation')
            selector = {
                **copy.deepcopy(cost.get('selector') or {}),
                'as_operation': operation,
            }
            options = self.selector_options(selector, context)
            minimum = _number(resolve_value(
                selector.get('min', 1), self.state, context,
            ), 1)
            maximum = _number(resolve_value(
                selector.get('max', minimum), self.state, context,
            ), minimum)
            if len(options) < minimum:
                self.emit('defense_cost_unavailable', side, {
                    'card_instance_id': defense.get('instance_id'),
                    'rule_index': rule_index, 'operation': operation,
                    'minimum': minimum, 'candidate_count': len(options),
                })
                continue
            if cost.get('optional'):
                options = [
                    *options,
                    {'id': 'decline', 'label': '비용을 지불하지 않음'},
                ]
            self.create_decision(
                owner=side, kind='defense_cost',
                prompt=(
                    cost.get('prompt')
                    or '수비 판정 비용으로 버릴 카드를 선택하세요.'
                ),
                options=options, minimum=minimum,
                maximum=min(maximum, len(options)),
                default=['decline'] if cost.get('optional') else [],
                optional=bool(cost.get('optional')),
                continuation={
                    'type': 'defense_cost', 'side': side,
                    'card_instance_id': defense.get('instance_id'),
                    'rule_index': rule_index, 'cost': copy.deepcopy(cost),
                    'context': copy.deepcopy(context),
                },
            )
            return True
        return False

    def _late_combo_result_triggers(self):
        """Collect Combo windows created by earlier result-timing effects.

        The initial result sequence can include a Combo judgment that was
        already printed when battle judgment was calculated. Effects such as
        Rai! Bounce! change the Hit judgment *during* Clash timing, so that
        Combo window can only be discovered after the existing result effects
        have resolved and still before judgment FP/damage.
        """
        battle = self.engine_state.get('battle') or {}
        triggered = battle.setdefault('combo_triggered_sources', [])
        triggered_set = set(str(value) for value in triggered)
        for event_type, context in battle.get('trigger_sequence') or []:
            if event_type == 'combo':
                instance_id = str(context.get('source_card_instance_id') or '')
                if instance_id and instance_id not in triggered_set:
                    triggered.append(instance_id)
                    triggered_set.add(instance_id)
        sequence = []
        for side in self._priority_order():
            entry = battle.get(side) or {}
            instance_id = str(entry.get('instance_id') or '')
            if not instance_id or instance_id in triggered_set:
                continue
            result = (battle.get('result') or {}).get(side)
            card = entry.get('card') or {}
            judgment_field = 'hit' if result == 'clash' else result
            if (
                result not in {'hit', 'counter', 'clash'}
                or str(card.get(judgment_field) or '') != '콤보'
            ):
                continue
            triggered.append(instance_id)
            triggered_set.add(instance_id)
            sequence.append(('combo', {
                'controller': side, 'result': 'combo',
                'combo_judgment': True,
                'source_card_instance_id': entry.get('instance_id'),
                'source_card': card,
                'opponent_card': (battle.get(opponent(side)) or {}).get('card'),
                'source_battle_card_only': True,
            }))
        return sequence

    def _result_trigger_sequence(self, results, pre_result_triggers=None):
        sequence = []
        battle = self.engine_state['battle']
        reference_speed = battle.get('reference_speed') or {}

        def result_context(side, **extra):
            entry = battle[side]
            other_entry = battle[opponent(side)]
            return {
                'controller': side,
                'source_card_instance_id': entry['instance_id'],
                'source_card': entry['card'],
                'opponent_card': other_entry['card'],
                # Result-timing effects refer to Speed after card effects but
                # before FP, the same reference captured for judgment.
                'controller_speed': reference_speed.get(side),
                'opponent_speed': reference_speed.get(opponent(side)),
                'source_battle_card_only': True,
                **extra,
            }
        # The order is rulebook p36: dodge, guard, hit/counter, clash, combo.
        # Each tuple is a fixed sub-timing. Priority alternation applies only
        # inside one sub-timing; it must never move an "opponent ..." effect
        # ahead of the corresponding player's own result effect (Q&A 574/577).
        groups = [
            ({'dodge'}, {'opponent_dodge'}),
            ({'guard'}, {'guarded'}),
            ({'hit', 'counter'}, {'countered', 'failed_defense', 'grabbed'}),
        ]
        mapping = {
            'dodge': 'dodge', 'opponent_dodge': 'opponent_dodge',
            'guard': 'guard', 'guarded': 'opponent_guard',
            'hit': 'hit', 'counter': 'counter', 'countered': 'opponent_counter',
            'failed_defense': 'opponent_hit', 'grabbed': 'opponent_hit',
            'clash': 'clash',
        }
        for event_type, side in pre_result_triggers or []:
            sequence.append((event_type, result_context(
                side, result=event_type,
            )))
        for timing_group in groups:
            for result_group in timing_group:
                for side in self._priority_order():
                    result = results.get(side)
                    if result in result_group:
                        sequence.append((mapping[result], result_context(
                            side, result=result,
                        )))
        # A Clash applies each attacking Technique's Hit judgment before the
        # later Clash window (rulebook p36).  This ordering matters for live
        # judgment checks such as Zephyr changing Hit to Combo before Paki
        # Defense decides whether its Clash effect is legal (Q&A 469).
        for side in self._priority_order():
            if (
                results.get(side) == 'clash'
                and _is_attack((battle.get(side) or {}).get('card'))
            ):
                sequence.append(('hit', result_context(
                    side, result='clash', clash_hit=True,
                )))
        for side in self._priority_order():
            if results.get(side) == 'clash':
                sequence.append(('clash', result_context(
                    side, result='clash',
                )))
        # A printed Combo judgment is itself a result-timing effect window.
        # It resolves after dodge/guard/hit-counter/clash effects but before
        # judgment FP and damage. The later Combo Time only opens card plays;
        # it must not fire the source card's "콤보 시" text a second time.
        for side in self._priority_order():
            result = results.get(side)
            entry = self.engine_state['battle'][side]
            other_entry = self.engine_state['battle'][opponent(side)]
            if (
                result in {'hit', 'counter'}
                and str((entry.get('card') or {}).get(result) or '') == '콤보'
            ):
                sequence.append(('combo', result_context(
                    side, result='combo', combo_judgment=True,
                )))
        return sequence

    def _prepare_battle_outcomes(self):
        battle = self.engine_state['battle']
        results = battle['result']
        damage_candidates = {side: False for side in PLAYER_SIDES}
        outcomes = []
        for side in PLAYER_SIDES:
            card = battle[side]['card']
            result = results[side]
            if result in {'hit', 'counter'} and _is_attack(card):
                outcomes.append({'kind': 'fp', 'side': side, 'amount': _fp_value(card.get(result)), 'result': result})
                damage_candidates[side] = True
            elif result == 'guarded':
                outcomes.append({'kind': 'fp', 'side': side, 'amount': _fp_value(card.get('guard')), 'result': result})
            elif result == 'clash' and _is_attack(card):
                outcomes.append({'kind': 'fp', 'side': side, 'amount': _fp_value(card.get('hit')), 'result': result})
                damage_candidates[side] = True
        battle['outcome_queue'] = outcomes
        battle['damage_candidates'] = damage_candidates
        battle['damage_prepared'] = False
        battle['damage'] = {side: 0 for side in PLAYER_SIDES}

    def _prepare_battle_damage_outcomes(self):
        battle = self.engine_state['battle']
        results = battle['result']
        damages = {
            side: max(0, self.card_stat(battle[side]['card'], 'damage', side))
            if (battle.get('damage_candidates') or {}).get(side) else 0
            for side in PLAYER_SIDES
        }
        damage_outcomes = []
        if results['p1'] == results['p2'] == 'clash':
            difference = damages['p1'] - damages['p2']
            if difference:
                winner = 'p1' if difference > 0 else 'p2'
                damage_outcomes.append({
                    'kind': 'damage', 'side': opponent(winner), 'amount': abs(difference),
                    'source': 'clash', 'controller': winner,
                })
        else:
            for side in self._priority_order():
                if damages[side]:
                    damage_outcomes.append({
                        'kind': 'damage', 'side': opponent(side), 'amount': damages[side],
                        'source': 'battle', 'controller': side,
                    })
        self.engine_state['battle_damage_remaining'] = len(damage_outcomes)
        battle['outcome_queue'] = damage_outcomes
        battle['damage'] = damages
        battle['damage_prepared'] = True

    def _apply_battle_outcome(self, outcome):
        side = outcome['side']
        source_side = outcome.get('controller', side)
        entry = (self.engine_state.get('battle') or {}).get(source_side) or {}
        context = {
            'controller': source_side,
            'source_card_instance_id': entry.get('instance_id'),
            'source_card': entry.get('card'),
            'result': outcome.get('result'),
        }
        if outcome['kind'] == 'fp':
            self.change_fp(side, outcome.get('amount'), source='judgment', context=context)
        else:
            self.deal_damage(
                side, outcome.get('amount'), source=outcome.get('source') or 'battle',
                context={**context, 'battle_batch': True},
            )

    def _open_combo_from_battle(self):
        battle = self.engine_state.get('battle') or {}
        suppressed = list(
            self.engine_state.pop('suppressed_battle_combos', []) or []
        )
        candidates = list(self.engine_state.pop('granted_combos', []) or [])
        for side in self._priority_order():
            entry = battle.get(side) or {}
            result = (battle.get('result') or {}).get(side)
            card = entry.get('card') or {}
            judgment_field = 'hit' if result == 'clash' else result
            if (
                result in {'hit', 'counter', 'clash'}
                and str(card.get(judgment_field) or '') == '콤보'
            ):
                candidates.append({
                    'owner': side, 'source': entry.get('instance_id'),
                    'special': False, 'combo_triggered': True,
                })
        if suppressed:
            retained = []
            for item in candidates:
                blocked = any(
                    rule.get('owner') == item.get('owner')
                    and (
                        not rule.get('source')
                        or rule.get('source') == item.get('source')
                    )
                    for rule in suppressed
                )
                if blocked:
                    self.emit('combo_skipped', item.get('owner'), {
                        'reason': 'card_effect_ended_combo_time',
                        'source_card_instance_id': item.get('source'),
                    })
                else:
                    retained.append(item)
            candidates = retained
        mutual_combo = {
            item.get('owner') for item in candidates
        } >= set(PLAYER_SIDES)
        available_candidates = []
        for item in candidates:
            if (
                not mutual_combo
                and not self._combo_grant_can_open(item)
            ):
                self._emit_unavailable_combo(item)
                continue
            available_candidates.append(item)
        candidates = available_candidates
        if not candidates:
            return False
        missed_catches = list(self.engine_state.get('granted_catches') or [])
        self.engine_state['granted_catches'] = []
        for missed in missed_catches:
            self.emit('catch_skipped', missed.get('owner'), {
                'reason': 'combo_time_started',
                'source': missed.get('source'),
            })
        if {item.get('owner') for item in candidates} >= set(PLAYER_SIDES):
            # Rulebook p25 and card Q&A: when both players receive a combo
            # result, the already-resolved ready cards are each the sole
            # 1-combo. No additional combo cards or catch window is opened.
            for side in self._priority_order():
                source = next(
                    (item.get('source') for item in candidates if item.get('owner') == side),
                    None,
                )
                self.emit('combo_started', side, {
                    'source_card_instance_id': source,
                    'special': False,
                    'mutual': True,
                })
                self.emit('combo_ended', side, {
                    'used': [],
                    'mutual': True,
                })
                if source:
                    sources = self.engine_state.setdefault('combo_source_ids', [])
                    if source not in sources:
                        sources.append(source)
            self.emit('mutual_combo_resolved', 'system', {})
            self.engine_state['step'] = 'combo_end'
            self.engine_state['pipeline'] = {
                'kind': 'mutual_combo_end', 'stage': 'owner_effects',
                'index': 0,
                'combos': [
                    {
                        'owner': side,
                        'source': next((
                            item.get('source') for item in candidates
                            if item.get('owner') == side
                        ), None),
                        'used': [], 'special': False, 'mutual': True,
                    }
                    for side in self._priority_order()
                ],
            }
            return 'mutual'
        self.engine_state['combo_queue'] = candidates[1:]
        first = candidates[0]
        self.grant_combo(
            first['owner'], source=first.get('source'),
            special=first.get('special', False),
            trigger_event=not first.get('combo_triggered'),
        )
        return True

    def queue_combo(self, owner_side, *, source=None, special=False):
        if owner_side not in PLAYER_SIDES:
            raise EngineError('콤보 대상 플레이어가 올바르지 않습니다.')
        self.engine_state.setdefault('granted_combos', []).append({
            'owner': owner_side, 'source': source, 'special': bool(special),
        })
        self.emit('combo_granted', owner_side, {
            'source_card_instance_id': source, 'special': bool(special),
        })

    def suppress_battle_combo(self, owner_side, *, source=None):
        """Prevent a not-yet-open Combo time created by the ready card."""
        if owner_side not in PLAYER_SIDES:
            raise EngineError('콤보 종료 대상 플레이어가 올바르지 않습니다.')
        entry = {'owner': owner_side, 'source': source}
        suppressed = self.engine_state.setdefault(
            'suppressed_battle_combos', [],
        )
        if entry not in suppressed:
            suppressed.append(entry)
        self.emit('combo_time_ended', owner_side, {
            'source_card_instance_id': source,
            'before_open': True,
        })

    def grant_combo(
        self, owner_side, *, source=None, special=False, trigger_event=True,
    ):
        # A normal Hit/Counter Combo source is the already-used 1-combo and
        # therefore goes to the List.  An effect-created special Combo uses
        # newly presented 1/2-combo cards; its Defense source returns to Hand
        # during ordinary battle cleanup (Q&A 455).
        if source and not special:
            sources = self.engine_state.setdefault('combo_source_ids', [])
            if source not in sources:
                sources.append(source)
        source_card = self._find_card(source) if source and not special else None
        source_speed = (
            self.card_stat(
                source_card, 'frame', owner_side, include_fp=False,
            )
            if source_card and _is_attack(source_card) else None
        )
        self.engine_state['combo'] = {
            'owner': owner_side, 'source': source, 'special': bool(special),
            'used': [], 'next_penalty': 0 if special else 100,
            'proposal_submitted': False,
            **({'last_speed': source_speed} if source_speed is not None else {}),
        }
        self.engine_state['step'] = 'combo'
        self.emit('combo_started', owner_side, {'source_card_instance_id': source, 'special': bool(special)})
        if trigger_event:
            self._fire('combo', {
                'controller': owner_side,
                'source_card_instance_id': source,
            })

    def _combo_grant_can_open(self, item):
        """Return whether a newly opened Combo has its mandatory first pair.

        Production rulesets must be able to present both initial cards at
        once.  The synthetic automatic-effect review ruleset is the sole
        exception for normal Combos: it intentionally isolates one arbitrary
        Combo slot without manufacturing unrelated filler cards.  Special
        Combos always require their two-card proposal, including in reviews.
        """
        if not isinstance(item, dict):
            return False
        special = bool(item.get('special'))
        if (
            not special
            and str(self.ruleset.get('version') or '')
            == 'automatic-effect-v2'
        ):
            return True
        return self._combo_has_legal_initial_pair(
            item.get('owner'), source=item.get('source'), special=special,
        )

    def _emit_unavailable_combo(self, item):
        item = item if isinstance(item, dict) else {'owner': item}
        self.emit('combo_skipped', item.get('owner'), {
            'reason': (
                'special_combo_requires_pair'
                if item.get('special')
                else 'normal_combo_requires_two_cards'
            ),
            'source_card_instance_id': item.get('source'),
        })

    def _next_available_combo(self, queue):
        """Pop invalid grants until an initial two-card proposal is possible."""
        while queue:
            raw = queue.pop(0)
            if isinstance(raw, dict):
                item = raw
            else:
                item = {
                    'owner': raw,
                    'source': (
                        (self.engine_state.get('battle') or {}).get(raw) or {}
                    ).get('instance_id'),
                    'special': False,
                }
            if self._combo_grant_can_open(item):
                return item
            self._emit_unavailable_combo(item)
        return None

    def end_combo(self):
        combo = self.engine_state.get('combo')
        if not combo:
            return
        self.emit('combo_ended', combo.get('owner'), {'used': combo.get('used') or []})
        self.engine_state['combo'] = None
        self.engine_state['step'] = 'combo_end'
        self.engine_state['pipeline'] = {
            'kind': 'combo_end', 'stage': 'owner_effects',
            'combo': copy.deepcopy(combo),
        }

    def _advance_combo_end_pipeline(self, pipeline):
        combo = pipeline.get('combo') or {}
        owner = combo.get('owner')
        context = {
            'controller': owner, 'combo_owner': owner,
            'combo_used': copy.deepcopy(combo.get('used') or []),
            'combo_used_count': len(combo.get('used') or []),
            'source_card_instance_id': combo.get('source'),
            'combo_card_instance_ids': [
                *([combo.get('source')] if combo.get('source') else []),
                *(combo.get('used') or []),
            ],
        }
        if pipeline.get('stage') == 'owner_effects':
            pipeline['stage'] = 'opponent_effects'
            self._fire('combo_end', context)
            return not self.is_waiting
        if pipeline.get('stage') == 'opponent_effects':
            pipeline['stage'] = 'finish'
            self._fire('opponent_combo_end', context)
            return not self.is_waiting
        # Q&A 171: after all Combo-end windows resolve, both FP values are
        # cleared before the next Combo grant or Catch window is opened.
        for side in PLAYER_SIDES:
            self.set_fp(side, 0, source='combo_cleanup')
        self._return_borrowed_combo_cards(combo)
        self._expire_modifiers('combo')
        self.engine_state['pipeline'] = None
        queue = list(self.engine_state.get('combo_queue') or [])
        queue.extend(self.engine_state.pop('granted_combos', []) or [])
        self.engine_state['combo_queue'] = queue
        next_combo = self._next_available_combo(queue)
        if next_combo:
            self.grant_combo(
                next_combo.get('owner'), source=next_combo.get('source'),
                special=next_combo.get('special', False),
                trigger_event=not next_combo.get('combo_triggered'),
            )
            return True
        if self.engine_state.pop('resume_catch_after_combo', False):
            self._continue_catch_queue()
            return True
        self._open_catch_or_cleanup()
        return True

    def _advance_mutual_combo_end_pipeline(self, pipeline):
        """Resolve both own Combo-end windows before opponent windows.

        A mutual Combo consists only of the two already-resolved Ready cards,
        but delayed effects still observe that each player completed a Combo
        Time.  Own Combo-end effects are resolved first for both players so a
        delayed return such as West Wind Zephyr cannot be pre-empted by its
        opponent-Combo break effect (Q&A 433).
        """
        combos = pipeline.get('combos') or []
        stage = pipeline.get('stage')
        index = _number(pipeline.get('index'))
        if stage in {'owner_effects', 'opponent_effects'}:
            if index >= len(combos):
                pipeline['stage'] = (
                    'opponent_effects'
                    if stage == 'owner_effects' else 'finish'
                )
                pipeline['index'] = 0
                return True
            combo = combos[index]
            pipeline['index'] = index + 1
            owner = combo.get('owner')
            context = {
                'controller': owner, 'combo_owner': owner,
                'combo_used': [], 'combo_used_count': 0,
                'source_card_instance_id': combo.get('source'),
                'combo_card_instance_ids': [
                    combo.get('source'),
                ] if combo.get('source') else [],
                'mutual': True,
            }
            self._fire(
                'combo_end' if stage == 'owner_effects'
                else 'opponent_combo_end',
                context,
            )
            return not self.is_waiting
        for side in PLAYER_SIDES:
            self.set_fp(side, 0, source='mutual_combo_cleanup')
        self._expire_modifiers('combo')
        self.engine_state['pipeline'] = None
        self._cleanup_battle()
        return not self.is_waiting

    def _combo_actions(self, role, combo, *, staged=False):
        if combo.get('proposal_submitted'):
            return []
        # A normal Combo begins by presenting its 2- and 3-Combo Techniques
        # together.  After both cards have finished through ``after_use``,
        # later extensions are offered one card at a time.  Effect-created
        # special Combos likewise present their 1/2-Combo pair together and
        # never expose an incomplete one-card proposal.
        # Card-definition reviews deliberately isolate one arbitrary Combo
        # slot. They use a synthetic ruleset version and retain the wider
        # enumerator so a card's own rule can be tested without inventing
        # unrelated filler cards. Real sessions always use the staged sizes.
        review_isolation = str(self.ruleset.get('version') or '') == 'automatic-effect-v2'
        proposal_size = (
            None if review_isolation and not combo.get('special')
            else (2 if not (combo.get('used') or []) else 1)
        )
        if combo.get('special') and (combo.get('used') or []):
            return []
        base_cards = []
        # Enumerate every owned zone and let ``_combo_zone_allowed`` enforce
        # the actual grant.  Restricting this seed list to the ordinary four
        # zones made effects that explicitly grant Combo use from Break (or a
        # future zone) impossible to select even though their modifier was
        # otherwise valid.
        for zone_cards in self.state['players'][role]['zones'].values():
            for card in zone_cards:
                if _is_attack(card) and not _is_special(card):
                    base_cards.append(card)
        for modifier in self.engine_state.get('modifiers') or []:
            if (
                modifier.get('op') != 'modify_combo'
                or modifier.get('borrow_from') != 'opponent'
                or (modifier.get('player') or modifier.get('controller')) != role
            ):
                continue
            for zone in modifier.get('allow_zones') or ['list']:
                for card in self._zone(opponent(role), zone):
                    if _is_attack(card) and not _is_special(card) and card not in base_cards:
                        base_cards.append(card)

        actions = []

        def candidate_cards(projected):
            cards = list(base_cards)
            known_ids = {
                card.get('instance_id') for card in cards
                if card.get('instance_id')
            }
            for modifier in projected.get('proposal_modifiers') or []:
                if (
                    modifier.get('op') != 'modify_combo'
                    or modifier.get('borrow_from') != 'opponent'
                    or (modifier.get('player') or modifier.get('controller')) != role
                ):
                    continue
                for zone in modifier.get('allow_zones') or ['list']:
                    for card in self._zone(opponent(role), zone):
                        instance_id = card.get('instance_id')
                        if (
                            not instance_id or instance_id in known_ids
                            or not _is_attack(card) or _is_special(card)
                        ):
                            continue
                        cards.append(card)
                        known_ids.add(instance_id)
            return cards

        def add_action(
            proposed_cards, speeds, ignores, speed_ignores,
            proposed_rule_sets,
        ):
            if proposal_size is not None and len(proposed_cards) != proposal_size:
                return
            if combo.get('special') and len(proposed_cards) != 2:
                return
            card_ids = [card.get('instance_id') for card in proposed_cards]
            source_zones = []
            for card_id in card_ids:
                _owner, source_zone, _index, _card = self._find_location(card_id)
                source_zones.append(source_zone)
            first_combo_number = self._next_combo_number(combo)
            combo_numbers = [
                first_combo_number + index
                for index in range(len(card_ids))
            ]
            if any(
                speed_ignore
                and not self._combo_optional_speed_cost_affordable(
                    role, card, combo, rules,
                    proposed_ids=card_ids,
                )
                for card, speed_ignore, rules in zip(
                    proposed_cards, speed_ignores, proposed_rule_sets,
                )
            ):
                return
            labels = []
            for card, speed, ignore, speed_ignore, rules in zip(
                proposed_cards, speeds, ignores, speed_ignores,
                proposed_rule_sets,
            ):
                label = f'{card.get("name") or "카드"}({speed})'
                if ignore:
                    label = f'{label}·보정 없음'
                if speed_ignore:
                    declared_within_window = any(
                        rule.get('optional_any_speed')
                        and self._combo_rule_respects_speed_window(rule)
                        for rule in rules
                    )
                    label = (
                        f'{label}·속도 선언'
                        if declared_within_window
                        else f'{label}·속도 무시'
                    )
                labels.append(label)
            if len(card_ids) == 1:
                payload = {
                    'card_instance_id': card_ids[0],
                    'combo_speed': speeds[0],
                    'choice_speed': speeds[0],
                    'combo_number': combo_numbers[0],
                    'source_zone': source_zones[0],
                    'ignore_damage_penalty': list(ignores),
                }
                if any(speed_ignores):
                    payload['ignore_speed'] = list(speed_ignores)
                actions.append(self._action(
                    'play_combo_card', label=labels[0],
                    payload=payload,
                    card=self._private_action_card(proposed_cards[0]),
                    choice_speed=speeds[0],
                    source_zone=source_zones[0],
                    combo_number=combo_numbers[0],
                ))
                return
            action_type = 'play_combo_pair' if len(card_ids) == 2 else 'play_combo_sequence'
            payload = {
                'card_instance_ids': card_ids,
                'combo_speeds': list(speeds),
                'combo_numbers': combo_numbers,
                'source_zones': source_zones,
                'ignore_damage_penalty': list(ignores),
            }
            if any(speed_ignores):
                payload['ignore_speed'] = list(speed_ignores)
            actions.append(self._action(
                action_type, label=' → '.join(labels),
                payload=payload,
                cards=[self._private_action_card(card) for card in proposed_cards],
            ))

        def propose(
            projected, proposed_cards, speeds, ignores, speed_ignores,
            proposed_rule_sets,
        ):
            if proposed_cards:
                first_card = self._project_card_for_use(
                    proposed_cards[0], role, 'combo',
                )
                first_rules = self._combo_rules(role, first_card, combo)
                first_combo_number = self._next_combo_number(combo)
                needs_followup = bool(
                    speed_ignores[0]
                    and any(
                        rule.get('optional_any_speed')
                        and _number(rule.get('requires_followup_at_combo'))
                        == first_combo_number
                        for rule in first_rules
                    )
                    and len(proposed_cards) < 2
                )
                if not needs_followup:
                    add_action(
                        proposed_cards, speeds, ignores, speed_ignores,
                        proposed_rule_sets,
                    )
            proposal_cap = (
                2 if projected.get('special')
                else (5 if proposal_size is None else proposal_size)
            )
            if len(proposed_cards) >= proposal_cap:
                return
            used_ids = set(projected.get('used') or [])
            proposed_ids = {
                card.get('instance_id') for card in proposed_cards
                if card.get('instance_id')
            }
            for card in candidate_cards(projected):
                instance_id = card.get('instance_id')
                # A card cannot occupy two slots in one atomic proposal. A
                # card already resolved earlier in this Combo is likewise
                # excluded unless its own currently applicable rule grants
                # an explicitly limited reuse (Tempo de Deux).
                if not instance_id or instance_id in proposed_ids:
                    continue
                found_owner, found_zone, _index, live_card = self._find_location(instance_id)
                if not live_card:
                    continue
                projected_card, combo_rules, borrow_rule = (
                    self._combo_candidate_projection(
                        role, live_card, projected,
                        found_owner=found_owner, found_zone=found_zone,
                    )
                )
                if (
                    instance_id in used_ids
                    and not any(
                        self._combo_rule_allows_reuse(rule, projected_card)
                        for rule in combo_rules
                    )
                ):
                    continue
                if found_owner != role and not borrow_rule:
                    continue
                if not self._combo_zone_allowed(role, live_card, found_zone, projected):
                    continue
                for speed_ignore in self._combo_speed_ignore_options(
                    role, projected_card, projected,
                ):
                    if (
                        speed_ignore and any(speed_ignores)
                        and any(
                            rule.get('optional_any_speed')
                            and rule.get('counter_cost')
                            for rule in combo_rules
                        )
                    ):
                        continue
                    for speed in self._combo_speed_options(
                        role, projected_card, projected, rules=combo_rules,
                        use_optional_speed_ignore=speed_ignore,
                    ):
                        for ignore in self._combo_penalty_options(
                            role, projected_card, projected,
                        ):
                            # A limited optional penalty waiver can be assigned
                            # to only one card in a proposed chain.
                            if ignore and any(ignores):
                                continue
                            if not self._combo_card_legal(
                                role, projected_card, projected,
                                selected_speed=speed,
                                use_optional_ignore=ignore,
                                use_optional_speed_ignore=speed_ignore,
                            ):
                                continue
                            next_projected = {
                                **copy.deepcopy(projected),
                                'next_penalty': _number(
                                    projected.get('next_penalty'), 100,
                                ) + 100,
                                'last_speed': speed,
                                'used': [
                                    *(projected.get('used') or []), instance_id,
                                ],
                            }
                            next_projected['last_speed_ignored'] = bool(
                                speed_ignore
                            )
                            next_projected['counter_overrides'] = (
                                self._project_combo_counter_overrides(
                                    role, projected_card, projected, combo_rules,
                                    selected_speed=speed,
                                    use_optional_speed_ignore=speed_ignore,
                                )
                            )
                            projected_usage_counts = copy.deepcopy(
                                projected.get(
                                    'projected_limited_usage_counts',
                                ) or {}
                            )
                            if not projected_usage_counts:
                                for projected_key in projected.get(
                                    'projected_limited_usage_keys',
                                ) or []:
                                    projected_usage_counts[projected_key] = (
                                        _number(projected_usage_counts.get(
                                            projected_key,
                                        )) + 1
                                    )
                            for projected_key in self._combo_rule_usage_keys(
                                combo_rules, found_zone,
                                use_optional_ignore=ignore,
                                use_optional_speed_ignore=speed_ignore,
                            ):
                                projected_usage_counts[projected_key] = (
                                    _number(projected_usage_counts.get(
                                        projected_key,
                                    )) + 1
                                )
                            if projected_usage_counts:
                                next_projected[
                                    'projected_limited_usage_counts'
                                ] = projected_usage_counts
                                next_projected[
                                    'projected_limited_usage_keys'
                                ] = sorted(projected_usage_counts)
                            previews = self._combo_proposal_modifiers(
                                role, projected_card, projected,
                            )
                            if previews:
                                next_projected['proposal_modifiers'] = [
                                    *(projected.get('proposal_modifiers') or []),
                                    *previews,
                                ]
                            propose(
                                next_projected,
                                [*proposed_cards, live_card],
                                [*speeds, speed],
                                [*ignores, ignore],
                                [*speed_ignores, speed_ignore],
                                [*proposed_rule_sets, combo_rules],
                            )

        proposal_seed = copy.deepcopy(combo)
        # The Technique which opened Combo Time does not constrain the
        # 2-Combo speed.  The speed chain starts with the selected 2-Combo
        # Technique and is enforced for its follow-up from there.
        if not review_isolation and not (combo.get('used') or []):
            proposal_seed.pop('last_speed', None)
            if not combo.get('special'):
                proposal_seed['initial_pair_proposal'] = True
        propose(proposal_seed, [], [], [], [], [])

        # Real games stage the first proposal.  Showing every Cartesian pair
        # is both hard to use and can explode for cards with multiple legal
        # speeds.  Only first cards that have at least one legal follow-up are
        # shown.  After one is selected, only its compatible follow-up cards
        # are returned; the two cards are still committed and resolved as one
        # atomic proposal.
        if review_isolation or (combo.get('used') or []) or not staged:
            return actions
        pair_actions = [
            action for action in actions
            if action.get('type') == 'play_combo_pair'
            and len((action.get('payload') or {}).get('card_instance_ids') or []) == 2
        ]
        selected_first = combo.get('initial_selection') or {}
        if selected_first:
            followups = []
            for action in pair_actions:
                payload = action.get('payload') or {}
                ids = payload.get('card_instance_ids') or []
                speeds = payload.get('combo_speeds') or []
                ignores = payload.get('ignore_damage_penalty') or [False, False]
                speed_ignores = payload.get('ignore_speed') or [False, False]
                if not (
                    ids[0] == selected_first.get('card_instance_id')
                    and _number(speeds[0]) == _number(selected_first.get('combo_speed'))
                    and bool(ignores[0]) == bool(selected_first.get('ignore_damage_penalty'))
                    and bool(speed_ignores[0]) == bool(selected_first.get('ignore_speed'))
                ):
                    continue
                second = self._find_card(ids[1])
                if not second:
                    continue
                second_label = f'{second.get("name") or "카드"}({speeds[1]}속도)'
                followups.append(self._action(
                    'select_combo_followup', label=second_label,
                    payload={
                        'card_instance_id': ids[1],
                        'choice_speed': speeds[1],
                        'combo_number': (
                            (payload.get('combo_numbers') or [2, 3])[1]
                        ),
                        'source_zone': (
                            (payload.get('source_zones') or [None, None])[1]
                        ),
                        'proposal': copy.deepcopy(payload),
                    },
                    card=self._private_action_card(second),
                    choice_speed=speeds[1],
                    source_zone=(
                        (payload.get('source_zones') or [None, None])[1]
                    ),
                    combo_number=(
                        (payload.get('combo_numbers') or [2, 3])[1]
                    ),
                ))
            if followups:
                followups.append(self._action(
                    'cancel_combo_first', label='첫 카드 다시 선택',
                ))
            return followups

        first_actions = []
        seen = set()
        for action in pair_actions:
            payload = action.get('payload') or {}
            ids = payload.get('card_instance_ids') or []
            speeds = payload.get('combo_speeds') or []
            ignores = payload.get('ignore_damage_penalty') or [False, False]
            speed_ignores = payload.get('ignore_speed') or [False, False]
            key = (
                ids[0], _number(speeds[0]), bool(ignores[0]),
                bool(speed_ignores[0]),
            )
            if key in seen:
                continue
            seen.add(key)
            first = self._find_card(ids[0])
            if not first:
                continue
            label = f'{first.get("name") or "카드"}({speeds[0]}속도)'
            first_actions.append(self._action(
                'select_combo_first', label=label,
                payload={
                    'card_instance_id': ids[0],
                    'combo_speed': speeds[0],
                    'choice_speed': speeds[0],
                    'combo_number': (
                        (payload.get('combo_numbers') or [2])[0]
                    ),
                    'source_zone': (
                        (payload.get('source_zones') or [None])[0]
                    ),
                    'ignore_damage_penalty': bool(ignores[0]),
                    'ignore_speed': bool(speed_ignores[0]),
                },
                card=self._private_action_card(first),
                choice_speed=speeds[0],
                source_zone=(
                    (payload.get('source_zones') or [None])[0]
                ),
                combo_number=(
                    (payload.get('combo_numbers') or [2])[0]
                ),
            ))
        return first_actions

    def _combo_has_legal_initial_pair(
        self, role, *, source=None, special=False,
    ):
        if role not in PLAYER_SIDES:
            return False
        combo = {
            'owner': role, 'source': source, 'special': bool(special),
            'used': [], 'next_penalty': 0 if special else 100,
            'proposal_submitted': False,
        }
        if source and not special:
            source_card = self._find_card(source)
            if source_card and _is_attack(source_card):
                combo['last_speed'] = self.card_stat(
                    source_card, 'frame', role, include_fp=False,
                )
        return any(
            action.get('type') == 'play_combo_pair'
            and len((action.get('payload') or {}).get('card_instance_ids') or []) == 2
            for action in self._combo_actions(role, combo)
        )

    def _special_combo_has_legal_pair(self, role, *, source=None):
        return self._combo_has_legal_initial_pair(
            role, source=source, special=True,
        )

    @staticmethod
    def _next_combo_number(combo):
        return len((combo or {}).get('used') or []) + (
            1 if (combo or {}).get('special') else 2
        )

    @staticmethod
    def _current_combo_number(combo):
        return len((combo or {}).get('used') or []) + (
            0 if (combo or {}).get('special') else 1
        )

    def _combo_penalty_options(self, role, card, combo):
        rules = self._combo_rules(role, card, combo)
        return [False, True] if any(
            rule.get('optional_ignore_damage_penalty') for rule in rules
        ) else [False]

    def _combo_speed_ignore_options(self, role, card, combo):
        rules = self._combo_rules(role, card, combo)
        return [False, True] if any(
            rule.get('optional_ignore_speed') or rule.get('optional_any_speed')
            for rule in rules
        ) else [False]

    @staticmethod
    def _combo_optional_speed_cost_rule(rules):
        return next((
            rule for rule in rules or []
            if (
                rule.get('optional_any_speed')
                or rule.get('optional_ignore_speed')
            )
            and isinstance(rule.get('optional_speed_cost'), dict)
        ), None)

    def _combo_speed_cost_context(
        self, role, card, combo, *, proposed_ids=None,
    ):
        return {
            'controller': role, 'opponent': opponent(role),
            'source_card': card,
            'source_card_instance_id': card.get('instance_id'),
            'use_context': 'combo',
            'combo_proposed_card_ids': list(
                proposed_ids
                if proposed_ids is not None
                else (
                    combo.get('proposed_card_ids')
                    or combo.get('used') or []
                )
            ),
        }

    def _combo_optional_speed_cost_affordable(
        self, role, card, combo, rules, *, proposed_ids=None,
    ):
        rule = self._combo_optional_speed_cost_rule(rules)
        if not rule:
            return True
        cost = rule.get('optional_speed_cost') or {}
        selector = {
            **(cost.get('selector') or {}),
            'as_operation': cost.get('operation'),
        }
        context = self._combo_speed_cost_context(
            role, card, combo, proposed_ids=proposed_ids,
        )
        minimum = _number(resolve_value(
            selector.get('min', 1), self.state, context,
        ), 1)
        return len(self.selector_options(selector, context)) >= minimum

    def _begin_combo_optional_speed_cost(
        self, role, card, combo, rules, *, card_ids, combo_speeds,
        ignore_damage_penalty, ignore_speed, cost_paid_for=None,
    ):
        rule = self._combo_optional_speed_cost_rule(rules)
        if not rule:
            return False
        cost = rule.get('optional_speed_cost') or {}
        selector = {
            **(cost.get('selector') or {}),
            'as_operation': cost.get('operation'),
        }
        context = self._combo_speed_cost_context(role, card, combo)
        options = self.selector_options(selector, context)
        minimum = _number(resolve_value(
            selector.get('min', 1), self.state, context,
        ), 1)
        maximum = _number(resolve_value(
            selector.get('max', minimum), self.state, context,
        ), minimum)
        if len(options) < minimum:
            raise IllegalAction('콤보 속도 예외 비용을 지불할 수 없습니다.')
        self.create_decision(
            owner=role, kind='combo_speed_cost',
            prompt='콤보 속도 예외 비용으로 버릴 카드를 선택하세요.',
            options=options, minimum=minimum, maximum=maximum, default=[],
            continuation={
                'type': 'combo_speed_cost',
                'cost': copy.deepcopy(cost),
                'context': copy.deepcopy(context),
                'card_instance_id': card.get('instance_id'),
                'cost_paid_for': cost_paid_for,
                'play': {
                    'kind': 'combo', 'card_ids': list(card_ids),
                    'combo_speeds': list(combo_speeds),
                    'ignore_damage_penalty': list(ignore_damage_penalty),
                    'ignore_speed': list(ignore_speed),
                },
            },
        )
        return True

    def _play_combo(
        self, role, card_ids, combo_speeds=None, ignore_damage_penalty=None,
        ignore_speed=None,
    ):
        combo = self.engine_state.get('combo') or {}
        if combo.get('owner') != role:
            raise IllegalAction('콤보 사용자가 아닙니다.')
        if combo.get('proposal_submitted'):
            raise IllegalAction('콤보 카드는 이미 함께 제시했습니다.')
        card_ids = list(card_ids)
        # Public submissions can only reach this method through a server
        # issued action whose payload fixes the exact proposal.  Keep direct
        # calls available to deterministic card-review fixtures, which often
        # isolate a later Combo card without constructing its earlier pair.
        if (
            not card_ids or len(card_ids) > 5
            or len(card_ids) != len(set(card_ids))
        ):
            raise IllegalAction('제시한 콤보 카드 수가 올바르지 않습니다.')
        if combo.get('special') and len(card_ids) != 2:
            raise IllegalAction('효과 콤보는 1·2콤보 두 장을 함께 제시해야 합니다.')
        combo['proposal_submitted'] = True
        combo.pop('initial_selection', None)
        combo['proposed_card_ids'] = list(card_ids)
        combo['proposal_size'] = len(card_ids)
        if (
            not combo.get('special')
            and not (combo.get('used') or [])
            and len(card_ids) == 2
        ):
            combo['initial_pair_proposal'] = True
        self.emit('combo_proposed', role, {'card_instance_ids': list(card_ids)})
        self._start_combo_card(
            role, card_ids, list(combo_speeds or []),
            list(ignore_damage_penalty or []),
            list(ignore_speed or []),
        )

    def _start_combo_card(
        self, role, card_ids, combo_speeds=None, ignore_damage_penalty=None,
        ignore_speed=None,
        *, cost_paid_for=None, speed_cost_paid_for=None,
    ):
        if not card_ids:
            self.engine_state['step'] = 'combo'
            self.engine_state['pipeline'] = None
            return
        combo_speeds = list(combo_speeds or [])
        ignore_damage_penalty = list(ignore_damage_penalty or [])
        ignore_speed = list(ignore_speed or [])
        use_optional_penalty_rule = bool(
            ignore_damage_penalty[0] if ignore_damage_penalty else False
        )
        use_optional_speed_rule = bool(
            ignore_speed[0] if ignore_speed else False
        )
        combo = self.engine_state.get('combo') or {}
        # The Ready Technique is the 1-Combo source, but its Speed does not
        # constrain the first Technique selected during Combo Time.  Keep the
        # source Speed in the authoritative state because effects such as
        # Grace still compare the actually consecutive cards; only legality
        # and declared-Speed calculation use a source-less projection.
        legality_combo = combo
        if not combo.get('special') and not (combo.get('used') or []):
            legality_combo = copy.deepcopy(combo)
            legality_combo.pop('last_speed', None)
        instance_id = card_ids[0]
        self._refresh_continuous_rules()
        found_owner, found_zone, _index, card = self._find_location(instance_id)
        projected_card, combo_rules, borrow_rule = (
            self._combo_candidate_projection(
                role, card, legality_combo,
                found_owner=found_owner, found_zone=found_zone,
            ) if card else (None, [], None)
        )
        if (
            not card or (found_owner != role and not borrow_rule)
            or not self._combo_zone_allowed(
                role, card, found_zone, legality_combo,
            )
            or not self._combo_card_legal(
                role, projected_card, legality_combo,
                selected_speed=combo_speeds[0] if combo_speeds else None,
                ignore_cost=cost_paid_for == instance_id,
                ignore_optional_speed_cost=(
                    speed_cost_paid_for == instance_id
                ),
                use_optional_ignore=use_optional_penalty_rule,
                use_optional_speed_ignore=use_optional_speed_rule,
            )
        ):
            if combo.get('used'):
                self.emit('combo_interrupted', role, {'reason': 'next_card_illegal', 'card_instance_id': instance_id})
                self.engine_state['pipeline'] = None
                self.end_combo()
                return
            raise IllegalAction('사용할 수 없는 콤보 카드입니다.')
        if cost_paid_for != instance_id and self._begin_play_cost(
            role, card, 'combo', {
                'kind': 'combo', 'card_ids': list(card_ids),
                'combo_speeds': list(combo_speeds), 'card_instance_id': instance_id,
                'ignore_damage_penalty': list(ignore_damage_penalty),
                'ignore_speed': list(ignore_speed),
            },
        ):
            return
        if (
            use_optional_speed_rule
            and speed_cost_paid_for != instance_id
            and self._begin_combo_optional_speed_cost(
                role, card, legality_combo, combo_rules,
                card_ids=card_ids, combo_speeds=combo_speeds,
                ignore_damage_penalty=ignore_damage_penalty,
                ignore_speed=ignore_speed,
                cost_paid_for=cost_paid_for,
            )
        ):
            return
        if use_optional_speed_rule:
            counter_rule = next((
                rule for rule in combo_rules
                if rule.get('optional_any_speed') and rule.get('counter_cost')
            ), None)
            if counter_rule:
                counter_cost = counter_rule.get('counter_cost') or {}
                counter_key = str(counter_cost.get('counter') or '')
                counter_amount = max(0, _number(counter_cost.get('amount')))
                current_count = _number(
                    self.state['players'][role].setdefault(
                        'passive_state', {},
                    ).get(counter_key, {}).get('count')
                )
                if not counter_key or current_count < counter_amount:
                    raise IllegalAction('콤보 속도 예외 비용을 지불할 수 없습니다.')
                self.change_counter(
                    role, counter_key, -counter_amount, minimum=0,
                )
                self.emit('combo_counter_cost_paid', role, {
                    'card_instance_id': instance_id,
                    'counter': counter_key, 'amount': counter_amount,
                    'selected_speed': (
                        combo_speeds[0] if combo_speeds else None
                    ),
                })
        penalty = _number(combo.get('next_penalty'), 100)
        previous_combo_card = copy.deepcopy(self._combo_last_card(combo))
        previous_combo_speed = combo.get('last_speed')
        projected_card, combo_rules, borrow_rule = self._combo_candidate_projection(
            role, card, legality_combo,
            found_owner=found_owner, found_zone=found_zone,
        )
        consumed_usage_keys = set()
        for rule in combo_rules:
            usage_key = self._limited_grant_key(rule)
            if (
                usage_key and usage_key not in consumed_usage_keys
                and (
                    not rule.get('allow_zones')
                    or found_zone in (rule.get('allow_zones') or [])
                )
                and (
                    not rule.get('optional_ignore_damage_penalty')
                    or use_optional_penalty_rule
                )
                and (
                    not rule.get('optional_ignore_speed')
                    or use_optional_speed_rule
                )
            ):
                self._consume_limited_grant(rule, role)
                consumed_usage_keys.add(usage_key)
                if rule.get('skip_get_on_use'):
                    self.engine_state.setdefault('skip_get', {})[role] = True
                    self.emit('combo_rule_get_skip_scheduled', role, {
                        'card_instance_id': instance_id,
                        'source': rule.get('source'),
                        'usage_key': usage_key,
                    })
        applied_penalty = self._combo_applied_penalty(
            role, projected_card, legality_combo, penalty, rules=combo_rules,
            use_optional_ignore=use_optional_penalty_rule,
        )
        available_speeds = self._combo_speed_options(
            role, projected_card, legality_combo, rules=combo_rules,
            use_optional_speed_ignore=use_optional_speed_rule,
        )
        selected_speed = combo_speeds[0] if combo_speeds else available_speeds[0]
        damage_bonus = self._combo_damage_bonus(
            combo_rules, selected_speed,
            use_optional_speed_ignore=use_optional_speed_rule,
        )
        self.move_card(
            instance_id, 'battle', to_player=role if borrow_rule else None,
            reason='borrowed_combo' if borrow_rule else 'combo',
        )
        if borrow_rule:
            card['numbered_effects_negated'] = bool(borrow_rule.get('negate_effects', True))
            card['borrowed_combo'] = {
                'controller': role, 'original_owner': found_owner,
                'return_zone': borrow_rule.get('return_to_owner_zone_on_combo_end') or 'list',
            }
        card['face_up'] = True
        if selected_speed != self.card_stat(
            projected_card, 'frame', role, include_fp=False,
        ):
            self.add_modifier({
                'op': 'fix_speed', 'controller': role, 'player': role,
                'source': instance_id, 'where': {'instance_id': instance_id},
                'stat': 'frame', 'value': selected_speed, 'duration': 'battle',
                'override_fixed': any(
                    rule.get('any_speed')
                    or (
                        use_optional_speed_rule
                        and rule.get('optional_any_speed')
                    )
                    for rule in combo_rules
                ),
            })
        self._mark_card_used(card, role, 'combo')
        combo.setdefault('used', []).append(instance_id)
        combo['next_penalty'] = penalty + 100
        self.engine_state['step'] = 'combo_resolution'
        self.engine_state['pipeline'] = {
            'kind': 'combo_resolution', 'stage': 'combo', 'owner': role,
            'card_instance_id': instance_id, 'card': copy.deepcopy(card),
            'source_from_zone': found_zone,
            'penalty': penalty, 'damage': 0, 'remaining_ids': card_ids[1:],
            'remaining_speeds': combo_speeds[1:], 'combo_speed': selected_speed,
            'remaining_ignore_damage_penalty': ignore_damage_penalty[1:],
            'remaining_ignore_speed': ignore_speed[1:],
            'used_optional_ignore_damage_penalty': use_optional_penalty_rule,
            'used_optional_ignore_speed': use_optional_speed_rule,
            'combo_rules': copy.deepcopy(combo_rules),
            'previous_combo_card': previous_combo_card,
            'previous_combo_speed': previous_combo_speed,
        }
        self._refresh_continuous_rules()
        pipeline_card = self.engine_state['pipeline']['card']
        damage = max(
            0,
            self.card_stat(pipeline_card, 'damage', role)
            - applied_penalty + damage_bonus,
        )
        self.engine_state['pipeline']['damage'] = damage
        self.emit('combo_card_used', role, {
            'card_instance_id': instance_id, 'damage': damage,
        })

    def _return_borrowed_combo_cards(self, combo):
        combo_owner = combo.get('owner')
        for side in PLAYER_SIDES:
            for cards in list(self.state['players'][side]['zones'].values()):
                for card in list(cards):
                    borrowed = card.get('borrowed_combo') or {}
                    if borrowed.get('controller') != combo_owner:
                        continue
                    instance_id = card.get('instance_id')
                    original_owner = borrowed.get('original_owner')
                    return_zone = borrowed.get('return_zone') or 'list'
                    self.move_card(
                        instance_id, return_zone, to_player=original_owner,
                        reason='borrowed_combo_return',
                    )
                    returned = self._find_card(instance_id)
                    if returned:
                        returned.pop('borrowed_combo', None)
                        returned.pop('numbered_effects_negated', None)
                    self.emit('borrowed_combo_returned', combo_owner, {
                        'card_instance_id': instance_id,
                        'owner': original_owner, 'zone': return_zone,
                    })

    def _advance_combo_pipeline(self, pipeline):
        combo = self.engine_state.get('combo')
        if not combo:
            self.engine_state['pipeline'] = None
            return False
        role, card = pipeline['owner'], pipeline['card']
        context = {
            'controller': role, 'source_card_instance_id': pipeline['card_instance_id'],
            'source_card': card, 'combo': True, 'use_context': 'combo',
            'source_from_zone': pipeline.get('source_from_zone'),
            'combo_number': self._current_combo_number(combo),
            'combo_speed': pipeline.get('combo_speed'),
            'combo_previous_card': copy.deepcopy(
                pipeline.get('previous_combo_card'),
            ),
            'combo_previous_speed': pipeline.get('previous_combo_speed'),
            'combo_proposed_card_ids': list(
                combo.get('proposed_card_ids') or []
            ),
            'combo_speed_ignored': bool(
                pipeline.get('used_optional_ignore_speed')
            ),
        }
        stage = pipeline['stage']
        if stage == 'combo':
            pipeline['stage'] = 'combo_window'
            self._fire('combo', {**context, 'source_only_event': True})
            return not self.is_waiting
        if stage == 'combo_window':
            pipeline['stage'] = 'use'
            self._fire('combo_window', context)
            return not self.is_waiting
        if stage == 'use':
            pipeline['stage'] = 'hit'
            self._fire('use', context)
            return not self.is_waiting
        if stage == 'hit':
            if (
                not pipeline.get('continue_after_source_left')
                and not self._find_card(
                    pipeline['card_instance_id'], owner=role, zone='battle',
                )
            ):
                return self._interrupt_combo_resolution(pipeline, 'source_card_left_battle')
            pipeline['stage'] = 'damage'
            self._fire('hit', context)
            return not self.is_waiting
        if stage == 'damage':
            if (
                not pipeline.get('continue_after_source_left')
                and not self._find_card(
                    pipeline['card_instance_id'], owner=role, zone='battle',
                )
            ):
                return self._interrupt_combo_resolution(pipeline, 'source_card_left_battle')
            pipeline['stage'] = 'after_use'
            rules_combo = copy.deepcopy(combo)
            used = list(rules_combo.get('used') or [])
            if used and used[-1] == pipeline.get('card_instance_id'):
                rules_combo['used'] = used[:-1]
            applied_penalty = self._combo_applied_penalty(
                role, card, rules_combo, _number(pipeline.get('penalty'), 100),
                use_optional_ignore=bool(
                    pipeline.get('used_optional_ignore_damage_penalty')
                ),
            )
            combo_rules = self._combo_rules(role, card, rules_combo)
            damage_bonus = self._combo_damage_bonus(
                combo_rules, pipeline.get('combo_speed'),
                use_optional_speed_ignore=bool(
                    pipeline.get('used_optional_ignore_speed')
                ),
            )
            pipeline['damage'] = max(
                0, self.card_stat(card, 'damage', role) - applied_penalty + damage_bonus,
            )
            self.deal_damage(opponent(role), pipeline['damage'], source='combo', context=context)
            self.change_fp(role, _fp_value(card.get('hit')), source='combo', context=context)
            return not self.is_waiting
        if stage == 'after_use':
            pipeline['stage'] = 'done'
            self._fire('after_use', context)
            return not self.is_waiting
        resolved_rules = pipeline.get('combo_rules') or self._combo_rules(role, card, combo)
        if (
            any(
                self._combo_rule_breaks_after_use(
                    rule, pipeline.get('combo_speed'),
                    use_optional_ignore=bool(
                        pipeline.get(
                            'used_optional_ignore_damage_penalty'
                        )
                    ),
                )
                for rule in resolved_rules
            )
            and not pipeline.get('break_after_use_resolved')
        ):
            pipeline['break_after_use_resolved'] = True
            self.break_card(
                pipeline['card_instance_id'], reason='combo_rule_after_use',
                effect_controller=role, effect_source=pipeline.get('card_instance_id'),
            )
            if self.is_waiting:
                return False
        if any(rule.get('end_after_use') for rule in resolved_rules):
            self.engine_state['pipeline'] = None
            self.engine_state['step'] = 'combo'
            self.end_combo()
            if (
                any(rule.get('return_to_hand_after_use') for rule in resolved_rules)
                and self._find_card(pipeline['card_instance_id'], owner=role, zone='battle')
            ):
                self.move_card(
                    pipeline['card_instance_id'], 'hand',
                    reason='combo_rule_after_use_return',
                )
            return True
        remaining = list(pipeline.get('remaining_ids') or [])
        combo['last_speed'] = self.card_stat(card, 'frame', role, include_fp=False)
        combo['last_speed_ignored'] = bool(
            pipeline.get('used_optional_ignore_speed')
        )
        self.engine_state['pipeline'] = None
        self.engine_state['step'] = 'combo'
        if self.engine_state.get('status') == 'running' and self.engine_state.get('combo'):
            if remaining:
                self._start_combo_card(
                    role, remaining, pipeline.get('remaining_speeds') or [],
                    pipeline.get('remaining_ignore_damage_penalty') or [],
                    pipeline.get('remaining_ignore_speed') or [],
                )
            elif (
                not self._reopen_required_combo_followup(role, combo)
                and not self._reopen_optional_combo_grant(role, combo)
                and not self._reopen_combo_continuation(role, combo)
            ):
                self.end_combo()
        return True

    @staticmethod
    def _combo_rule_breaks_after_use(
        rule, selected_speed, *, use_optional_ignore=False,
    ):
        if not (rule or {}).get('break_after_use'):
            return False
        if (
            rule.get('break_on_optional_ignore_damage_penalty')
            and not use_optional_ignore
        ):
            return False
        speeds = rule.get('break_after_use_speeds')
        return not speeds or _number(selected_speed) in {
            _number(speed) for speed in speeds
        }

    def _interrupt_combo_resolution(self, pipeline, reason):
        role = pipeline.get('owner')
        self.emit('combo_interrupted', role, {
            'reason': reason, 'card_instance_id': pipeline.get('card_instance_id'),
        })
        self.engine_state['pipeline'] = None
        self.engine_state['step'] = 'combo'
        remaining = list(pipeline.get('remaining_ids') or [])
        if self.engine_state.get('status') == 'running' and self.engine_state.get('combo'):
            if remaining:
                self._start_combo_card(
                    role, remaining, pipeline.get('remaining_speeds') or [],
                    pipeline.get('remaining_ignore_damage_penalty') or [],
                    pipeline.get('remaining_ignore_speed') or [],
                )
            else:
                self.end_combo()
        return True

    def _combo_speed_options(
        self, role, card, combo, *, rules=None,
        use_optional_speed_ignore=False,
    ):
        rules = self._combo_rules(role, card, combo) if rules is None else rules
        speeds = {max(1, _number(self.card_stat(card, 'frame', role, include_fp=False), 1))}
        optional_any_speed = bool(
            use_optional_speed_ignore
            and any(rule.get('optional_any_speed') for rule in rules)
        )
        any_speed = any(rule.get('any_speed') for rule in rules) or optional_any_speed
        if any_speed:
            maximum = max(
                [
                    max(1, _number(self.card_stat(candidate, 'frame', role, include_fp=False), 1))
                    for zone in self.state['players'][role]['zones'].values()
                    for candidate in zone
                    if _is_attack(candidate) and not _is_special(candidate)
                ]
                or list(speeds)
            )
            maximum = max(maximum, _number(combo.get('last_speed'), 0) + 2)
            speeds.update(range(1, maximum + 1))
        for rule in rules:
            rule_speeds = {
                max(1, _number(value, 1))
                for value in (rule.get('speed_options') or [])
            }
            speeds.update(rule_speeds)
        # ``_combo_actions`` removes the opener's Speed while proposing the
        # initial 2-Combo. From 3-Combo onward ordinary characters link at
        # exactly +1 Speed; rules such as Viola's Matude widen that window.
        last_speed = combo.get('last_speed')
        # Some "declare any Speed" effects also bypass the link window, while
        # Matude explicitly does not (Q&A 125). Keep that distinction on the
        # concrete grant so unrelated cards such as Heretic Execution retain
        # their reviewed behavior.
        optional_any_speed_ignores_link = bool(
            optional_any_speed
            and any(
                rule.get('optional_any_speed')
                and not self._combo_rule_respects_speed_window(rule)
                for rule in rules
            )
        )
        ignore_speed = (
            any(rule.get('ignore_speed') for rule in rules)
            or optional_any_speed_ignores_link
            or bool(
                use_optional_speed_ignore
                and any(rule.get('optional_ignore_speed') for rule in rules)
            )
        )
        maximum_deltas = [
            _number(rule.get('max_speed_delta'))
            for rule in rules
            if _number(rule.get('max_speed_delta')) > 0
        ]
        # Card review sandboxes isolate an effect's own speed choices and do
        # not model a character's ordinary link rule. Real rulesets always
        # start at +1; explicit grants can widen it (Matude: +2).
        if str(self.ruleset.get('version') or '') != 'automatic-effect-v2':
            maximum_deltas.append(1)
        maximum_delta = max(maximum_deltas) if maximum_deltas else None
        bypass_maximum_delta = any(rule.get('any_speed') for rule in rules)
        return sorted(
            speed for speed in speeds
            if (
                ignore_speed
                or last_speed is None
                or (
                    speed >= _number(last_speed) + 1
                    and (
                        maximum_delta is None
                        or bypass_maximum_delta
                        or speed <= _number(last_speed) + maximum_delta
                    )
                )
            )
        )

    def _combo_rule_source_code(self, rule, fallback_card=None):
        """Resolve the card which granted a Combo rule.

        Immutable ruleset releases can predate newly explicit DSL flags.  The
        source instance is retained on both card rules and passive modifiers,
        so established card rulings can remain compatible without mutating a
        published release.
        """
        source_card = self._find_card((rule or {}).get('source'))
        source_card = source_card or fallback_card or {}
        return str(source_card.get('code') or '').strip().upper()

    def _combo_rule_respects_speed_window(self, rule):
        if (rule or {}).get('respect_speed_window') is True:
            return True
        # ST6-PS1 Matude: spending three Hidden Bond counters lets the player
        # declare the card's Speed, but Q&A 125 still requires that declared
        # Speed to be exactly +1 or +2 from the preceding Combo Technique.
        return bool(
            (rule or {}).get('optional_any_speed')
            and (rule or {}).get('counter_cost') == {
                'counter': 'hidden_bond', 'amount': 3,
            }
            and self._combo_rule_source_code(rule) == 'ST6-PS1'
        )

    def _combo_rule_allows_reuse(self, rule, card=None):
        if (rule or {}).get('allow_reuse') is True:
            return True
        # CB02-AT-026 Tempo de Deux: releases published before allow_reuse
        # existed already carry this unique, once-per-turn Battle reuse key.
        return bool(
            (rule or {}).get('usage_key') == 'cb02-at-026-battle-reuse'
            and (rule or {}).get('max_uses') == 1
            and self._combo_rule_source_code(rule, card) == 'CB02-AT-026'
        )

    def _combo_maximum(self, role, combo):
        """Return an explicit Combo cap, or ``None`` when it is unbounded.

        The rules do not impose a default maximum Combo number.  A cap exists
        only when the open Combo or an active effect explicitly installs one.
        Legacy extension rules remain meaningful when such a soft cap exists,
        while ``max_combo_cap`` is always a hard restriction.
        """
        maximum = (
            max(1, _number(combo.get('max_combo'), 1))
            if combo.get('max_combo') is not None else None
        )
        modifiers = [
            *(self.engine_state.get('modifiers') or []),
            *(combo.get('proposal_modifiers') or []),
        ]
        caps = []
        extensions = []
        extension_keys = set()
        required_followups = self._required_combo_followup_rules(
            role, combo, include_previews=True,
        )
        for modifier in modifiers:
            if modifier.get('op') != 'modify_combo':
                continue
            target = modifier.get('player') or modifier.get('controller')
            usage_key = self._limited_grant_key(modifier)
            if (
                (target and target != role)
                or not self._limited_grant_projected_available(
                    modifier, role, combo,
                )
            ):
                continue
            if (
                modifier.get('max_combo') is not None
                and not modifier.get('allow_zones')
            ):
                value = max(1, _number(modifier.get('max_combo'), 1))
                maximum = value if maximum is None else max(maximum, value)
            if modifier.get('max_combo_cap') is not None:
                caps.append(max(
                    1, _number(modifier.get('max_combo_cap'), 1),
                ))
            if modifier in required_followups and maximum is not None:
                maximum = max(maximum, self._next_combo_number(combo))
            extension = _number(modifier.get('extend_combo_by'))
            if extension > 0:
                if usage_key and usage_key in extension_keys:
                    continue
                if usage_key:
                    extension_keys.add(usage_key)
                extensions.append(extension)
        # Older releases encoded "N Combo or later" permissions as an
        # extension from the former default cap. They only need to raise a
        # real, explicitly installed soft cap now; an unbounded Combo needs no
        # extension at all.
        if maximum is not None:
            last_card = self._combo_last_card(combo)
            for zone, cards in self.state['players'][role]['zones'].items():
                for card in cards:
                    if not _is_attack(card) or _is_special(card):
                        continue
                    definition = self._definition_for_card(card)
                    for rule in definition.get('combo_rules') or []:
                        if not isinstance(rule, dict):
                            continue
                        if (
                            rule.get('numbered_effect')
                            and card.get('numbered_effects_negated')
                        ):
                            continue
                        extension = _number(
                            rule.get('extend_combo_to') or rule.get('min_combo')
                        )
                        if extension <= maximum:
                            continue
                        if zone != 'hand' and zone not in (rule.get('allow_zones') or []):
                            continue
                        if rule.get('where') and not card_matches(card, rule.get('where')):
                            continue
                        if rule.get('after_where') and not card_matches(
                            last_card, rule.get('after_where'), self.state,
                            {'controller': role, 'source_card': card,
                             'opponent_card': last_card,
                             'combo_number': extension},
                        ):
                            continue
                        context = {
                            'controller': role, 'player': role,
                            'source_card': card, 'opponent_card': last_card,
                            'combo_number': extension,
                        }
                        if not condition_matches(rule.get('condition'), self.state, context):
                            continue
                        if not self._card_use_allowed(card, role, 'combo'):
                            continue
                        maximum = extension
            maximum += sum(extensions)
        if caps:
            hard_cap = min(caps)
            maximum = hard_cap if maximum is None else min(maximum, hard_cap)
        return max(1, int(maximum)) if maximum is not None else None

    def _combo_candidate_maximum(self, role, card, combo, rules):
        """Return the deepest slot this concrete card may occupy.

        Global enumeration uses ``_combo_maximum`` so a later slot can be
        offered at all.  This second bound keeps zone-scoped grants attached
        to their intended candidate: a list-only extension must not let an
        ordinary Hand card occupy the extra slot.  ``extend_combo_by`` stacks
        after fixed maximum grants, which is required when Thief Gimmick adds
        one use after Madness has already opened the fourth Combo (Q&A 665).
        """
        maximum = (
            max(1, _number(combo.get('max_combo'), 1))
            if combo.get('max_combo') is not None else None
        )
        found_owner, card_zone, _index, _live = self._find_location(
            (card or {}).get('instance_id'),
        )
        caps = []
        extensions = []
        extension_keys = set()
        unbounded_zone_permission = False
        for rule in rules or []:
            allow_zones = rule.get('allow_zones') or []
            zone_scoped = bool(allow_zones)
            extension_applies = not zone_scoped or card_zone in allow_zones
            if rule.get('op') == 'modify_combo':
                if (
                    zone_scoped and extension_applies
                    and rule.get('max_combo') is None
                    and rule.get('max_combo_cap') is None
                ):
                    # Zone permissions are alternatives, not cumulative
                    # restrictions. A one-use List grant without a Combo
                    # number remains usable even if another List permission
                    # only covers (for example) up to 4-Combo.
                    unbounded_zone_permission = True
                if (
                    rule.get('requires_followup')
                    and self._combo_rule_location_allowed(
                        rule, role, found_owner, card_zone,
                    )
                ):
                    if maximum is not None:
                        maximum = max(
                            maximum, self._next_combo_number(combo),
                        )
                if extension_applies and rule.get('max_combo') is not None:
                    value = max(1, _number(rule.get('max_combo'), 1))
                    maximum = value if maximum is None else max(maximum, value)
                if rule.get('max_combo_cap') is not None:
                    caps.append(max(
                        1, _number(rule.get('max_combo_cap'), 1),
                    ))
                extension = (
                    _number(rule.get('extend_combo_by'))
                    if extension_applies else 0
                )
                if extension > 0:
                    usage_key = self._limited_grant_key(rule)
                    if usage_key and usage_key in extension_keys:
                        continue
                    if usage_key:
                        extension_keys.add(usage_key)
                    extensions.append(extension)
            elif extension_applies and maximum is not None:
                maximum = max(
                    maximum,
                    _number(rule.get('extend_combo_to')),
                    _number(rule.get('min_combo')),
                )
        if maximum is not None:
            maximum += sum(extensions)
        if unbounded_zone_permission:
            maximum = None
        if caps:
            hard_cap = min(caps)
            maximum = hard_cap if maximum is None else min(maximum, hard_cap)
        return max(1, int(maximum)) if maximum is not None else None

    def _combo_card_legal(
        self, role, card, combo, *, selected_speed=None, ignore_cost=False,
        use_optional_ignore=False, use_optional_speed_ignore=False,
        ignore_optional_speed_cost=False,
    ):
        if not _is_attack(card) or _is_special(card):
            return False
        rules = self._combo_rules(role, card, combo)
        required_followups = self._required_combo_followup_rules(role, combo)
        if required_followups:
            found_owner, found_zone, _index, _live = self._find_location(
                (card or {}).get('instance_id'),
            )
            if not any(
                rule in required_followups
                and self._combo_rule_location_allowed(
                    rule, role, found_owner, found_zone,
                )
                for rule in rules
            ):
                return False
        counter_rule = next((
            rule for rule in rules
            if use_optional_speed_ignore
            and rule.get('optional_any_speed') and rule.get('counter_cost')
        ), None)
        projected_counters = copy.deepcopy(
            ((combo.get('counter_overrides') or {}).get(role) or {})
        )
        passive_state = self.state['players'][role].setdefault(
            'passive_state', {},
        )
        originals = {}
        for counter_key, projected_count in projected_counters.items():
            originals[counter_key] = (
                counter_key in passive_state,
                copy.deepcopy(passive_state.get(counter_key)),
            )
            passive_state.setdefault(counter_key, {})['count'] = _number(
                projected_count,
            )
        if counter_rule:
            counter_cost = counter_rule.get('counter_cost') or {}
            counter_key = str(counter_cost.get('counter') or '')
            counter_amount = max(0, _number(counter_cost.get('amount')))
            if not counter_key:
                for key, (existed, original) in originals.items():
                    if existed:
                        passive_state[key] = original
                    else:
                        passive_state.pop(key, None)
                return False
            if counter_key not in originals:
                originals[counter_key] = (
                    counter_key in passive_state,
                    copy.deepcopy(passive_state.get(counter_key)),
                )
            state_entry = passive_state.setdefault(counter_key, {})
            before_count = _number(state_entry.get('count'))
            if before_count < counter_amount:
                for key, (existed, original) in originals.items():
                    if existed:
                        passive_state[key] = original
                    else:
                        passive_state.pop(key, None)
                return False
            # Q&A 124: the counter cost is paid before the selected card's
            # own use requirement is checked.  Evaluate that requirement on a
            # temporary state and restore it without emitting public events.
            state_entry['count'] = before_count - counter_amount
        try:
            use_allowed = self._card_use_allowed(
                card, role, 'combo', ignore_cost=ignore_cost,
            )
        finally:
            for key, (existed, original) in originals.items():
                if existed:
                    passive_state[key] = original
                else:
                    passive_state.pop(key, None)
        if not use_allowed:
            return False
        opponent_card = ((self.engine_state.get('battle') or {}).get(opponent(role)) or {}).get('card')
        if self._rule_blocked('combo', role, card, opponent_card):
            return False
        if use_optional_ignore and not any(
            rule.get('optional_ignore_damage_penalty') for rule in rules
        ):
            return False
        if use_optional_speed_ignore and not any(
            rule.get('optional_ignore_speed') or rule.get('optional_any_speed')
            for rule in rules
        ):
            return False
        if (
            use_optional_speed_ignore
            and not ignore_optional_speed_cost
            and not self._combo_optional_speed_cost_affordable(
                role, card, combo, rules,
            )
        ):
            return False
        combo_number = self._next_combo_number(combo)
        maximum = self._combo_maximum(role, combo)
        if maximum is not None and combo_number > maximum:
            return False
        candidate_maximum = self._combo_candidate_maximum(
            role, card, combo, rules,
        )
        if (
            candidate_maximum is not None
            and combo_number > candidate_maximum
        ):
            return False
        if any(rule.get('min_combo') and combo_number < _number(rule.get('min_combo')) for rule in rules):
            return False
        if any(
            rule.get('op') != 'modify_combo'
            and rule.get('max_combo')
            and combo_number > _number(rule.get('max_combo'))
            for rule in rules
        ):
            return False
        penalty = self._combo_applied_penalty(
            role, card, combo, _number(combo.get('next_penalty'), 100), rules=rules,
            use_optional_ignore=use_optional_ignore,
        )
        speed_options = self._combo_speed_options(
            role, card, combo, rules=rules,
            use_optional_speed_ignore=use_optional_speed_ignore,
        )
        if selected_speed is not None:
            speed = _number(selected_speed)
            return bool(
                speed in speed_options
                and self.card_stat(card, 'damage', role) - penalty
                + self._combo_damage_bonus(
                    rules, speed,
                    use_optional_speed_ignore=use_optional_speed_ignore,
                ) > 0
            )
        return any(
            self.card_stat(card, 'damage', role) - penalty
            + self._combo_damage_bonus(
                rules, speed,
                use_optional_speed_ignore=use_optional_speed_ignore,
            ) > 0
            for speed in speed_options
        )

    def _combo_last_card(self, combo):
        used = combo.get('used') or []
        instance_id = used[-1] if used else combo.get('source')
        return self._find_card(instance_id) if instance_id else None

    def _combo_rules(self, role, card, combo):
        last_card = self._combo_last_card(combo)
        _card_owner, card_zone, _card_index, _live_card = self._find_location(
            (card or {}).get('instance_id'),
        )
        definition = self._definition_for_card(card)
        rules = []
        static_context = {
            'controller': role, 'player': role, 'opponent': opponent(role),
            'source_card': card,
            'opponent_card': last_card,
            'combo_number': self._next_combo_number(combo),
            # Effect-modified reference Speed of the immediately preceding
            # Combo Technique. FP never changes this value (ST2-001,
            # Q&A 166/400).
            'combo_previous_speed': combo.get('last_speed'),
            # 2/3-combo cards are presented together. Conditions that inspect
            # Hand size may therefore exclude every card in the active
            # proposal, including cards that the sequential resolver has not
            # moved to Battle yet (Q&A 578).
            'combo_proposed_card_ids': list(
                combo.get('proposed_card_ids')
                or combo.get('used') or []
            ),
            'controller_hp': self.state['players'][role].get('hp'),
            'controller_fp': self.state['players'][role].get('fp'),
            'opponent_hp': self.state['players'][opponent(role)].get('hp'),
            'opponent_fp': self.state['players'][opponent(role)].get('fp'),
        }
        for rule in definition.get('combo_rules') or []:
            if not isinstance(rule, dict):
                continue
            if (
                rule.get('numbered_effect')
                and (card or {}).get('numbered_effects_negated')
            ):
                continue
            usage_key = self._limited_grant_key(rule)
            if usage_key and not self._limited_grant_projected_available(
                rule, role, combo,
            ):
                continue
            if rule.get('source_zones') and card_zone not in (
                rule.get('source_zones') or []
            ):
                continue
            if rule.get('where') and not card_matches(card, rule.get('where')):
                continue
            if rule.get('after_where') and not card_matches(last_card, rule.get('after_where')):
                continue
            if not condition_matches(rule.get('condition'), self.state, static_context):
                continue
            rules.append({
                **copy.deepcopy(rule), 'controller': role, 'player': role,
                'source': card.get('instance_id'),
            })
        modifiers = [
            *(self.engine_state.get('modifiers') or []),
            *(combo.get('proposal_modifiers') or []),
        ]
        for modifier in modifiers:
            if modifier.get('op') != 'modify_combo':
                continue
            target = modifier.get('player') or modifier.get('controller')
            if target and target != role:
                continue
            usage_key = self._limited_grant_key(modifier)
            if usage_key and not self._limited_grant_projected_available(
                modifier, role, combo,
            ):
                continue
            if modifier.get('source_zones') and card_zone not in (
                modifier.get('source_zones') or []
            ):
                continue
            if (
                modifier.get('exclude_source')
                and card.get('instance_id') == modifier.get('source')
            ):
                continue
            if modifier.get('where') and not card_matches(card, modifier.get('where')):
                continue
            if modifier.get('after_source_sequence'):
                predecessor_ids = {
                    *([combo.get('source')] if combo.get('source') else []),
                    *(combo.get('used') or []),
                }
                if modifier.get('source') not in predecessor_ids:
                    continue
            if modifier.get('after_where') and not card_matches(last_card, modifier.get('after_where')):
                continue
            context = {
                'controller': modifier.get('controller'), 'player': role,
                'source_card': card, 'opponent_card': last_card,
                'combo_number': self._next_combo_number(combo),
                'combo_previous_speed': combo.get('last_speed'),
            }
            if not condition_matches(modifier.get('condition'), self.state, context):
                continue
            rules.append(modifier)
        return rules

    def _combo_proposal_modifiers(self, role, card, combo):
        """Preview source-dependent follow-up permissions for one proposal.

        Combo cards are presented together, so an action must be issuable
        before the first proposed card resolves. Some cards explicitly grant
        permission to reuse a prior card *after this card*. We preview only
        direct ``modify_combo`` commands carrying ``after_source`` or
        ``after_source_sequence``; the real effect still has to resolve and
        each later card is checked again before use. Declining an optional
        effect or losing its condition therefore interrupts the proposed
        remainder safely.
        """
        definition = self._definition_for_card(card)
        context = {
            'controller': role, 'player': role, 'opponent': opponent(role),
            'source_card': card,
            'source_card_instance_id': card.get('instance_id'),
            'event_card': card,
            'event_card_instance_id': card.get('instance_id'),
            'combo': True, 'use_context': 'combo',
            'combo_number': self._next_combo_number(combo),
        }
        previews = []
        for ability in definition.get('abilities') or []:
            if (
                card.get('numbered_effects_negated')
                and ability.get('kind') == 'effect'
            ):
                continue
            active_zones = ability.get('active_zones')
            if active_zones is not None and 'battle' not in active_zones:
                continue
            trigger = ability.get('trigger') or {}
            events = set(trigger.get('events') or [trigger.get('event')])
            if not events.intersection({'combo', 'combo_window'}):
                continue
            if not condition_matches(ability.get('condition'), self.state, context):
                continue
            if (
                ability.get('availability_selector') is not None
                and not self.selector_has_minimum(
                    ability.get('availability_selector'), context,
                )
            ):
                continue
            for effect in ability.get('effects') or []:
                if (
                    effect.get('op') != 'modify_combo'
                    or not (
                        effect.get('after_source')
                        or effect.get('after_source_sequence')
                    )
                ):
                    continue
                resolved = copy.deepcopy(effect)
                if resolved.pop('after_source', False):
                    resolved['after_where'] = {
                        **copy.deepcopy(resolved.get('after_where') or {}),
                        'instance_id': card.get('instance_id'),
                    }
                target = resolved.get('player')
                if isinstance(target, dict) and target.get('opponent'):
                    target = opponent(role)
                elif isinstance(target, dict):
                    target = role
                resolved.update({
                    'controller': role,
                    'player': target if target in PLAYER_SIDES else role,
                    'source': card.get('instance_id'),
                    'proposal_preview': True,
                })
                previews.append(resolved)
        return previews

    def _project_combo_counter_overrides(
        self, role, card, combo, rules, *, selected_speed,
        use_optional_speed_ignore=False,
    ):
        """Preview counter payment/gain between jointly proposed cards.

        Combo cards are revealed together but resolve one at a time.  The
        preview lets a later card become legal from an earlier card's known
        After-use counter gain (Q&A 625), while execution still rechecks the
        real state before each card.
        """
        overrides = copy.deepcopy(combo.get('counter_overrides') or {})
        player_overrides = overrides.setdefault(role, {})

        def current(counter_key):
            if counter_key in player_overrides:
                return _number(player_overrides[counter_key])
            return _number(
                self.state['players'][role].setdefault(
                    'passive_state', {},
                ).get(counter_key, {}).get('count')
            )

        if use_optional_speed_ignore:
            counter_rule = next((
                rule for rule in rules
                if rule.get('optional_any_speed') and rule.get('counter_cost')
            ), None)
            if counter_rule:
                cost = counter_rule.get('counter_cost') or {}
                key = str(cost.get('counter') or '')
                if key:
                    player_overrides[key] = max(
                        0, current(key) - _number(cost.get('amount')),
                    )

        previous_speed = combo.get('last_speed')
        for rule in rules:
            gain = rule.get('counter_on_speed_delta') or {}
            key = str(gain.get('counter') or '')
            if (
                not key or previous_speed is None
                or _number(selected_speed)
                != _number(previous_speed) + _number(gain.get('delta'))
            ):
                continue
            value = current(key) + _number(gain.get('amount'), 1)
            if gain.get('max') is not None:
                value = min(value, _number(gain.get('max')))
            player_overrides[key] = max(0, value)
        return overrides

    def _combo_zone_allowed(self, role, card, zone, combo):
        if zone == 'hand':
            return True
        return any(zone in (rule.get('allow_zones') or []) for rule in self._combo_rules(role, card, combo))

    @staticmethod
    def _combo_rule_location_allowed(rule, role, found_owner, found_zone):
        if rule.get('borrow_from') == 'opponent':
            if found_owner != opponent(role):
                return False
        elif found_owner != role:
            return False
        allow_zones = rule.get('allow_zones') or []
        return not allow_zones or found_zone in allow_zones

    def _combo_candidate_projection(
        self, role, card, combo, *, found_owner=None, found_zone=None,
    ):
        """Project a Combo candidate under the permission that will use it.

        A borrowed opponent card has its numbered effects negated before its
        use requirements, speed options, and proposal effects are inspected
        (Q&A 423). Numberless functions still participate in the projection.
        """
        if not card:
            return None, [], None
        if found_owner is None or found_zone is None:
            found_owner, found_zone, _index, _live = self._find_location(
                card.get('instance_id'),
            )

        projected = self._project_card_for_use(card, role, 'combo')
        rules = self._combo_rules(role, projected, combo)

        def borrow_rule(candidates):
            return next((
                rule for rule in candidates
                if rule.get('borrow_from') == 'opponent'
                and self._combo_rule_location_allowed(
                    rule, role, found_owner, found_zone,
                )
            ), None)

        initial_borrow = borrow_rule(rules)
        if found_owner != opponent(role):
            return projected, rules, initial_borrow

        negated_seed = copy.deepcopy(card)
        negated_seed['numbered_effects_negated'] = True
        negated_projected = self._project_card_for_use(
            negated_seed, role, 'combo',
        )
        negated_rules = self._combo_rules(role, negated_projected, combo)
        negated_borrow = borrow_rule(negated_rules)
        if negated_borrow and negated_borrow.get('negate_effects', True):
            return negated_projected, negated_rules, negated_borrow
        if initial_borrow and initial_borrow.get('negate_effects', True):
            return negated_projected, negated_rules, None
        return projected, rules, initial_borrow

    def _required_combo_followup_rules(
        self, role, combo, *, include_previews=False,
    ):
        if role not in PLAYER_SIDES or not combo:
            return []
        last_card = self._combo_last_card(combo)
        if not last_card:
            return []
        predecessor_ids = {
            *([combo.get('source')] if combo.get('source') else []),
            *(combo.get('used') or []),
        }
        required = []
        for modifier in [
            *(self.engine_state.get('modifiers') or []),
            *(combo.get('proposal_modifiers') or []),
        ]:
            if (
                modifier.get('op') != 'modify_combo'
                or not modifier.get('requires_followup')
                or (modifier.get('proposal_preview') and not include_previews)
                or (modifier.get('player') or modifier.get('controller')) not in {
                    None, role,
                }
                or not self._limited_grant_available(modifier, role)
                or (
                    modifier.get('after_source_sequence')
                    and modifier.get('source') not in predecessor_ids
                )
                or (
                    modifier.get('after_where')
                    and not card_matches(last_card, modifier.get('after_where'))
                )
            ):
                continue
            required.append(modifier)
        return required

    def _reopen_required_combo_followup(self, role, combo):
        if not self._required_combo_followup_rules(role, combo):
            return False
        combo['proposal_submitted'] = False
        combo.pop('proposed_card_ids', None)
        combo.pop('proposal_size', None)
        actions = self._combo_actions(role, combo)
        if not actions:
            return False
        self.emit('combo_followup_required', role, {
            'after_card_instance_id': (self._combo_last_card(combo) or {}).get(
                'instance_id'
            ),
            'legal_action_count': len(actions),
        })
        return True

    def _reopen_optional_combo_grant(self, role, combo):
        """Reopen Combo after a mid-resolution optional zone grant.

        A Combo proposal is normally submitted as one sequence. Some effects
        can be accepted at a later Combo timing and only then permit a card
        from another zone. Such a permission must reopen the action window,
        while still leaving ``end_combo`` available because using it is not
        mandatory.
        """
        grants = [
            modifier
            for modifier in self.engine_state.get('modifiers') or []
            if modifier.get('op') == 'modify_combo'
            and modifier.get('reopen_combo')
            and (modifier.get('player') or modifier.get('controller'))
            in {None, role}
            and self._limited_grant_available(modifier, role)
        ]
        if not grants:
            return False
        combo['proposal_submitted'] = False
        combo.pop('proposed_card_ids', None)
        combo.pop('proposal_size', None)
        granted_actions = []
        for action in self._combo_actions(role, combo):
            payload = action.get('payload') or {}
            card_ids = payload.get('card_instance_ids') or [
                payload.get('card_instance_id'),
            ]
            if any(
                found_card
                and found_zone in (grant.get('allow_zones') or [])
                and (
                    not grant.get('where')
                    or card_matches(found_card, grant.get('where'))
                )
                for card_id in card_ids
                for _found_owner, found_zone, _index, found_card
                in [self._find_location(card_id)]
                for grant in grants
            ):
                granted_actions.append(action)
        if not granted_actions:
            return False
        self.emit('combo_optional_grant_opened', role, {
            'sources': sorted({
                str(grant.get('source')) for grant in grants
                if grant.get('source')
            }),
        })
        return True

    def _reopen_combo_continuation(self, role, combo):
        """Offer fourth-or-later Combo cards after the prior batch resolves."""
        if (
            role not in PLAYER_SIDES or not combo
            or combo.get('special') or len(combo.get('used') or []) < 2
        ):
            return False
        combo['proposal_submitted'] = False
        combo.pop('proposed_card_ids', None)
        combo.pop('proposal_size', None)
        actions = self._combo_actions(role, combo)
        if not actions:
            return False
        self.emit('combo_continuation_opened', role, {
            'after_card_instance_id': (self._combo_last_card(combo) or {}).get(
                'instance_id'
            ),
            'legal_action_count': len(actions),
            'next_combo_number': self._next_combo_number(combo),
        })
        return True

    def _combo_applied_penalty(
        self, role, card, combo, penalty, *, rules=None,
        use_optional_ignore=False,
    ):
        rules = self._combo_rules(role, card, combo) if rules is None else rules
        ignores_penalty = any(rule.get('ignore_damage_penalty') for rule in rules)
        if use_optional_ignore:
            # The server-issued action already proved the optional grant was
            # legal.  Its usage is consumed before damage resolves, so looking
            # it up again here would incorrectly restore the normal penalty.
            ignores_penalty = True
        return 0 if ignores_penalty else penalty

    @staticmethod
    def _combo_damage_bonus(
        rules, selected_speed=None, *, use_optional_speed_ignore=False,
    ):
        return sum(
            _number(rule.get('damage_bonus'))
            for rule in rules or []
            if (
                rule.get('damage_bonus_speed') is None
                or (
                    selected_speed is not None
                    and _number(rule.get('damage_bonus_speed'))
                    == _number(selected_speed)
                )
            )
        )

    @staticmethod
    def _limited_grant_key(grant):
        key = (grant or {}).get('usage_key')
        if (
            key and (grant or {}).get('usage_key_source_scoped')
            and (grant or {}).get('source')
        ):
            key = f'{key}:{grant.get("source")}'
        return key

    def _combo_rule_usage_keys(
        self, rules, found_zone, *, use_optional_ignore=False,
        use_optional_speed_ignore=False,
    ):
        """Return limited grants consumed by one proposed Combo card."""
        return {
            usage_key
            for rule in rules or []
            for usage_key in [self._limited_grant_key(rule)]
            if usage_key
            and (
                not rule.get('allow_zones')
                or found_zone in (rule.get('allow_zones') or [])
            )
            and (
                not rule.get('optional_ignore_damage_penalty')
                or use_optional_ignore
            )
            and (
                not rule.get('optional_ignore_speed')
                or use_optional_speed_ignore
            )
        }

    def _limited_grant_available(self, grant, role):
        key = self._limited_grant_key(grant)
        if not key:
            return True
        scope = str(grant.get('usage_scope') or 'turn')
        used = (
            self.engine_state.setdefault('usage', {}).setdefault(scope, {})
            .setdefault(role, {}).get(str(key), 0)
        )
        return _number(used) < max(1, _number(grant.get('max_uses'), 1))

    def _limited_grant_projected_available(self, grant, role, combo):
        """Check an action proposal without collapsing a multi-use grant.

        A proposal may present several Combo cards together.  The legacy
        projected key set correctly protected once-only grants, but treated a
        ``max_uses: 2`` grant as exhausted after the first proposed card.  A
        count map preserves both rules while runtime usage remains authoritative
        when the cards resolve one by one.
        """
        key = self._limited_grant_key(grant)
        if not key:
            return True
        scope = str(grant.get('usage_scope') or 'turn')
        actual = _number(
            self.engine_state.setdefault('usage', {}).setdefault(scope, {})
            .setdefault(role, {}).get(str(key), 0)
        )
        counts = (combo or {}).get('projected_limited_usage_counts') or {}
        if counts:
            projected = _number(counts.get(str(key), 0))
        else:
            projected = sum(
                str(item) == str(key)
                for item in (
                    (combo or {}).get('projected_limited_usage_keys') or []
                )
            )
        maximum = max(1, _number(grant.get('max_uses'), 1))
        return actual + projected < maximum

    def _consume_limited_grant(self, grant, role):
        key = self._limited_grant_key(grant)
        if not key:
            return
        scope = str(grant.get('usage_scope') or 'turn')
        usage = (
            self.engine_state.setdefault('usage', {}).setdefault(scope, {})
            .setdefault(role, {})
        )
        usage[str(key)] = _number(usage.get(str(key))) + 1
        self.emit('limited_use_consumed', role, {
            'usage_key': str(key), 'scope': scope, 'count': usage[str(key)],
        })

    def _open_catch_or_cleanup(self):
        # Effect-granted catches are exhausted before the first FP catch is
        # calculated.  FP is calculated again after each resolved catch so a
        # catch card can legitimately open another catch.
        catches = [
            catch for catch in (self.engine_state.get('granted_catches') or [])
            if self._limited_grant_available(catch, catch.get('owner'))
        ]
        self.engine_state['granted_catches'] = []
        self.engine_state['catch_queue'] = catches
        self.engine_state['catch_fp_history'] = []
        self._continue_catch_queue()

    def _catch_has_legal_option(self, catch):
        role = (catch or {}).get('owner')
        if role not in PLAYER_SIDES:
            return False
        if self._legal_catch_options(role, catch):
            return True
        exemption = self._catch_source_break_exemption(role, catch)
        return bool(
            exemption
            and self._legal_catch_options(
                role, catch,
                counter_exemptions={str(exemption.get('counter') or '')},
            )
        )

    def _remember_declined_fp_catch(self, catch):
        if (catch or {}).get('source') != 'fp' or (catch or {}).get('performed'):
            return
        owner = catch.get('owner')
        negative_side = opponent(owner) if owner in PLAYER_SIDES else None
        if (
            negative_side in PLAYER_SIDES
            and _number(self.state['players'][negative_side].get('fp')) < 0
        ):
            preserved = self.engine_state.setdefault(
                'preserve_negative_fp_through_recovery', [],
            )
            if negative_side not in preserved:
                preserved.append(negative_side)

    def _catch_counter_cost_affordable(
        self, role, rule, *, counter_exemptions=None,
    ):
        cost = (rule or {}).get('counter_cost') or {}
        if not cost:
            return True
        key = str(cost.get('counter') or '')
        if key and key in set(counter_exemptions or []):
            return True
        amount = max(0, _number(cost.get('amount')))
        current = _number(
            self.state['players'][role].setdefault('passive_state', {})
            .get(key, {}).get('count')
        )
        return bool(key and current >= amount)

    def _legal_catch_options(
        self, role, catch, *, ignore_cost_for=None, counter_exemptions=None,
    ):
        if not catch or catch.get('owner') != role:
            return []
        if not self._limited_grant_available(catch, role):
            return []
        options = []
        base_zones = set(catch.get('allow_zones') or ['hand'])
        for zone in self.state['players'][role]['zones']:
            for card in self._zone(role, zone):
                if not _is_attack(card) or _is_special(card):
                    continue
                catch_rules = self._catch_rules(role, card)
                projected_card = self._project_card_for_use(
                    card, role, 'catch',
                )
                card_zones = {
                    allowed_zone
                    for rule in catch_rules
                    for allowed_zone in (rule.get('allow_zones') or [])
                }
                if zone not in base_zones and zone not in card_zones:
                    continue
                if not self._card_use_allowed(
                    card, role, 'catch', ignore_cost=card.get('instance_id') == ignore_cost_for,
                ):
                    continue
                opponent_card = ((self.engine_state.get('battle') or {}).get(opponent(role)) or {}).get('card')
                if self._rule_blocked('catch', role, card, opponent_card):
                    continue
                maximum = catch.get('max_speed')
                fixed_speed = next((
                    rule.get('fixed_speed') for rule in catch_rules
                    if rule.get('fixed_speed') is not None
                    and rule.get('optional_fixed_speed') is None
                ), None)
                effective_speed = (
                    _number(fixed_speed) if fixed_speed is not None
                    else self.card_stat(
                        projected_card, 'frame', role, include_fp=False,
                    )
                )
                minimum = catch.get('min_speed')
                base_speed_allowed = not (
                    minimum is not None and effective_speed < _number(minimum)
                ) and not (
                    maximum is not None and effective_speed > _number(maximum)
                )
                if base_speed_allowed and card_matches(
                    projected_card, catch.get('where'), self.state,
                    {'controller': role, 'source_card': projected_card},
                ):
                    options.append({
                        'card': card, 'catch_rule_index': None,
                        'fixed_speed': fixed_speed,
                    })
                for rule_index, rule in enumerate(catch_rules):
                    optional_speed = rule.get('optional_fixed_speed')
                    if optional_speed is None or not self._catch_counter_cost_affordable(
                        role, rule, counter_exemptions=counter_exemptions,
                    ):
                        continue
                    optional_speed = _number(optional_speed)
                    if minimum is not None and optional_speed < _number(minimum):
                        continue
                    if maximum is not None and optional_speed > _number(maximum):
                        continue
                    if not card_matches(
                        projected_card, catch.get('where'), self.state,
                        {'controller': role, 'source_card': projected_card},
                    ):
                        continue
                    options.append({
                        'card': card, 'catch_rule_index': rule_index,
                        'optional_fixed_speed': optional_speed,
                        'fixed_speed': optional_speed,
                        'counter_cost': copy.deepcopy(
                            rule.get('counter_cost') or {},
                        ),
                    })
        return options

    def _catch_source_break_exemption(self, role, catch):
        exemption = catch.get('counter_exemption_on_source_break') or {}
        counter_key = str(exemption.get('counter') or '')
        source_id = catch.get('source')
        source_owner, source_zone, _index, source_card = self._find_location(
            source_id,
        )
        if (
            not counter_key or not source_card or source_owner != role
            or source_zone in {None, 'break'}
        ):
            return None
        if (
            self._card_ignores_effect(
                source_card, role, source_id, zone=source_zone,
            )
            or self._rule_blocked(
                'break', role, source_card, zone=source_zone,
            )
            or self._break_rule_prevents(
                source_card, source_zone, role,
                effect_controller=role, direct_controller=role,
            )
            or not self._zone_limit_allows(source_card, role, 'break')
        ):
            return None
        return {'counter': counter_key, 'source': source_id}

    def _legal_catch_cards(self, role, catch, *, ignore_cost_for=None):
        cards = []
        seen = set()
        for option in self._legal_catch_options(
            role, catch, ignore_cost_for=ignore_cost_for,
        ):
            card = option['card']
            instance_id = card.get('instance_id')
            if instance_id in seen:
                continue
            seen.add(instance_id)
            cards.append(card)
        return cards

    def _play_catch(
        self, role, instance_id, *, cost_paid=False, catch_rule_index=None,
        source_break_counter_exemption=None, source_break_paid=False,
    ):
        catch = self.engine_state.get('catch') or {}
        card = self._find_card(instance_id, owner=role)
        if catch.get('owner') != role or not card:
            raise IllegalAction('캐치에 사용할 수 없는 카드입니다.')
        options = [
            option for option in self._legal_catch_options(
                role, catch,
                ignore_cost_for=instance_id if cost_paid else None,
                counter_exemptions={source_break_counter_exemption}
                if source_break_counter_exemption else None,
            )
            if (option.get('card') or {}).get('instance_id') == instance_id
            and option.get('catch_rule_index') == catch_rule_index
        ]
        selected_option = options[0] if options else None
        resolved_catch_rules = self._catch_rules(role, card)
        _owner, found_zone, _index, _card = self._find_location(instance_id)
        card_rule_zones = {
            zone
            for rule in resolved_catch_rules
            for zone in (rule.get('allow_zones') or [])
        }
        if found_zone not in set(catch.get('allow_zones') or ['hand']) | card_rule_zones:
            card = None
        if not card or not selected_option:
            raise IllegalAction('캐치에 사용할 수 없는 카드입니다.')
        counter_exemptions = (
            {str(source_break_counter_exemption)}
            if source_break_counter_exemption else set()
        )
        if source_break_counter_exemption and not source_break_paid:
            exemption = self._catch_source_break_exemption(role, catch)
            if (
                not exemption
                or exemption.get('counter') != source_break_counter_exemption
            ):
                raise IllegalAction('캐치 원본을 브레이크해 비용을 면제할 수 없습니다.')
            resume_play = {
                'kind': 'catch', 'card_instance_id': instance_id,
                'catch_rule_index': catch_rule_index,
                'source_break_counter_exemption': source_break_counter_exemption,
                'source_break_paid': True, 'cost_paid': bool(cost_paid),
            }
            resume_item = {
                'kind': 'play_resume', 'role': role, 'play': resume_play,
            }
            self.engine_state.setdefault('domain_queue', []).insert(
                0, resume_item,
            )
            broken = self.break_card(
                exemption['source'], reason='granted_catch_counter_exemption',
                effect_controller=role, effect_source=exemption['source'],
                direct_controller=role,
            )
            if broken is None:
                self.engine_state['domain_queue'] = [
                    item for item in self.engine_state.get('domain_queue') or []
                    if item is not resume_item
                ]
                raise IllegalAction('캐치 원본을 브레이크할 수 없습니다.')
            self.emit('catch_source_broken_for_counter_exemption', role, {
                'source_card_instance_id': exemption['source'],
                'catch_card_instance_id': instance_id,
                'counter': source_break_counter_exemption,
            })
            return
        if not cost_paid and self._begin_play_cost(
            role, card, 'catch', {
                'kind': 'catch', 'card_instance_id': instance_id,
                'catch_rule_index': catch_rule_index,
                'source_break_counter_exemption': source_break_counter_exemption,
                'source_break_paid': bool(source_break_paid),
                'cost_paid': True,
            },
        ):
            return
        catch['performed'] = True
        self.engine_state.pop('preserve_negative_fp_through_recovery', None)
        counter_cost = selected_option.get('counter_cost') or {}
        if counter_cost:
            counter_key = str(counter_cost.get('counter') or '')
            counter_amount = max(0, _number(counter_cost.get('amount')))
            if not self._catch_counter_cost_affordable(
                role, selected_option, counter_exemptions=counter_exemptions,
            ):
                raise IllegalAction('캐치 속도 변경 비용을 지불할 수 없습니다.')
            if counter_key in counter_exemptions:
                self.emit('catch_counter_cost_waived', role, {
                    'card_instance_id': instance_id,
                    'counter': counter_key, 'amount': counter_amount,
                    'fixed_speed': selected_option.get('fixed_speed'),
                })
            else:
                self.change_counter(
                    role, counter_key, -counter_amount, minimum=0,
                )
                self.emit('catch_counter_cost_paid', role, {
                    'card_instance_id': instance_id,
                    'counter': counter_key, 'amount': counter_amount,
                    'fixed_speed': selected_option.get('fixed_speed'),
                })
        applied_catch_rules = [
            rule for index, rule in enumerate(resolved_catch_rules)
            if rule.get('optional_fixed_speed') is None
            or index == catch_rule_index
        ]
        # Q&A 406/641: effect-granted catch opportunities are offered in
        # priority order.  Once one player actually catches, every previously
        # queued opportunity from that catch window misses its timing.  Effects
        # triggered by the catching card can still grant a new catch later.
        missed_catches = list(self.engine_state.get('catch_queue') or [])
        self.engine_state['catch_queue'] = []
        for missed in missed_catches:
            self.emit('catch_skipped', missed.get('owner'), {
                'reason': 'timing_missed',
                'source': missed.get('source'),
            })
        # Rulebook p35: declaring a catch resets both FP before the catching
        # card applies its own hit judgment FP.
        for side in PLAYER_SIDES:
            self.set_fp(side, 0, source='catch_declared')
        self._consume_limited_grant(catch, role)
        self.move_card(instance_id, 'battle', reason='catch')
        card['face_up'] = True
        self._mark_card_used(card, role, 'catch')
        catch_sources = self.engine_state.setdefault('catch_source_ids', [])
        if instance_id not in catch_sources:
            catch_sources.append(instance_id)
        fixed_speed = selected_option.get('fixed_speed')
        if fixed_speed is not None:
            self.add_modifier({
                'op': 'fix_speed', 'controller': role, 'player': role,
                'source': instance_id, 'where': {'instance_id': instance_id},
                'stat': 'frame', 'value': _number(fixed_speed), 'duration': 'battle',
            })
        self.engine_state['pipeline'] = {
            'kind': 'catch_resolution', 'stage': 'use', 'owner': role,
            'card_instance_id': instance_id, 'card': copy.deepcopy(card),
            'grant': copy.deepcopy(catch),
            'catch_rules': copy.deepcopy(applied_catch_rules),
            'catch_rule_index': catch_rule_index,
            'fixed_speed': (
                _number(fixed_speed) if fixed_speed is not None else None
            ),
            'counter_spend_exemptions': [
                {
                    'counter': counter_key,
                    'card_instance_id': instance_id,
                }
                for counter_key in sorted(counter_exemptions)
            ],
        }
        self.engine_state['step'] = 'catch_resolution'
        self._refresh_continuous_rules()

    def _catch_rules(self, role, card):
        definition = self._definition_for_card(card)
        context = {
            'controller': role, 'opponent': opponent(role),
            'controller_hp': self.state['players'][role].get('hp'),
            'controller_fp': self.state['players'][role].get('fp'),
            'opponent_hp': self.state['players'][opponent(role)].get('hp'),
            'opponent_fp': self.state['players'][opponent(role)].get('fp'),
            'source_card': card, 'use_context': 'catch',
        }
        return [
            rule for rule in definition.get('catch_rules') or []
            if isinstance(rule, dict)
            and not (
                rule.get('numbered_effect')
                and (card or {}).get('numbered_effects_negated')
            )
            and condition_matches(rule.get('condition'), self.state, context)
        ]

    @staticmethod
    def _catch_effect_replacement_definition(replacement):
        """Build the temporary ability set for one effect-modified Catch.

        Printed characteristics and use legality remain those of the selected
        card. Only its abilities are replaced while the Catch pipeline exists,
        so the live card is never polluted with a persistent override.
        """
        if not isinstance(replacement, dict):
            return None
        abilities = []
        for item in replacement.get('abilities') or []:
            if not isinstance(item, dict):
                continue
            event = str(item.get('event') or '')
            effects = item.get('effects')
            if event not in {'use', 'catch', 'hit', 'after_use'} or not effects:
                continue
            abilities.append({
                'id': str(item.get('id') or f'catch-replacement-{event}'),
                'kind': 'function', 'mode': 'mandatory',
                'timing': item.get('timing') or event,
                'visibility': 'public', 'active_zones': ['battle'],
                'trigger': {'event': event},
                'effects': copy.deepcopy(effects),
            })
        if not abilities:
            return None
        return {'schema_version': 1, 'abilities': abilities}

    def _advance_catch_pipeline(self, pipeline):
        role, card = pipeline['owner'], pipeline['card']
        context = {
            'controller': role,
            'source_card_instance_id': pipeline['card_instance_id'],
            'source_card': card, 'catch': True,
            'fixed_speed': pipeline.get('fixed_speed'),
            'catch_rule_index': pipeline.get('catch_rule_index'),
            'counter_spend_exemptions': copy.deepcopy(
                pipeline.get('counter_spend_exemptions') or [],
            ),
        }
        stage = pipeline['stage']
        if stage == 'use':
            self._fire('use', context)
            pipeline['stage'] = 'catch'
            return not self.is_waiting
        if stage == 'catch':
            self._fire('catch', context)
            pipeline['stage'] = 'hit'
            return not self.is_waiting
        if stage == 'hit':
            self._fire('hit', context)
            pipeline['stage'] = 'damage'
            return not self.is_waiting
        if stage == 'damage':
            if (
                not pipeline.get('continue_after_source_left')
                and not self._find_card(
                    pipeline['card_instance_id'], owner=role, zone='battle',
                )
            ):
                self.emit('catch_interrupted', role, {
                    'reason': 'source_card_left_battle',
                    'card_instance_id': pipeline['card_instance_id'],
                })
                self.engine_state['pipeline'] = None
                self.end_catch()
                return True
            self.deal_damage(
                opponent(role), max(
                    0,
                    self.card_stat(card, 'damage', role)
                    + _number((pipeline.get('grant') or {}).get('damage_bonus')),
                ),
                source='catch', context=context,
            )
            self.change_fp(role, _fp_value(card.get('hit')), source='catch', context=context)
            pipeline['stage'] = 'after_use'
            return True
        if stage == 'after_use':
            self._fire('after_use', context)
            pipeline['stage'] = 'card_rule_cleanup'
            return not self.is_waiting
        if stage == 'card_rule_cleanup':
            # Set the continuation first: breaking a normal attack can open a
            # mandatory list-replenishment decision and pause the pipeline.
            pipeline['stage'] = 'grant_cleanup'
            if any(
                rule.get('break_after_use')
                for rule in (pipeline.get('catch_rules') or [])
            ):
                catch_card_id = pipeline.get('card_instance_id')
                catch_owner, catch_zone, _index, _catch_card = self._find_location(
                    catch_card_id,
                )
                if catch_owner == role and catch_zone not in {None, 'break'}:
                    self.break_card(catch_card_id, reason='card_catch_rule_after_use')
            return not self.is_waiting
        if stage == 'grant_cleanup':
            grant = pipeline.get('grant') or {}
            source_id = grant.get('source')
            catch_card_id = pipeline.get('card_instance_id')
            if grant.get('break_after_use') and catch_card_id:
                catch_owner, catch_zone, _index, _catch_card = self._find_location(catch_card_id)
                if catch_owner == role and catch_zone not in {None, 'break'}:
                    self.break_card(catch_card_id, reason='granted_catch_after_use')
            if grant.get('break_source_after_use') and source_id:
                source_owner, source_zone, _index, _source_card = self._find_location(source_id)
                if source_owner == role and source_zone not in {None, 'break'}:
                    self.break_card(source_id, reason='granted_catch_source_after_use')
            if grant.get('return_source_to_hand') and source_id:
                source_owner, source_zone, _index, _source_card = self._find_location(source_id)
                if source_owner == role and source_zone not in {None, 'hand', 'side', 'break'}:
                    self.move_card(source_id, 'hand', reason='granted_catch_source_return')
                    self.emit('catch_source_returned', role, {
                        'card_instance_id': source_id,
                        'catch_card_instance_id': pipeline.get('card_instance_id'),
                    })
            pipeline['stage'] = 'opportunity_resolved'
            return True
        if stage == 'opportunity_resolved':
            # Q&A 490: an effect that happens after a granted Catch is
            # processed must wait until the Catch card's use/after-use steps
            # finish, but must run before a Combo granted by that Catch opens.
            pipeline['stage'] = 'done'
            self._fire_catch_opportunity_resolved(
                pipeline.get('grant') or {},
                catch_card=card,
                declined=False,
            )
            return not self.is_waiting
        self.engine_state['pipeline'] = None
        if self.engine_state.get('end_battle_requested'):
            self._finish_catch_end(
                self.engine_state.get('catch') or pipeline.get('grant') or {},
            )
            return True
        granted = list(self.engine_state.pop('granted_combos', []) or [])
        next_combo = self._next_available_combo(granted)
        if next_combo:
            self.engine_state['catch'] = None
            self.engine_state['resume_catch_after_combo'] = True
            self.engine_state.setdefault('combo_queue', []).extend(granted)
            self.grant_combo(
                next_combo.get('owner'), source=next_combo.get('source'),
                special=next_combo.get('special', True),
            )
            return True
        if str(card.get('hit') or '') == '콤보':
            printed_combo = {
                'owner': role, 'source': pipeline['card_instance_id'],
                'special': False, 'combo_triggered': True,
            }
            if self._combo_grant_can_open(printed_combo):
                self.engine_state['catch'] = None
                self.engine_state['resume_catch_after_combo'] = True
                # Catch has no separate judgment-trigger sequence. Its
                # printed Combo judgment is announced when Combo Time opens,
                # so opponent Combo reactions fire here exactly once.
                self.grant_combo(role, source=pipeline['card_instance_id'])
                return True
            self._emit_unavailable_combo(printed_combo)
        self.end_catch()
        return True

    def end_catch(self):
        catch = self.engine_state.get('catch')
        if not catch:
            return
        self._remember_declined_fp_catch(catch)
        if not catch.get('opportunity_resolved'):
            self._fire_catch_opportunity_resolved(catch, declined=True)
            if self.is_waiting:
                self.engine_state['pipeline'] = {
                    'kind': 'catch_end', 'stage': 'done',
                    'catch': copy.deepcopy(catch),
                }
                self.engine_state['step'] = 'catch_resolution'
                return
        self._finish_catch_end(catch)

    def _fire_catch_opportunity_resolved(
        self, catch, *, catch_card=None, declined=False,
    ):
        catch = catch or {}
        if catch.get('opportunity_resolved'):
            return
        catch['opportunity_resolved'] = True
        current = self.engine_state.get('catch') or {}
        if (
            current.get('owner') == catch.get('owner')
            and current.get('source') == catch.get('source')
        ):
            current['opportunity_resolved'] = True
        source_id = catch.get('source')
        if not source_id or source_id == 'fp':
            return
        source_card = self._find_card(source_id)
        context = {
            'controller': catch.get('owner'),
            'source_card_instance_id': source_id,
            'source_card': copy.deepcopy(source_card),
            'catch_card': copy.deepcopy(catch_card),
            'catch_card_instance_id': (catch_card or {}).get('instance_id'),
            'catch_declined': bool(declined),
            'source_only_event': True,
        }
        self.emit('catch_opportunity_resolved', catch.get('owner'), {
            'source': source_id,
            'catch_card_instance_id': context['catch_card_instance_id'],
            'declined': bool(declined),
        })
        self._fire('catch_opportunity_resolved', context)

    def _advance_catch_end_pipeline(self, pipeline):
        self.engine_state['pipeline'] = None
        catch = self.engine_state.get('catch') or pipeline.get('catch')
        if catch:
            self._finish_catch_end(catch)
        return True

    def _finish_catch_end(self, catch):
        self.emit('catch_ended', catch.get('owner'), {})
        if self.engine_state.pop('end_battle_requested', False):
            missed = [
                *(self.engine_state.get('catch_queue') or []),
                *(self.engine_state.get('granted_catches') or []),
            ]
            self.engine_state['catch_queue'] = []
            self.engine_state['granted_catches'] = []
            self.engine_state['catch'] = None
            self.engine_state.pop('catch_fp_history', None)
            for opportunity in missed:
                self.emit('catch_skipped', opportunity.get('owner'), {
                    'reason': 'battle_ended_by_effect',
                    'source': opportunity.get('source'),
                })
            self._cleanup_battle()
            return
        self._continue_catch_queue()

    def _continue_catch_queue(self):
        queue = self.engine_state.get('catch_queue') or []
        newly_granted = list(self.engine_state.get('granted_catches') or [])
        if newly_granted:
            self.engine_state['granted_catches'] = []
            queue[0:0] = newly_granted
        while queue:
            next_catch = queue.pop(0)
            if not self._limited_grant_available(next_catch, next_catch.get('owner')):
                self.emit('catch_skipped', next_catch.get('owner'), {
                    'reason': 'usage_limit', 'usage_key': next_catch.get('usage_key'),
                })
                continue
            if not self._catch_has_legal_option(next_catch):
                self.emit('catch_skipped', next_catch.get('owner'), {
                    'reason': 'no_legal_card',
                    'source': next_catch.get('source'),
                })
                self._fire_catch_opportunity_resolved(
                    next_catch, declined=True,
                )
                if self.is_waiting:
                    self.engine_state['catch'] = next_catch
                    self.engine_state['pipeline'] = {
                        'kind': 'catch_end', 'stage': 'done',
                        'catch': copy.deepcopy(next_catch),
                    }
                    self.engine_state['step'] = 'catch_resolution'
                    return
                continue
            self.engine_state['catch'] = next_catch
            self.engine_state['step'] = 'catch'
            self.emit('catch_started', next_catch.get('owner'), copy.deepcopy(next_catch))
            return

        history = self.engine_state.setdefault('catch_fp_history', [])
        for side in self._priority_order():
            fp = _number(self.state['players'][side].get('fp'))
            other_fp = _number(self.state['players'][opponent(side)].get('fp'))
            if not ((fp > 0 and other_fp == 0) or (fp == 0 and other_fp < 0)):
                continue
            signature = f'{side}:{fp}:{other_fp}'
            if signature in history:
                continue
            history.append(signature)
            next_catch = {
                'owner': side, 'source': 'fp',
                'max_speed': fp if fp > 0 else -other_fp,
                'fp_signature': signature,
            }
            if not self._catch_has_legal_option(next_catch):
                self._remember_declined_fp_catch(next_catch)
                self.emit('catch_skipped', side, {
                    'reason': 'no_legal_card', 'source': 'fp',
                    'max_speed': next_catch.get('max_speed'),
                })
                continue
            self.engine_state['catch'] = next_catch
            self.engine_state['step'] = 'catch'
            self.emit('catch_started', side, copy.deepcopy(next_catch))
            return

        self.engine_state['catch'] = None
        self.engine_state.pop('catch_fp_history', None)
        self._cleanup_battle()

    def _cleanup_battle(self):
        pipeline = {
            'kind': 'battle_cleanup', 'stage': 'battle_end',
            'index': 0, 'replenish_index': 0,
        }
        self.engine_state['step'] = 'battle_cleanup'
        self.engine_state['pipeline'] = pipeline
        return self._advance_cleanup_pipeline(pipeline)

    def _advance_cleanup_pipeline(self, pipeline):
        stage = pipeline.get('stage')
        if stage == 'battle_end':
            pipeline['stage'] = 'prepare_cards'
            self._fire('battle_end', {'phase': 'battle'})
            return not self.is_waiting
        if stage == 'prepare_cards':
            used_order = []
            battle = self.engine_state.get('battle') or {}
            pipeline['defense_over'] = self._record_defense_over(battle)
            combo_source_ids = set(self.engine_state.get('combo_source_ids') or [])
            catch_source_ids = set(self.engine_state.get('catch_source_ids') or [])
            for side in self._priority_order():
                if (battle.get(side) or {}).get('instance_id'):
                    instance_id = battle[side]['instance_id']
                    if not self._find_card(instance_id, owner=side, zone='battle'):
                        continue
                    destination = (
                        'list'
                        if instance_id in combo_source_ids | catch_source_ids
                        else 'hand'
                    )
                    used_order.append((side, instance_id, destination))
            combo = self.engine_state.get('combo') or {}
            combo_owner = combo.get('owner')
            used_order.extend(
                (combo_owner, instance_id, 'list')
                for instance_id in combo.get('used') or []
            )
            known_ids = {
                instance_id for _side, instance_id, _destination in used_order
            }
            for side in self._priority_order():
                for card in list(self._zone(side, 'battle')):
                    if card.get('instance_id') in known_ids:
                        continue
                    # Cards not present in the original ready battle are combo
                    # or catch cards and therefore go to the list (p44).
                    destination = (
                        'hand' if card.get('return_to_hand_on_attachment_expiry')
                        else 'list'
                    )
                    used_order.append((side, card.get('instance_id'), destination))
                    known_ids.add(card.get('instance_id'))
            for side in self._priority_order():
                for cards in self.state['players'][side]['zones'].values():
                    for card in list(cards):
                        instance_id = card.get('instance_id')
                        if instance_id in known_ids:
                            continue
                        if (
                            card.get('attached_to')
                            and card.get('return_to_hand_on_attachment_expiry')
                        ):
                            used_order.append((side, instance_id, 'hand'))
                            known_ids.add(instance_id)
            pipeline.update({'stage': 'cards', 'used_order': used_order, 'index': 0})
            return True
        defense_over = bool(pipeline.get('defense_over'))
        if stage == 'cards':
            used_order = pipeline.get('used_order') or []
            index = _number(pipeline.get('index'))
            if index >= len(used_order):
                pipeline['stage'] = 'finalize'
                return True
            side, instance_id, destination = used_order[index]
            pipeline['index'] = index + 1
            card = self._find_card(instance_id)
            if not card:
                return True
            if card.get('virtual'):
                owner, zone, index, _card = self._find_location(instance_id)
                self.state['players'][owner]['zones'][zone].pop(index)
                return True
            card_owner = card.get('owner') if card.get('owner') in PLAYER_SIDES else side
            if card.get('break_after_use'):
                self.break_card(instance_id, reason='deck_rule_after_use')
            elif _is_special(card):
                self.break_card(instance_id, reason='battle_cleanup')
            elif defense_over:
                self.move_card(instance_id, 'break', to_player=card_owner, reason='battle_cleanup')
                self.emit('card_broken', card_owner, {'card_instance_id': instance_id, 'reason': 'defense_over'})
                self._fire('card_broken', {
                    'controller': card_owner, 'source_card_instance_id': instance_id,
                    'source_card': copy.deepcopy(card), 'reason': 'defense_over',
                })
            else:
                self.move_card(instance_id, destination, to_player=card_owner, reason='battle_cleanup')
            return not self.is_waiting
        if stage == 'finalize':
            self.engine_state['battle'] = {}
            self.engine_state.pop('continuous_judgments', None)
            for side in PLAYER_SIDES:
                for cards in self.state['players'][side]['zones'].values():
                    for card in cards:
                        if card.get('attachment_expires') == 'battle':
                            card.pop('attached_to', None)
                            card.pop('attachment_expires', None)
                            card.pop('return_to_hand_on_attachment_expiry', None)
                            card.pop('set_order', None)
                        if card.get('move_to_hand_blocked_until') == 'battle':
                            card.pop('move_to_hand_blocked_until', None)
            self._expire_modifiers('battle')
            self.engine_state['ready_cards'] = {}
            self.engine_state['granted_catches'] = []
            self.engine_state['combo'] = None
            self.engine_state.pop('combo_source_ids', None)
            self.engine_state.pop('catch_source_ids', None)
            self._reset_usage('battle')
            deferred_hand_adjustments = list(
                self.engine_state.pop('deferred_hand_adjustments', []) or []
            )
            for side in deferred_hand_adjustments:
                self._queue_hand_limit_adjustment(
                    side, defer_during_battle=False,
                )
            pipeline['stage'] = 'defense_over' if defense_over else 'advance'
            return True
        if stage == 'defense_over':
            pipeline['stage'] = 'replenish'
            self.emit('defense_over', 'system', {})
            self._fire('defense_over', {})
            return not self.is_waiting
        if stage == 'replenish':
            index = _number(pipeline.get('replenish_index'))
            if index < len(PLAYER_SIDES):
                pipeline['replenish_index'] = index + 1
                self._offer_break_replenishment(PLAYER_SIDES[index])
                return not self.is_waiting
            pipeline['stage'] = 'advance'
            return True
        self.engine_state['pipeline'] = None
        self._advance_phase('get')
        return not self.is_waiting

    def _record_defense_over(self, battle):
        both_defense = all(_is_defense((battle.get(side) or {}).get('card')) for side in PLAYER_SIDES)
        damage_count = sum(1 for event in self.events if event.get('type') == 'damage_dealt')
        no_damage = damage_count == _number(battle.get('damage_event_count_before'))
        fp_count = sum(1 for event in self.events if event.get('type') == 'fp_changed')
        no_fp = fp_count == _number(battle.get('fp_event_count_before'))
        effect_count = sum(1 for event in self.events if event.get('type') == 'effect_resolved')
        no_effect = effect_count == _number(battle.get('effect_count_before'))
        if both_defense and no_damage and no_fp and no_effect:
            count = _number(self.engine_state.get('defense_over_count')) + 1
        else:
            count = 0
        self.engine_state['defense_over_count'] = count
        if count >= 3:
            self.engine_state['defense_over_count'] = 0
            return True
        return False

    def _get_card(self, role, instance_id):
        if role != self.engine_state.get('current_actor'):
            raise IllegalAction('현재 Get 차례가 아닙니다.')
        if role in (self.engine_state.get('forced_get_designators') or {}):
            raise IllegalAction('상대가 지정한 기술을 획득해야 합니다.')
        source_zone = 'ultimate' if self._find_card(instance_id, owner=role, zone='ultimate') else 'list'
        card = self._find_card(instance_id, owner=role, zone=source_zone)
        if (
            not card or _is_special(card)
            or self._rule_blocked('get_card', role, card)
        ):
            raise IllegalAction('획득할 수 없는 카드입니다.')
        self.move_card(instance_id, 'hand', reason='get')
        self._finish_get_action(role, instance_id)

    def _finish_get_action(self, role, instance_id):
        done = self.engine_state.setdefault('get_done', [])
        done.append(role)
        self.emit('get_completed', role, {'card_instance_id': instance_id})
        order = self.engine_state.get('get_order') or []
        if len(done) >= len(order):
            self.engine_state['current_actor'] = None
            self._advance_phase('recovery')
        else:
            self.engine_state['current_actor'] = order[len(done)]
            self._open_forced_get_decision()

    def replace_get_action(self, side, *, source=None):
        """Consume the normal Get only after its replacement succeeded."""
        if side not in PLAYER_SIDES or self.state.get('phase') != 'get':
            raise EngineError('현재 Get을 대체할 수 없습니다.')
        if side in (self.engine_state.get('get_done') or []):
            raise EngineError('이미 Get을 완료했습니다.')
        self.engine_state.setdefault('replaced_get', {})[side] = {
            'source': source,
        }
        self.emit('get_replaced', side, {'source': source})

    def _settle_replaced_get_action(self):
        if self.state.get('phase') != 'get':
            return False
        role = self.engine_state.get('current_actor')
        replacement = (
            self.engine_state.setdefault('replaced_get', {}).pop(role, None)
            if role in PLAYER_SIDES else None
        )
        if not replacement:
            return False
        self._finish_get_action(role, None)
        return True

    def _open_forced_get_decision(self):
        beneficiary = self.engine_state.get('current_actor')
        chooser = (self.engine_state.get('forced_get_designators') or {}).get(beneficiary)
        if beneficiary not in PLAYER_SIDES or chooser not in PLAYER_SIDES:
            return False
        options = [
            {
                'id': card.get('instance_id'),
                'label': card.get('name') or '카드',
                'owner': beneficiary, 'zone': 'list',
            }
            for card in self._zone(beneficiary, 'list')
            if not _is_special(card) and not self._rule_blocked('get_card', beneficiary, card)
        ]
        options.sort(key=lambda item: str(item.get('id')))
        if not options:
            self.engine_state.setdefault('forced_get_designators', {}).pop(beneficiary, None)
            self.engine_state.setdefault('forced_get_turns', {}).pop(
                beneficiary, None,
            )
            self._finish_get_action(beneficiary, None)
            return False
        self.create_decision(
            owner=chooser, kind='forced_get_designation',
            prompt='상대가 획득할 리스트의 기술을 선택하세요.',
            options=options, minimum=1, maximum=1,
            default=[options[0]['id']],
            continuation={
                'type': 'forced_get_designation',
                'beneficiary': beneficiary,
            },
        )
        return True

    def _resolve_forced_get_designation(self, beneficiary, instance_id):
        chooser = (self.engine_state.get('forced_get_designators') or {}).get(beneficiary)
        if (
            beneficiary != self.engine_state.get('current_actor')
            or chooser not in PLAYER_SIDES
        ):
            raise IllegalAction('현재 강제 Get 선택이 아닙니다.')
        card = self._find_card(instance_id, owner=beneficiary, zone='list')
        if not card or _is_special(card) or self._rule_blocked('get_card', beneficiary, card):
            raise IllegalAction('지정하여 획득할 수 없는 카드입니다.')
        self.engine_state.setdefault('forced_get_designators', {}).pop(beneficiary, None)
        self.engine_state.setdefault('forced_get_turns', {}).pop(
            beneficiary, None,
        )
        self.move_card(instance_id, 'hand', reason='forced_designated_get')
        self.emit('forced_get_completed', chooser, {
            'beneficiary': beneficiary, 'card_instance_id': instance_id,
        })
        self._finish_get_action(beneficiary, instance_id)

    def _recovery_core(self):
        # A negative-FP Catch opportunity that was declined or had no legal
        # card carries that FP through this Recovery.  Declaring a Catch still
        # clears both players' FP in ``_play_catch``.
        preserved = set(
            self.engine_state.pop(
                'preserve_negative_fp_through_recovery', [],
            ) or []
        )
        for side in PLAYER_SIDES:
            if self.state['players'][side]['fp'] < 0 and side not in preserved:
                self.set_fp(side, 0, source='recovery')

    # ------------------------------------------------------------------
    # Timers, decisions, no-response and rewind

    def _timeout_seconds(self, key, fallback):
        settings = self.engine_state.get('settings') or {}
        if key in settings:
            value = settings.get(key)
            return None if value is None else max(0, _number(value))
        return fallback

    def _start_clock(self, kind, *, owner, seconds):
        if seconds is None or _number(seconds) <= 0:
            self._clear_clock()
            return
        self.engine_state['clock'] = {
            'kind': kind, 'owner': owner, 'duration_seconds': int(seconds),
            'deadline': (self.now + timedelta(seconds=int(seconds))).isoformat(),
            'paused': False, 'pause_reason': '', 'paused_by': None,
        }
        self.emit('clock_started', 'system', {'kind': kind, 'owner': owner, 'seconds': int(seconds)})

    def _clear_clock(self):
        self.engine_state['clock'] = None

    def reconcile_clock(self, *, both_disconnected=False):
        clock = self.engine_state.get('clock') or {}
        if not clock or clock.get('paused') or both_disconnected:
            return False
        deadline = _as_datetime(clock.get('deadline'))
        if not deadline or self.now < deadline:
            return False
        kind = clock.get('kind')
        owner = clock.get('owner')
        self._clear_clock()
        if kind == 'ready':
            self._ready_timeout(owner)
        elif kind == 'decision':
            self._decision_timeout(owner)
        elif kind == 'rewind':
            self.emit('rewind_expired', 'system', {'requested_by': (self.engine_state.get('rewind_request') or {}).get('requested_by')})
            self.engine_state['rewind_request'] = None
        self._continue()
        return True

    def _pause_clock(self, role, reason):
        clock = self.engine_state.get('clock') or {}
        if not clock or clock.get('owner') == role:
            raise IllegalAction('이 타이머를 일시정지할 수 없습니다.')
        if not reason:
            raise IllegalAction('일시정지 사유가 필요합니다.')
        deadline = _as_datetime(clock.get('deadline'))
        remaining = max(0, int((deadline - self.now).total_seconds())) if deadline else 0
        clock.update({'paused': True, 'remaining_seconds': remaining, 'pause_reason': reason, 'paused_by': role, 'deadline': None})
        self.emit('clock_paused', role, {'kind': clock.get('kind'), 'reason': reason, 'remaining_seconds': remaining})

    def _resume_clock(self, role):
        clock = self.engine_state.get('clock') or {}
        if not clock.get('paused'):
            raise IllegalAction('일시정지된 타이머가 없습니다.')
        remaining = max(0, _number(clock.get('remaining_seconds')))
        clock.update({'paused': False, 'deadline': (self.now + timedelta(seconds=remaining)).isoformat(), 'remaining_seconds': None})
        self.emit('clock_resumed', role, {'kind': clock.get('kind'), 'remaining_seconds': remaining})

    def create_decision(
        self, *, owner, kind, prompt, options, minimum=1, maximum=1,
        default=None, optional=False, distinct_by=None, continuation=None,
    ):
        normalized = []
        for index, option in enumerate(options or []):
            if isinstance(option, dict):
                option_id = str(option.get('id') if option.get('id') is not None else index)
                normalized.append({**copy.deepcopy(option), 'id': option_id})
            else:
                normalized.append({'id': str(option), 'label': str(option)})
        if minimum > len(normalized) or maximum < minimum:
            raise EffectResolutionError('필수 선택 후보가 부족합니다.')
        decision = {
            'id': self._next_id('decision'), 'owner': owner, 'kind': kind, 'prompt': str(prompt or ''),
            'options': normalized, 'minimum': int(minimum), 'maximum': int(maximum),
            'default': [str(item) for item in (default or [])], 'optional': bool(optional),
            'distinct_by': distinct_by,
            'continuation': copy.deepcopy(continuation or {}), 'created_at': self.now.isoformat(),
        }
        self.engine_state['pending_decision'] = decision
        self._start_clock(
            'decision', owner=owner,
            seconds=self._timeout_seconds(
                'effect_timeout_seconds', DEFAULT_EFFECT_CHOICE_SECONDS,
            ),
        )
        self.emit('decision_requested', owner, {'decision_id': decision['id'], 'kind': kind}, visibility='private')
        return decision

    def _decision_options_for(self, role, decision):
        if decision.get('owner') != role:
            return []
        return copy.deepcopy(decision.get('options') or [])

    def _submit_decision(self, role, decision_id, selected):
        decision = self.engine_state.get('pending_decision') or {}
        if decision.get('id') != decision_id or decision.get('owner') != role:
            raise IllegalAction('현재 선택 요청과 일치하지 않습니다.')
        valid = {str(item.get('id')) for item in decision.get('options') or []}
        selected = [str(item) for item in selected]
        if len(selected) != len(set(selected)) or any(item not in valid for item in selected):
            raise IllegalAction('유효하지 않은 선택 대상입니다.')
        distinct_by = decision.get('distinct_by')
        if distinct_by:
            values = [(self._find_card(item) or {}).get(distinct_by) for item in selected]
            if len(values) != len(set(values)):
                raise IllegalAction('서로 다른 값의 카드를 선택해야 합니다.')
        if not decision.get('minimum', 1) <= len(selected) <= decision.get('maximum', 1):
            raise IllegalAction('선택 수가 허용 범위를 벗어났습니다.')
        self._resolve_decision(decision, selected, timed_out=False)

    def _decision_timeout(self, owner):
        decision = self.engine_state.get('pending_decision') or {}
        if decision.get('owner') != owner:
            return
        valid = [str(item.get('id')) for item in decision.get('options') or []]
        if decision.get('optional') or decision.get('kind') == 'optional_effect':
            selected = ['decline'] if 'decline' in valid else []
        else:
            minimum = _number(decision.get('minimum'), 1)
            maximum = _number(decision.get('maximum'), minimum)
            selected = []
            distinct_values = set()
            distinct_by = decision.get('distinct_by')
            for item in decision.get('default') or []:
                distinct_value = (
                    (self._find_card(item) or {}).get(distinct_by)
                    if distinct_by else None
                )
                if (
                    item in valid and item not in selected and len(selected) < maximum
                    and (not distinct_by or distinct_value not in distinct_values)
                ):
                    selected.append(item)
                    distinct_values.add(distinct_value)
            for item in sorted(valid):
                if len(selected) >= minimum:
                    break
                distinct_value = (
                    (self._find_card(item) or {}).get(distinct_by)
                    if distinct_by else None
                )
                if item not in selected and (
                    not distinct_by or distinct_value not in distinct_values
                ):
                    selected.append(item)
                    distinct_values.add(distinct_value)
        self._resolve_decision(decision, selected, timed_out=True)

    def _resolve_decision(self, decision, selected, *, timed_out):
        self.engine_state['pending_decision'] = None
        self._clear_clock()
        options_by_id = {
            str(option.get('id')): option
            for option in decision.get('options') or []
        }
        selected_options = []
        for selected_id in selected:
            option = options_by_id.get(str(selected_id)) or {}
            selected_card = self._find_card(str(selected_id))
            selected_options.append({
                key: copy.deepcopy(value)
                for key, value in {
                    'id': str(selected_id),
                    'label': option.get('label') or str(selected_id),
                    'card_instance_id': (
                        option.get('card_instance_id')
                        or (selected_card or {}).get('instance_id')
                    ),
                    'card_id': (
                        option.get('card_id')
                        or (selected_card or {}).get('card_id')
                    ),
                    'card_code': (
                        option.get('card_code')
                        or (selected_card or {}).get('code')
                    ),
                }.items()
                if value is not None
            })
        self.emit('decision_resolved', decision.get('owner'), {
            'decision_id': decision.get('id'),
            'kind': decision.get('kind'),
            'prompt': decision.get('prompt'),
            'selected': selected,
            'selected_options': selected_options,
            'timed_out': timed_out,
        }, visibility='private')
        continuation = decision.get('continuation') or {}
        if continuation.get('type') == 'optional_effect':
            self.resolver.continue_optional(continuation.get('item') or {}, 'accept' in selected)
        elif continuation.get('type') == 'effect_order':
            self.resolver.continue_effect_order(
                continuation.get('group_id'), selected[0] if selected else None,
            )
        elif continuation.get('type') == 'effect_choice':
            context = continuation.get('context') or {}
            context[continuation.get('selection_key') or 'selected'] = selected
            self.resolver.continue_effects(
                continuation.get('effects') or [], context,
            )
        elif continuation.get('type') == 'effect_branch':
            selected_id = selected[0] if selected else None
            branch = next(
                (
                    option for option in continuation.get('options') or []
                    if str(option.get('id')) == selected_id
                ),
                None,
            )
            if branch:
                self.resolver.continue_effects(
                    branch.get('effects') or [], continuation.get('context') or {},
                )
        elif continuation.get('type') == 'hand_guess_card':
            self.resolver.continue_hand_guess_card(
                continuation.get('effect') or {},
                continuation.get('context') or {},
                selected[0] if selected else None,
            )
        elif continuation.get('type') == 'hand_guess_parity':
            self.resolver.resolve_hand_parity_guess(
                continuation.get('effect') or {},
                continuation.get('context') or {},
                continuation.get('card_instance_id'),
                selected[0] if selected else 'odd',
            )
        elif continuation.get('type') == 'hand_guess_repeat':
            self.resolver.continue_hand_guess_repeat(
                continuation.get('effect') or {},
                continuation.get('context') or {},
                continuation.get('attempt'),
                'accept' in selected,
            )
        elif continuation.get('type') == 'forced_get_designation':
            self._resolve_forced_get_designation(
                continuation.get('beneficiary'), selected[0] if selected else None,
            )
        elif continuation.get('type') == 'ability_target':
            self.resolver.continue_target(continuation.get('item') or {}, selected)
        elif continuation.get('type') == 'play_cost':
            cost = continuation.get('cost') or {}
            operation = cost.get('operation')
            cost_context = continuation.get('context') or {}
            selector = self._play_cost_selector(cost)
            current_options = {
                str(item.get('id'))
                for item in self.selector_options(selector, cost_context)
            }
            successful = []
            if all(instance_id in current_options for instance_id in selected):
                for instance_id in selected:
                    if self._pay_play_cost_item(
                        instance_id, cost, decision.get('owner'), cost_context,
                    ):
                        successful.append(instance_id)
            minimum = _number(resolve_value(
                selector.get('min', 1), self.state, cost_context,
            ), 1)
            if len(successful) >= minimum:
                self.emit('play_cost_paid', decision.get('owner'), {
                    'card_instance_id': cost_context.get(
                        'source_card_instance_id'
                    ),
                    'operation': operation, 'selected': successful,
                    'payment_timing': cost.get(
                        'payment_timing', 'before_play'
                    ),
                })
                self.engine_state.setdefault('domain_queue', []).append({
                    'kind': 'play_resume', 'role': decision.get('owner'),
                    'play': copy.deepcopy(continuation.get('play') or {}),
                })
            else:
                self.emit('play_cost_failed', decision.get('owner'), {
                    'card_instance_id': cost_context.get(
                        'source_card_instance_id'
                    ),
                    'operation': operation, 'selected': successful,
                    'minimum': minimum,
                })
        elif continuation.get('type') == 'battle_reveal_play_cost':
            cost = continuation.get('cost') or {}
            operation = cost.get('operation')
            cost_context = continuation.get('context') or {}
            selector = self._play_cost_selector(cost)
            current_options = {
                str(item.get('id'))
                for item in self.selector_options(selector, cost_context)
            }
            successful = []
            if all(instance_id in current_options for instance_id in selected):
                for instance_id in selected:
                    if self._pay_play_cost_item(
                        instance_id, cost, decision.get('owner'), cost_context,
                    ):
                        successful.append(instance_id)
            minimum = _number(resolve_value(
                selector.get('min', 1), self.state, cost_context,
            ), 1)
            side = continuation.get('side')
            source_id = cost_context.get('source_card_instance_id')
            if len(successful) >= minimum:
                self.emit('play_cost_paid', side, {
                    'card_instance_id': source_id, 'operation': operation,
                    'selected': successful,
                    'payment_timing': 'battle_reveal',
                })
            else:
                live_source = self._find_card(source_id)
                battle_source = (
                    (self.engine_state.get('battle') or {}).get(side) or {}
                ).get('card')
                for source in (live_source, battle_source):
                    if isinstance(source, dict):
                        source['technique_invalidated'] = True
                self.emit('play_cost_failed', side, {
                    'card_instance_id': source_id, 'operation': operation,
                    'selected': successful, 'minimum': minimum,
                    'payment_timing': 'battle_reveal',
                })
        elif continuation.get('type') == 'combo_speed_cost':
            cost = continuation.get('cost') or {}
            cost_context = continuation.get('context') or {}
            selector = {
                **(cost.get('selector') or {}),
                'as_operation': cost.get('operation'),
            }
            current_options = {
                str(item.get('id'))
                for item in self.selector_options(selector, cost_context)
            }
            successful = []
            if all(instance_id in current_options for instance_id in selected):
                for instance_id in selected:
                    moved = self.discard_card(
                        instance_id,
                        effect_controller=decision.get('owner'),
                        effect_source=continuation.get(
                            'card_instance_id'
                        ),
                    )
                    if moved is not None:
                        successful.append(instance_id)
            minimum = _number(resolve_value(
                selector.get('min', 1), self.state, cost_context,
            ), 1)
            source_id = continuation.get('card_instance_id')
            if len(successful) >= minimum:
                self.emit('combo_speed_cost_paid', decision.get('owner'), {
                    'card_instance_id': source_id,
                    'operation': cost.get('operation'),
                    'selected': successful,
                })
                play = copy.deepcopy(continuation.get('play') or {})
                play['cost_paid_for'] = continuation.get('cost_paid_for')
                play['speed_cost_paid_for'] = source_id
                self.engine_state.setdefault('domain_queue', []).append({
                    'kind': 'combo_speed_resume',
                    'role': decision.get('owner'), 'play': play,
                })
            else:
                self.emit('combo_speed_cost_failed', decision.get('owner'), {
                    'card_instance_id': source_id,
                    'operation': cost.get('operation'),
                    'selected': successful, 'minimum': minimum,
                })
                self.engine_state['pipeline'] = None
                if self.engine_state.get('combo'):
                    self.end_combo()
        elif continuation.get('type') == 'defense_cost':
            cost = continuation.get('cost') or {}
            operation = cost.get('operation')
            cost_context = continuation.get('context') or {}
            selector = {
                **copy.deepcopy(cost.get('selector') or {}),
                'as_operation': operation,
            }
            current_options = {
                str(item.get('id'))
                for item in self.selector_options(selector, cost_context)
            }
            successful = []
            for instance_id in selected:
                if instance_id == 'decline' or instance_id not in current_options:
                    continue
                moved = None
                if operation == 'discard':
                    moved = self.discard_card(
                        instance_id,
                        effect_controller=decision.get('owner'),
                        effect_source=continuation.get('card_instance_id'),
                    )
                if moved is not None:
                    successful.append(instance_id)
            minimum = _number(resolve_value(
                (cost.get('selector') or {}).get('min', 1),
                self.state, cost_context,
            ), 1)
            side = continuation.get('side')
            source = self._find_card(continuation.get('card_instance_id')) or (
                ((self.engine_state.get('battle') or {}).get(side) or {}).get('card')
                or {}
            )
            rule_index = _number(continuation.get('rule_index'))
            if len(successful) >= minimum:
                key = self._defense_cost_key(side, source, rule_index)
                paid = (self.engine_state.get('battle') or {}).setdefault(
                    'defense_costs_paid', [],
                )
                if key not in paid:
                    paid.append(key)
                self.emit('defense_cost_paid', side, {
                    'card_instance_id': source.get('instance_id'),
                    'rule_index': rule_index, 'operation': operation,
                    'selected': successful,
                })
            else:
                self.emit(
                    'defense_cost_declined'
                    if cost.get('optional') and 'decline' in selected
                    else 'defense_cost_failed', side, {
                    'card_instance_id': source.get('instance_id'),
                    'rule_index': rule_index, 'operation': operation,
                    'selected': successful, 'minimum': minimum,
                })
        elif continuation.get('type') == 'no_response_card':
            self._resolve_no_response_card(continuation.get('missing'), selected)
        elif continuation.get('type') == 'no_response_result':
            self.engine_state['forced_no_response_result'] = {
                'missing': continuation.get('missing'),
                'result': selected[0] if selected else 'hit',
            }
            self._advance_phase('battle')
        elif continuation.get('type') == 'break_replenish':
            if selected and selected[0] != 'decline':
                card = self._find_card(selected[0], owner=decision.get('owner'), zone='side')
                if card and (_is_attack(card) or _is_defense(card)) and not _is_special(card):
                    self.move_card(selected[0], 'list', reason='break_replenish')
        elif continuation.get('type') == 'hand_limit_discard':
            self._resolve_hand_limit_discard(
                continuation.get('player'), selected,
            )
        elif continuation.get('type') == 'grab_negation':
            if selected and selected[0] != 'decline':
                self._invalidate_grab(decision.get('owner'), selected[0])

    def _ready_timeout(self, missing):
        if missing not in PLAYER_SIDES or missing in self.engine_state.get('ready_cards', {}):
            return
        self._begin_no_response(missing, declared=False)

    def _begin_no_response(self, missing, *, declared):
        count = _number(self.engine_state.setdefault('no_response', {}).get(missing)) + 1
        self.engine_state['no_response'][missing] = count
        self.engine_state.setdefault('skip_get', {})[missing] = True
        self.emit('no_response', missing, {'count': count, 'declared': bool(declared)})
        pipeline = {
            'kind': 'no_response', 'missing': missing, 'count': count,
            'declared': bool(declared),
        }
        self.engine_state['pipeline'] = pipeline
        self._fire('no_response', {'controller': missing, 'count': count, 'declared': bool(declared)})
        if not self.is_waiting:
            self._advance_no_response_pipeline(pipeline)

    def _advance_no_response_pipeline(self, pipeline):
        missing = pipeline.get('missing')
        count = _number(pipeline.get('count'))
        declared = bool(pipeline.get('declared'))
        self.engine_state['pipeline'] = None
        if count >= 3:
            self._finish(opponent(missing), 'no_response_disqualification')
            return False
        chooser = opponent(missing)
        if declared:
            instance_id = self._append_virtual_no_response(missing)
            self.engine_state['ready_cards'][missing] = instance_id
            if chooser not in self.engine_state['ready_cards']:
                self._start_clock(
                    'ready', owner=chooser,
                    seconds=self._timeout_seconds(
                        'ready_timeout_seconds', DEFAULT_READY_SECONDS,
                    ),
                )
                return False
            other_card = self._find_card(self.engine_state['ready_cards'][chooser])
            if other_card and other_card.get('virtual'):
                self._clear_clock()
                self._advance_phase('battle')
            else:
                self._request_virtual_result(missing, chooser)
            return False
        options = [
            {
                'id': card.get('instance_id'),
                'label': card.get('name') or '카드',
                # This is intentionally disclosed only through the chooser's
                # private pending decision; the opponent hand itself remains
                # redacted in every board projection.
                'card': self._private_action_card(card),
            }
            for card in self._zone(missing, 'hand') if self._legal_ready_card(card)
        ]
        if options:
            self.create_decision(
                owner=chooser, kind='no_response_card', prompt='상대 손패에서 강제 레디할 카드를 선택하세요.',
                options=options, minimum=1, maximum=1, default=[sorted(item['id'] for item in options)[0]],
                continuation={'type': 'no_response_card', 'missing': missing},
            )
        else:
            self._create_virtual_no_response(missing, chooser)
        return False

    def _declare_no_response(self, missing):
        if any(self._legal_ready_card(card) for card in self._zone(missing, 'hand')):
            raise IllegalAction('사용 가능한 레디 카드가 있습니다.')
        self._begin_no_response(missing, declared=True)

    def _resolve_no_response_card(self, missing, selected):
        instance_id = selected[0] if selected else None
        card = self._find_card(instance_id, owner=missing, zone='hand')
        if not card or not self._legal_ready_card(card):
            self._create_virtual_no_response(missing, opponent(missing))
            return
        self.move_card(instance_id, 'battle', reason='no_response')
        card['face_up'] = False
        self.engine_state['ready_cards'][missing] = instance_id
        self._advance_phase('battle')

    def _create_virtual_no_response(self, missing, chooser):
        instance_id = self._append_virtual_no_response(missing)
        self.engine_state['ready_cards'][missing] = instance_id
        self._request_virtual_result(missing, chooser)

    def _append_virtual_no_response(self, missing):
        instance_id = f'virtual-no-response-{self.state.get("turn")}-{missing}'
        virtual = {
            'instance_id': instance_id, 'kind': 'virtual', 'owner': missing,
            'name': '무응답 기술', 'code': '__NO_RESPONSE__', 'type': '공격',
            'frame': 999, 'damage': 0, 'pos': None, 'hit': '0', 'guard': '0',
            'counter': '0', 'face_up': False, 'virtual': True,
        }
        self._zone(missing, 'battle').append(virtual)
        return instance_id

    def _request_virtual_result(self, missing, chooser):
        # The opponent chooses hit/counter by selecting which synthetic speed
        # result should be used.  This is represented as a mandatory decision.
        self.create_decision(
            owner=chooser, kind='no_response_result', prompt='무응답 기술에 대한 판정을 선택하세요.',
            options=[{'id': 'hit', 'label': '히트'}, {'id': 'counter', 'label': '카운터'}],
            minimum=1, maximum=1, default=['hit'],
            continuation={'type': 'no_response_result', 'missing': missing},
        )

    def _offer_grab_negation(self):
        self._refresh_continuous_rules()
        battle = self.engine_state.get('battle') or {}
        for defender in self._priority_order():
            attacker = opponent(defender)
            attacker_card = (battle.get(attacker) or {}).get('card')
            effective_attacker = self._effective_card_for_operation(
                attacker_card, 'special_judgment',
            )
            if not _has_grab(effective_attacker):
                continue
            if self._rule_blocked('grab_negation', defender):
                continue
            options = [
                {
                    'id': card.get('instance_id'),
                    'label': card.get('name') or '그랩 기술',
                    'card_instance_id': card.get('instance_id'),
                    'card': self._private_action_card(card),
                }
                for card in self._zone(defender, 'hand')
                if (
                    _is_attack(card)
                    and _has_grab(self._effective_card_for_operation(
                        card, 'special_judgment',
                    ))
                )
                and not self._break_rule_prevents(
                    card, 'hand', defender, direct_controller=defender,
                )
            ]
            if options:
                self.create_decision(
                    owner=defender, kind='grab_negation', prompt='패의 그랩을 브레이크해 상대 그랩을 무효로 할 수 있습니다.',
                    options=options,
                    minimum=0, maximum=1, default=[], optional=True,
                    continuation={'type': 'grab_negation'},
                )
                return True
        return False

    def _invalidate_grab(self, defender, hand_grab_id):
        moved = self.break_card(
            hand_grab_id, reason='grab_negation', direct_controller=defender,
        )
        if moved is None:
            return False
        attacker = opponent(defender)
        attacker_entry = copy.deepcopy(
            (self.engine_state.get('battle') or {}).get(attacker) or {}
        )
        defender_entry = copy.deepcopy(
            (self.engine_state.get('battle') or {}).get(defender) or {}
        )
        for side in PLAYER_SIDES:
            entry = (self.engine_state.get('battle') or {}).get(side) or {}
            instance_id = entry.get('instance_id')
            if self._find_card(instance_id, owner=side, zone='battle'):
                self.move_card(instance_id, 'hand', reason='grab_negated')
        self.state['phase'] = 'ready'
        self.engine_state['step'] = 'ready_actions'
        self.engine_state['ready_cards'] = {}
        self.engine_state['battle'] = {}
        self.engine_state['pipeline'] = None
        self._clear_clock()
        self.emit('grab_negated', defender, {'card_instance_id': hand_grab_id})
        if attacker_entry.get('card'):
            self._fire('grab_negated', {
                'controller': attacker,
                'source_card_instance_id': attacker_entry.get('instance_id'),
                'source_card': attacker_entry.get('card'),
                'opponent_card': defender_entry.get('card'),
                'negated_by_card_instance_id': hand_grab_id,
            })
        return True

    def _request_rewind(self, role):
        self.engine_state['rewind_request'] = {
            'requested_by': role, 'requested_at': self.now.isoformat(),
            'target_command': self.engine_state.get('command_count'),
        }
        self._start_clock('rewind', owner=opponent(role), seconds=30)
        self.emit('rewind_requested', role, {'target_command': self.engine_state.get('command_count')})

    def _answer_rewind(self, role, accept):
        request = self.engine_state.get('rewind_request') or {}
        if not request or request.get('requested_by') == role:
            raise IllegalAction('응답할 되감기 요청이 없습니다.')
        request['accepted'] = bool(accept)
        request['answered_by'] = role
        self._clear_clock()
        self.emit('rewind_answered', role, {'accept': bool(accept), 'target_command': request.get('target_command')})
        # Persistence restores the pre-command snapshot after seeing accepted.
        if not accept:
            self.engine_state['rewind_request'] = None

    # ------------------------------------------------------------------
    # Effect-resolver domain commands

    def _fire(self, event_type, context=None):
        context = copy.deepcopy(context or {})
        parent_depth = context.get('depth')
        context['depth'] = 0 if parent_depth is None else _number(parent_depth) + 1
        self._refresh_continuous_state_grants()
        self._run_scheduled(event_type, context)
        self.resolver.collect(event_type, context, depth=context['depth'])
        self.resolver.drain()

    def _run_scheduled(self, event_type, context):
        # Iterate a snapshot, but mutate the live queue one item at a time.
        # A scheduled command may recursively fire another event and append a
        # new schedule (for example state loss creating a next-turn lock).
        # Replacing the whole queue at the end would silently discard it.
        pending = list(self.engine_state.get('scheduled') or [])
        for item in pending:
            live = self.engine_state.setdefault('scheduled', [])
            if not any(candidate is item for candidate in live):
                # A nested event already consumed this original item.
                continue
            when = item.get('when') or {}
            matches = when.get('event') == event_type
            if when.get('phase') and when.get('phase') != self.state.get('phase'):
                matches = False
            if (
                when.get('where_event_card')
                and not card_matches(
                    context.get('source_card') or context.get('event_card'),
                    when.get('where_event_card'), self.state, context,
                )
            ):
                matches = False
            expected_controller = when.get('controller')
            scheduled_controller = (item.get('context') or {}).get('controller')
            if expected_controller == 'self':
                expected_controller = scheduled_controller
            elif expected_controller == 'opponent':
                expected_controller = opponent(scheduled_controller)
            if (
                expected_controller in PLAYER_SIDES
                and context.get('controller') in PLAYER_SIDES
                and context.get('controller') != expected_controller
            ):
                matches = False
            scheduled_context = {
                **copy.deepcopy(item.get('context') or {}),
                **copy.deepcopy(context),
            }
            if item.get('preserve_source'):
                origin = copy.deepcopy(item.get('context') or {})
                event_card = copy.deepcopy(
                    context.get('event_card') or context.get('source_card')
                )
                event_card_instance_id = (
                    context.get('event_card_instance_id')
                    or context.get('source_card_instance_id')
                )
                scheduled_context.update({
                    'event_card': event_card,
                    'event_card_instance_id': event_card_instance_id,
                    'source_card': copy.deepcopy(origin.get('source_card')),
                    'source_card_instance_id': origin.get(
                        'source_card_instance_id'
                    ),
                })
            effective_controller = scheduled_controller
            if (
                item.get('effect_controller') == 'event'
                and context.get('controller') in PLAYER_SIDES
            ):
                effective_controller = context.get('controller')
            if effective_controller in PLAYER_SIDES:
                scheduled_context.update({
                    'controller': effective_controller,
                    'opponent': opponent(effective_controller),
                    'controller_hp': _number(
                        self.state['players'][effective_controller].get('hp')
                    ),
                    'controller_fp': _number(
                        self.state['players'][effective_controller].get('fp')
                    ),
                    'opponent_hp': _number(
                        self.state['players'][opponent(effective_controller)].get('hp')
                    ),
                    'opponent_fp': _number(
                        self.state['players'][opponent(effective_controller)].get('fp')
                    ),
                })
            if matches and when.get('condition') is not None:
                matches = condition_matches(
                    when.get('condition'), self.state, scheduled_context,
                )
            if matches and not item.get('repeat'):
                self.engine_state['scheduled'] = [
                    candidate for candidate in self.engine_state.get('scheduled') or []
                    if candidate is not item
                ]
            if matches and scheduled_controller in set(context.get('excluded_controllers') or []):
                self.emit('scheduled_effect_skipped', scheduled_controller, {
                    'event': event_type, 'phase': self.state.get('phase'),
                })
                continue
            if matches:
                self.resolver.execute_effect(item.get('effect') or {}, scheduled_context)

    def change_hp(self, side, amount, *, source='', context=None):
        if side not in PLAYER_SIDES:
            raise EngineError('HP 대상 플레이어가 올바르지 않습니다.')
        before = _number(self.state['players'][side].get('hp'))
        delta = _number(amount)
        after = max(0, before + delta)
        if delta > 0 and self.state['players'][side].get('initial_hp') is not None:
            # Recovery never raises HP above the player's printed/starting
            # maximum.  If an imported legacy state is already above that
            # value, healing must not reduce it as a side effect.
            maximum = max(
                before,
                _number(self.state['players'][side].get('initial_hp')),
            )
            after = min(after, maximum)
        self.state['players'][side]['hp'] = after
        self.emit('hp_changed', side, {'before': before, 'after': after, 'amount': after - before, 'source': source})
        if context is not None:
            self._fire('hp_changed', {**copy.deepcopy(context), 'player': side, 'amount': after - before})
        if self.is_waiting:
            self.engine_state.setdefault('domain_queue', []).append({'kind': 'victory_check'})
        else:
            self._check_victory()
        return after

    def deal_damage(self, side, amount, *, source='', context=None):
        amount = max(0, _number(amount))
        if not amount:
            return 0
        item = {
            'kind': 'damage', 'stage': 'before', 'side': side, 'amount': amount,
            'source': source, 'context': copy.deepcopy(context or {}),
        }
        if self.is_waiting:
            self.engine_state.setdefault('domain_queue', []).append(item)
            return None
        return self._advance_damage(item)

    def _advance_damage(self, item):
        side = item['side']
        context = {
            **copy.deepcopy(item.get('context') or {}), 'player': side,
            'amount': item['amount'], 'source': item.get('source'),
        }
        if item['stage'] == 'before':
            item['stage'] = 'apply'
            self._fire('damage_before', context)
            if self.is_waiting:
                self.engine_state.setdefault('domain_queue', []).insert(0, item)
                return None
        if item['stage'] == 'apply':
            replaced = max(0, self._replacement_value('damage', side, item['amount']))
            absorbed = self._consume_shields(side, replaced, source=item.get('source'))
            actual = max(0, replaced - absorbed)
            if actual:
                received_this_turn = self.engine_state.setdefault(
                    'turn_damage_received', {player: 0 for player in PLAYER_SIDES},
                )
                received_this_turn[side] = _number(received_this_turn.get(side)) + actual
            if context.get('battle_batch'):
                received = (self.engine_state.get('battle') or {}).setdefault(
                    'actual_damage_received', {player: 0 for player in PLAYER_SIDES},
                )
                received[side] = _number(received.get(side)) + actual
            item['absorbed'] = absorbed
            item['actual'] = actual
            before = _number(self.state['players'][side].get('hp'))
            after = max(0, before - actual)
            self.state['players'][side]['hp'] = after
            self.emit('hp_changed', side, {
                'before': before, 'after': after, 'amount': -actual, 'source': item.get('source'),
            })
            item['stage'] = 'after_hp'
            self._fire('hp_changed', {**context, 'amount': -actual, 'before': before, 'after': after})
            if self.is_waiting:
                self.engine_state.setdefault('domain_queue', []).insert(0, item)
                return None
        if item['stage'] == 'after_hp':
            self.emit('damage_dealt', context.get('controller') or opponent(side), {
                'target': side, 'amount': item['actual'], 'source': item.get('source'),
            })
            item['stage'] = 'done'
            self._fire('damage_after', {**context, 'amount': item['actual']})
            if self.is_waiting:
                self.engine_state.setdefault('domain_queue', []).insert(0, item)
                return None
        if context.get('battle_batch') and not item.get('batch_counted'):
            item['batch_counted'] = True
            remaining = max(0, _number(self.engine_state.get('battle_damage_remaining')) - 1)
            self.engine_state['battle_damage_remaining'] = remaining
            if remaining == 0:
                self._check_victory()
        else:
            self._check_victory()
        return item.get('actual', 0)

    def change_fp(self, side, amount, *, source='', context=None):
        return self.set_fp(side, _number(self.state['players'][side].get('fp')) + _number(amount), source=source, context=context)

    def set_fp(self, side, value, *, source='', context=None):
        if side not in PLAYER_SIDES:
            raise EngineError('FP 대상 플레이어가 올바르지 않습니다.')
        before = _number(self.state['players'][side].get('fp'))
        after = _number(value)
        self.state['players'][side]['fp'] = after
        if before != after:
            self.emit('fp_changed', side, {'before': before, 'after': after, 'amount': after - before, 'source': source})
            if context is not None:
                self._fire('fp_changed', {**copy.deepcopy(context), 'player': side, 'amount': after - before})
        return after

    def _find_location(self, instance_id):
        for side in PLAYER_SIDES:
            for zone, cards in self.state['players'][side]['zones'].items():
                for index, card in enumerate(cards):
                    if card.get('instance_id') == instance_id:
                        return side, zone, index, card
        return None, None, None, None

    def _find_card(self, instance_id, *, owner=None, zone=None):
        side, found_zone, _index, card = self._find_location(instance_id)
        if owner and side != owner:
            return None
        if zone and found_zone != zone:
            return None
        return card

    def move_card(
        self, instance_id, to_zone, *, to_player=None, reason='',
        effect_controller=None, effect_source=None,
        preserve_attachment=False, block_hand_until=None, set_flags=None,
        allow_special_destination=False, face_up=None,
        defer_triggers=False, trigger_queue=None, _skip_effect_checks=False,
    ):
        from_player, from_zone, index, card = self._find_location(instance_id)
        if not card:
            raise EngineError(f'카드를 찾을 수 없습니다: {instance_id}')
        owner = card.get('owner') if card.get('owner') in PLAYER_SIDES else from_player
        if is_passive_card(card) and (to_zone != 'passive' or to_player not in {None, owner}):
            self.emit('card_move_prevented', owner, {
                'card_instance_id': instance_id, 'from_zone': from_zone,
                'to_zone': to_zone, 'reason': 'passive_zone_locked',
            })
            return None
        blocked_until = card.get('move_to_hand_blocked_until')
        blocked_through = card.get('move_to_hand_blocked_through_turn')
        hand_move_blocked = (
            blocked_until == 'turn'
            or (blocked_until == 'battle' and self.state.get('phase') == 'battle')
            or (
                blocked_through is not None
                and _number(self.state.get('turn'), 1) <= _number(blocked_through)
            )
        )
        if to_zone == 'hand' and hand_move_blocked:
            self.emit('card_move_prevented', owner, {
                'card_instance_id': instance_id, 'from_zone': from_zone,
                'to_zone': to_zone, 'reason': 'battle_hand_restriction',
            })
            return None
        if (
            not _skip_effect_checks
            and self._card_ignores_effect(
                card, effect_controller, effect_source, zone=from_zone,
                operation='move_card', to_zone=to_zone,
            )
        ):
            self.emit('card_effect_ignored', owner, {
                'card_instance_id': instance_id, 'operation': 'move_card',
                'effect_controller': effect_controller, 'effect_source': effect_source,
            })
            return None
        target = to_player if to_player in PLAYER_SIDES else owner
        if not _skip_effect_checks and not self._zone_limit_allows(card, target, to_zone):
            self.emit('card_move_prevented', owner, {
                'card_instance_id': instance_id, 'from_zone': from_zone,
                'to_zone': to_zone, 'reason': 'zone_limit',
            })
            return None
        attached_card_ids = [
            candidate.get('instance_id')
            for side in PLAYER_SIDES
            for cards in self.state['players'][side]['zones'].values()
            for candidate in cards
            if candidate.get('attached_to') == instance_id
            and (
                candidate.get('character_key') == 'cmyk'
                or candidate.get('return_to_hand_on_attachment_expiry')
            )
        ]
        self.state['players'][from_player]['zones'][from_zone].pop(index)
        invalid_special_move = (
            _is_special(card)
            and not allow_special_destination
            and to_zone not in {'side', 'lumen', 'ultimate', 'break'}
        )
        if invalid_special_move:
            to_zone = 'break'
            target = owner
        card['owner'] = owner
        separate_set_use = reason in {'ready', 'combo', 'catch', 'borrowed_combo'}
        preserve_cmyk_public_set = (
            card.get('character_key') == 'cmyk'
            and to_zone not in {'hand', 'side'}
            and not separate_set_use
        )
        clear_attachment = (
            not preserve_attachment
            and bool(card.get('attached_to'))
            and not preserve_cmyk_public_set
        )
        if clear_attachment:
            card.pop('attached_to', None)
            card.pop('attachment_expires', None)
            card.pop('return_to_hand_on_attachment_expiry', None)
            card.pop('set_order', None)
        if block_hand_until:
            if block_hand_until == 'next_turn':
                card.pop('move_to_hand_blocked_until', None)
                card['move_to_hand_blocked_through_turn'] = (
                    _number(self.state.get('turn'), 1) + 1
                )
            else:
                card['move_to_hand_blocked_until'] = block_hand_until
        for flag_name, flag_value in (set_flags or {}).items():
            if flag_value is None:
                card.pop(str(flag_name), None)
            else:
                card[str(flag_name)] = copy.deepcopy(flag_value)
        if (
            from_zone == 'lumen' and to_zone != 'lumen'
            and card.get('non_technique_while_face_down')
        ):
            card.pop('non_technique_while_face_down', None)
            card.pop('effects_negated', None)
            card.pop('secret_time_host', None)
        if face_up is None:
            public_get_hand = (
                to_zone == 'hand' and self.state.get('phase') == 'get'
            )
            card['face_up'] = (
                to_zone in {
                    'character', 'passive', 'list', 'break', 'lumen',
                    'ultimate',
                }
                or public_get_hand
            )
            if public_get_hand:
                card['hide_after_get'] = True
        else:
            card['face_up'] = bool(face_up)
            card.pop('hide_after_get', None)
        if to_zone != 'hand':
            card.pop('hide_after_get', None)
        self._apply_card_form(card, to_zone)
        self.state['players'][target]['zones'][to_zone].append(card)
        if from_zone != to_zone or from_player != target:
            for attached_id in attached_card_ids:
                attached_location = self._find_location(attached_id)
                if not attached_location[3] or attached_location[1] == 'list':
                    continue
                self.move_card(
                    attached_id, 'list', reason='set_host_moved',
                    preserve_attachment=True,
                    defer_triggers=defer_triggers,
                    trigger_queue=trigger_queue,
                )
        self.emit('card_moved', owner, {
            'card_instance_id': instance_id, 'from_player': from_player, 'from_zone': from_zone,
            'to_player': target, 'to_zone': to_zone, 'reason': reason,
            'card_id': card.get('card_id'), 'card_code': card.get('code'),
            'card_label': card.get('name') or card.get('code') or '카드',
        }, visibility='public' if card.get('face_up') else 'private')
        self._enforce_list_limit(target)
        self._reconcile_trait_states()
        moved_context = {
            'controller': owner, 'source_card_instance_id': instance_id,
            'source_card': copy.deepcopy(card), 'from_zone': from_zone, 'to_zone': to_zone,
        }
        if defer_triggers:
            if trigger_queue is not None:
                trigger_queue.append(('card_moved', moved_context))
        else:
            self._fire('card_moved', moved_context)
        if to_zone == 'hand':
            self._queue_hand_limit_adjustment(target)
        if invalid_special_move:
            self.emit('card_broken', owner, {
                'card_instance_id': instance_id, 'reason': 'invalid_special_destination',
            })
            broken_context = {
                'controller': owner, 'source_card_instance_id': instance_id,
                'source_card': copy.deepcopy(card), 'reason': 'invalid_special_destination',
            }
            if defer_triggers:
                if trigger_queue is not None:
                    trigger_queue.append(('card_broken', broken_context))
            else:
                self._fire('card_broken', broken_context)
        return card

    def exchange_cards(
        self, first_id, second_id, *, reason='', effect_controller=None,
        effect_source=None,
    ):
        """Atomically exchange two cards without an intermediate zone state."""
        first_side, first_zone, first_index, first = self._find_location(first_id)
        second_side, second_zone, second_index, second = self._find_location(second_id)
        if (
            not first or not second or first_id == second_id
            or first_side not in PLAYER_SIDES or second_side not in PLAYER_SIDES
            or first_side != second_side or first_zone == second_zone
        ):
            raise EngineError('교체할 두 카드의 영역이 올바르지 않습니다.')
        if first.get('attached_to') or second.get('attached_to'):
            raise EngineError('다른 카드에 세트된 카드는 교체할 수 없습니다.')
        if is_passive_card(first) or is_passive_card(second):
            self.emit('card_exchange_prevented', effect_controller or first_side, {
                'first_card_instance_id': first_id,
                'second_card_instance_id': second_id,
                'reason': 'passive_zone_locked',
            })
            return False
        attached_hosts = {
            card.get('attached_to')
            for side in PLAYER_SIDES
            for cards in self.state['players'][side]['zones'].values()
            for card in cards if card.get('attached_to')
        }
        if first_id in attached_hosts or second_id in attached_hosts:
            raise EngineError('세트 카드가 있는 기술은 교체할 수 없습니다.')
        for card, zone in ((first, first_zone), (second, second_zone)):
            if self._card_ignores_effect(
                card, effect_controller, effect_source, zone=zone,
                operation='exchange_cards',
            ):
                self.emit('card_effect_ignored', card.get('owner'), {
                    'card_instance_id': card.get('instance_id'),
                    'operation': 'exchange_cards',
                    'effect_controller': effect_controller,
                    'effect_source': effect_source,
                })
                return False

        def destination_allows(card, destination, replaced_id):
            if _is_special(card) and destination not in {
                'side', 'lumen', 'ultimate', 'break',
            }:
                return False
            return self._zone_limit_allows(
                card, first_side, destination,
                exclude_instance_ids={replaced_id},
            )

        if not destination_allows(first, second_zone, second_id) or not destination_allows(
            second, first_zone, first_id,
        ):
            self.emit('card_exchange_prevented', effect_controller, {
                'first_card_instance_id': first_id,
                'second_card_instance_id': second_id,
                'reason': 'zone_limit',
            })
            return False

        first_face_up = bool(first.get('face_up'))
        second_face_up = bool(second.get('face_up'))
        first['face_up'] = second_face_up
        second['face_up'] = first_face_up
        self._apply_card_form(first, second_zone)
        self._apply_card_form(second, first_zone)
        first_cards = self.state['players'][first_side]['zones'][first_zone]
        second_cards = self.state['players'][second_side]['zones'][second_zone]
        first_cards[first_index], second_cards[second_index] = second, first
        self.emit('cards_exchanged', effect_controller or first_side, {
            'first_card_instance_id': first_id,
            'first_from_zone': first_zone, 'first_to_zone': second_zone,
            'second_card_instance_id': second_id,
            'second_from_zone': second_zone, 'second_to_zone': first_zone,
            'source': effect_source, 'reason': reason,
        })
        moved_contexts = (
            (first, first_zone, second_zone),
            (second, second_zone, first_zone),
        )
        for card, from_zone, to_zone in moved_contexts:
            self.emit('card_moved', first_side, {
                'card_instance_id': card.get('instance_id'),
                'from_player': first_side, 'from_zone': from_zone,
                'to_player': first_side, 'to_zone': to_zone,
                'reason': reason or 'exchange',
            }, visibility='public' if card.get('face_up') else 'private')
        if 'list' in {first_zone, second_zone}:
            self._enforce_list_limit(first_side)
        # Reconcile only after both cards occupy their final zones. This keeps
        # Calling Card-derived Advance Notice active throughout Kissing You's
        # single exchange effect (Q&A 119).
        self._reconcile_trait_states()
        for card, from_zone, to_zone in moved_contexts:
            self._fire('card_moved', {
                'controller': first_side,
                'source_card_instance_id': card.get('instance_id'),
                'source_card': copy.deepcopy(card),
                'from_zone': from_zone, 'to_zone': to_zone,
            })
        return True

    def _active_player_zone_limits(self, target):
        """Return live player-scoped limits granted by continuous cards.

        A root ``zone_limits`` block normally constrains the card carrying the
        definition.  A continuous ``static_rule`` that references that block
        instead grants the limit to its controller, so other effects cannot
        bypass an Ultimate such as Lucky Days by moving the limited token.
        Resolve this from live zones on demand so moving the source out of its
        active zone removes the limit within the same command sequence.
        """
        limits = []
        for item in self.resolver.continuous_effects({
            'phase': self.state.get('phase'),
        }):
            for effect in (item.get('ability') or {}).get('effects') or []:
                if (
                    effect.get('op') != 'static_rule'
                    or 'zone_limits' not in (effect.get('rules') or [])
                ):
                    continue
                player = effect.get('player')
                if isinstance(player, dict):
                    player = (
                        opponent(item.get('controller'))
                        if 'opponent' in player else item.get('controller')
                    )
                player = player or item.get('controller')
                if player != target:
                    continue
                source_card = self._find_card(item.get('card_instance_id'))
                definition = self._definition_for_card(source_card or {
                    'code': item.get('card_code'),
                })
                for limit in definition.get('zone_limits') or []:
                    if isinstance(limit, dict):
                        limits.append(copy.deepcopy(limit))
        return limits

    def _zone_limit_allows(
        self, card, target, to_zone, *, exclude_instance_ids=None,
    ):
        definition = self._definition_for_card(card)
        limits = [
            *copy.deepcopy(definition.get('zone_limits') or []),
            *self._active_player_zone_limits(target),
        ]
        excluded = {
            str(instance_id) for instance_id in (exclude_instance_ids or set())
            if instance_id
        }
        for limit in limits:
            if not isinstance(limit, dict) or limit.get('zone') != to_zone:
                continue
            if limit.get('where') and not card_matches(
                card, limit.get('where'), self.state, {},
            ):
                continue
            maximum = max(0, _number(limit.get('max')))
            matching = sum(
                1 for existing in self._zone(target, to_zone)
                if str(existing.get('instance_id')) not in excluded
                and existing.get('instance_id') != card.get('instance_id')
                and card_matches(existing, limit.get('where'))
            )
            if matching >= maximum:
                return False
        return True

    def _break_replenishes(self, card, from_zone=None):
        printed = self._printed_card_snapshot(card)
        is_token = (
            (card or {}).get('kind') == 'token'
            or '토큰' in str((printed or {}).get('type') or '')
        )
        return bool(
            from_zone != 'side'
            and not is_token
            and (_is_attack(card) or _is_defense(card))
            and not _is_special(card)
        )

    def break_card(
        self, instance_id, *, reason='', effect_controller=None,
        effect_source=None, direct_controller=None, _prevalidated=False,
        _defer_followups=False, _trigger_queue=None,
    ):
        location_side, current_zone, _index, card = self._find_location(instance_id)
        if not card:
            return None
        owner = card.get('owner') if card.get('owner') in PLAYER_SIDES else location_side
        if (
            not _prevalidated
            and self._card_ignores_effect(
                card, effect_controller, effect_source, zone=current_zone,
            )
        ):
            self.emit('card_effect_ignored', owner, {
                'card_instance_id': instance_id, 'operation': 'break_card',
                'effect_controller': effect_controller, 'effect_source': effect_source,
            })
            return None
        if not _prevalidated:
            self._refresh_continuous_rules()
        if not _prevalidated and self._rule_blocked(
            'break', owner, card, zone=current_zone,
            effect_controller=effect_controller,
            direct_controller=direct_controller,
        ):
            self.emit('card_break_prevented', owner, {
                'card_instance_id': instance_id, 'zone': current_zone,
                'reason': 'continuous_rule', 'requested_reason': reason,
                'effect_controller': effect_controller,
                'direct_controller': direct_controller,
            })
            return None
        prevented = False if _prevalidated else self._break_rule_prevents(
            card, current_zone, owner, effect_controller=effect_controller,
            direct_controller=direct_controller,
        )
        if prevented:
            self.emit('card_break_prevented', owner, {
                'card_instance_id': instance_id, 'zone': current_zone,
                'reason': 'card_rule', 'requested_reason': reason,
                'effect_controller': effect_controller,
                'direct_controller': direct_controller,
            })
            return None
        was_normal = self._break_replenishes(card, current_zone)
        moved = self.move_card(
            instance_id, 'break', to_player=owner, reason=reason or 'break',
            effect_controller=effect_controller, effect_source=effect_source,
            defer_triggers=_defer_followups, trigger_queue=_trigger_queue,
            _skip_effect_checks=_prevalidated,
        )
        if moved is None:
            return None
        self.emit('card_broken', owner, {'card_instance_id': instance_id, 'reason': reason})
        broken_context = {
            'controller': owner,
            'source_card_instance_id': instance_id,
            'source_card': copy.deepcopy(moved),
        }
        if _defer_followups:
            if _trigger_queue is not None:
                _trigger_queue.append(('card_broken', broken_context))
        else:
            self._fire('card_broken', broken_context)
        if was_normal and not _defer_followups:
            self._offer_break_replenishment(owner)
        return moved

    def break_cards(
        self, instance_ids, *, reason='', effect_controller=None,
        effect_source=None, direct_controller=None, require_all=False,
    ):
        """Break several cards after resolving every target's eligibility.

        ``require_all`` is used by effects such as Jump: Q&A 656 rules that
        Jump is not broken when the opposing Technique cannot be broken.
        Card-moved/card-broken triggers and replenishment choices are delayed
        until every eligible card has physically moved.
        """
        card_ids = list(dict.fromkeys(
            str(value) for value in (instance_ids or []) if value
        ))
        if not card_ids:
            return []

        self._refresh_continuous_rules()
        planned = []
        blocked = []
        for instance_id in card_ids:
            location_side, current_zone, _index, card = self._find_location(instance_id)
            if not card:
                blocked.append((instance_id, None, current_zone, 'missing'))
                continue
            owner = card.get('owner') if card.get('owner') in PLAYER_SIDES else location_side
            if self._card_ignores_effect(
                card, effect_controller, effect_source, zone=current_zone,
            ):
                blocked.append((instance_id, owner, current_zone, 'effect_ignored'))
                continue
            if self._rule_blocked(
                'break', owner, card, zone=current_zone,
                effect_controller=effect_controller,
                direct_controller=direct_controller,
            ):
                blocked.append((instance_id, owner, current_zone, 'continuous_rule'))
                continue
            if self._break_rule_prevents(
                card, current_zone, owner,
                effect_controller=effect_controller,
                direct_controller=direct_controller,
            ):
                blocked.append((instance_id, owner, current_zone, 'card_rule'))
                continue
            if not self._zone_limit_allows(card, owner, 'break'):
                blocked.append((instance_id, owner, current_zone, 'zone_limit'))
                continue
            planned.append((instance_id, owner, card, current_zone))

        for instance_id, owner, current_zone, blocked_reason in blocked:
            if blocked_reason == 'effect_ignored':
                self.emit('card_effect_ignored', owner, {
                    'card_instance_id': instance_id,
                    'operation': 'break_cards',
                    'effect_controller': effect_controller,
                    'effect_source': effect_source,
                })
            elif blocked_reason != 'missing':
                self.emit('card_break_prevented', owner, {
                    'card_instance_id': instance_id,
                    'zone': current_zone,
                    'reason': blocked_reason,
                    'requested_reason': reason,
                    'effect_controller': effect_controller,
                    'direct_controller': direct_controller,
                })

        if require_all and blocked:
            self.emit('card_break_batch_cancelled', effect_controller, {
                'card_instance_ids': card_ids,
                'blocked_card_instance_ids': [item[0] for item in blocked],
                'reason': reason,
            })
            return []

        trigger_queue = []
        moved_cards = []
        replenish_owners = []
        for instance_id, owner, card, _current_zone in planned:
            was_normal = self._break_replenishes(card, _current_zone)
            moved = self.break_card(
                instance_id,
                reason=reason,
                effect_controller=effect_controller,
                effect_source=effect_source,
                direct_controller=direct_controller,
                _prevalidated=True,
                _defer_followups=True,
                _trigger_queue=trigger_queue,
            )
            if moved is not None:
                moved_cards.append(moved)
                if was_normal:
                    replenish_owners.append(owner)

        for event_type, context in trigger_queue:
            self._fire(event_type, context)
        for owner in replenish_owners:
            self._offer_break_replenishment(owner)
        return moved_cards

    def _break_rule_prevents(
        self, card, current_zone, owner, *, effect_controller=None,
        direct_controller=None,
    ):
        definition = self._definition_for_card(card)
        break_rules = definition.get('break_rules') or {}
        if current_zone in (break_rules.get('forbidden_zones') or []):
            return True
        context = {
            'controller': owner, 'opponent': opponent(owner),
            'source_card': card,
            'source_card_instance_id': card.get('instance_id'),
            'source_zone': current_zone, 'effect_controller': effect_controller,
            'direct_controller': direct_controller,
        }
        for prevention in break_rules.get('preventions') or []:
            if not isinstance(prevention, dict):
                continue
            if (
                prevention.get('numbered_effect')
                and card.get('numbered_effects_negated')
            ):
                continue
            if not condition_matches(prevention.get('condition'), self.state, context):
                continue
            scope = prevention.get('scope')
            if scope == 'all':
                return True
            if scope == 'owner_direct' and direct_controller == owner:
                return True
            if (
                scope == 'opponent_effect'
                and effect_controller in PLAYER_SIDES
                and effect_controller != owner
            ):
                return True
        return False

    def discard_card(
        self, instance_id, *, effect_controller=None, effect_source=None,
        block_hand_until=None,
    ):
        location_side, from_zone, _index, card = self._find_location(instance_id)
        if not card:
            raise EngineError(f'버릴 카드를 찾을 수 없습니다: {instance_id}')
        owner = card.get('owner') if card.get('owner') in PLAYER_SIDES else location_side
        moved = self.move_card(
            instance_id, 'list', to_player=owner, reason='discard',
            effect_controller=effect_controller, effect_source=effect_source,
            block_hand_until=block_hand_until,
        )
        if moved is None:
            return None
        effect_source_card = self._find_card(effect_source) if effect_source else None
        event_card = self._effective_card_for_operation(
            moved, 'discard', {
                'controller': effect_controller,
                'source_card_instance_id': effect_source,
                'source_card': effect_source_card,
            },
        )
        self.emit('card_discarded', owner, {
            'card_instance_id': instance_id, 'from_zone': from_zone,
            'to_zone': 'break' if _is_special(card) else 'list',
        }, visibility='public' if moved.get('face_up') else 'private')
        self._fire('card_discarded', {
            'controller': owner, 'source_card_instance_id': instance_id,
            'source_card': copy.deepcopy(event_card), 'from_zone': from_zone,
            'effect_controller': effect_controller, 'effect_source': effect_source,
            'effect_source_card': copy.deepcopy(effect_source_card),
        })
        return moved

    def _offer_break_replenishment(self, owner):
        queue = self.engine_state.setdefault('break_replenishment_queue', [])
        queue.append(owner)
        if not self.engine_state.get('pending_decision'):
            queued_owner = queue.pop(0)
            self._start_break_replenishment(queued_owner)

    def _start_break_replenishment(self, owner):
        if len(self._zone(owner, 'list')) >= 14:
            return
        options = [
            {'id': card.get('instance_id'), 'label': card.get('name') or '사이드 카드'}
            for card in self._zone(owner, 'side') if (_is_attack(card) or _is_defense(card)) and not _is_special(card)
        ]
        if options and not self.engine_state.get('pending_decision'):
            self.create_decision(
                owner=owner, kind='break_replenish', prompt='사이드 덱에서 리스트로 보충할 카드를 선택할 수 있습니다.',
                options=[*options, {'id': 'decline', 'label': '보충하지 않음'}], minimum=1, maximum=1,
                default=['decline'], optional=True,
                continuation={'type': 'break_replenish'},
            )

    def draw_cards(self, side, count, *, from_zone='list'):
        for _ in range(max(0, _number(count))):
            cards = self._zone(side, from_zone)
            if not cards:
                break
            self.move_card(cards[0].get('instance_id'), 'hand', reason='draw')

    def set_card_visibility(
        self, instance_id, face_up, *, effect_controller=None, effect_source=None,
    ):
        owner, zone, _index, card = self._find_location(instance_id)
        if card:
            if self._card_ignores_effect(card, effect_controller, effect_source, zone=zone):
                self.emit('card_effect_ignored', owner, {
                    'card_instance_id': instance_id, 'operation': 'visibility',
                    'effect_controller': effect_controller, 'effect_source': effect_source,
                })
                return False
            was_face_up = bool(card.get('face_up'))
            card['face_up'] = bool(face_up)
            payload = {
                'card_instance_id': instance_id, 'face_up': bool(face_up),
                'was_face_up': was_face_up,
            }
            if face_up or was_face_up:
                payload.update({
                    'card_id': card.get('card_id'),
                    'card_code': card.get('code'),
                    'card_label': card.get('name') or card.get('code') or '카드',
                })
            if face_up:
                payload['card'] = {
                    key: copy.deepcopy(card.get(key))
                    for key in (
                        'instance_id', 'card_id', 'code', 'name', 'type', 'frame',
                        'damage', 'pos', 'body', 'special', 'hit', 'guard', 'counter',
                        'g_top', 'g_mid', 'g_bot', 'character_key', 'token_key',
                    )
                    if card.get(key) is not None
                }
            self.emit('card_visibility_changed', card.get('owner'), payload)
            return True
        return False

    def _schedule_state_expiration(
        self, side, key, expires, *, source_card=None,
    ):
        expires = copy.deepcopy(expires or {})
        event = str(expires.get('event') or 'phase_end')
        phase = str(expires.get('phase') or '')
        occurrences = max(1, _number(expires.get('occurrences'), 1))
        entries = [
            item for item in self.engine_state.setdefault(
                'state_expirations', [],
            )
            if not (
                item.get('player') == side and item.get('state') == key
            )
        ]
        entry = {
            'player': side, 'state': key, 'event': event,
            'phase': phase, 'remaining': occurrences,
            'source': (source_card or {}).get('instance_id'),
            'source_code': (source_card or {}).get('code'),
        }
        entries.append(entry)
        self.engine_state['state_expirations'] = entries
        self.emit('state_expiration_scheduled', side, copy.deepcopy(entry))

    def _clear_state_expiration(self, side, key):
        entries = self.engine_state.setdefault('state_expirations', [])
        self.engine_state['state_expirations'] = [
            item for item in entries
            if not (
                item.get('player') == side and item.get('state') == key
            )
        ]

    def _expire_state_durations(self, event, *, phase=None):
        retained = []
        expired = []
        for item in self.engine_state.setdefault('state_expirations', []):
            if (
                item.get('event') != event
                or (item.get('phase') and item.get('phase') != phase)
            ):
                retained.append(item)
                continue
            remaining = max(0, _number(item.get('remaining'), 1) - 1)
            self.emit('state_expiration_advanced', item.get('player'), {
                'state': item.get('state'), 'event': event,
                'phase': phase, 'remaining': remaining,
            })
            if remaining:
                retained.append({**item, 'remaining': remaining})
            else:
                expired.append(item)
        self.engine_state['state_expirations'] = retained
        for item in expired:
            side = item.get('player')
            key = str(item.get('state') or '')
            entry = (
                (self.state.get('players') or {}).get(side, {})
                .get('passive_state', {}).get(key, {})
            )
            if entry.get('value'):
                self.set_passive(side, key, value=False)
                self.emit('state_expired', side, {
                    'state': key, 'event': event, 'phase': phase,
                })

    def set_passive(
        self, side, key, *, value, label=None, visibility='public',
        source_card=None, expires=None,
    ):
        states = self.state['players'][side].setdefault('passive_state', {})
        before = copy.deepcopy(states.get(key))
        origin = {}
        if value and isinstance(source_card, dict):
            source_is_trait = str(source_card.get('type') or '') == '특성'
            previous_origin = (before or {}).get('trait_origin')
            # A state independently granted by any non-trait Technique remains
            # available while traits are negated (Q&A 220). Multiple trait
            # grants must not overwrite that independent origin.
            trait_origin = (
                source_is_trait
                if previous_origin is None
                else bool(previous_origin) and source_is_trait
            )
            origin = {
                'trait_origin': trait_origin,
                'state_source_code': source_card.get('code'),
            }
        if bool((before or {}).get('value')) == bool(value):
            if before is not None and ('value' not in before or origin):
                states[key] = {
                    **before,
                    'value': bool(value), 'label': label or before.get('label') or key,
                    'visibility': visibility, 'owner': side,
                    **origin,
                }
            if value and expires:
                self._schedule_state_expiration(
                    side, key, expires, source_card=source_card,
                )
            elif not value:
                self._clear_state_expiration(side, key)
            return True
        if not value and self._rule_blocked(
            'state_loss', side, {'state': key, 'owner': side},
        ):
            self.emit('state_loss_prevented', side, {
                'state': key, 'before': before,
            }, visibility=visibility)
            return False
        if value and self._rule_blocked(
            'state_gain', side, {'state': key, 'owner': side}, source_card,
        ):
            self.emit('state_gain_prevented', side, {
                'state': key, 'before': before,
                'source_card_instance_id': (source_card or {}).get('instance_id'),
                'source_card_code': (source_card or {}).get('code'),
            }, visibility=visibility)
            return False
        states[key] = {
            **(before or {}),
            'value': bool(value), 'label': label or key,
            'visibility': visibility, 'owner': side,
            **origin,
        }
        if value and expires:
            self._schedule_state_expiration(
                side, key, expires, source_card=source_card,
            )
        elif not value:
            self._clear_state_expiration(side, key)
        event_type = 'state_gained' if value else 'state_lost'
        self.emit(
            event_type, side, {'state': key, 'before': before, 'value': bool(value)},
            visibility=visibility,
        )
        self._fire(event_type, {'controller': side, 'player': side, 'state': key})
        return True

    def change_counter(
        self, side, key, value, *, absolute=False, label=None,
        visibility='public', minimum=0, maximum=None,
    ):
        states = self.state['players'][side].setdefault('passive_state', {})
        current = states.get(key) or {}
        current_count = _number(current.get('count'))
        count = _number(value) if absolute else current_count + _number(value)
        if count > current_count:
            requested_gain = count - current_count
            allowed_gain = requested_gain
            matching_limits = [
                item for item in self.engine_state.get('counter_gain_limits') or []
                if item.get('player') == side and item.get('counter') == key
            ]
            for item in matching_limits:
                allowed_gain = min(allowed_gain, max(0, _number(item.get('remaining'))))
            if self._rule_blocked(
                'counter_gain', side, {'counter': key, 'owner': side},
            ):
                allowed_gain = 0
            count = current_count + allowed_gain
            for item in matching_limits:
                item['remaining'] = max(0, _number(item.get('remaining')) - allowed_gain)
            if allowed_gain < requested_gain:
                self.emit('counter_gain_limited', side, {
                    'counter': key, 'requested': requested_gain, 'applied': allowed_gain,
                })
        if minimum is not None:
            count = max(_number(minimum), count)
        if maximum is not None:
            count = min(_number(maximum), count)
        states[key] = {
            **current,
            'count': count, 'label': label or current.get('label') or key,
            'visibility': visibility, 'owner': side,
        }
        applied_amount = count - current_count
        counter_context = {
            'controller': side, 'player': side, 'counter': key,
            'before': current_count, 'count': count, 'amount': applied_amount,
        }
        self.emit(
            'counter_changed', side,
            {
                'counter': key, 'before': current_count, 'count': count,
                'amount': applied_amount,
            },
            visibility=visibility,
        )
        self._fire('counter_changed', counter_context)

    def gain_shield(self, side, amount, *, duration='turn', source=None):
        if side not in PLAYER_SIDES:
            raise EngineError('보호막 대상 플레이어가 올바르지 않습니다.')
        amount = max(0, _number(amount))
        if not amount:
            return None
        shield = {
            'id': self._next_id('shield'),
            'amount': amount,
            'duration': duration or 'turn',
            'source': source,
        }
        self.engine_state.setdefault('shields', {}).setdefault(side, []).append(shield)
        self.emit('shield_gained', side, copy.deepcopy(shield))
        return shield

    def _consume_shields(self, side, amount, *, source=None):
        remaining_damage = max(0, _number(amount))
        absorbed = 0
        shields = self.engine_state.setdefault('shields', {}).setdefault(side, [])
        active = []
        for shield in shields:
            shield = copy.deepcopy(shield)
            available = max(0, _number(shield.get('amount')))
            used = min(available, remaining_damage)
            if used:
                available -= used
                remaining_damage -= used
                absorbed += used
                self.emit('shield_absorbed', side, {
                    'shield_id': shield.get('id'), 'amount': used,
                    'remaining': available, 'source': source,
                })
            if available:
                shield['amount'] = available
                active.append(shield)
        self.engine_state['shields'][side] = active
        return absorbed

    def add_modifier(self, modifier):
        value = copy.deepcopy(modifier or {})
        value.setdefault('id', self._next_id('modifier'))
        value.setdefault('duration', 'event')
        if self._speed_modifier_conflicts_with_earlier(value):
            return None
        self.engine_state.setdefault('modifiers', []).append(value)
        self.emit('modifier_added', value.get('controller'), {'modifier': value})
        if value.get('op') == 'fix_speed':
            player = value.get('player') or value.get('controller')
            where = value.get('where') or {}
            instance_id = where.get('instance_id')
            if not instance_id and player in PLAYER_SIDES:
                instance_id = (
                    (self.engine_state.get('ready_cards') or {}).get(player)
                    or ((self.engine_state.get('battle') or {}).get(player) or {}).get('instance_id')
                )
            fixed_card = self._find_card(instance_id) if instance_id else None
            if player in PLAYER_SIDES and fixed_card:
                self.emit('speed_fixed', player, {
                    'card_instance_id': instance_id, 'speed': value.get('value'),
                    'source': value.get('source'),
                })
                fixed_context = {
                    'controller': player,
                    'source_card_instance_id': instance_id,
                    'source_card': copy.deepcopy(fixed_card),
                    'fixed_speed': value.get('value'),
                    'modifier_source': value.get('source'),
                }
                # A speed-lock reaction happens after the effect which
                # installed the lock has finished, not between two commands
                # of that effect (Wingstar Q&A 680/681).  Direct core calls
                # outside an ability still dispatch immediately.
                if _number(self.engine_state.get('effect_resolution_depth')):
                    self.engine_state.setdefault(
                        'deferred_speed_fixed_events', [],
                    ).append(fixed_context)
                else:
                    self._fire('speed_fixed', fixed_context)
        return value.get('id')

    def _flush_deferred_speed_fixed_events(self):
        if self.engine_state.get('flushing_speed_fixed_events'):
            return
        self.engine_state['flushing_speed_fixed_events'] = True
        try:
            queue = self.engine_state.setdefault(
                'deferred_speed_fixed_events', [],
            )
            while queue:
                self._fire('speed_fixed', queue.pop(0))
        finally:
            self.engine_state.pop('flushing_speed_fixed_events', None)
            if not self.engine_state.get('deferred_speed_fixed_events'):
                self.engine_state.pop('deferred_speed_fixed_events', None)

    def _speed_modifier_conflicts_with_earlier(self, modifier):
        """Keep the first of a genuine same-window Speed change/fix conflict.

        Additive Speed changes can compose with each other. A Speed fix and a
        Speed change cannot: the rulebook conflict rule retains whichever
        mandatory effect was applied first (Q&A 500). Restrict this check to
        one concrete battle card and one trigger window so ordinary modifiers
        from different timings continue to work normally.

        A card-specific fix may explicitly preserve the card's *already
        modified* current Speed. Such a fix is compatible with the earlier
        change rather than replacing it, and must be installed so FP and
        still-later changes are ignored (Platinum Impact, Q&A 657). Other
        simultaneous change/fix pairs remain conflicts (Q&A 500).
        """
        if modifier.get('stat') != 'frame' or not modifier.get('timing_window'):
            return False
        where = modifier.get('where') or {}
        instance_id = where.get('instance_id')
        if not instance_id or modifier.get('override_fixed'):
            return False
        new_fixed = bool(
            modifier.get('op') == 'fix_speed' or modifier.get('fixed')
        )
        for existing in self.engine_state.get('modifiers') or []:
            existing_where = existing.get('where') or {}
            if (
                existing.get('stat') != 'frame'
                or existing.get('timing_window') != modifier.get('timing_window')
                or existing.get('player') != modifier.get('player')
                or existing_where.get('instance_id') != instance_id
                or existing.get('override_fixed')
            ):
                continue
            existing_fixed = bool(
                existing.get('op') == 'fix_speed' or existing.get('fixed')
            )
            if existing_fixed == new_fixed:
                continue
            if (
                new_fixed and not existing_fixed
                and modifier.get('preserve_prior_speed_changes') is True
            ):
                target_player = (
                    modifier.get('player') or modifier.get('controller')
                )
                target_card = self._find_card(instance_id)
                if target_player in PLAYER_SIDES and target_card:
                    current_speed = self.card_stat(
                        target_card, 'frame', target_player,
                        include_fp=False,
                    )
                    fixed_speed = max(1, _number(
                        modifier.get('value', modifier.get('amount')), 1,
                    ))
                    if current_speed == fixed_speed:
                        continue
            self.emit('modifier_conflict_ignored', modifier.get('controller'), {
                'modifier': copy.deepcopy(modifier),
                'kept_modifier_id': existing.get('id'),
                'kept_source': existing.get('source'),
                'reason': 'existing_effect_precedes',
            })
            return True
        return False

    def modify_judgment(
        self, side, field, value, *, source=None, mode='replace',
        effect_controller=None, duration='battle',
    ):
        if side not in PLAYER_SIDES or field not in {
            'hit', 'counter', 'guard', 'pos', 'special',
            'g_top', 'g_mid', 'g_bot',
        }:
            raise EngineError('판정 변경 대상이 올바르지 않습니다.')
        pipeline = self.engine_state.get('pipeline') or {}
        pipeline_target = bool(
            pipeline.get('kind') in {'combo_resolution', 'catch_resolution'}
            and pipeline.get('owner') == side
            and pipeline.get('card_instance_id') == source
        )
        if pipeline_target:
            instance_id = pipeline.get('card_instance_id')
            card = self._find_card(instance_id, owner=side, zone='battle')
            if not isinstance(card, dict):
                card = pipeline.get('card')
        else:
            entry = (self.engine_state.get('battle') or {}).get(side) or {}
            instance_id = entry.get('instance_id')
            card = entry.get('card')
        if not isinstance(card, dict):
            raise EngineError('판정을 변경할 배틀 카드가 없습니다.')
        if self._card_ignores_effect(card, effect_controller, source, zone='battle'):
            self.emit('card_effect_ignored', card.get('owner'), {
                'card_instance_id': instance_id,
                'operation': 'modify_judgment', 'field': field,
                'effect_controller': effect_controller, 'effect_source': source,
            })
            return False
        before = card.get(field)
        if mode == 'append' and before:
            values = [item.strip() for item in str(before).replace('•', '·').split('·') if item.strip()]
            if value not in values:
                values.append(value)
            value = ' · '.join(values)
        if before == value:
            return True
        card[field] = value
        if (
            pipeline.get('kind') in {'combo_resolution', 'catch_resolution'}
            and pipeline.get('card_instance_id') == instance_id
            and isinstance(pipeline.get('card'), dict)
        ):
            pipeline['card'][field] = value
        self._track_temporary_judgment(
            instance_id, field, before, value, duration,
        )
        self.emit('judgment_modified', side, {
            'card_instance_id': instance_id, 'field': field,
            'before': before, 'after': value, 'source': source, 'mode': mode,
        })
        return True

    def _track_temporary_judgment(
        self, instance_id, field, before, after, duration,
    ):
        if not instance_id or duration in {None, 'continuous'}:
            return
        records = self.engine_state.setdefault('temporary_judgments', [])
        previous = [
            item for item in records
            if item.get('card_instance_id') == instance_id
            and item.get('field') == field
        ]
        baseline = previous[0].get('baseline') if previous else before
        records.append({
            'card_instance_id': instance_id,
            'field': field,
            'baseline': copy.deepcopy(baseline),
            'before': copy.deepcopy(before),
            'after': copy.deepcopy(after),
            'duration': duration,
        })

    def _expire_temporary_judgments(self, duration):
        records = list(self.engine_state.get('temporary_judgments') or [])
        expiring = [item for item in records if item.get('duration') == duration]
        if not expiring:
            return
        retained = [item for item in records if item.get('duration') != duration]
        self.engine_state['temporary_judgments'] = retained
        keys = {
            (item.get('card_instance_id'), item.get('field'))
            for item in expiring
        }
        for instance_id, field in keys:
            history = [
                item for item in records
                if item.get('card_instance_id') == instance_id
                and item.get('field') == field
            ]
            remaining = [
                item for item in retained
                if item.get('card_instance_id') == instance_id
                and item.get('field') == field
            ]
            if not history:
                continue
            expected = history[-1].get('after')
            restored = (
                remaining[-1].get('after')
                if remaining else history[0].get('baseline')
            )
            targets = []
            live = self._find_card(instance_id)
            if isinstance(live, dict):
                targets.append(live)
            for side in PLAYER_SIDES:
                entry = (self.engine_state.get('battle') or {}).get(side) or {}
                if (
                    entry.get('instance_id') == instance_id
                    and isinstance(entry.get('card'), dict)
                ):
                    targets.append(entry['card'])
            pipeline = self.engine_state.get('pipeline') or {}
            if (
                pipeline.get('card_instance_id') == instance_id
                and isinstance(pipeline.get('card'), dict)
            ):
                targets.append(pipeline['card'])
            seen = set()
            changed = False
            for card in targets:
                marker = id(card)
                if marker in seen:
                    continue
                seen.add(marker)
                if card.get(field) != expected:
                    continue
                card[field] = copy.deepcopy(restored)
                changed = True
            if changed:
                self.emit('judgment_restored', 'system', {
                    'card_instance_id': instance_id,
                    'field': field,
                    'value': copy.deepcopy(restored),
                    'duration': duration,
                })

    def modify_defense_judgments(
        self, side, value, *, source=None, effect_controller=None,
    ):
        """Replace every printed, non-empty positional defense judgment.

        An empty positional field is not a judgment and therefore cannot be
        created by an effect that changes existing defense judgments (Q&A
        341/380).  Route each change through ``modify_judgment`` so immunity,
        battle snapshots, and audit events remain consistent.
        """
        if side not in PLAYER_SIDES or not str(value or '').strip():
            raise EngineError('수비 판정 일괄 변경 대상이 올바르지 않습니다.')
        entry = (self.engine_state.get('battle') or {}).get(side) or {}
        card = entry.get('card')
        if not isinstance(card, dict) or not _is_defense(card):
            raise EngineError('수비 판정을 변경할 수비 기술이 없습니다.')
        changed = []
        for field in ('g_top', 'g_mid', 'g_bot'):
            if not str(card.get(field) or '').strip():
                continue
            if self.modify_judgment(
                side, field, str(value), source=source,
                effect_controller=effect_controller,
            ):
                changed.append(field)
        self.emit('defense_judgments_modified', side, {
            'card_instance_id': entry.get('instance_id'),
            'fields': changed, 'value': str(value), 'source': source,
        })
        return changed

    def copy_defense_judgments(self, side, from_instance_id, *, source=None):
        selected = self._find_card(from_instance_id)
        entry = (self.engine_state.get('battle') or {}).get(side) or {}
        battle_card = entry.get('card')
        if side not in PLAYER_SIDES or not selected or not isinstance(battle_card, dict):
            raise EngineError('수비 판정을 복사할 카드를 찾을 수 없습니다.')
        self.emit('card_inspected', side, {
            'card_instance_id': selected.get('instance_id'),
            'card': {
                key: copy.deepcopy(selected.get(key))
                for key in ('code', 'name', 'type', 'frame', 'g_top', 'g_mid', 'g_bot')
            },
            'source': source,
        })
        if not _is_defense(selected):
            return False
        copied = {}
        for field in ('g_top', 'g_mid', 'g_bot'):
            if selected.get(field):
                battle_card[field] = copy.deepcopy(selected[field])
                copied[field] = copy.deepcopy(selected[field])
        self.emit('defense_judgments_copied', side, {
            'card_instance_id': entry.get('instance_id'),
            'from_card_instance_id': selected.get('instance_id'),
            'judgments': copied, 'source': source,
        })
        return True

    def copy_clash_judgments(
        self, side, from_instance_ids, *, source=None, effect_controller=None,
    ):
        """Append only current positional Clash judgments from selected cards.

        This intentionally copies no source-card restrictions such as a speed
        limit.  A judgment that another ability would grant at a later timing
        is likewise absent until that later ability actually resolves.
        """
        entry = (self.engine_state.get('battle') or {}).get(side) or {}
        battle_card = entry.get('card')
        if side not in PLAYER_SIDES or not isinstance(battle_card, dict):
            raise EngineError('상쇄 판정을 복사할 배틀 카드가 없습니다.')
        positions = []
        inspected_ids = []
        for instance_id in list(dict.fromkeys(
            str(value) for value in (from_instance_ids or []) if value
        )):
            selected = self._find_card(instance_id)
            if not selected:
                continue
            inspected_ids.append(instance_id)
            for position in ('상단', '중단', '하단'):
                if (
                    _special_result(selected, position) == 'clash'
                    or _guard_result(selected, position) == 'clash'
                ) and position not in positions:
                    positions.append(position)
        for position in positions:
            self.modify_judgment(
                side, 'special', f'{position} 상쇄', source=source,
                mode='append', effect_controller=effect_controller,
            )
        self.emit('clash_judgments_copied', side, {
            'card_instance_id': entry.get('instance_id'),
            'from_card_instance_ids': inspected_ids,
            'positions': positions, 'source': source,
        })
        return positions

    def force_ready_card(self, side, instance_id, *, source=None):
        card = self._find_card(instance_id, owner=side, zone='hand')
        if side not in PLAYER_SIDES or not card or not self._legal_ready_card(card):
            raise EngineError('강제 레디할 수 있는 패의 기술이 아닙니다.')
        self.engine_state.setdefault('forced_ready_cards', {})[side] = instance_id
        self.engine_state.setdefault('forced_ready_card_sources', {})[side] = source
        self.engine_state['forced_ready_first'] = side
        self.engine_state['forced_ready_first_source'] = source
        self.emit('ready_card_forced', side, {
            'card_instance_id': instance_id, 'source': source,
        })
        return True

    def force_ready_first(self, side, *, source=None):
        existing = self.engine_state.get('forced_ready_first')
        if side in PLAYER_SIDES and existing in PLAYER_SIDES:
            # Conflicting effects at the same timing retain the first-applied
            # instruction. When both players resolve Third Eye, the priority
            # player's effect therefore makes the non-priority player Ready
            # first (Q&A 602).
            if existing != side:
                self.emit('ready_first_force_ignored', side, {
                    'source': source,
                    'kept_player': existing,
                    'kept_source': self.engine_state.get(
                        'forced_ready_first_source'
                    ),
                    'reason': 'existing_effect_precedes',
                })
            return existing == side
        if side not in PLAYER_SIDES:
            raise EngineError('먻저 레디할 플레이어 지정이 올바르지 않습니다.')
        self.engine_state['forced_ready_first'] = side
        self.engine_state['forced_ready_first_source'] = source
        self.emit('ready_first_forced', side, {'source': source})
        return True

    def force_designated_get(
        self, beneficiary, chooser, *, source=None, duration='turn',
    ):
        if (
            beneficiary not in PLAYER_SIDES or chooser not in PLAYER_SIDES
            or beneficiary == chooser
        ):
            raise EngineError('강제 Get 플레이어 지정이 올바르지 않습니다.')
        if duration != 'turn':
            raise EngineError('강제 Get 만료 범위가 올바르지 않습니다.')
        self.engine_state.setdefault('forced_get_designators', {})[beneficiary] = chooser
        self.engine_state.setdefault('forced_get_turns', {})[beneficiary] = int(
            self.state.get('turn') or 1
        )
        self.emit('forced_get_scheduled', chooser, {
            'beneficiary': beneficiary, 'source': source,
            'duration': duration,
        })

    def invalidate_battle_card(
        self, instance_id, *, effect_controller=None, effect_source=None,
        return_zone='hand',
    ):
        owner, zone, _index, card = self._find_location(instance_id)
        if (
            not card or owner not in PLAYER_SIDES or zone != 'battle'
            or not (_is_attack(card) or _is_defense(card))
        ):
            raise EngineError('무효화할 상대 배틀 존의 기술을 찾을 수 없습니다.')
        if effect_controller in PLAYER_SIDES and owner == effect_controller:
            raise EngineError('자신의 배틀 기술은 이 효과로 무효화할 수 없습니다.')
        if self._card_ignores_effect(
            card, effect_controller, effect_source, zone=zone,
            operation='invalidate_battle_card',
        ):
            self.emit('card_effect_ignored', owner, {
                'card_instance_id': instance_id,
                'operation': 'invalidate_battle_card',
                'effect_controller': effect_controller,
                'effect_source': effect_source,
            })
            return False

        battle_entry = (self.engine_state.get('battle') or {}).get(owner) or {}
        is_ready_card = battle_entry.get('instance_id') == instance_id
        if is_ready_card and isinstance(battle_entry.get('card'), dict):
            battle_entry['card']['technique_invalidated'] = True
            battle_entry['card']['effects_negated'] = True
        self.emit('battle_card_invalidated', effect_controller or 'system', {
            'card_instance_id': instance_id,
            'owner': owner,
            'was_ready_card': is_ready_card,
            'source': effect_source,
        })
        self.move_card(
            instance_id, return_zone, to_player=owner,
            reason='battle_card_invalidated',
            effect_controller=effect_controller,
            effect_source=effect_source,
        )
        return True

    def _refresh_continuous_rules(self):
        self._refresh_continuous_state_grants()
        previous_judgments = self.engine_state.pop('continuous_judgments', {})
        battle = self.engine_state.get('battle') or {}
        for side, fields in previous_judgments.items():
            entry = battle.get(side) or {}
            card = entry.get('card')
            if not isinstance(card, dict):
                continue
            for field, values in fields.items():
                if card.get(field) == values.get('applied'):
                    card[field] = values.get('baseline')
        previous_pipeline_judgments = self.engine_state.pop(
            'continuous_pipeline_judgments', {},
        )
        pipeline = self.engine_state.get('pipeline') or {}
        pipeline_card = pipeline.get('card')
        if isinstance(pipeline_card, dict):
            fields = previous_pipeline_judgments.get(
                pipeline_card.get('instance_id'), {},
            )
            for field, values in fields.items():
                if pipeline_card.get(field) == values.get('applied'):
                    pipeline_card[field] = values.get('baseline')
        self.engine_state['modifiers'] = [
            item for item in self.engine_state.get('modifiers') or [] if item.get('duration') != 'continuous'
        ]
        self.engine_state['replacements'] = [
            item for item in self.engine_state.get('replacements') or [] if item.get('duration') != 'continuous'
        ]
        for item in self.resolver.continuous_effects({'phase': self.state.get('phase')}):
            for effect in item['ability'].get('effects') or []:
                op = effect.get('op')
                if op in {'modify_stat', 'fix_speed', 'modify_combo', 'modify_state_rule'}:
                    player = effect.get('player')
                    if isinstance(player, dict):
                        player = opponent(item['controller']) if 'opponent' in player else item['controller']
                    resolved_effect = copy.deepcopy(effect)
                    context = item.get('context') or {}
                    if 'amount' in resolved_effect:
                        resolved_effect['amount'] = resolve_value(resolved_effect['amount'], self.state, context)
                    if 'value' in resolved_effect:
                        resolved_effect['value'] = resolve_value(resolved_effect['value'], self.state, context)
                    if (
                        op in {'modify_stat', 'fix_speed'}
                        and not resolved_effect.get('where')
                        and resolved_effect.get('scope', 'source_card') == 'source_card'
                    ):
                        resolved_effect['where'] = {
                            'instance_id': item.get('card_instance_id'),
                        }
                    self.engine_state['modifiers'].append({
                        **resolved_effect, 'controller': item['controller'],
                        'player': player or item['controller'],
                        'source': item.get('card_instance_id'),
                        'source_code': item.get('card_code'), 'duration': 'continuous',
                    })
                elif op in {
                    'prevent', 'negate', 'replace', 'modify_damage',
                    'grant_effect_immunity',
                }:
                    player = effect.get('player')
                    if isinstance(player, dict):
                        player = opponent(item['controller']) if 'opponent' in player else item['controller']
                    resolved_effect = copy.deepcopy(effect)
                    if (
                        op in {'prevent', 'negate', 'replace'}
                        and resolved_effect.get('scope') is None
                    ):
                        # A Technique's numberless prohibition normally means
                        # "this Technique".  It may be projected while the
                        # card is still in Hand/List, but it must not prohibit
                        # the same judgment against an unrelated Technique.
                        # Persistent public-zone cards are global unless their
                        # DSL explicitly selects a narrower scope.
                        resolved_effect['scope'] = (
                            'all'
                            if item.get('zone') in {
                                'character', 'passive', 'lumen', 'ultimate',
                            }
                            else 'source_card'
                        )
                    if op == 'modify_damage':
                        resolved_effect['amount'] = resolve_value(
                            effect.get('amount', 0), self.state, item.get('context') or {},
                        )
                    self.engine_state['replacements'].append({
                        **resolved_effect, 'controller': item['controller'],
                        'player': player or item['controller'],
                        'source': item.get('card_instance_id'),
                        'source_code': item.get('card_code'),
                        'duration': 'continuous',
                    })
                elif op == 'modify_judgment':
                    raw_player = effect.get('player')
                    player = raw_player
                    if isinstance(player, dict):
                        player = opponent(item['controller']) if 'opponent' in player else item['controller']
                    target = player or item['controller']
                    source_id = item.get('card_instance_id')
                    if effect.get('scope') == 'all_zones':
                        self.engine_state['replacements'].append({
                            **copy.deepcopy(effect),
                            'controller': item['controller'],
                            'player': target,
                            'source': item.get('card_instance_id'),
                            'source_code': item.get('card_code'),
                            'duration': 'continuous',
                        })
                    target_entry = (
                        (self.engine_state.get('battle') or {}).get(target) or {}
                    )
                    target_card = target_entry.get('card')
                    source_scoped = bool(
                        effect.get('scope', 'source_card') == 'source_card'
                        and target == item['controller']
                        and (
                            raw_player is None
                            or raw_player == {'controller': True}
                            or raw_player == item['controller']
                        )
                    )
                    current_pipeline = self.engine_state.get('pipeline') or {}
                    current_pipeline_card = current_pipeline.get('card')
                    pipeline_is_source = bool(
                        isinstance(current_pipeline_card, dict)
                        and current_pipeline.get('card_instance_id') == source_id
                        and current_pipeline_card.get('instance_id') == source_id
                    )
                    battle_is_source = bool(
                        isinstance(target_card, dict)
                        and target_entry.get('instance_id') == source_id
                    )
                    if source_scoped and pipeline_is_source and not battle_is_source:
                        field = str(effect.get('field') or '')
                        before = current_pipeline_card.get(field)
                        value = str(effect.get('value') or '')
                        mode = effect.get('mode') or 'replace'
                        if mode == 'append' and before:
                            values = [
                                entry.strip() for entry in str(before).replace(
                                    '•', '·',
                                ).split('·') if entry.strip()
                            ]
                            if value not in values:
                                values.append(value)
                            value = ' · '.join(values)
                        if before != value:
                            current_pipeline_card[field] = value
                            self.emit('judgment_modified', target, {
                                'card_instance_id': source_id,
                                'field': field, 'before': before,
                                'after': value, 'source': source_id,
                                'mode': mode,
                            })
                        tracked = self.engine_state.setdefault(
                            'continuous_pipeline_judgments', {},
                        ).setdefault(source_id, {})
                        baseline = (tracked.get(field) or {}).get(
                            'baseline', before,
                        )
                        tracked[field] = {
                            'baseline': baseline,
                            'applied': current_pipeline_card.get(field),
                        }
                        continue
                    if source_scoped and not battle_is_source:
                        continue
                    if target_card:
                        before = target_card.get(str(effect.get('field') or ''))
                        self.modify_judgment(
                            target, str(effect.get('field') or ''), str(effect.get('value') or ''),
                            source=item.get('card_instance_id'), mode=effect.get('mode') or 'replace',
                            effect_controller=item['controller'],
                            duration=None,
                        )
                        field = str(effect.get('field') or '')
                        tracked = self.engine_state.setdefault(
                            'continuous_judgments', {},
                        ).setdefault(target, {})
                        baseline = (tracked.get(field) or {}).get('baseline', before)
                        tracked[field] = {
                            'baseline': baseline,
                            'applied': target_card.get(str(effect.get('field') or '')),
                        }

    def card_stat(self, card, stat, controller, *, include_fp=False):
        base = _number((card or {}).get(stat), 0)
        fixed = self._fixed_stat(card, stat, controller)
        delta = 0
        for modifier in self.engine_state.get('modifiers') or []:
            if modifier.get('stat') != stat:
                continue
            target = modifier.get('player') or modifier.get('controller')
            if target and target != controller:
                continue
            if self._card_ignores_effect(
                card, modifier.get('controller'), modifier.get('source'),
                effect_source_code=modifier.get('source_code'),
                operation='modify_stat', stat=stat, amount=modifier.get('amount'),
            ):
                continue
            where = modifier.get('where')
            if where and not card_matches(card, where):
                continue
            if modifier.get('op') != 'fix_speed' and not modifier.get('fixed') and fixed is None:
                delta += _number(modifier.get('amount'))
        result = fixed if fixed is not None else base + delta
        if stat == 'frame':
            result = max(1, result)
            if include_fp and fixed is None:
                result = max(1, result - _number(self.state['players'][controller].get('fp')))
        return result

    def _fixed_stat(self, card, stat, controller):
        modifiers = sorted(
            self.engine_state.get('modifiers') or [],
            # A deliberately selected override (for example a card's
            # ``any_speed`` Combo value) wins first. Numberless continuous
            # fixed-Speed functions were already in force before later
            # timing effects and therefore keep precedence over an ordinary
            # later fix (Q&A 691), even after continuous rules are rebuilt.
            key=lambda item: (
                0 if item.get('override_fixed') else
                1 if item.get('duration') == 'continuous' else
                2
            ),
        )
        for modifier in modifiers:
            if modifier.get('stat') != stat:
                continue
            target = modifier.get('player') or modifier.get('controller')
            if target and target != controller:
                continue
            if self._card_ignores_effect(
                card, modifier.get('controller'), modifier.get('source'),
                effect_source_code=modifier.get('source_code'),
                operation='modify_stat', stat=stat,
                amount=modifier.get('value', modifier.get('amount')),
            ):
                continue
            where = modifier.get('where')
            if where and not card_matches(card, where):
                continue
            if modifier.get('op') == 'fix_speed' or modifier.get('fixed'):
                value = _number(
                    modifier.get('value', modifier.get('amount')),
                    1 if stat == 'frame' else 0,
                )
                return max(1, value) if stat == 'frame' else value
        return None

    def select_cards(self, selector, context=None):
        options = self.selector_options(selector, context)
        selector = selector or {}
        minimum = _number(
            resolve_value(
                selector.get('min', 1), self.state, context or {},
            ),
            1,
        )
        if len(options) < max(0, minimum):
            return []
        if selector.get('all') is True:
            return [option['id'] for option in options]
        maximum = selector.get('max')
        if maximum is None:
            return [option['id'] for option in options]
        return [option['id'] for option in options[:max(0, _number(maximum))]]

    def selector_has_minimum(self, selector, context=None):
        if not selector:
            return True
        minimum = _number(resolve_value(selector.get('min', 1), self.state, context or {}), 1)
        return len(self.selector_options(selector, context)) >= minimum

    def selector_options(self, selector, context=None):
        selector = selector or {}
        context = context or {}
        kind = selector.get('kind', 'card')
        if kind == 'player':
            sides = selector.get('players') or list(PLAYER_SIDES)
            return [{'id': side, 'label': side} for side in sides if side in PLAYER_SIDES]
        controller = context.get('controller')
        raw_player = selector.get('player', controller)
        if isinstance(raw_player, dict) and 'opponent' in raw_player:
            raw_player = opponent(controller)
        elif isinstance(raw_player, dict):
            raw_player = controller
        sides = list(PLAYER_SIDES) if raw_player in {'any', None} else [raw_player]
        zones = selector.get('zones') or [selector.get('zone', 'hand')]
        history_ids = None
        if selector.get('history') == 'combo_used':
            history_ids = set((self.engine_state.get('combo') or {}).get('used') or [])
        elif selector.get('history') == 'combo_predecessors':
            combo = self.engine_state.get('combo') or {}
            history_ids = set([
                *([combo.get('source')] if combo.get('source') else []),
                *(combo.get('used') or []),
            ])
        elif selector.get('history') == 'combo_previous':
            combo = self.engine_state.get('combo') or {}
            used = list(combo.get('used') or [])
            previous = used[-2] if len(used) >= 2 else combo.get('source')
            history_ids = {previous} if previous else set()
        source_id = context.get('source_card_instance_id')
        combo_proposed_ids = set(
            context.get('combo_proposed_card_ids')
            or (self.engine_state.get('combo') or {}).get(
                'proposed_card_ids'
            )
            or []
        )
        selected_filter = None
        if selector.get('selection_key'):
            selected_filter = set(context.get(selector.get('selection_key')) or [])
        attached_target = None
        if selector.get('attached_to_source'):
            attached_target = source_id
        elif selector.get('attached_to_event'):
            attached_target = context.get('event_card_instance_id')
        options = []
        for side in sides:
            if side not in PLAYER_SIDES:
                continue
            for zone in zones:
                for card in self._zone(side, zone):
                    if (
                        selected_filter is not None
                        and card.get('instance_id') not in selected_filter
                    ):
                        continue
                    if attached_target is not None:
                        if card.get('attached_to') != attached_target:
                            continue
                    elif card.get('attached_to'):
                        continue
                    if history_ids is not None and card.get('instance_id') not in history_ids:
                        continue
                    if selector.get('exclude_source') and card.get('instance_id') == source_id:
                        continue
                    if (
                        selector.get('exclude_combo_proposed')
                        and card.get('instance_id') in combo_proposed_ids
                    ):
                        continue
                    effective_card = self._effective_card_for_operation(
                        card, selector.get('as_operation'), context,
                    )
                    if (
                        selector.get('as_operation') == 'break_card'
                        and not selector.get('include_operation_blocked')
                    ):
                        owner = card.get('owner') if card.get('owner') in PLAYER_SIDES else side
                        if (
                            is_passive_card(card)
                            or self._card_ignores_effect(
                                card, controller, source_id, zone=zone,
                            )
                            or self._card_ignores_effect(
                                card, controller, source_id, zone=zone,
                                operation='move_card', to_zone='break',
                            )
                            or self._rule_blocked(
                                'break', owner, card, zone=zone,
                                effect_controller=controller,
                            )
                            or self._break_rule_prevents(
                                card, zone, owner, effect_controller=controller,
                            )
                        ):
                            continue
                    if (
                        selector.get('as_operation') == 'move_card'
                        and not selector.get('include_operation_blocked')
                    ):
                        destination = selector.get('to_zone')
                        owner = (
                            card.get('owner')
                            if card.get('owner') in PLAYER_SIDES else side
                        )
                        blocked_until = card.get('move_to_hand_blocked_until')
                        blocked_through = card.get(
                            'move_to_hand_blocked_through_turn'
                        )
                        hand_move_blocked = (
                            destination == 'hand'
                            and (
                                blocked_until == 'turn'
                                or (
                                    blocked_until == 'battle'
                                    and self.state.get('phase') == 'battle'
                                )
                                or (
                                    blocked_through is not None
                                    and _number(self.state.get('turn'), 1)
                                    <= _number(blocked_through)
                                )
                            )
                        )
                        if (
                            (is_passive_card(card) and destination != 'passive')
                            or (
                                _is_special(card)
                                and not selector.get(
                                    'allow_special_destination', False,
                                )
                                and destination not in {
                                    'side', 'lumen', 'ultimate', 'break',
                                }
                            )
                            or hand_move_blocked
                            or self._card_ignores_effect(
                                card, controller, source_id, zone=zone,
                                operation='move_card', to_zone=destination,
                            )
                            or not self._zone_limit_allows(
                                card, owner, destination,
                            )
                        ):
                            continue
                    if (
                        selector.get('as_operation') == 'discard'
                        and not selector.get('include_operation_blocked')
                    ):
                        owner = (
                            card.get('owner')
                            if card.get('owner') in PLAYER_SIDES else side
                        )
                        discard_destination = (
                            'break' if _is_special(card) else 'list'
                        )
                        if (
                            is_passive_card(card)
                            or self._card_ignores_effect(
                                card, controller, source_id, zone=zone,
                                operation='move_card',
                                to_zone=discard_destination,
                            )
                            or not self._zone_limit_allows(
                                card, owner, discard_destination,
                            )
                        ):
                            continue
                    if card_matches(effective_card, selector.get('where'), self.state, context):
                        hidden_opponent_hand = (
                            side != controller and zone == 'hand' and not card.get('face_up')
                        )
                        options.append({
                            'id': card.get('instance_id'),
                            'label': '뒷면 카드' if hidden_opponent_hand else card.get('name') or '카드',
                            'owner': side, 'zone': zone,
                        })
        return sorted(options, key=lambda item: (str(item.get('owner')), str(item.get('zone')), str(item.get('id'))))

    def _effective_card_for_operation(self, card, operation, context=None):
        effective = copy.deepcopy(card or {})
        if not effective:
            return effective
        owner, zone, _index, _live = self._find_location(
            effective.get('instance_id'),
        )
        owner = (
            effective.get('owner')
            if effective.get('owner') in PLAYER_SIDES else owner
        )
        for override in self.engine_state.get('replacements') or []:
            if (
                override.get('op') != 'modify_judgment'
                or override.get('scope') != 'all_zones'
                or override.get('player') not in {None, owner}
                or (
                    override.get('target_zones')
                    and zone not in override.get('target_zones')
                )
                or (
                    override.get('where')
                    and not card_matches(
                        effective, override.get('where'), self.state,
                        context or {},
                    )
                )
            ):
                continue
            field = str(override.get('field') or '')
            if field not in {'hit', 'counter', 'guard', 'pos', 'special'}:
                continue
            value = str(override.get('value') or '')
            mode = override.get('mode') or 'replace'
            if mode == 'clear':
                effective[field] = ''
            elif mode == 'append' and effective.get(field):
                values = [
                    item.strip()
                    for item in str(effective.get(field)).replace(
                        '•', '·',
                    ).split('·')
                    if item.strip()
                ]
                if value not in values:
                    values.append(value)
                effective[field] = ' · '.join(values)
            else:
                effective[field] = value
        if operation != 'discard':
            return effective
        definition = self._definition_for_card(effective)
        alias = definition.get('discard_state_alias') or {}
        source_card = (context or {}).get('source_card') or self._find_card(
            (context or {}).get('source_card_instance_id'),
        )
        if (
            not alias
            or not source_card
            or source_card.get('character_key') != alias.get('source_character')
        ):
            return effective
        markers = ''.join(
            f' [[state:{state_key}]]' for state_key in alias.get('states') or []
        )
        effective['text'] = f'{effective.get("text") or ""}{markers}'
        effective['discard_state_alias_applied'] = True
        return effective

    def attach_card(
        self, instance_id, host_instance_id, *, controller=None,
        attachment_expires=None, return_to_hand_on_expiry=False, face_up=True,
    ):
        card = self._find_card(instance_id)
        host = self._find_card(host_instance_id)
        if not card or not host or instance_id == host_instance_id:
            raise EngineError('세트할 카드 또는 대상 기술을 찾을 수 없습니다.')
        card['attached_to'] = host_instance_id
        card['set_order'] = max(
            [
                _number(candidate.get('set_order'))
                for side in PLAYER_SIDES
                for cards in self.state['players'][side]['zones'].values()
                for candidate in cards
                if candidate.get('attached_to') == host_instance_id
                and candidate.get('instance_id') != instance_id
            ] or [0]
        ) + 1
        card.pop('staged_attachment_key', None)
        if attachment_expires:
            card['attachment_expires'] = attachment_expires
        if return_to_hand_on_expiry:
            card['return_to_hand_on_attachment_expiry'] = True
        card['face_up'] = bool(face_up)
        actor = controller if controller in PLAYER_SIDES else card.get('owner')
        self.emit('card_attached', actor, {
            'card_instance_id': instance_id,
            'card_id': card.get('card_id'),
            'card_code': card.get('code'),
            'card_label': card.get('name') or card.get('code') or '카드',
            'host_instance_id': host_instance_id,
            'host_card_id': host.get('card_id'),
            'host_card_code': host.get('code'),
            'host_card_label': host.get('name') or host.get('code') or '카드',
        })
        self._fire('card_attached', {
            'controller': actor,
            'source_card_instance_id': instance_id,
            'source_card': copy.deepcopy(card),
            'host_card_instance_id': host_instance_id,
            'host_card': copy.deepcopy(host),
        })
        return card

    def random_choice(self, options, count, *, visibility='public', actor='system'):
        options = copy.deepcopy(options or [])
        count = max(0, min(_number(count), len(options)))
        counter = _number(self.engine_state.get('random_counter'))
        self.engine_state['random_counter'] = counter + 1
        rng = random.Random(f'{self.seed}:{counter}')
        selected = rng.sample(options, count)
        self.emit(
            'random_resolved', actor,
            {'counter': counter, 'selected': [item.get('id') for item in selected]},
            visibility=visibility,
        )
        return selected

    def shuffle_zone(self, side, zone, *, face_up=None):
        if side not in PLAYER_SIDES or zone not in ALL_ZONES:
            raise EngineError('섞을 존이 올바르지 않습니다.')
        cards = self._zone(side, zone)
        shuffled = self.random_choice(
            [{'id': card.get('instance_id')} for card in cards], len(cards),
            visibility='private', actor='system',
        )
        by_id = {card.get('instance_id'): card for card in cards}
        cards[:] = [by_id[item['id']] for item in shuffled]
        if face_up is not None:
            for card in cards:
                card['face_up'] = bool(face_up)
        self.emit('zone_shuffled', side, {
            'zone': zone, 'count': len(cards), 'face_up': face_up,
        })
        return cards

    def create_token(self, side, definition):
        token = {
            'instance_id': f'token-{self._next_id("token")}', 'kind': 'token', 'owner': side,
            'name': definition.get('name') or '토큰', 'code': definition.get('code') or '',
            'type': definition.get('type') or '토큰', 'face_up': bool(definition.get('face_up', True)),
            **copy.deepcopy(definition.get('card') or {}),
        }
        released_definition = (
            ((self.ruleset.get('cards') or {}).get(token['code']) or {})
            .get('effect_definition') or {}
        )
        if released_definition.get('token_key'):
            token['token_key'] = released_definition['token_key']
        if released_definition.get('token_usage'):
            token['token_usage'] = copy.deepcopy(
                released_definition['token_usage']
            )
        zone = definition.get('zone') or 'passive'
        self._apply_card_form(token, zone, definition=released_definition)
        self._zone(side, zone).append(token)
        self.emit('token_created', side, {'card_instance_id': token['instance_id'], 'zone': zone})
        return token

    def delete_token(self, instance_id):
        owner, zone, index, card = self._find_location(instance_id)
        if card and (card.get('kind') == 'token' or card.get('token_key')):
            self.state['players'][owner]['zones'][zone].pop(index)
            self.emit('token_deleted', owner, {'card_instance_id': instance_id, 'zone': zone})
            return card
        return None

    # ------------------------------------------------------------------
    # Helpers and projections

    def _zone(self, side, zone):
        return self.state['players'][side]['zones'][zone]

    def _printed_card_snapshot(self, card):
        """Overlay immutable released characteristics without mutating live state."""
        if not isinstance(card, dict):
            return {}
        snapshot = copy.deepcopy(card)
        released_card = (
            (self.ruleset.get('cards') or {}).get(str(card.get('code') or '')) or {}
        )
        for field_name in (
            'type', 'text', 'frame', 'damage', 'pos', 'body', 'special',
            'hit', 'guard', 'counter', 'g_top', 'g_mid', 'g_bot',
        ):
            if field_name in released_card:
                snapshot[field_name] = copy.deepcopy(released_card[field_name])
        if is_passive_card(card):
            snapshot['type'] = PASSIVE_CARD_TYPE
        return snapshot

    def _definition_for_card(self, card):
        if (
            not isinstance(card, dict) or card.get('effects_negated')
            or card.get('non_technique_while_face_down')
        ):
            return {}
        pipeline = self.engine_state.get('pipeline') or {}
        if (
            pipeline.get('kind') == 'catch_resolution'
            and pipeline.get('card_instance_id') == card.get('instance_id')
        ):
            replacement = self._catch_effect_replacement_definition(
                (pipeline.get('grant') or {}).get('effect_replacement')
            )
            if replacement is not None:
                return replacement
        definition = (
            ((self.ruleset.get('cards') or {}).get(str(card.get('code') or '')) or {})
            .get('effect_definition') or {}
        )
        if card.get('instance_id'):
            _side, zone, _index, _live = self._find_location(card.get('instance_id'))
            if zone == 'passive' and self._traits_negated():
                return {}
        return definition

    def _traits_negated(self):
        cards = self.ruleset.get('cards') or {}
        for side in PLAYER_SIDES:
            for zone, live_cards in ((self.state.get('players') or {}).get(side, {}).get('zones') or {}).items():
                for live_card in live_cards:
                    definition = (
                        (cards.get(str(live_card.get('code') or '')) or {})
                        .get('effect_definition') or {}
                    )
                    rule = definition.get('trait_negation') or {}
                    if rule.get('players') == 'both' and zone in (rule.get('active_zones') or []):
                        return True
        return False

    def _refresh_continuous_state_grants(self):
        grants = {side: {} for side in PLAYER_SIDES}
        cards = self.ruleset.get('cards') or {}
        traits_negated = self._traits_negated()
        for controller in PLAYER_SIDES:
            zones = (
                ((self.state.get('players') or {}).get(controller) or {}).get('zones') or {}
            )
            for zone, live_cards in zones.items():
                if zone == 'passive' and traits_negated:
                    continue
                for live_card in live_cards:
                    definition = (
                        (cards.get(str(live_card.get('code') or '')) or {})
                        .get('effect_definition') or {}
                    )
                    for rule in definition.get('state_grants') or []:
                        if zone not in (rule.get('active_zones') or []):
                            continue
                        if (
                            rule.get('numbered_effect')
                            and live_card.get('numbered_effects_negated')
                        ):
                            continue
                        context = {
                            'controller': controller,
                            'opponent': opponent(controller),
                            'controller_hp': self.state['players'][controller].get('hp'),
                            'controller_fp': self.state['players'][controller].get('fp'),
                            'opponent_hp': self.state['players'][opponent(controller)].get('hp'),
                            'opponent_fp': self.state['players'][opponent(controller)].get('fp'),
                            'source_card': copy.deepcopy(live_card),
                            'source_card_instance_id': live_card.get('instance_id'),
                            'source_zone': zone,
                        }
                        if not condition_matches(
                            rule.get('condition'), self.state, context,
                        ):
                            continue
                        player = rule.get('player', 'controller')
                        targets = (
                            PLAYER_SIDES if player == 'both'
                            else (opponent(controller),) if player == 'opponent'
                            else (controller,)
                        )
                        for target in targets:
                            for state_key in rule.get('states') or []:
                                grants[target].setdefault(str(state_key), []).append(
                                    live_card.get('instance_id') or live_card.get('code')
                                )
        self.engine_state['continuous_states'] = grants

    def _cancel_trait_origin_effects(self):
        """End temporary Trait effects when a mutual Trait negator appears.

        Cleanup commands such as hiding a hand card must run immediately;
        simply dropping their delayed entry would leave the temporary public
        information in place.  Activation history and usage counters are kept
        so effects that care whether the Trait was used still see that fact
        (Q&A 564).
        """
        trait_instance_ids = {
            str(card.get('instance_id'))
            for side in PLAYER_SIDES
            for card in self._zone(side, 'passive')
            if card.get('instance_id')
        }

        def from_trait(context):
            context = context or {}
            source = context.get('source_card') or {}
            return bool(
                str(context.get('source_card_instance_id') or '')
                in trait_instance_ids
                or str(source.get('type') or '') == '특성'
            )

        retained = []
        cancelled = []
        for item in list(self.engine_state.get('scheduled') or []):
            if not from_trait(item.get('context')):
                retained.append(item)
                continue
            cancelled.append(item)
        self.engine_state['scheduled'] = retained
        for item in cancelled:
            effect = item.get('effect') or {}
            # A delayed hide is the inverse/cleanup half of a temporary reveal,
            # so perform it at the point where the originating Trait ends.
            if effect.get('op') == 'hide':
                self.resolver.execute_effect(
                    effect, copy.deepcopy(item.get('context') or {}),
                )

        first_source = self.engine_state.get('forced_ready_first_source')
        if str(first_source or '') in trait_instance_ids:
            self.engine_state.pop('forced_ready_first', None)
            self.engine_state.pop('forced_ready_first_source', None)
        forced_sources = self.engine_state.get('forced_ready_card_sources') or {}
        forced_cards = self.engine_state.get('forced_ready_cards') or {}
        for side, source in list(forced_sources.items()):
            if str(source or '') in trait_instance_ids:
                forced_sources.pop(side, None)
                forced_cards.pop(side, None)
        if cancelled or first_source or forced_sources:
            self.emit('trait_temporary_effects_ended', 'system', {
                'scheduled_count': len(cancelled),
            })

    def _reconcile_trait_states(self):
        traits_negated = self._traits_negated()
        was_negated = bool(self.engine_state.get('traits_negated_active'))
        self.engine_state['traits_negated_active'] = traits_negated
        if traits_negated and not was_negated:
            self._cancel_trait_origin_effects()
        if not traits_negated:
            return
        cards = self.ruleset.get('cards') or {}
        for side in PLAYER_SIDES:
            state_keys = []
            preserved_state_keys = []
            for card in self._zone(side, 'passive'):
                definition = (
                    (cards.get(str(card.get('code') or '')) or {})
                    .get('effect_definition') or {}
                )
                state_keys.extend(definition.get('trait_state_keys') or [])
                preserved_state_keys.extend(
                    definition.get('trait_state_preserve_on_negation') or []
                )
            preserved_state_keys = set(preserved_state_keys)
            for state_key in dict.fromkeys(state_keys):
                entry = self.state['players'][side].setdefault('passive_state', {}).get(state_key) or {}
                origin = entry.get('trait_origin')
                if origin is False:
                    continue
                if origin is None and state_key in preserved_state_keys:
                    continue
                if entry.get('value'):
                    self.set_passive(side, state_key, value=False)

    def _apply_card_form(self, card, zone, *, definition=None):
        """Apply printed characteristics when a card enters their active zone.

        The characteristics intentionally remain on the live card after it is
        played from that zone so battle/combo resolution sees the Technique
        that was legally used.
        """
        if not isinstance(card, dict):
            return
        definition = definition if isinstance(definition, dict) else self._definition_for_card(card)
        form = definition.get('card_form') or {}
        if not isinstance(form, dict) or zone not in (form.get('active_zones') or []):
            return
        for key in ('type', 'frame', 'damage', 'pos', 'special', 'character_key', 'token_key'):
            if key in form:
                card[key] = copy.deepcopy(form[key])

    def _apply_owner_deck_rules(self, card):
        if not isinstance(card, dict) or card.get('kind') == 'character':
            return
        owner = card.get('owner')
        if owner not in PLAYER_SIDES:
            return
        player_character_id = (
            ((self.state.get('players') or {}).get(owner) or {}).get('character') or {}
        ).get('id')
        character_rules = (
            ((self.ruleset.get('characters') or {}).get(str(player_character_id)) or {})
            .get('deck_rules') or {}
        )
        imported = character_rules.get('other_character_cards') or {}
        released = (
            (self.ruleset.get('cards') or {}).get(str(card.get('code') or '')) or {}
        )
        original_character_id = card.get(
            'original_character_id', released.get('character_id', card.get('character_id')),
        )
        if original_character_id in {None, player_character_id}:
            return
        if original_character_id in set(imported.get('exclude_character_ids') or []):
            return
        if card.get('type', released.get('type')) not in set(imported.get('allowed_types') or []):
            return
        if imported.get('exclude_ultimate') and bool(card.get('ultimate', released.get('ultimate'))):
            return
        card['original_character_id'] = original_character_id
        if imported.get('treat_as_own_character'):
            card['character_id'] = player_character_id
            owner_character = (
                (self.ruleset.get('characters') or {}).get(str(player_character_id)) or {}
            )
            if owner_character.get('key'):
                card['character_key'] = owner_character['key']
        if imported.get('negate_effects'):
            card['effects_negated'] = True
        if imported.get('break_after_use'):
            card['break_after_use'] = True

    @staticmethod
    def _public_action_card(card):
        return {
            key: card.get(key)
            for key in (
                'instance_id', 'card_id', 'code', 'name', 'type', 'frame',
                'damage', 'pos', 'special', 'img', 'img_sm',
            )
        }

    @staticmethod
    def _private_action_card(card):
        return AutomaticGameEngine._public_action_card(card)

    def _legal_ready_card(self, card, *, ignore_cost=False):
        if is_passive_card(card) or _is_special(card) or not (_is_attack(card) or _is_defense(card)):
            return False
        owner = card.get('owner')
        if not self._card_use_allowed(card, owner, 'ready', ignore_cost=ignore_cost):
            return False
        return not self._rule_blocked('ready', owner, card)

    def _play_cost_context(self, card, owner, use_context):
        return {
            'controller': owner, 'opponent': opponent(owner),
            'source_card': card, 'source_card_instance_id': card.get('instance_id'),
            'use_context': use_context,
        }

    def _applicable_play_costs(self, card, use_context):
        definition = self._definition_for_card(card)
        _owner, source_zone, _index, _live_card = self._find_location(
            card.get('instance_id'),
        )
        return [
            cost for cost in definition.get('play_costs') or []
            if not (
                cost.get('numbered_effect')
                and card.get('numbered_effects_negated')
            )
            and (
                not cost.get('use_contexts')
                or use_context in (cost.get('use_contexts') or [])
            )
            and (
                not cost.get('source_zones')
                or source_zone in (cost.get('source_zones') or [])
            )
        ]

    @staticmethod
    def _play_cost_selector(cost):
        cost = cost or {}
        selector = {
            **copy.deepcopy(cost.get('selector') or {}),
            'as_operation': cost.get('operation'),
        }
        if cost.get('operation') == 'move_card':
            selector['to_zone'] = cost.get('to_zone')
        return selector

    def _pay_play_cost_item(self, instance_id, cost, owner, context):
        operation = (cost or {}).get('operation')
        source_id = (context or {}).get('source_card_instance_id')
        if operation == 'discard':
            return self.discard_card(
                instance_id, effect_controller=owner,
                effect_source=source_id,
            ) is not None
        if operation == 'delete_token':
            existed = self._find_card(instance_id) is not None
            self.delete_token(instance_id)
            return existed and self._find_card(instance_id) is None
        if operation == 'move_card':
            return self.move_card(
                instance_id, cost.get('to_zone'), reason='play_cost',
                effect_controller=owner, effect_source=source_id,
                allow_special_destination=bool(
                    (cost.get('selector') or {}).get(
                        'allow_special_destination', False,
                    )
                ),
            ) is not None
        return False

    def _play_costs_affordable(self, card, owner, use_context):
        context = self._play_cost_context(card, owner, use_context)
        for cost in self._applicable_play_costs(card, use_context):
            selector = self._play_cost_selector(cost)
            minimum = _number(selector.get('min'), 1)
            if len(self.selector_options(selector, context)) < minimum:
                return False
        return True

    def _begin_play_cost(self, owner, card, use_context, play):
        costs = [
            cost for cost in self._applicable_play_costs(card, use_context)
            if cost.get('payment_timing', 'before_play') == 'before_play'
        ]
        if not costs:
            return False
        cost = costs[0]
        selector = self._play_cost_selector(cost)
        context = self._play_cost_context(card, owner, use_context)
        options = self.selector_options(selector, context)
        minimum = _number(selector.get('min'), 1)
        maximum = _number(selector.get('max'), minimum)
        if len(options) < minimum:
            raise IllegalAction('카드 사용 비용을 지불할 수 없습니다.')
        self.create_decision(
            owner=owner, kind='play_cost', prompt='카드 사용 비용을 지불할 대상을 선택하세요.',
            options=options, minimum=minimum, maximum=maximum, default=[],
            continuation={
                'type': 'play_cost', 'cost': copy.deepcopy(cost),
                'play': copy.deepcopy(play),
                'context': copy.deepcopy(context),
            },
        )
        return True

    def _offer_next_battle_reveal_play_cost(self, pipeline):
        entries = pipeline.get('battle_reveal_play_cost_entries')
        if entries is None:
            entries = []
            battle = self.engine_state.get('battle') or {}
            for side in self._priority_order():
                card = (battle.get(side) or {}).get('card') or {}
                for cost in self._applicable_play_costs(card, 'ready'):
                    if cost.get('payment_timing') == 'battle_reveal':
                        entries.append({
                            'side': side, 'cost': copy.deepcopy(cost),
                        })
            pipeline['battle_reveal_play_cost_entries'] = entries
            pipeline['battle_reveal_play_cost_index'] = 0
        while _number(
            pipeline.get('battle_reveal_play_cost_index')
        ) < len(entries):
            index = _number(pipeline.get('battle_reveal_play_cost_index'))
            pipeline['battle_reveal_play_cost_index'] = index + 1
            entry = entries[index]
            side = entry.get('side')
            cost = entry.get('cost') or {}
            card = (
                (self.engine_state.get('battle') or {}).get(side) or {}
            ).get('card') or {}
            context = self._play_cost_context(card, side, 'ready')
            selector = self._play_cost_selector(cost)
            options = self.selector_options(selector, context)
            minimum = _number(resolve_value(
                selector.get('min', 1), self.state, context,
            ), 1)
            maximum = _number(resolve_value(
                selector.get('max', minimum), self.state, context,
            ), minimum)
            if len(options) < minimum:
                live_source = self._find_card(card.get('instance_id'))
                for source in (live_source, card):
                    if isinstance(source, dict):
                        source['technique_invalidated'] = True
                self.emit('play_cost_unavailable', side, {
                    'card_instance_id': card.get('instance_id'),
                    'operation': cost.get('operation'),
                    'minimum': minimum, 'candidate_count': len(options),
                    'payment_timing': 'battle_reveal',
                })
                continue
            self.create_decision(
                owner=side, kind='play_cost',
                prompt='공개된 기술의 사용 조건으로 버릴 카드를 선택하세요.',
                options=options, minimum=minimum, maximum=maximum,
                default=[],
                continuation={
                    'type': 'battle_reveal_play_cost',
                    'side': side, 'cost': copy.deepcopy(cost),
                    'context': copy.deepcopy(context),
                },
            )
            return True
        return False

    def _card_use_allowed(self, card, owner, use_context, *, ignore_cost=False):
        if is_passive_card(card):
            return False
        definition = self._definition_for_card(card)
        context = {
            'controller': owner, 'opponent': opponent(owner),
            'controller_hp': self.state['players'][owner].get('hp'),
            'controller_fp': self.state['players'][owner].get('fp'),
            'opponent_hp': self.state['players'][opponent(owner)].get('hp'),
            'opponent_fp': self.state['players'][opponent(owner)].get('fp'),
            'source_card': card, 'source_card_instance_id': card.get('instance_id'),
            'use_context': use_context,
        }
        if definition.get('play_condition') is not None and not condition_matches(definition['play_condition'], self.state, context):
            return False
        limit = definition.get('play_limit') or {}
        if limit:
            scope = str(limit.get('scope') or 'game')
            key = str(limit.get('key') or f'card:{card.get("code") or ""}')
            used = (
                self.engine_state.setdefault('usage', {})
                .setdefault(scope, {})
                .setdefault(owner, {})
                .get(key, 0)
            )
            if int(used or 0) >= int(limit.get('max', 1)):
                return False
        if not ignore_cost and not self._play_costs_affordable(card, owner, use_context):
            return False
        return not self._rule_blocked('use_card', owner, card)

    def _project_card_for_use(self, card, owner, use_context):
        """Project source-card continuous changes after entering Battle.

        Combo and Catch legality is calculated while the candidate still sits
        in Hand/List, but a Battle-only continuous effect applies immediately
        after that card is used.  Project only the candidate's own source-card
        stat/judgment changes here; global modifiers remain layered by
        ``card_stat`` in their normal order.
        """
        projected = copy.deepcopy(card or {})
        if (
            not projected or owner not in PLAYER_SIDES
            or use_context not in {'ready', 'combo', 'catch'}
        ):
            return projected
        _found_owner, current_zone, _index, _live = self._find_location(
            projected.get('instance_id'),
        )
        definition = self._definition_for_card(projected)
        context = {
            'controller': owner, 'opponent': opponent(owner),
            'controller_hp': self.state['players'][owner].get('hp'),
            'controller_fp': self.state['players'][owner].get('fp'),
            'opponent_hp': self.state['players'][opponent(owner)].get('hp'),
            'opponent_fp': self.state['players'][opponent(owner)].get('fp'),
            'source_card': projected,
            'source_card_instance_id': projected.get('instance_id'),
            'source_zone': 'battle', 'use_context': use_context,
            'opponent_card': copy.deepcopy(
                ((self.engine_state.get('battle') or {}).get(
                    opponent(owner),
                ) or {}).get('card')
            ),
        }
        for ability in definition.get('abilities') or []:
            active_zones = ability.get('active_zones')
            if (
                ability.get('mode') != 'continuous'
                or not active_zones
                or 'battle' not in active_zones
                or current_zone in active_zones
                or (
                    projected.get('numbered_effects_negated')
                    and ability.get('kind') == 'effect'
                )
                or not condition_matches(
                    ability.get('condition'), self.state, context,
                )
            ):
                continue
            for effect in ability.get('effects') or []:
                raw_player = effect.get('player', {'controller': True})
                target = resolve_value(raw_player, self.state, context)
                if (
                    target != owner
                    or effect.get('scope', 'source_card') != 'source_card'
                ):
                    continue
                op = effect.get('op')
                if op == 'modify_stat':
                    stat = str(effect.get('stat') or '')
                    if stat not in {'frame', 'damage'}:
                        continue
                    amount = _number(resolve_value(
                        effect.get('amount', 0), self.state, context,
                    ))
                    if self._card_ignores_effect(
                        projected, owner, projected.get('instance_id'),
                        zone=current_zone, operation='modify_stat',
                        stat=stat, amount=amount,
                    ):
                        continue
                    projected[stat] = _number(projected.get(stat)) + amount
                elif op == 'modify_judgment':
                    field = str(effect.get('field') or '')
                    if field not in {
                        'hit', 'counter', 'guard', 'pos', 'special',
                        'g_top', 'g_mid', 'g_bot',
                    }:
                        continue
                    if self._card_ignores_effect(
                        projected, owner, projected.get('instance_id'),
                        zone=current_zone, operation='modify_judgment',
                    ):
                        continue
                    value = str(effect.get('value') or '')
                    mode = effect.get('mode') or 'replace'
                    if mode == 'clear':
                        projected[field] = ''
                    elif mode == 'append' and projected.get(field):
                        values = [
                            item.strip() for item in str(
                                projected.get(field),
                            ).replace('•', '·').split('·') if item.strip()
                        ]
                        if value not in values:
                            values.append(value)
                        projected[field] = ' · '.join(values)
                    else:
                        projected[field] = value
        return projected

    def _card_ignores_effect(
        self, card, effect_controller=None, effect_source=None, *, zone=None,
        effect_source_code=None, operation=None, stat=None, amount=None,
        to_zone=None,
    ):
        """Return whether a card-level effect is blocked by printed immunity.

        Core game movement does not supply an effect controller and is never
        blocked here.  A card's own effects likewise remain applicable.
        """
        if not isinstance(card, dict) or effect_controller not in PLAYER_SIDES:
            return False
        instance_id = card.get('instance_id')
        if effect_source and effect_source == instance_id:
            return False
        owner = card.get('owner')
        definition = self._definition_for_card(card)
        printed = definition.get('effect_immunity') or {}
        immunities = []
        if isinstance(printed, dict) and not (
            printed.get('numbered_effect')
            and card.get('numbered_effects_negated')
        ):
            immunities.append(printed)
        immunities.extend(
            rule for rule in self.engine_state.get('replacements') or []
            if rule.get('op') == 'grant_effect_immunity'
            and (not rule.get('player') or rule.get('player') == owner)
            and (
                not rule.get('where')
                or card_matches(card, rule.get('where'), self.state, {})
            )
        )
        for immunity in immunities:
            active_zones = immunity.get('active_zones') or []
            if active_zones:
                if zone is None:
                    _side, zone, _index, _live = self._find_location(instance_id)
                if zone not in active_zones:
                    continue
            if immunity.get('operations') and operation not in immunity.get('operations'):
                continue
            if immunity.get('to_zones') and to_zone not in immunity.get('to_zones'):
                continue
            if immunity.get('stats') and stat not in immunity.get('stats'):
                continue
            directions = set(immunity.get('directions') or [])
            if directions:
                direction = 'decrease' if _number(amount) < 0 else 'increase'
                if direction not in directions:
                    continue
            scope = immunity.get('scope')
            if scope == 'opponent':
                if owner in PLAYER_SIDES and effect_controller != owner:
                    return True
                continue
            if scope == 'other_cards':
                if effect_source and effect_source != instance_id:
                    return True
                continue
            if scope == 'source_codes':
                source_code = effect_source_code
                if not source_code and effect_source:
                    source_card = self._find_card(effect_source)
                    source_code = (source_card or {}).get('code')
                if source_code in set(immunity.get('source_codes') or []):
                    return True
        return False

    def _mark_card_used(self, card, owner, use_context='ready'):
        self.engine_state.setdefault('card_use_history', []).append({
            'turn': _number(self.state.get('turn'), 1),
            'player': owner, 'use_context': use_context,
            'instance_id': card.get('instance_id'),
            'card': copy.deepcopy(card),
        })
        definition = self._definition_for_card(card)
        limit = definition.get('play_limit') or {}
        if not limit:
            return
        scope = str(limit.get('scope') or 'game')
        key = str(limit.get('key') or f'card:{card.get("code") or ""}')
        usage = self.engine_state.setdefault('usage', {}).setdefault(scope, {}).setdefault(owner, {})
        usage[key] = int(usage.get(key) or 0) + 1
        self.emit('card_usage_recorded', owner, {
            'card_instance_id': card.get('instance_id'), 'key': key,
            'scope': scope, 'count': usage[key],
        })

    def _rule_blocked(
        self, kind, side, card=None, against_card=None, *, zone=None,
        effect_controller=None, direct_controller=None,
    ):
        for replacement in self.engine_state.get('replacements') or []:
            if replacement.get('op') not in {'prevent', 'negate'}:
                continue
            if replacement.get('kind', replacement.get('target')) != kind:
                continue
            player = replacement.get('player')
            if player and player != side:
                continue
            if replacement.get('controller_only'):
                cause_controller = (
                    direct_controller
                    if direct_controller in PLAYER_SIDES else effect_controller
                )
                if cause_controller != replacement.get('controller'):
                    continue
            target_zones = replacement.get('target_zones')
            if target_zones is not None and zone not in target_zones:
                continue
            if replacement.get('scope') == 'source_card':
                source_id = replacement.get('source')
                scoped_card = (
                    card
                    if side == replacement.get('controller')
                    else against_card
                ) or {}
                if (
                    not source_id
                    or scoped_card.get('instance_id') != source_id
                ):
                    continue
            if replacement.get('where') and not card_matches(card, replacement.get('where')):
                continue
            if replacement.get('against_where') and not card_matches(against_card, replacement.get('against_where')):
                continue
            if self._card_ignores_effect(
                card, replacement.get('controller'), replacement.get('source'),
            ):
                continue
            context = {
                'controller': replacement.get('controller'),
                'opponent': opponent(replacement.get('controller')) if replacement.get('controller') in PLAYER_SIDES else None,
                'player': side,
                'source_card': card,
                'opponent_card': against_card,
                'rule_kind': kind,
            }
            if not condition_matches(replacement.get('condition'), self.state, context):
                continue
            return True
        return False

    def _priority_order(self):
        priority = self.state.get('priority_player')
        return [priority, opponent(priority)]

    def _recalculate_priority(self):
        scores = {
            side: (
                _number(self.state['players'][side].get('fp')),
                _number(self.state['players'][side].get('hp')),
                len(self._zone(side, 'hand')),
            )
            for side in PLAYER_SIDES
        }
        if scores['p1'] > scores['p2']:
            self.state['priority_player'] = 'p1'
        elif scores['p2'] > scores['p1']:
            self.state['priority_player'] = 'p2'
        self.emit('priority_calculated', 'system', {'scores': scores, 'priority_player': self.state['priority_player']})
        return self.state['priority_player']

    def _phase_skipped(self, phase):
        skip = self.engine_state.get('skip_phases') or {}
        skipped = False
        for side in PLAYER_SIDES:
            if (skip.get(side) or {}).pop(phase, False):
                skipped = True
        return skipped

    def _consume_phase_skip_players(self, phase):
        skip = self.engine_state.get('skip_phases') or {}
        skipped = []
        for side in PLAYER_SIDES:
            if (skip.get(side) or {}).pop(phase, False):
                skipped.append(side)
        return skipped

    def _enforce_list_limit(self, side):
        cards = self._zone(side, 'list')
        while len(cards) > 14:
            overflow = cards[-1]
            instance_id = overflow.get('instance_id')
            # Direct move avoids recursive limit checks.
            cards.pop()
            overflow['face_up'] = True
            self._zone(side, 'break').append(overflow)
            self.emit('card_broken', side, {
                'card_instance_id': instance_id,
                'card_id': overflow.get('card_id'),
                'card_code': overflow.get('code'),
                'card_label': overflow.get('name') or overflow.get('code') or '카드',
                'reason': 'list_limit',
            })
            self._fire('card_broken', {
                'controller': side, 'source_card_instance_id': instance_id,
                'source_card': copy.deepcopy(overflow), 'reason': 'list_limit',
            })
            # Q&A #232: a card broken because the list was already full does
            # not create the normal side-deck replenishment opportunity.

    def _current_hand_limit(self, side):
        if side not in PLAYER_SIDES:
            return None
        player = self.state['players'][side]
        character = player.get('character') or {}
        table = {}
        for threshold, limit in (character.get('hand_table') or {}).items():
            try:
                table[int(threshold)] = int(limit)
            except (TypeError, ValueError):
                continue
        if table:
            hp = _number(player.get('hp'))
            base = next(
                (
                    table[threshold] for threshold in sorted(table)
                    if hp <= threshold
                ),
                table[max(table)],
            )
            bonus = 0
            for card in self._zone(side, 'lumen'):
                if card.get('effects_negated'):
                    continue
                definition = self._definition_for_card(card)
                bonus += max(0, _number(
                    definition.get('hand_limit_bonus'),
                ))
            return max(0, base + bonus)
        fallback = character.get('hand_limit')
        if fallback is None:
            return None
        return max(0, _number(fallback))

    def _queue_hand_limit_adjustment(
        self, side, *, defer_during_battle=True,
    ):
        limit = self._current_hand_limit(side)
        if limit is None or len(self._zone(side, 'hand')) <= limit:
            return False
        if defer_during_battle and self.state.get('phase') == 'battle':
            deferred = self.engine_state.setdefault(
                'deferred_hand_adjustments', [],
            )
            if side not in deferred:
                deferred.append(side)
            return True
        queue = self.engine_state.setdefault('hand_adjustment_queue', [])
        if side not in queue:
            queue.append(side)
        return True

    def _start_hand_limit_adjustment(self, side):
        limit = self._current_hand_limit(side)
        if limit is None:
            return False
        hand = list(self._zone(side, 'hand'))
        excess = max(0, len(hand) - limit)
        if not excess:
            return False
        options = [
            {
                'id': card.get('instance_id'),
                'label': card.get('name') or '패의 카드',
                'owner': side, 'zone': 'hand',
            }
            for card in hand if card.get('instance_id')
        ]
        options.sort(key=lambda item: str(item.get('id')))
        self.create_decision(
            owner=side, kind='hand_limit_discard',
            prompt=(
                f'패 매수 상한 {limit}장을 맞추기 위해 '
                f'{excess}장을 버리세요.'
            ),
            options=options, minimum=excess, maximum=excess,
            default=[item['id'] for item in options[:excess]],
            continuation={'type': 'hand_limit_discard', 'player': side},
        )
        return True

    def _resolve_hand_limit_discard(self, side, selected):
        limit = self._current_hand_limit(side)
        if side not in PLAYER_SIDES or limit is None:
            raise IllegalAction('패 매수 상한을 확인할 수 없습니다.')
        excess = max(0, len(self._zone(side, 'hand')) - limit)
        selected = list(selected or [])
        if len(selected) != excess or any(
            not self._find_card(instance_id, owner=side, zone='hand')
            for instance_id in selected
        ):
            raise IllegalAction('패 매수 상한 조정 대상이 올바르지 않습니다.')
        for instance_id in selected:
            self.discard_card(instance_id)
        self.emit('hand_limit_adjusted', side, {
            'discarded_card_instance_ids': selected,
            'hand_limit': limit,
            'hand_count': len(self._zone(side, 'hand')),
        }, visibility='private')
        self._queue_hand_limit_adjustment(
            side, defer_during_battle=False,
        )

    def _expire_modifiers(self, duration):
        self._expire_temporary_judgments(duration)

        def expired(item):
            if duration == 'turn' and item.get('duration') == 'next_turn':
                return _number(self.state.get('turn'), 1) > _number(
                    item.get('expires_turn'), self.state.get('turn'),
                )
            return item.get('duration') == duration

        self.engine_state['modifiers'] = [
            item for item in self.engine_state.get('modifiers') or []
            if not expired(item)
        ]
        self.engine_state['replacements'] = [
            item for item in self.engine_state.get('replacements') or []
            if not expired(item)
        ]
        self.engine_state['counter_gain_limits'] = [
            item for item in self.engine_state.get('counter_gain_limits') or []
            if item.get('duration') != duration
        ]
        active_scheduled = []
        for item in self.engine_state.get('scheduled') or []:
            if item.get('duration') == duration:
                self.emit('scheduled_effect_expired', (item.get('context') or {}).get('controller'), {
                    'event': (item.get('when') or {}).get('event'), 'duration': duration,
                })
            else:
                active_scheduled.append(item)
        self.engine_state['scheduled'] = active_scheduled
        shields = self.engine_state.setdefault('shields', {})
        for side in PLAYER_SIDES:
            active = []
            for shield in shields.setdefault(side, []):
                if shield.get('duration') == duration:
                    self.emit('shield_expired', side, {
                        'shield_id': shield.get('id'), 'amount': _number(shield.get('amount')),
                        'duration': duration,
                    })
                else:
                    active.append(shield)
            shields[side] = active

    def _reset_usage(self, scope):
        self.engine_state.setdefault('usage', {}).pop(scope, None)
        self.engine_state.setdefault('effect_damage_counts', {}).pop(scope, None)

    def _replacement_value(self, kind, side, value):
        result = value
        remaining = []
        applied = False
        replacements = list(self.engine_state.get('replacements') or [])
        replacements.sort(key=lambda item: (
            0 if item.get('op') in {'prevent', 'negate'}
            else 1 if item.get('op') == 'replace'
            else 2
        ))
        for item in replacements:
            applies = item.get('kind', item.get('target')) in {kind, None}
            player = item.get('player')
            if player and player != side:
                applies = False
            if applies and item.get('op') == 'modify_damage':
                result = max(0, _number(result) + _number(item.get('amount')))
                uses_left = item.get('remaining_uses')
                if uses_left is not None:
                    uses_left = max(0, _number(uses_left) - 1)
                    item['remaining_uses'] = uses_left
                if (
                    item.get('duration') not in {'event', None}
                    and (uses_left is None or uses_left > 0)
                ):
                    remaining.append(item)
                continue
            if applies and not applied:
                if item.get('op') in {'prevent', 'negate'}:
                    result = 0
                elif item.get('op') == 'replace':
                    result = _number(item.get('amount'), result)
                applied = True
                uses_left = item.get('remaining_uses')
                if uses_left is not None:
                    uses_left = max(0, _number(uses_left) - 1)
                    item['remaining_uses'] = uses_left
                if (
                    item.get('duration') not in {'event', None}
                    and (uses_left is None or uses_left > 0)
                ):
                    remaining.append(item)
            elif applies:
                if item.get('duration') == 'continuous':
                    remaining.append(item)
            else:
                remaining.append(item)
        self.engine_state['replacements'] = remaining
        return result

    def _check_victory(self):
        if self.engine_state.get('status') != 'running' or self.engine_state.get('suspend_victory_check'):
            return
        dead = [side for side in PLAYER_SIDES if self.state['players'][side]['hp'] <= 0]
        if self.engine_state.get('sudden_death'):
            if len(dead) == 1:
                self._finish(opponent(dead[0]), 'hp_zero')
            elif len(dead) == 2:
                self._finish(None, 'sudden_death_simultaneous_zero_draw')
            return
        if len(dead) == 1:
            self._finish(opponent(dead[0]), 'hp_zero')
        elif len(dead) == 2:
            self._start_sudden_death()

    def _start_sudden_death(self):
        engine = self.engine_state
        self.state['turn'] = 1
        engine['sudden_death'] = True
        engine['sudden_death_turns_remaining'] = 3
        engine['pending_decision'] = None
        engine['clock'] = None
        engine['resolution_queue'] = []
        engine['resolution_order_groups'] = {}
        engine['deferred_effects'] = []
        for side in PLAYER_SIDES:
            player = self.state['players'][side]
            player['hp'] = 1000
            player['fp'] = 0
            player['passive_state'] = copy.deepcopy(
                (engine.get('initial_passive_states') or {}).get(side) or {}
            )
            pool = []
            for zone in ('hand', 'list', 'side', 'break', 'battle', 'lumen'):
                pool.extend(player['zones'][zone])
                player['zones'][zone] = []
            normal = [card for card in pool if not _is_special(card) and not card.get('ultimate') and not card.get('virtual')]
            specials = [card for card in pool if _is_special(card) and not card.get('ultimate')]
            ultimates = [card for card in pool if card.get('ultimate')]
            rng = random.Random(f'{self.seed}:sudden-death:{side}:{engine.get("random_counter", 0)}')
            rng.shuffle(normal)
            raw_hand_table = (player.get('character') or {}).get('hand_table') or {}
            hand_table = {}
            for threshold, limit in raw_hand_table.items():
                try:
                    hand_table[int(threshold)] = int(limit)
                except (TypeError, ValueError):
                    continue
            hand_limit = 5
            if hand_table:
                hand_limit = next(
                    (hand_table[threshold] for threshold in sorted(hand_table) if 1000 <= threshold),
                    hand_table[max(hand_table)],
                )
            for index, card in enumerate(normal):
                zone = 'hand' if index < hand_limit else 'list' if index < hand_limit + 9 else 'side'
                card['face_up'] = zone == 'list'
                player['zones'][zone].append(card)
            for card in specials:
                card['face_up'] = False
                player['zones']['side'].append(card)
            for card in ultimates:
                card['face_up'] = True
                player['zones']['ultimate'].append(card)
            self.emit('sudden_death_rebuilt', side, {
                'order': [card.get('instance_id') for card in normal],
                'hand_count': min(hand_limit, len(normal)),
                'list_count': min(9, max(0, len(normal) - hand_limit)),
            }, visibility='private')
        self.emit('sudden_death_started', 'system', {'turns': 3})
        self._fire('sudden_death_start', {})
        self.state['phase'] = 'lumen'
        engine['step'] = 'phase_actions'
        engine['phase_passes'] = []
        engine['pipeline'] = None
        engine['battle'] = {}
        engine['ready_cards'] = {}
        engine['modifiers'] = []
        engine['scheduled'] = []
        engine['usage'] = {}
        engine['skip_phases'] = {}
        engine['no_response'] = {side: 0 for side in PLAYER_SIDES}
        engine['defense_over_count'] = 0

    def _resolve_sudden_death(self):
        hp = {side: _number(self.state['players'][side].get('hp')) for side in PLAYER_SIDES}
        if hp['p1'] > hp['p2']:
            self._finish('p1', 'sudden_death')
        elif hp['p2'] > hp['p1']:
            self._finish('p2', 'sudden_death')
        else:
            self._finish(None, 'sudden_death_hp_tie_draw')

    def _finish(self, winner, reason):
        self.engine_state.update({
            'status': 'finished', 'winner': winner, 'reason': reason,
            'pending_decision': None, 'clock': None,
            'resolution_queue': [], 'resolution_order_groups': {},
            'deferred_effects': [],
        })
        self.emit('game_finished', 'system', {'winner': winner, 'reason': reason})

    def finish_game(self, winner, *, reason='card_effect'):
        """Finish a running game from a deterministic domain command."""
        if winner not in PLAYER_SIDES:
            raise EngineError('승리 플레이어가 올바르지 않습니다.')
        if self.engine_state.get('status') != 'running':
            return False
        self._finish(winner, str(reason or 'card_effect'))
        return True

    def observe(self, role, *, include_state=True):
        """Return the role-filtered automatic overlay for humans or AI."""
        # Project current continuous rules before copying state.  In particular,
        # Trait-granted states must be visible to the player/AI observation even
        # though their authoritative representation lives in ``engine_state``.
        self._refresh_continuous_rules()
        decision = self.engine_state.get('pending_decision')
        if decision and decision.get('owner') != role:
            decision_payload = {
                'owner': decision.get('owner'), 'prompt': '상대가 선택 중입니다.',
            }
        else:
            decision_payload = copy.deepcopy(decision)
            if decision_payload:
                decision_payload.pop('continuation', None)
        return {
            'state': self._observation_state(role) if include_state else None,
            'legal_actions': self.legal_actions(role),
            'pending_decision': decision_payload,
            'clocks': copy.deepcopy(self.engine_state.get('clock')),
            'timer_settings': {
                'ready_timeout_seconds': self._timeout_seconds(
                    'ready_timeout_seconds', DEFAULT_READY_SECONDS,
                ),
                'effect_timeout_seconds': self._timeout_seconds(
                    'effect_timeout_seconds', DEFAULT_EFFECT_CHOICE_SECONDS,
                ),
            },
            'engine_status': {
                'status': self.engine_state.get('status'), 'step': self.engine_state.get('step'),
                'winner': self.engine_state.get('winner'), 'reason': self.engine_state.get('reason'),
            },
            'ruleset_version': self.ruleset.get('version') or self.ruleset.get('content_hash'),
        }

    def _observation_state(self, role):
        state = copy.deepcopy(self.state)
        state.pop('random_seed', None)
        continuous_states = copy.deepcopy(
            self.engine_state.get('continuous_states') or {}
        )
        for side in PLAYER_SIDES:
            player = ((state.get('players') or {}).get(side) or {})
            passive_state = player.setdefault('passive_state', {})
            for key, sources in (continuous_states.get(side) or {}).items():
                if not sources:
                    continue
                existing = passive_state.get(key)
                existing = existing if isinstance(existing, dict) else {}
                passive_state[key] = {
                    **existing,
                    'value': True,
                    'label': existing.get('label') or key,
                    'visibility': 'public',
                    'owner': side,
                    'derived': True,
                    'sources': list(sources),
                }
        state['engine'] = {
            'status': self.engine_state.get('status'),
            'step': self.engine_state.get('step'),
            'winner': self.engine_state.get('winner'),
            'reason': self.engine_state.get('reason'),
        }
        hidden_board_keys = {}
        for player_side, player in (state.get('players') or {}).items():
            for zone, cards in (player.get('zones') or {}).items():
                for index, card in enumerate(cards):
                    if role == card.get('owner') or card.get('face_up'):
                        continue
                    instance_id = card.get('instance_id')
                    if instance_id:
                        hidden_board_keys[instance_id] = f'hidden-{player_side}-{zone}-{index}'
        for player in (state.get('players') or {}).values():
            passive_state = player.get('passive_state') or {}
            for key in list(passive_state):
                entry = passive_state.get(key) or {}
                if isinstance(entry, dict) and entry.get('visibility') == 'private' and entry.get('owner') != role:
                    passive_state.pop(key, None)
            for zone, cards in (player.get('zones') or {}).items():
                projected = []
                for card in cards:
                    if role == card.get('owner') or card.get('face_up'):
                        visible = copy.deepcopy(card)
                        visible['hidden'] = False
                        projected.append(visible)
                    else:
                        hidden = {
                            'kind': card.get('kind') or 'card',
                            'owner': card.get('owner'), 'zone': zone,
                            'name': '비공개 카드', 'face_up': False, 'hidden': True,
                            'board_key': hidden_board_keys.get(card.get('instance_id')),
                        }
                        attached_board_key = hidden_board_keys.get(card.get('attached_to'))
                        if attached_board_key:
                            hidden['attached_to_board_key'] = attached_board_key
                            hidden['set_order'] = card.get('set_order')
                        projected.append(hidden)
                player['zones'][zone] = projected
        return state
