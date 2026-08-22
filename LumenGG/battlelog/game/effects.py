"""Deterministic execution of validated effect definitions."""

import copy
import re

from .handlers import get_handler
from .spec import MAX_EVENT_DEPTH, MAX_RESOLUTION_STEPS, PLAYER_SIDES, TIMING_ORDER


EVENT_TIMING = {
    'battle_reveal': 'function',
    'dodge': 'dodge', 'opponent_dodge': 'opponent_dodge',
    'guard': 'guard', 'opponent_guard': 'opponent_guard',
    'hit': 'hit_counter', 'counter': 'hit_counter',
    'opponent_hit': 'opponent_hit_counter',
    'opponent_counter': 'opponent_hit_counter',
    'clash': 'clash', 'opponent_clash': 'opponent_clash',
    'combo': 'combo', 'combo_window': 'combo', 'catch': 'catch',
    'combo_end': 'cleanup', 'opponent_combo_end': 'cleanup',
    'battle_end': 'cleanup',
    'card_guess_resolved': 'result', 'grab_negated': 'result',
}

# These timings ordinarily belong to the Technique that is currently being
# used or judged. A different Technique sitting in Battle/List/Hand/Side or
# Break must not react merely because it has text with the same timing. Cards
# in persistent public zones may still define controller-wide reactions, and
# exceptional effects can opt in with ``allow_non_source_trigger``.
SOURCE_TECHNIQUE_EVENTS = {
    'use', 'before_judgment', 'dodge', 'opponent_dodge',
    'guard', 'opponent_guard', 'hit', 'counter',
    'opponent_hit', 'opponent_counter', 'clash', 'opponent_clash',
    'combo', 'combo_window', 'catch', 'after_judgment', 'after_use',
}
GLOBAL_REACTION_ZONES = {'passive', 'lumen', 'ultimate'}

# Compatibility for already-published immutable ruleset snapshots created
# before ``allow_non_source_trigger`` became part of DSL v1.  These are the
# catalog's deliberate Hand/List/Side reactions to another Technique's result
# timing. New definitions must use the explicit schema flag instead.
KNOWN_NON_SOURCE_TRIGGER_ABILITIES = {
    'cb02-at-035-n1', 'cb02-at-035-function',
    'rfs-at-038-n1',
    'lmi-at-041-side-placement',
    'crs-at-054-n1',
    'st3-010-opponent-combo',
}

# Compatibility for immutable releases created before ``requires_combo_use``
# was introduced.  Endless Ballare's Combo-end text belongs only to a Combo
# in which the card was actually played as a Combo Technique; merely remaining
# in Battle, or being the Ready Technique that opened Combo Time, is not enough.
KNOWN_COMBO_USE_REQUIRED_ABILITIES = {'dfr-at-020-n2'}


class EffectResolutionError(ValueError):
    pass


def _opponent(side):
    return 'p2' if side == 'p1' else 'p1'


def _is_technique(card):
    if (card or {}).get('non_technique_while_face_down'):
        return False
    card_type = str((card or {}).get('type') or '')
    return any(kind in card_type for kind in ('공격', '수비', '특수'))


def state_path(root, path, default=None):
    if path in (None, ''):
        return default
    current = root
    for raw_part in str(path).split('.'):
        part = raw_part.strip()
        if isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return default
            current = current[index]
        else:
            return default
    return current


def resolve_value(value, state, context):
    if not isinstance(value, dict):
        return value
    if set(value) == {'value'}:
        return value['value']
    if 'path' in value:
        path = str(value.get('path') or '')
        if path.startswith('context.'):
            return state_path(context, path[8:], value.get('default'))
        return state_path(state, path, value.get('default'))
    if 'controller' in value:
        return context.get('controller')
    if 'opponent' in value:
        return _opponent(context.get('controller'))
    op = value.get('op')
    if op in {'add', 'multiply', 'min', 'max'}:
        values = [resolve_value(item, state, context) for item in value.get('values') or []]
        numeric = [_numeric(item) for item in values]
        if op == 'add':
            return sum(numeric)
        if op == 'multiply':
            result = 1
            for item in numeric:
                result *= item
            return result
        if not numeric:
            return 0
        return min(numeric) if op == 'min' else max(numeric)
    if op in {'subtract', 'floor_divide', 'modulo'}:
        left = _numeric(resolve_value(value.get('left'), state, context))
        right = _numeric(resolve_value(value.get('right'), state, context))
        if op == 'subtract':
            return left - right
        if op == 'floor_divide':
            return left // right if right else resolve_value(value.get('default', 0), state, context)
        return left % right if right else resolve_value(value.get('default', 0), state, context)
    if op in {'negate', 'abs'}:
        resolved = _numeric(resolve_value(value.get('value'), state, context))
        return -resolved if op == 'negate' else abs(resolved)
    if op == 'clamp':
        resolved = _numeric(resolve_value(value.get('value'), state, context))
        lower = _numeric(resolve_value(value.get('min'), state, context), resolved)
        upper = _numeric(resolve_value(value.get('max'), state, context), resolved)
        return max(lower, min(upper, resolved))
    if op == 'if':
        branch = 'then' if condition_matches(value.get('condition'), state, context) else 'else'
        return resolve_value(value.get(branch, 0), state, context)
    if op == 'zone_count':
        side = resolve_value(value.get('player', {'controller': True}), state, context)
        cards = state_path(state, f'players.{side}.zones.{value.get("zone")}', []) or []
        return len([
            card for card in cards
            if card_matches(card, value.get('where'), state, context)
        ])
    if op == 'zone_distinct_count':
        side = resolve_value(value.get('player', {'controller': True}), state, context)
        cards = state_path(state, f'players.{side}.zones.{value.get("zone")}', []) or []
        field = str(value.get('field') or 'frame')
        excluded = set(value.get('exclude_values') or [])

        def distinct_value(card):
            if field == 'printed_character_id':
                return card.get('original_character_id') or card.get('character_id')
            return card.get(field)

        return len({
            distinct_value(card) for card in cards
            if distinct_value(card) is not None
            and distinct_value(card) not in excluded
            and card_matches(card, value.get('where'), state, context)
        })
    if op == 'counter_count':
        side = resolve_value(value.get('player', {'controller': True}), state, context)
        entry = state_path(
            state, f'players.{side}.passive_state.{value.get("counter")}', {},
        ) or {}
        return int(entry.get('count') or 0)
    if op == 'state_rule_value':
        side = resolve_value(value.get('player', {'controller': True}), state, context)
        state_key = str(value.get('state') or '')
        field = str(value.get('field') or '')
        resolved = resolve_value(value.get('default', 0), state, context)
        for modifier in state_path(state, 'engine.modifiers', []) or []:
            if modifier.get('op') != 'modify_state_rule':
                continue
            target = modifier.get('player') or modifier.get('controller')
            if target and target != side:
                continue
            if modifier.get('state') != state_key or modifier.get('field') != field:
                continue
            candidate = resolve_value(modifier.get('value'), state, context)
            if modifier.get('mode') == 'minimum':
                resolved = max(_numeric(resolved), _numeric(candidate))
            elif modifier.get('mode') == 'maximum':
                resolved = min(_numeric(resolved), _numeric(candidate))
            else:
                resolved = candidate
        return resolved
    if op == 'memory_value':
        side = resolve_value(
            value.get('player', {'controller': True}), state, context,
        )
        key = str(value.get('key') or '')
        return state_path(
            state, f'engine.effect_memory.{side}.{key}',
            value.get('default'),
        )
    if op == 'selection_count':
        selected = set(
            context.get(str(value.get('selection_key') or 'selected')) or []
        )
        where = value.get('where')
        if not where:
            return len(selected)
        zones = state_path(state, 'players', {}) or {}
        return sum(
            1
            for player in zones.values()
            for cards in (player.get('zones') or {}).values()
            for card in cards
            if card.get('instance_id') in selected
            and card_matches(card, where, state, context)
        )
    if op == 'selected_value':
        selected = context.get(str(value.get('selection_key') or 'selected')) or []
        raw = selected[0] if isinstance(selected, list) and selected else selected
        return _numeric(raw, _numeric(value.get('default'), 0))
    if op == 'selected_card_field':
        selected = context.get(str(value.get('selection_key') or 'selected')) or []
        instance_id = selected[0] if isinstance(selected, list) and selected else selected
        for player in (state.get('players') or {}).values():
            for cards in (player.get('zones') or {}).values():
                for card in cards:
                    if card.get('instance_id') == instance_id:
                        return card.get(str(value.get('field') or ''), value.get('default'))
        return value.get('default')
    if op == 'selected_cards_field_sum':
        selected = set(
            context.get(str(value.get('selection_key') or 'selected')) or []
        )
        field = str(value.get('field') or '')
        return sum(
            _numeric(card.get(field), _numeric(value.get('default'), 0))
            for player in (state.get('players') or {}).values()
            for cards in (player.get('zones') or {}).values()
            for card in cards
            if card.get('instance_id') in selected
        )
    if op == 'attached_count':
        side = resolve_value(value.get('player', {'controller': True}), state, context)
        host = resolve_value(
            value.get('host', {'path': 'context.source_card_instance_id'}), state, context,
        )
        where = value.get('where') or {}
        zones = state_path(state, f'players.{side}.zones', {}) or {}
        return sum(
            1 for cards in zones.values() for card in cards
            if card.get('attached_to') == host
            and card_matches(card, where, state, context)
        )
    return copy.deepcopy(value)


def _numeric(value, default=0):
    if isinstance(value, bool):
        return default
    try:
        return float(value) if isinstance(value, float) else int(value)
    except (TypeError, ValueError):
        return default


def _comparison_values(left, right):
    """Compare printed numeric judgments such as ``+6`` as numbers."""
    try:
        if isinstance(left, bool) or isinstance(right, bool):
            return left, right
        return float(str(left).strip()), float(str(right).strip())
    except (TypeError, ValueError):
        return left, right


def condition_matches(condition, state, context):
    if condition in (None, True):
        return True
    if condition is False or not isinstance(condition, dict):
        return False
    op = condition.get('op')
    if op == 'all':
        return all(condition_matches(item, state, context) for item in condition.get('conditions') or [])
    if op == 'any':
        return any(condition_matches(item, state, context) for item in condition.get('conditions') or [])
    if op == 'not':
        return not condition_matches(condition.get('condition'), state, context)
    left_operand = condition.get('left')
    left = (
        resolve_value(left_operand, state, context)
        if isinstance(left_operand, dict)
        else resolve_value({'path': left_operand, 'default': None}, state, context)
    )
    right = resolve_value(condition.get('right'), state, context)
    if op == 'equals':
        return left == right
    if op == 'not_equals':
        return left != right
    left, right = _comparison_values(left, right)
    if op == 'gt':
        try:
            return left is not None and right is not None and left > right
        except TypeError:
            return False
    if op == 'gte':
        try:
            return left is not None and right is not None and left >= right
        except TypeError:
            return False
    if op == 'lt':
        try:
            return left is not None and right is not None and left < right
        except TypeError:
            return False
    if op == 'lte':
        try:
            return left is not None and right is not None and left <= right
        except TypeError:
            return False
    if op == 'in':
        return left in (right or [])
    if op == 'contains':
        return right in (left or [])
    if op == 'exists':
        return left is not None
    if op == 'phase_is':
        return state.get('phase') == condition.get('phase')
    if op == 'result_is':
        return context.get('result') in (condition.get('results') or [condition.get('result')])
    if op == 'has_state':
        side = resolve_value(condition.get('player', {'controller': True}), state, context)
        key = str(condition.get('state') or '')
        entry = state_path(state, f'players.{side}.passive_state.{key}', {}) or {}
        derived = state_path(state, f'engine.continuous_states.{side}.{key}', []) or []
        return bool(entry.get('value', entry.get('count', False)) or derived)
    if op == 'counter_at_least':
        side = resolve_value(condition.get('player', {'controller': True}), state, context)
        key = str(condition.get('counter') or '')
        entry = state_path(state, f'players.{side}.passive_state.{key}', {}) or {}
        return int(entry.get('count') or 0) >= int(condition.get('value') or 0)
    if op == 'once_available':
        key = str(condition.get('key') or context.get('ability_id') or '')
        scope = str(condition.get('scope') or 'game')
        controller = context.get('controller')
        return not state_path(state, f'engine.usage.{scope}.{controller}.{key}', False)
    if op == 'zone_count':
        side = resolve_value(condition.get('player', {'controller': True}), state, context)
        cards = state_path(state, f'players.{side}.zones.{condition.get("zone")}', []) or []
        source_id = (
            context.get('source_card_instance_id')
            or (context.get('source_card') or {}).get('instance_id')
        )
        combo_proposed_ids = set(
            context.get('combo_proposed_card_ids') or []
        ) if condition.get('exclude_combo_proposed') else set()
        count = len([
            card for card in cards
            if (
                not condition.get('exclude_source')
                or card.get('instance_id') != source_id
            )
            and card.get('instance_id') not in combo_proposed_ids
            and card_matches(card, condition.get('where'), state, context)
        ])
        minimum = int(condition.get('min', 0))
        maximum = condition.get('max')
        return count >= minimum and (maximum is None or count <= int(maximum))
    if op == 'card_matches':
        card = resolve_value(condition.get('card', {'path': 'context.source_card'}), state, context)
        return card_matches(card, condition.get('where'), state, context)
    if op == 'used_card':
        side = resolve_value(condition.get('player', {'controller': True}), state, context)
        current_turn = int(state.get('turn') or 1)
        current_card_id = (
            (context.get('source_card') or {}).get('instance_id')
            if condition.get('current_card') else None
        )
        count = 0
        for item in state_path(state, 'engine.card_use_history', []) or []:
            if item.get('player') != side or int(item.get('turn') or 0) != current_turn:
                continue
            if current_card_id and item.get('instance_id') != current_card_id:
                continue
            if condition.get('use_context') and item.get('use_context') != condition.get('use_context'):
                continue
            if condition.get('exclude_source') and item.get('instance_id') == context.get('source_card_instance_id'):
                continue
            if card_matches(item.get('card') or {}, condition.get('where'), state, context):
                count += 1
        return count >= int(condition.get('min', 1))
    if op == 'ability_resolved':
        side = resolve_value(condition.get('player', {'controller': True}), state, context)
        current_turn = int(state.get('turn') or 1)
        ability_id = str(condition.get('ability_id') or '')
        return any(
            item.get('player') == side
            and int(item.get('turn') or 0) == current_turn
            and (not ability_id or item.get('ability_id') == ability_id)
            and (
                not condition.get('same_source')
                or item.get('card_instance_id')
                == context.get('source_card_instance_id')
            )
            for item in state_path(state, 'engine.ability_resolution_history', []) or []
        )
    if op == 'battle_result':
        side = resolve_value(condition.get('player', {'controller': True}), state, context)
        current_turn = int(state.get('turn') or 1)
        results = set(condition.get('results') or [condition.get('result')]) - {None}
        for item in state_path(state, 'engine.battle_result_history', []) or []:
            if item.get('player') != side or int(item.get('turn') or 0) != current_turn:
                continue
            if results and item.get('result') not in results:
                continue
            if not card_matches(item.get('opponent_card') or {}, condition.get('opponent_where'), state, context):
                continue
            return True
        return False
    return False


def card_matches(card, where, state=None, context=None):
    if not isinstance(card, dict):
        return False
    if not where:
        return True
    context = context or {}
    for key, expected in where.items():
        if key in {'any', 'all'}:
            filters = expected if isinstance(expected, list) else []
            if not filters:
                return False
            matched = [
                card_matches(card, item, state, context)
                for item in filters if isinstance(item, dict)
            ]
            if len(matched) != len(filters):
                return False
            if key == 'any' and not any(matched):
                return False
            if key == 'all' and not all(matched):
                return False
            continue
        if isinstance(expected, dict):
            expected = resolve_value(expected, state or {}, context)
        actual = card.get(key)
        if key == 'type_contains':
            if (
                card.get('non_technique_while_face_down')
                or str(expected) not in str(card.get('type') or '')
            ):
                return False
        elif key == 'type_not_contains':
            if str(expected) in str(card.get('type') or ''):
                return False
        elif key == 'name_contains':
            if str(expected).casefold() not in str(card.get('name') or '').casefold():
                return False
        elif key == 'name_not_contains':
            if str(expected).casefold() in str(card.get('name') or '').casefold():
                return False
        elif key == 'judgment_contains':
            if str(expected) not in {
                str(card.get('hit') or ''), str(card.get('counter') or ''),
            }:
                return False
        elif key == 'judgment_contains_any':
            judgments = {
                str(card.get('hit') or ''), str(card.get('counter') or ''),
            }
            if not any(str(item) in judgments for item in (expected or [])):
                return False
        elif key == 'instance_id_not':
            if str(card.get('instance_id') or '') == str(expected):
                return False
        elif key == 'keyword_any':
            keywords = {item.strip() for item in str(card.get('keyword') or '').split('/') if item.strip()}
            if not any(str(item) in keywords for item in expected):
                return False
        elif key == 'text_contains':
            if str(expected) not in str(card.get('text') or ''):
                return False
        elif key == 'text_contains_any':
            if not any(str(item) in str(card.get('text') or '') for item in (expected or [])):
                return False
        elif key == 'text_effect_prefix':
            marker = str(expected or '').strip()
            text = str(card.get('text') or '').replace('\r\n', '\n')
            if not marker or not re.search(
                rf'(?:^|\n)\s*(?:[①-⑳]\s*)?{re.escape(marker)}\s*:',
                text,
                re.IGNORECASE,
            ):
                return False
        elif key == 'text_not_contains':
            if str(expected) in str(card.get('text') or ''):
                return False
        elif key == 'type_in':
            if card.get('non_technique_while_face_down') or card.get('type') not in expected:
                return False
        elif key == 'is_technique':
            card_type = str(card.get('type') or '')
            # Tokens and other generic cards are not Techniques merely because
            # they are face-up.  A card-form rule can still turn a token into
            # a Technique by assigning an attack/defense/special type in its
            # active zone (for example New Single in hand).
            is_technique = bool(
                not card.get('non_technique_while_face_down')
                and any(label in card_type for label in ('공격', '수비', '특수'))
            )
            if is_technique != bool(expected):
                return False
        elif key == 'special_truthy':
            if bool(card.get('special')) != bool(expected):
                return False
        elif key == 'special_contains':
            if str(expected) not in str(card.get('special') or ''):
                return False
        elif key == 'battle_judgment_contains':
            judgments = ' '.join(str(card.get(field) or '') for field in (
                'special', 'g_top', 'g_mid', 'g_bot',
            ))
            if str(expected) not in judgments:
                return False
        elif key == 'frame_gte':
            if _numeric(card.get('frame')) < _numeric(expected):
                return False
        elif key == 'frame_lte':
            if _numeric(card.get('frame')) > _numeric(expected):
                return False
        elif key == 'frame_parity':
            frame = _numeric(card.get('frame'))
            parity = 'odd' if frame % 2 else 'even'
            if frame <= 0 or parity != str(expected):
                return False
        elif key == 'code_in':
            if card.get('code') not in expected:
                return False
        elif key == 'owner':
            if card.get('owner') != expected:
                return False
        elif key == 'face_up':
            if bool(actual) != bool(expected):
                return False
        elif isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _ability_limit_key(ability, context):
    limit = ability.get('limit') or {}
    key = str(limit.get('key') or ability.get('id') or '')
    event_card = context.get('event_card') or {}
    event_card_id = (
        event_card.get('instance_id')
        or context.get('event_card_instance_id')
        or 'event'
    )
    if limit.get('per_event_card'):
        key = f'{key}:{event_card_id}'
    if limit.get('per_effect_resolution'):
        resolution_id = (
            context.get('effect_resolution_id')
            or f'card:{event_card_id}'
        )
        key = f'{key}:{resolution_id}'
    return key


class EffectResolver:
    def __init__(self, engine):
        self.engine = engine

    @property
    def state(self):
        return self.engine.state

    def _definition_for_card(self, card):
        return self.engine._definition_for_card(card)

    def _active_cards(self, event_context):
        source_id = event_context.get('source_card_instance_id')
        rows = []
        for side in PLAYER_SIDES:
            zones = ((self.state.get('players') or {}).get(side) or {}).get('zones') or {}
            for zone, cards in zones.items():
                for card in cards:
                    definition = self._definition_for_card(card)
                    if not definition.get('abilities'):
                        continue
                    rows.append((side, zone, card, definition))
        # Imported or deleted source cards can be supplied directly by context.
        source_card = event_context.get('source_card')
        if isinstance(source_card, dict) and source_card.get('instance_id') == source_id:
            if not any(card.get('instance_id') == source_id for _, _, card, _ in rows):
                definition = self._definition_for_card(source_card)
                if definition.get('abilities'):
                    rows.append((source_card.get('owner'), event_context.get('source_zone'), source_card, definition))
        return rows

    def collect(self, event_type, event_context=None, *, depth=0):
        if depth > MAX_EVENT_DEPTH:
            raise EffectResolutionError('효과 이벤트 깊이 제한을 초과했습니다.')
        event_context = copy.deepcopy(event_context or {})
        event_card = copy.deepcopy(event_context.get('source_card'))
        event_printed_card = self.engine._printed_card_snapshot(event_card)
        event_card_instance_id = event_context.get('source_card_instance_id')
        excluded_controllers = set(event_context.get('excluded_controllers') or [])
        collected = []
        deduplicated_triggers = set()
        for controller, zone, card, definition in self._active_cards(event_context):
            if controller in excluded_controllers:
                continue
            if event_type == 'combo_end' and controller != event_context.get('combo_owner'):
                continue
            if event_type == 'opponent_combo_end' and controller == event_context.get('combo_owner'):
                continue
            for ability in definition.get('abilities') or []:
                if card.get('numbered_effects_negated') and ability.get('kind') == 'effect':
                    continue
                trigger = ability.get('trigger') or {}
                trigger_events = trigger.get('events') or [trigger.get('event')]
                if event_type not in trigger_events:
                    continue
                active_zones = ability.get('active_zones')
                is_source = card.get('instance_id') == event_context.get('source_card_instance_id')
                is_attached_source = card.get('attached_to') == event_context.get('source_card_instance_id')
                attached_active = is_attached_source and ability.get('active_when_attached') is True
                explicit_global_reaction = bool(
                    active_zones is not None
                    and zone in GLOBAL_REACTION_ZONES
                    and zone in active_zones
                )
                combo_use_required = bool(
                    ability.get('requires_combo_use') is True
                    or ability.get('id') in KNOWN_COMBO_USE_REQUIRED_ABILITIES
                )
                used_in_combo = bool(
                    event_type == 'combo_end'
                    and combo_use_required
                    and card.get('instance_id') in set(
                        event_context.get('combo_used') or []
                    )
                )
                if (
                    event_type == 'combo_end'
                    and combo_use_required
                    and card.get('instance_id') not in set(
                        event_context.get('combo_used') or []
                    )
                ):
                    continue
                if (
                    event_type == 'combo_end'
                    and _is_technique(card)
                    and card.get('instance_id') not in set(
                        event_context.get('combo_card_instance_ids')
                        or [event_context.get('source_card_instance_id')]
                    )
                    and not explicit_global_reaction
                    and zone not in GLOBAL_REACTION_ZONES
                    and ability.get('allow_non_source_trigger') is not True
                ):
                    continue
                if event_context.get('source_only_event') and not (is_source or attached_active):
                    continue
                if (
                    (
                        event_context.get('source_battle_card_only')
                        or event_context.get('source_technique_event')
                        or event_type in SOURCE_TECHNIQUE_EVENTS
                    )
                    and _is_technique(card)
                    and not (
                        is_source or attached_active
                        or explicit_global_reaction
                    )
                    and ability.get('allow_non_source_trigger') is not True
                    and ability.get('id') not in KNOWN_NON_SOURCE_TRIGGER_ABILITIES
                ):
                    continue
                default_active = zone in {'passive', 'lumen', 'ultimate'} or is_source or attached_active
                if (
                    active_zones is not None and zone not in active_zones
                    and not used_in_combo
                ):
                    continue
                if active_zones is None and not default_active and not used_in_combo:
                    continue
                context = {
                    **event_context,
                    'event_controller': event_context.get('controller'),
                    # Preserve the ability that caused a nested domain event
                    # before replacing ``ability_id`` with the reacting
                    # ability below.  Damage reactions use this provenance to
                    # reject only their own bonus damage without suppressing
                    # damage produced by a different Technique effect.
                    'event_ability_id': event_context.get('ability_id'),
                    'event_type': event_type,
                    'controller': controller,
                    'opponent': _opponent(controller),
                    'controller_hp': state_path(self.state, f'players.{controller}.hp', 0),
                    'controller_fp': state_path(self.state, f'players.{controller}.fp', 0),
                    'opponent_hp': state_path(self.state, f'players.{_opponent(controller)}.hp', 0),
                    'opponent_fp': state_path(self.state, f'players.{_opponent(controller)}.fp', 0),
                    'controller_hand_limit': self.engine._current_hand_limit(
                        controller,
                    ),
                    'opponent_hand_limit': self.engine._current_hand_limit(
                        _opponent(controller),
                    ),
                    'controller_turn_damage_received': state_path(
                        self.state, f'engine.turn_damage_received.{controller}', 0,
                    ),
                    'opponent_turn_damage_received': state_path(
                        self.state, f'engine.turn_damage_received.{_opponent(controller)}', 0,
                    ),
                    'source_card': copy.deepcopy(card),
                    'source_card_instance_id': card.get('instance_id'),
                    'event_card': copy.deepcopy(event_card),
                    'event_printed_card': copy.deepcopy(event_printed_card),
                    'event_card_instance_id': event_card_instance_id,
                    # ``event_context.opponent_card`` is relative to the
                    # player whose timing slot is being dispatched. Passive
                    # and other global reactions may have the other
                    # controller, so derive their current opponent from the
                    # live battle first.
                    'opponent_card': copy.deepcopy(
                        ((((self.state.get('engine') or {}).get('battle') or {})
                          .get(_opponent(controller)) or {}).get('card'))
                        or event_context.get('opponent_card')
                    ),
                    'source_zone': zone,
                    'ability_id': ability.get('id'),
                    'ability_visibility': ability.get('visibility', 'public'),
                    'depth': depth,
                }
                limit = ability.get('limit') or {}
                if limit:
                    scope = str(limit.get('scope') or 'game')
                    key = _ability_limit_key(ability, context)
                    used = state_path(self.state, f'engine.usage.{scope}.{controller}.{key}', 0) or 0
                    if int(used) >= int(limit.get('max', 1)):
                        continue
                if (
                    condition_matches(ability.get('condition'), self.state, context)
                    and self.engine.selector_has_minimum(
                        ability.get('availability_selector'), context,
                    )
                ):
                    dedupe_key = str(ability.get('dedupe_trigger_key') or '').strip()
                    dedupe_identity = (controller, event_type, dedupe_key)
                    if dedupe_key and dedupe_identity in deduplicated_triggers:
                        continue
                    if dedupe_key:
                        deduplicated_triggers.add(dedupe_identity)
                    resolved_ability = copy.deepcopy(ability)
                    if trigger.get('events'):
                        resolved_ability['timing'] = EVENT_TIMING.get(
                            event_type, resolved_ability.get('timing'),
                        )
                    collected.append({
                        'controller': controller,
                        'zone': zone,
                        'card_instance_id': card.get('instance_id'),
                        'card_code': card.get('code'),
                        'ability': resolved_ability,
                        'context': context,
                    })
        self._enqueue_ordered(collected)
        return len(collected)

    def _enqueue_ordered(self, collected):
        """Queue alternating timing slots and defer same-owner order to them.

        Rulebook timing still alternates priority player/opponent.  Inside a
        player's slot, however, two or more effects at the same timing are a
        real player decision instead of an incidental card-code sort.
        """
        ordered = self._ordered(collected)
        if not ordered:
            return
        counts = {}
        for item in ordered:
            ability = item.get('ability') or {}
            key = (
                TIMING_ORDER.get(ability.get('timing'), 999),
                ability.get('visibility', 'public'),
                item.get('controller'),
            )
            counts[key] = counts.get(key, 0) + 1
        groups = self.state['engine'].setdefault('resolution_order_groups', {})
        queue = self.state['engine'].setdefault('resolution_queue', [])
        group_ids = {}
        for item in ordered:
            ability = item.get('ability') or {}
            key = (
                TIMING_ORDER.get(ability.get('timing'), 999),
                ability.get('visibility', 'public'),
                item.get('controller'),
            )
            if counts.get(key, 0) <= 1:
                queue.append(item)
                continue
            group_id = group_ids.get(key)
            if not group_id:
                group_id = self.engine._next_id('effect-order-group')
                group_ids[key] = group_id
                groups[group_id] = {
                    'controller': item.get('controller'),
                    'visibility': ability.get('visibility', 'public'),
                    'items': [],
                }
            order_id = self.engine._next_id('effect-order-option')
            groups[group_id]['items'].append({
                **copy.deepcopy(item), 'resolution_order_id': order_id,
            })
            queue.append({
                'kind': 'effect_order_slot', 'group_id': group_id,
                'controller': item.get('controller'),
            })

    def continuous_effects(self, event_context=None):
        """Return currently applicable numberless/function effects in rule order."""
        event_context = copy.deepcopy(event_context or {})
        collected = []
        for controller, zone, card, definition in self._active_cards(event_context):
            for ability in definition.get('abilities') or []:
                if card.get('numbered_effects_negated') and ability.get('kind') == 'effect':
                    continue
                if ability.get('mode') != 'continuous':
                    continue
                active_zones = ability.get('active_zones')
                if active_zones is not None and zone not in active_zones:
                    continue
                context = {
                    **event_context, 'controller': controller, 'opponent': _opponent(controller),
                    'controller_hp': state_path(self.state, f'players.{controller}.hp', 0),
                    'controller_fp': state_path(self.state, f'players.{controller}.fp', 0),
                    'opponent_hp': state_path(self.state, f'players.{_opponent(controller)}.hp', 0),
                    'opponent_fp': state_path(self.state, f'players.{_opponent(controller)}.fp', 0),
                    'controller_turn_damage_received': state_path(
                        self.state, f'engine.turn_damage_received.{controller}', 0,
                    ),
                    'opponent_turn_damage_received': state_path(
                        self.state, f'engine.turn_damage_received.{_opponent(controller)}', 0,
                    ),
                    'source_card': copy.deepcopy(card), 'source_card_instance_id': card.get('instance_id'),
                    'source_zone': zone, 'ability_id': ability.get('id'),
                    'opponent_card': copy.deepcopy(
                        (((self.state.get('engine') or {}).get('battle') or {}).get(_opponent(controller)) or {}).get('card')
                    ),
                }
                if condition_matches(ability.get('condition'), self.state, context):
                    collected.append({
                        'controller': controller, 'zone': zone, 'card_instance_id': card.get('instance_id'),
                        'card_code': card.get('code'), 'ability': copy.deepcopy(ability), 'context': context,
                    })
        return self._ordered(collected)

    def _ordered(self, items):
        priority = self.state.get('priority_player')
        other = _opponent(priority) if priority in PLAYER_SIDES else 'p2'
        output = []
        timings = sorted({TIMING_ORDER.get(item['ability'].get('timing'), 999) for item in items})
        for timing in timings:
            for visibility in ('public', 'private'):
                timed = [
                    item for item in items
                    if TIMING_ORDER.get(item['ability'].get('timing'), 999) == timing
                    and item['ability'].get('visibility', 'public') == visibility
                ]
                buckets = {
                    priority: [item for item in timed if item['controller'] == priority],
                    other: [item for item in timed if item['controller'] == other],
                }
                for side in (priority, other):
                    buckets[side].sort(key=lambda item: (
                        str(item['card_code'] or ''), str(item['ability'].get('id') or ''),
                    ))
                while buckets.get(priority) or buckets.get(other):
                    for side in (priority, other):
                        if buckets.get(side):
                            output.append(buckets[side].pop(0))
        return output

    def drain(self):
        engine_state = self.state['engine']
        steps = 0
        while engine_state.get('resolution_queue') and not engine_state.get('pending_decision'):
            steps += 1
            engine_state['resolution_steps'] = int(engine_state.get('resolution_steps') or 0) + 1
            if steps > MAX_RESOLUTION_STEPS or engine_state['resolution_steps'] > MAX_RESOLUTION_STEPS:
                raise EffectResolutionError('효과 해결 횟수 제한을 초과했습니다.')
            item = engine_state['resolution_queue'].pop(0)
            if item.get('kind') == 'effect_order_slot':
                group_id = item.get('group_id')
                group = (
                    engine_state.get('resolution_order_groups') or {}
                ).get(group_id) or {}
                candidates = group.get('items') or []
                if not candidates:
                    (engine_state.get('resolution_order_groups') or {}).pop(
                        group_id, None,
                    )
                    continue
                if len(candidates) == 1:
                    chosen = candidates.pop(0)
                    if not candidates:
                        (engine_state.get('resolution_order_groups') or {}).pop(
                            group_id, None,
                        )
                    engine_state['resolution_queue'].insert(0, chosen)
                    continue
                all_optional = all(
                    (candidate.get('ability') or {}).get('mode') == 'optional'
                    for candidate in candidates
                )
                self.engine.create_decision(
                    owner=group.get('controller'),
                    kind='effect_order',
                    prompt='먼저 해결할 효과를 선택하세요.',
                    options=[{
                        'id': candidate.get('resolution_order_id'),
                        'label': (
                            (candidate.get('ability') or {}).get('label')
                            or (candidate.get('ability') or {}).get('id')
                            or candidate.get('card_code')
                            or '효과'
                        ),
                        'card_code': candidate.get('card_code'),
                        'card_instance_id': candidate.get('card_instance_id'),
                        'effect_mode': (
                            (candidate.get('ability') or {}).get('mode')
                            or 'mandatory'
                        ),
                        'source_zone': (
                            candidate.get('zone')
                            or (candidate.get('context') or {}).get('source_zone')
                        ),
                        'active_zones': copy.deepcopy(
                            (candidate.get('ability') or {}).get('active_zones')
                            or ([
                                candidate.get('zone')
                                or (candidate.get('context') or {}).get('source_zone')
                            ] if (
                                candidate.get('zone')
                                or (candidate.get('context') or {}).get('source_zone')
                            ) else [])
                        ),
                        'ability_id': (candidate.get('ability') or {}).get('id'),
                    } for candidate in candidates],
                    minimum=0 if all_optional else 1, maximum=1,
                    default=[] if all_optional else [
                        candidates[0].get('resolution_order_id')
                    ],
                    optional=all_optional,
                    continuation={
                        'type': 'effect_order', 'group_id': group_id,
                    },
                )
                break
            ability = item['ability']
            context = item['context']
            limit = ability.get('limit') or {}
            if limit:
                scope = str(limit.get('scope') or 'game')
                key = _ability_limit_key(ability, context)
                used = state_path(self.state, f'engine.usage.{scope}.{item["controller"]}.{key}', 0) or 0
                if int(used) >= int(limit.get('max', 1)):
                    continue
            if ability.get('recheck_condition') and not condition_matches(
                ability.get('condition'), self.state, context,
            ):
                continue
            if not self.engine.selector_has_minimum(
                ability.get('availability_selector'), context,
            ):
                continue
            mode = ability.get('mode')
            if mode == 'optional' and not item.get('activation_preapproved'):
                self.engine.create_decision(
                    owner=item['controller'],
                    kind='optional_effect',
                    prompt=ability.get('label') or item.get('card_code') or ability.get('id'),
                    options=[
                        {
                            'id': 'accept', 'label': '발동',
                            'card_instance_id': item.get('card_instance_id'),
                            'effect_mode': 'optional',
                            'source_zone': (
                                item.get('zone')
                                or (item.get('context') or {}).get('source_zone')
                            ),
                            'active_zones': copy.deepcopy(
                                ability.get('active_zones')
                                or ([
                                    item.get('zone')
                                    or (item.get('context') or {}).get('source_zone')
                                ] if (
                                    item.get('zone')
                                    or (item.get('context') or {}).get('source_zone')
                                ) else [])
                            ),
                        },
                        {'id': 'decline', 'label': '발동하지 않음'},
                    ],
                    minimum=1,
                    maximum=1,
                    default=['decline'],
                    continuation={'type': 'optional_effect', 'item': item},
                )
                break
            self.execute_ability(item)
        return not engine_state.get('pending_decision')

    def continue_effect_order(self, group_id, selected_id):
        groups = self.state['engine'].setdefault('resolution_order_groups', {})
        group = groups.get(str(group_id or '')) or {}
        items = group.get('items') or []
        if selected_id is None:
            if items and all(
                (item.get('ability') or {}).get('mode') == 'optional'
                for item in items
            ):
                groups.pop(str(group_id or ''), None)
                return self.drain()
            raise EffectResolutionError('필수 효과의 해결 순서를 선택해야 합니다.')
        selected_index = next((
            index for index, item in enumerate(items)
            if str(item.get('resolution_order_id') or '')
            == str(selected_id or '')
        ), None)
        if selected_index is None:
            raise EffectResolutionError('선택한 효과 순서가 더 이상 유효하지 않습니다.')
        chosen = items.pop(selected_index)
        if (chosen.get('ability') or {}).get('mode') == 'optional':
            chosen['activation_preapproved'] = True
        if not items:
            groups.pop(str(group_id or ''), None)
        self.state['engine'].setdefault('resolution_queue', []).insert(0, chosen)
        return self.drain()

    def continue_optional(self, item, accepted):
        if accepted and (
            not item['ability'].get('recheck_condition')
            or condition_matches(
                item['ability'].get('condition'), self.state, item['context'],
            )
        ) and self.engine.selector_has_minimum(
            item['ability'].get('availability_selector'), item['context'],
        ):
            self.execute_ability(item)
        return self.drain()

    def execute_ability(self, item):
        ability = item['ability']
        context = item['context']
        targets = ability.get('targets') or []
        target_index = int(context.get('target_index') or 0)
        if target_index < len(targets):
            selector = targets[target_index]
            options = self.engine.selector_options(selector, context)
            minimum = int(resolve_value(selector.get('min', 1), self.state, context) or 0)
            maximum = int(resolve_value(selector.get('max', minimum), self.state, context) or 0)
            if len(options) < minimum:
                self.engine.emit('ability_target_skipped', item['controller'], {
                    'card_instance_id': item.get('card_instance_id'),
                    'card_code': item.get('card_code'),
                    'ability_id': ability.get('id'),
                    'reason': 'insufficient_candidates',
                    'minimum': minimum,
                    'candidate_count': len(options),
                }, visibility=ability.get('visibility', 'public'))
                return
            default = [str(value) for value in selector.get('default') or []]
            self.engine.create_decision(
                owner=item['controller'],
                kind='ability_target',
                prompt=selector.get('prompt') or ability.get('label') or ability.get('id') or '효과 대상 선택',
                options=options,
                minimum=minimum,
                maximum=maximum,
                default=default,
                optional=minimum == 0,
                continuation={'type': 'ability_target', 'item': copy.deepcopy(item)},
            )
            return
        self._execute_resolved_ability(item)

    def _execute_resolved_ability(self, item):
        """Finish one ability before returning to its sibling timing queue.

        Domain commands such as reveal and move emit nested events.  Those
        nested events may resolve immediately, but they must not accidentally
        drain a sibling ability that was already waiting in the parent timing
        queue.  Keep the parent queue detached until this ability either
        finishes or opens a decision, then append it after any unfinished
        nested work.
        """
        engine_state = self.state['engine']
        parent_queue = list(engine_state.get('resolution_queue') or [])
        engine_state['resolution_queue'] = []
        try:
            self._execute_resolved_ability_body(item)
        finally:
            nested_queue = list(engine_state.get('resolution_queue') or [])
            if engine_state.get('phase_restart_pending_start'):
                # A Ready restart intentionally discards every unresolved
                # timing from the interrupted battle (Q&A 404/645).
                parent_queue = []
            engine_state['resolution_queue'] = nested_queue + parent_queue

    def _execute_resolved_ability_body(self, item):
        ability = item['ability']
        context = item['context']
        # Reserve a limited use before executing domain commands.  An effect
        # can emit a nested event (damage_after is the common example) while
        # it is still resolving; recording the use afterwards allowed that
        # nested event to collect the same limited ability recursively.
        limit = ability.get('limit') or {}
        if limit:
            scope = str(limit.get('scope') or 'game')
            key = _ability_limit_key(ability, context)
            usage = (
                self.state['engine'].setdefault('usage', {})
                .setdefault(scope, {}).setdefault(item['controller'], {})
            )
            usage[key] = int(usage.get(key) or 0) + 1
        handler_name = ability.get('handler')
        if handler_name:
            handler = get_handler(handler_name)
            if not handler:
                raise EffectResolutionError(f'등록되지 않은 효과 핸들러입니다: {handler_name}')
            effects = handler(copy.deepcopy(self.state), copy.deepcopy(context), copy.deepcopy(ability))
            if effects is None:
                effects = []
            if not isinstance(effects, list) or any(not isinstance(effect, dict) for effect in effects):
                raise EffectResolutionError(f'{handler_name}: 핸들러는 도메인 명령 배열을 반환해야 합니다.')
        else:
            effects = ability.get('effects') or []
        definition = self._definition_for_card(context.get('source_card') or {})
        if definition.get('effect_damage_limit'):
            context['effect_damage_limit'] = copy.deepcopy(definition['effect_damage_limit'])
        self.engine.emit('effect_resolved', item['controller'], {
            'card_instance_id': item.get('card_instance_id'),
            'card_id': (context.get('source_card') or {}).get('card_id'),
            'card_code': item.get('card_code'),
            'card_label': (
                (context.get('source_card') or {}).get('name')
                or item.get('card_code')
                or '카드'
            ),
            'ability_id': ability.get('id'),
            'effect_label': ability.get('label'),
        }, visibility=ability.get('visibility', 'public'))
        self.state['engine'].setdefault('ability_resolution_history', []).append({
            'turn': int(self.state.get('turn') or 1),
            'player': item['controller'],
            'ability_id': ability.get('id'),
            'card_instance_id': item.get('card_instance_id'),
            'card_code': item.get('card_code'),
        })
        cost_context = copy.deepcopy(context)
        # Reactions to an HP payment must distinguish a real ability cost
        # from battle/effect damage or an unrelated HP change.  Preserve that
        # provenance through the nested ``hp_changed`` event.
        cost_context['effect_cost'] = True
        self.execute_effects(ability.get('cost') or [], cost_context)
        effect_context = copy.deepcopy(context)
        effect_context['effect_resolution_id'] = self.engine._next_id(
            'effect-resolution',
        )
        source_card = context.get('source_card') or {}
        event_card = context.get('event_card') or {}
        if source_card.get('attached_to') == event_card.get('instance_id'):
            host_definition = self._definition_for_card(event_card)
            multiplier = host_definition.get('attached_effect_multiplier') or {}
            if (
                multiplier.get('event') == context.get('event_type')
                and not (
                    multiplier.get('numbered_effect')
                    and event_card.get('numbered_effects_negated')
                )
                and card_matches(
                    source_card, multiplier.get('where'), self.state, context,
                )
            ):
                effect_context['effect_value_multiplier'] = int(multiplier.get('value') or 1)
        engine_state = self.state['engine']
        engine_state['effect_resolution_depth'] = int(
            engine_state.get('effect_resolution_depth') or 0
        ) + 1
        try:
            self.execute_effects(effects, effect_context)
        finally:
            depth = max(
                0, int(engine_state.get('effect_resolution_depth') or 1) - 1,
            )
            if depth:
                engine_state['effect_resolution_depth'] = depth
            else:
                engine_state.pop('effect_resolution_depth', None)
                self.engine._flush_deferred_speed_fixed_events()

    def continue_target(self, item, selected):
        context = item.setdefault('context', {})
        ability = item.get('ability') or {}
        index = int(context.get('target_index') or 0)
        selector = (ability.get('targets') or [])[index]
        key = selector.get('selection_key') or selector.get('id') or f'target_{index}'
        context.setdefault('targets', {})[key] = list(selected or [])
        context[key] = list(selected or [])
        context['target_index'] = index + 1
        self.execute_ability(item)
        return self.drain()

    def continue_effects(self, effects, context):
        """Resume one chosen branch before its sibling timing effects.

        A choice continuation can move a card, and that move emits a nested
        event.  Keep the still-unresolved sibling timing queue detached until
        every command after the choice has run, matching the atomic handling
        used by ``_execute_resolved_ability``.  Otherwise a sibling effect can
        run inside the move event and strand the remainder of the current
        ability behind a second decision.
        """
        engine_state = self.state['engine']
        parent_queue = list(engine_state.get('resolution_queue') or [])
        engine_state['resolution_queue'] = []
        engine_state['effect_resolution_depth'] = int(
            engine_state.get('effect_resolution_depth') or 0
        ) + 1
        try:
            self.execute_effects(effects, context)
        finally:
            nested_queue = list(engine_state.get('resolution_queue') or [])
            engine_state['resolution_queue'] = nested_queue + parent_queue
            depth = max(
                0, int(engine_state.get('effect_resolution_depth') or 1) - 1,
            )
            if depth:
                engine_state['effect_resolution_depth'] = depth
            else:
                engine_state.pop('effect_resolution_depth', None)
                self.engine._flush_deferred_speed_fixed_events()
        return self.drain()

    def execute_effects(self, effects, context):
        for index, effect in enumerate(effects or []):
            if context.get('_abort_effect_sequence'):
                return
            if self.state['engine'].get('pending_decision'):
                self.state['engine'].setdefault('deferred_effects', []).append({
                    'effects': copy.deepcopy(effects[index:]),
                    'context': copy.deepcopy(context),
                })
                return
            resolved_effect = effect
            if (
                effect.get('op') == 'move_card'
                and effect.get('to_zone') == 'lumen'
                and 'face_up' not in effect
            ):
                # Releases published before move_card.face_up existed encoded
                # an explicitly face-down Lumen placement as move -> hide.
                # Preserve that intent without briefly publishing the card in
                # the movement event. Secret Time used the same legacy shape
                # with a face-down-only flag and a conditional hide.
                following = (
                    effects[index + 1]
                    if index + 1 < len(effects or []) else {}
                )
                same_selection_hide = bool(
                    following.get('op') == 'hide'
                    and following.get('selection_key')
                    == effect.get('selection_key')
                )
                legacy_face_down_flag = bool(
                    (effect.get('set_flags') or {}).get(
                        'non_technique_while_face_down'
                    )
                )
                if same_selection_hide or legacy_face_down_flag:
                    resolved_effect = {**effect, 'face_up': False}
            self.execute_effect(resolved_effect, context)
            if context.get('_abort_effect_sequence'):
                return

    def execute_effect(self, effect, context):
        op = effect.get('op')
        controller = context.get('controller')
        target = resolve_value(effect.get('player', {'controller': True}), self.state, context)
        multiplier = max(1, int(context.get('effect_value_multiplier') or 1))
        if op == 'sequence':
            self.execute_effects(effect.get('effects'), context)
        elif op == 'conditional':
            branch = (
                effect.get('then') if condition_matches(effect.get('condition'), self.state, context)
                else effect.get('else')
            )
            self.execute_effects(branch or [], context)
        elif op == 'emit_event':
            payload = copy.deepcopy(effect.get('payload') or {})
            self.engine._fire(str(effect.get('event') or ''), {
                **copy.deepcopy(context), **payload,
                'source_only_event': bool(effect.get('source_only', True)),
            })
        elif op in {'deal_damage', 'change_hp'}:
            amount = int(resolve_value(effect.get('amount', 0), self.state, context) or 0) * multiplier
            if op == 'deal_damage':
                repeat = int(resolve_value(effect.get('repeat', 1), self.state, context) or 0)
                for _index in range(max(0, min(repeat, 50))):
                    limit = context.get('effect_damage_limit') or {}
                    is_opponent = target == context.get('opponent')
                    if is_opponent and limit.get('opponent'):
                        scope = str(limit.get('scope') or 'game')
                        source_key = str(
                            context.get('source_card_instance_id')
                            or (context.get('source_card') or {}).get('code')
                            or context.get('ability_id') or 'effect'
                        )
                        counts = (
                            self.state['engine'].setdefault('effect_damage_counts', {})
                            .setdefault(scope, {}).setdefault(controller, {})
                        )
                        if int(counts.get(source_key) or 0) >= int(limit['opponent']):
                            self.engine.emit('effect_damage_capped', controller, {
                                'source': source_key, 'maximum': int(limit['opponent']),
                            })
                            break
                        counts[source_key] = int(counts.get(source_key) or 0) + 1
                    damage_context = copy.deepcopy(context)
                    if effect.get('suppress_counter_gain') is True:
                        damage_context['suppress_counter_gain'] = True
                    self.engine.deal_damage(
                        target, abs(amount), source='effect',
                        context=damage_context,
                    )
            else:
                self.engine.change_hp(target, amount, source='effect', context=context)
        elif op == 'change_fp':
            amount = int(resolve_value(effect.get('amount', 0), self.state, context) or 0) * multiplier
            self.engine.change_fp(target, amount, source='effect', context=context)
        elif op == 'reset_fp':
            self.engine.set_fp(target, 0, source='effect')
        elif op == 'modify_damage':
            resolved_effect = copy.deepcopy(effect)
            resolved_effect['amount'] = int(
                resolve_value(effect.get('amount', 0), self.state, context) or 0
            ) * multiplier
            self.state['engine'].setdefault('replacements', []).append({
                **resolved_effect,
                'controller': controller,
                'player': target if target in PLAYER_SIDES else controller,
                'source': context.get('source_card_instance_id'),
                **(
                    {'remaining_uses': int(resolved_effect['max_uses'])}
                    if resolved_effect.get('max_uses') is not None else {}
                ),
            })
        elif op == 'move_card':
            card_id = resolve_value(effect.get('card_instance_id'), self.state, context)
            if not card_id and effect.get('target_card') == 'event_card':
                card_id = (
                    (context.get('event_card') or {}).get('instance_id')
                    or context.get('event_card_instance_id')
                )
            if not card_id:
                selected = context.get(effect.get('selection_key') or 'selected') or []
                card_ids = list(selected)
                if not card_ids and effect.get('selector'):
                    card_ids = self.engine.select_cards(effect.get('selector'), context)
                if (
                    not card_ids
                    and not effect.get('selector')
                    and not effect.get('selection_key')
                    and context.get('source_card_instance_id')
                ):
                    card_ids = [context.get('source_card_instance_id')]
            else:
                card_ids = [card_id]
            moved_ids = []
            for selected_id in card_ids:
                selected_card = self.engine._find_card(selected_id)
                if effect.get('as_get') and selected_card:
                    selected_owner = selected_card.get('owner')
                    if self.engine._rule_blocked(
                        'get_card', selected_owner, selected_card,
                    ):
                        self.engine.emit('card_move_prevented', controller, {
                            'card_instance_id': selected_id,
                            'from_zone': self.engine._find_location(selected_id)[1],
                            'to_zone': effect.get('to_zone'),
                            'reason': 'get_card_prevented',
                        })
                        continue
                max_zone_count = effect.get('max_zone_count')
                if max_zone_count is not None:
                    destination_owner = (
                        resolve_value(effect.get('to_player'), self.state, context)
                        or (selected_card or {}).get('owner')
                    )
                    destination = effect.get('to_zone')
                    token_key = (selected_card or {}).get('token_key')
                    existing = [
                        card for card in self.engine._zone(destination_owner, destination)
                        if not token_key or card.get('token_key') == token_key
                    ] if destination_owner in PLAYER_SIDES and destination else []
                    if len(existing) >= int(max_zone_count):
                        self.engine.emit('card_move_skipped', controller, {
                            'card_instance_id': selected_id, 'reason': 'destination_limit',
                            'to_zone': destination, 'maximum': int(max_zone_count),
                        })
                        continue
                pipeline = self.state.get('engine', {}).get('pipeline') or {}
                if (
                    effect.get('continue_resolution')
                    and pipeline.get('kind') in {
                        'combo_resolution', 'catch_resolution',
                    }
                    and pipeline.get('card_instance_id') == selected_id
                ):
                    pipeline['continue_after_source_left'] = True
                moved = self.engine.move_card(
                    selected_id, effect.get('to_zone'),
                    to_player=resolve_value(effect.get('to_player'), self.state, context),
                    reason='effect',
                    effect_controller=controller,
                    effect_source=context.get('source_card_instance_id'),
                    preserve_attachment=bool(effect.get('preserve_attachment')),
                    allow_special_destination=bool(
                        effect.get('allow_special_destination')
                    ),
                    face_up=(
                        effect.get('face_up')
                        if 'face_up' in effect else None
                    ),
                    block_hand_until=effect.get('block_hand_until'),
                    set_flags={
                        key: resolve_value(flag_value, self.state, context)
                        for key, flag_value in (effect.get('set_flags') or {}).items()
                    },
                )
                if moved is not None:
                    moved_ids.append(selected_id)
            if effect.get('result_key'):
                context[str(effect['result_key'])] = moved_ids
        elif op == 'exchange_cards':
            first = context.get(str(effect.get('first_selection_key') or '')) or []
            second = context.get(str(effect.get('second_selection_key') or '')) or []
            exchanged = False
            if first and second:
                exchanged = self.engine.exchange_cards(
                    first[0], second[0], reason='effect',
                    effect_controller=controller,
                    effect_source=context.get('source_card_instance_id'),
                )
            if effect.get('result_key'):
                context[str(effect['result_key'])] = (
                    [first[0], second[0]] if exchanged else []
                )
        elif op == 'break_card':
            card_id = resolve_value(effect.get('card_instance_id'), self.state, context)
            if not card_id and effect.get('selection_key'):
                selected = context.get(effect.get('selection_key')) or []
                card_ids = list(selected)
            elif card_id:
                card_ids = [card_id]
            elif effect.get('selector'):
                card_ids = self.engine.select_cards(effect.get('selector'), context)
            else:
                card_ids = [context.get('source_card_instance_id')]
            broken_ids = []
            for selected_id in [item for item in card_ids if item]:
                pipeline = self.state.get('engine', {}).get('pipeline') or {}
                if (
                    effect.get('continue_resolution')
                    and pipeline.get('kind') in {
                        'combo_resolution', 'catch_resolution',
                    }
                    and pipeline.get('card_instance_id') == selected_id
                ):
                    pipeline['continue_after_source_left'] = True
                broken = self.engine.break_card(
                    selected_id, reason='effect', effect_controller=controller,
                    effect_source=context.get('source_card_instance_id'),
                )
                if broken is not None:
                    broken_ids.append(selected_id)
            if effect.get('result_key'):
                context[str(effect['result_key'])] = broken_ids
        elif op == 'break_cards':
            if effect.get('selection_key'):
                card_ids = list(
                    context.get(str(effect.get('selection_key'))) or []
                )
            elif effect.get('selector'):
                card_ids = self.engine.select_cards(
                    effect.get('selector'), context,
                )
            else:
                card_ids = [
                    resolve_value(item, self.state, context)
                    for item in effect.get('card_instance_ids') or []
                ]
            broken = self.engine.break_cards(
                card_ids,
                reason='effect',
                effect_controller=controller,
                effect_source=context.get('source_card_instance_id'),
                require_all=bool(effect.get('require_all')),
            )
            if effect.get('result_key'):
                context[str(effect['result_key'])] = [
                    card.get('instance_id') for card in broken
                    if card.get('instance_id')
                ]
        elif op == 'discard':
            if effect.get('selection_key'):
                card_ids = list(context.get(effect.get('selection_key')) or [])
            else:
                card_ids = self.engine.select_cards(effect.get('selector'), context)
            discarded_ids = []
            for card_id in card_ids:
                discarded = self.engine.discard_card(
                    card_id, effect_controller=controller,
                    effect_source=context.get('source_card_instance_id'),
                    block_hand_until=effect.get('block_hand_until'),
                )
                if discarded is not None:
                    discarded_ids.append(card_id)
            if effect.get('result_key'):
                context[str(effect['result_key'])] = discarded_ids
        elif op in {'reveal', 'hide'}:
            card_id = resolve_value(effect.get('card_instance_id'), self.state, context)
            if card_id:
                card_ids = [card_id]
            elif effect.get('selection_key'):
                card_ids = list(context.get(effect.get('selection_key')) or [])
            else:
                card_ids = self.engine.select_cards(effect.get('selector'), context)
            for card_id in card_ids:
                self.engine.set_card_visibility(
                    card_id, op == 'reveal', effect_controller=controller,
                    effect_source=context.get('source_card_instance_id'),
                )
        elif op == 'draw':
            count = int(resolve_value(effect.get('count', 1), self.state, context) or 0)
            self.engine.draw_cards(target, count, from_zone=effect.get('from_zone', 'list'))
        elif op == 'shuffle_zone':
            self.engine.shuffle_zone(
                target if target in PLAYER_SIDES else controller,
                str(effect.get('zone') or ''), face_up=effect.get('face_up'),
            )
        elif op == 'attach_card':
            card_id = resolve_value(effect.get('card_instance_id'), self.state, context)
            if card_id:
                card_ids = [card_id]
            elif effect.get('selection_key'):
                card_ids = list(context.get(effect.get('selection_key')) or [])
            else:
                card_ids = self.engine.select_cards(effect.get('selector'), context)
            host_id = resolve_value(effect.get('to_card_instance_id'), self.state, context)
            for selected_id in card_ids:
                self.engine.attach_card(
                    selected_id, host_id, controller=controller,
                    attachment_expires=effect.get('attachment_expires'),
                    return_to_hand_on_expiry=bool(effect.get('return_to_hand_on_expiry')),
                    face_up=effect.get('face_up', True),
                )
        elif op == 'gain_state':
            self.engine.set_passive(
                target, str(effect.get('state') or ''), value=True, label=effect.get('label'),
                visibility=effect.get('visibility') or context.get('ability_visibility', 'public'),
                source_card=context.get('source_card'),
                expires=copy.deepcopy(effect.get('expires')),
            )
        elif op == 'lose_state':
            self.engine.set_passive(
                target, str(effect.get('state') or ''), value=False, label=effect.get('label'),
                visibility=effect.get('visibility') or context.get('ability_visibility', 'public'),
                source_card=context.get('source_card'),
            )
        elif op in {'change_counter', 'set_counter'}:
            value = int(resolve_value(effect.get('amount', effect.get('value', 0)), self.state, context) or 0) * multiplier
            counter_key = str(effect.get('counter') or '')
            counter_spend_waived = bool(
                op == 'change_counter'
                and value < 0
                and target == controller
                and any(
                    exemption.get('card_instance_id')
                    == context.get('source_card_instance_id')
                    and exemption.get('counter') == counter_key
                    for exemption in context.get('counter_spend_exemptions') or []
                    if isinstance(exemption, dict)
                )
            )
            if counter_spend_waived:
                self.engine.emit('counter_spend_waived', controller, {
                    'card_instance_id': context.get('source_card_instance_id'),
                    'counter': counter_key, 'amount': abs(value),
                })
                return
            self.engine.change_counter(
                target, counter_key, value,
                absolute=op == 'set_counter', label=effect.get('label'),
                visibility=effect.get('visibility') or context.get('ability_visibility', 'public'),
                minimum=effect.get('min', 0), maximum=effect.get('max'),
            )
        elif op == 'limit_counter_gain':
            side = target if target in PLAYER_SIDES else controller
            self.state['engine'].setdefault('counter_gain_limits', []).append({
                'id': self.engine._next_id('counter-gain-limit'),
                'player': side,
                'counter': str(effect.get('counter') or ''),
                'remaining': max(0, int(effect.get('max') or 0)),
                'duration': effect.get('duration') or 'turn',
                'source': context.get('source_card_instance_id'),
            })
        elif op == 'gain_shield':
            self.engine.gain_shield(
                target if target in PLAYER_SIDES else controller,
                int(resolve_value(effect.get('amount', 0), self.state, context) or 0) * multiplier,
                duration=effect.get('duration') or 'turn',
                source=context.get('source_card_instance_id'),
            )
        elif op == 'grant_effect_immunity':
            immunity = copy.deepcopy(effect)
            immunity.update({
                'controller': controller,
                'player': target if target in PLAYER_SIDES else controller,
                'source': context.get('source_card_instance_id'),
                'source_code': (context.get('source_card') or {}).get('code'),
            })
            if immunity.get('duration') == 'next_turn':
                immunity['expires_turn'] = int(self.state.get('turn') or 1) + 1
            self.state['engine'].setdefault('replacements', []).append(immunity)
        elif op in {'modify_stat', 'fix_speed'}:
            resolved_effect = copy.deepcopy(effect)
            if (
                not resolved_effect.get('where')
                and resolved_effect.get('scope') != 'player_cards'
            ):
                if resolved_effect.get('target_card') == 'event_card':
                    modified_card = context.get('event_card') or {}
                elif target in PLAYER_SIDES and target != controller:
                    modified_card = context.get('opponent_card') or {}
                else:
                    modified_card = context.get('source_card') or {}
                modified_id = (
                    modified_card.get('instance_id')
                    or context.get('source_card_instance_id')
                )
                if modified_id:
                    resolved_effect['where'] = {'instance_id': modified_id}
            if (
                op == 'fix_speed' and not resolved_effect.get('where')
                and context.get('source_card_instance_id')
            ):
                fixed_card = (
                    context.get('opponent_card')
                    if target in PLAYER_SIDES and target != controller
                    else context.get('source_card')
                ) or {}
                resolved_effect['where'] = {
                    'instance_id': (
                        fixed_card.get('instance_id')
                        or context.get('source_card_instance_id')
                    ),
                }
            if 'amount' in resolved_effect:
                resolved_effect['amount'] = (
                    int(resolve_value(resolved_effect['amount'], self.state, context) or 0) * multiplier
                )
            if 'value' in resolved_effect:
                resolved_effect['value'] = (
                    int(resolve_value(resolved_effect['value'], self.state, context) or 0) * multiplier
                )
            self.engine.add_modifier({
                **resolved_effect, 'controller': controller,
                'player': target if target in PLAYER_SIDES else controller,
                'source': context.get('source_card_instance_id'),
                'source_code': (context.get('source_card') or {}).get('code'),
                'timing_window': context.get('event_type'),
                'duration': effect.get('duration') or 'battle',
            })
        elif op == 'modify_judgment':
            self.engine.modify_judgment(
                target if target in PLAYER_SIDES else controller,
                str(effect.get('field') or ''),
                str(effect.get('value') or ''),
                source=context.get('source_card_instance_id'),
                mode=effect.get('mode') or 'replace',
                effect_controller=controller,
                duration=effect.get('duration') or 'battle',
            )
        elif op == 'modify_defense_judgments':
            self.engine.modify_defense_judgments(
                target if target in PLAYER_SIDES else controller,
                str(effect.get('value') or ''),
                source=context.get('source_card_instance_id'),
                effect_controller=controller,
            )
        elif op == 'copy_defense_judgments':
            selected = list(context.get(effect.get('selection_key') or 'selected') or [])
            if selected:
                self.engine.copy_defense_judgments(
                    target if target in PLAYER_SIDES else controller,
                    selected[0], source=context.get('source_card_instance_id'),
                )
        elif op == 'copy_clash_judgments':
            selected = list(
                context.get(effect.get('selection_key') or 'selected') or []
            )
            self.engine.copy_clash_judgments(
                target if target in PLAYER_SIDES else controller,
                selected, source=context.get('source_card_instance_id'),
                effect_controller=controller,
            )
        elif op == 'invalidate_battle_card':
            card_id = resolve_value(effect.get('card_instance_id'), self.state, context)
            selected = list(context.get(effect.get('selection_key') or 'selected') or [])
            if card_id:
                selected = [card_id]
            for selected_id in selected:
                self.engine.invalidate_battle_card(
                    selected_id,
                    effect_controller=controller,
                    effect_source=context.get('source_card_instance_id'),
                    return_zone=effect.get('return_zone') or 'hand',
                )
        elif op == 'guess_hand_parity':
            self.begin_hand_parity_guess(effect, context)
        elif op == 'modify_hand_guess_categories':
            event_card = context.get('event_card') or {}
            instance_id = (
                event_card.get('instance_id')
                or context.get('event_card_instance_id')
            )
            if instance_id:
                self.engine.add_modifier({
                    'op': 'modify_hand_guess_categories',
                    'controller': controller,
                    'player': target if target in PLAYER_SIDES else controller,
                    'where': {'instance_id': instance_id},
                    'categories': copy.deepcopy(effect.get('categories') or []),
                    'source': context.get('source_card_instance_id'),
                    'source_code': (context.get('source_card') or {}).get('code'),
                    'timing_window': context.get('event_type'),
                    'duration': effect.get('duration') or 'battle',
                })
        elif op == 'force_ready':
            card_id = resolve_value(effect.get('card_instance_id'), self.state, context)
            selected = list(context.get(effect.get('selection_key') or 'selected') or [])
            if card_id:
                selected = [card_id]
            if selected:
                self.engine.force_ready_card(
                    target if target in PLAYER_SIDES else controller,
                    selected[0], source=context.get('source_card_instance_id'),
                )
        elif op == 'force_ready_first':
            self.engine.force_ready_first(
                target if target in PLAYER_SIDES else controller,
                source=context.get('source_card_instance_id'),
            )
        elif op == 'force_designated_get':
            beneficiary = target if target in PLAYER_SIDES else controller
            chooser = resolve_value(
                effect.get('chooser') or {'opponent': True}, self.state, context,
            )
            self.engine.force_designated_get(
                beneficiary, chooser,
                source=context.get('source_card_instance_id'),
                duration=effect.get('duration') or 'turn',
            )
        elif op == 'skip_phase':
            side = target if target in PLAYER_SIDES else controller
            phase = str(effect.get('phase') or '')
            self.state['engine'].setdefault('skip_phases', {}).setdefault(side, {})[phase] = True
        elif op == 'skip_get':
            side = target if target in PLAYER_SIDES else controller
            self.state['engine'].setdefault('skip_get', {})[side] = True
        elif op == 'replace_get':
            side = target if target in PLAYER_SIDES else controller
            self.engine.replace_get_action(
                side, source=context.get('source_card_instance_id'),
            )
        elif op == 'repeat_phase':
            phase = str(effect.get('phase') or self.state.get('phase'))
            if effect.get('after_current'):
                self.state['engine']['repeat_phase'] = phase
                self.engine.emit('phase_repeat_scheduled', controller, {
                    'phase': phase,
                    'source': context.get('source_card_instance_id'),
                })
            else:
                self.engine.restart_phase_without_ending_battle(phase)
        elif op == 'schedule':
            self.state['engine'].setdefault('scheduled', []).append({
                'when': copy.deepcopy(effect.get('when') or {}),
                'effect': copy.deepcopy(effect.get('effect') or {}),
                'context': copy.deepcopy(context),
                'duration': effect.get('duration') or 'turn',
                'effect_controller': effect.get('effect_controller') or 'scheduled',
                'preserve_source': bool(effect.get('preserve_source')),
                'repeat': bool(effect.get('repeat')),
            })
        elif op == 'request_choice':
            options = self.engine.selector_options(effect.get('selector'), context)
            selector = effect.get('selector') or {}
            minimum = int(resolve_value(selector.get('min', 1), self.state, context) or 0)
            maximum = int(resolve_value(selector.get('max', minimum), self.state, context) or 0)
            maximum = min(maximum, len(options))
            selection_key = effect.get('selection_key') or 'selected'
            if len(options) < minimum:
                self.engine.emit('effect_choice_skipped', controller, {
                    'ability_id': context.get('ability_id'),
                    'reason': 'insufficient_candidates',
                    'minimum': minimum, 'candidate_count': len(options),
                })
                unavailable_effects = effect.get('else')
                if isinstance(unavailable_effects, list):
                    self.execute_effects(unavailable_effects, context)
                    return
                # A mandatory card movement is one atomic effect step.  If it
                # cannot be completed, later commands introduced by "그 후"
                # must not resolve on their own.
                context['_abort_effect_sequence'] = True
                return
            if minimum == 0 and maximum == 0:
                context[selection_key] = []
                self.execute_effects(effect.get('then') or [], context)
                return
            self.engine.create_decision(
                owner=target if target in PLAYER_SIDES else controller,
                kind='effect_choice',
                prompt=effect.get('prompt') or context.get('ability_id') or '효과 선택',
                options=options,
                minimum=minimum,
                maximum=maximum,
                default=copy.deepcopy(effect.get('default', [])),
                optional=bool(effect.get('optional')),
                distinct_by=selector.get('distinct_by'),
                continuation={
                    'type': 'effect_choice',
                    'effects': copy.deepcopy(effect.get('then') or []),
                    'context': copy.deepcopy(context),
                    'selection_key': selection_key,
                },
            )
        elif op == 'request_amount':
            minimum = int(resolve_value(effect.get('min', 0), self.state, context) or 0)
            maximum = int(resolve_value(effect.get('max'), self.state, context) or 0)
            if minimum < 0 or maximum < minimum or maximum > 100:
                raise EffectResolutionError('수치 선택 범위가 올바르지 않습니다.')
            selection_key = effect.get('selection_key') or 'selected'
            default = effect.get('default')
            if minimum == maximum:
                context[selection_key] = [str(minimum)]
                self.execute_effects(effect.get('then') or [], context)
                return
            allowed_values = effect.get('values')
            amounts = (
                [int(amount) for amount in allowed_values if minimum <= int(amount) <= maximum]
                if isinstance(allowed_values, list)
                else list(range(minimum, maximum + 1))
            )
            self.engine.create_decision(
                owner=target if target in PLAYER_SIDES else controller,
                kind='effect_amount',
                prompt=effect.get('prompt') or context.get('ability_id') or '수치를 선택하세요.',
                options=[{'id': str(amount), 'label': str(amount)} for amount in amounts],
                minimum=1, maximum=1,
                default=[str(default)] if isinstance(default, int) and minimum <= default <= maximum else [],
                continuation={
                    'type': 'effect_choice',
                    'effects': copy.deepcopy(effect.get('then') or []),
                    'context': copy.deepcopy(context),
                    'selection_key': selection_key,
                },
            )
        elif op == 'choose_effect':
            options = [
                copy.deepcopy(option)
                for option in (effect.get('options') or [])
                if condition_matches(option.get('condition'), self.state, context)
                and self.engine.selector_has_minimum(
                    option.get('selector_available'), context,
                )
            ]
            if not options:
                raise EffectResolutionError('적용할 수 있는 효과 선택지가 없습니다.')
            self.engine.create_decision(
                owner=target if target in PLAYER_SIDES else controller,
                kind='effect_branch',
                prompt=effect.get('prompt') or context.get('ability_id') or '적용할 효과를 선택하세요.',
                options=[{
                    'id': str(option.get('id')),
                    'label': option.get('label') or str(option.get('id')),
                } for option in options],
                minimum=0 if effect.get('optional') else 1,
                maximum=1,
                default=[str(effect.get('default'))] if effect.get('default') is not None else [],
                optional=bool(effect.get('optional')),
                continuation={
                    'type': 'effect_branch', 'options': options,
                    'context': copy.deepcopy(context),
                },
            )
        elif op == 'random_select':
            options = self.engine.selector_options(effect.get('selector'), context)
            count = int(resolve_value(effect.get('count', 1), self.state, context) or 0)
            selected = self.engine.random_choice(
                options, count,
                visibility=effect.get('visibility') or context.get('ability_visibility', 'public'),
                actor=controller,
            )
            context[effect.get('selection_key') or 'selected'] = [item['id'] for item in selected]
        elif op == 'capture_selection':
            context[effect.get('selection_key') or 'selected'] = self.engine.select_cards(
                effect.get('selector'), context,
            )
        elif op == 'start_combo':
            self.engine.queue_combo(
                target if target in PLAYER_SIDES else controller,
                source=context.get('source_card_instance_id'), special=True,
            )
        elif op == 'end_combo':
            if self.state['engine'].get('combo'):
                self.engine.end_combo()
            else:
                source = context.get('source_card_instance_id')
                if effect.get('source_event_card'):
                    source = context.get('event_card_instance_id')
                self.engine.suppress_battle_combo(
                    controller,
                    source=source,
                )
        elif op == 'end_battle':
            self.state['engine']['end_battle_requested'] = True
        elif op == 'end_turn':
            self.state['engine']['end_turn_requested'] = True
        elif op == 'win_game':
            winner = target if target in PLAYER_SIDES else controller
            self.engine.finish_game(
                winner,
                reason=str(effect.get('reason') or 'card_effect'),
            )
        elif op == 'grant_catch':
            where = copy.deepcopy(effect.get('where') or {})
            if effect.get('source_only') and context.get('source_card_instance_id'):
                where['instance_id'] = context.get('source_card_instance_id')
            if effect.get('source_attached') and context.get('source_card_instance_id'):
                where['attached_to'] = context.get('source_card_instance_id')
            self.state['engine'].setdefault('granted_catches', []).append({
                'owner': target if target in PLAYER_SIDES else controller,
                'where': where,
                'allow_zones': copy.deepcopy(effect.get('allow_zones') or ['hand']),
                'min_speed': effect.get('min_speed'),
                'max_speed': effect.get('max_speed'),
                'source': context.get('source_card_instance_id'),
                'damage_bonus': effect.get('damage_bonus', 0),
                'return_source_to_hand': bool(effect.get('return_source_to_hand')),
                'break_after_use': bool(effect.get('break_after_use')),
                'break_source_after_use': bool(effect.get('break_source_after_use')),
                'counter_exemption_on_source_break': copy.deepcopy(
                    effect.get('counter_exemption_on_source_break'),
                ),
                **({
                    'effect_replacement': copy.deepcopy(
                        effect.get('effect_replacement'),
                    ),
                } if effect.get('effect_replacement') is not None else {}),
            })
        elif op == 'grant_flexible_use':
            side = target if target in PLAYER_SIDES else controller
            usage_key = str(
                effect.get('usage_key')
                or f'{context.get("source_card_instance_id") or "card"}:{context.get("ability_id") or "ability"}:flexible-use'
            )
            shared = {
                'usage_key': usage_key,
                'usage_scope': effect.get('usage_scope') or 'turn',
                'max_uses': int(effect.get('max_uses') or 1),
            }
            allow_zones = copy.deepcopy(effect.get('allow_zones') or ['list'])
            where = copy.deepcopy(effect.get('where') or {})
            contexts = set(effect.get('contexts') or ['combo', 'catch'])
            if 'combo' in contexts:
                self.engine.add_modifier({
                    'op': 'modify_combo', 'controller': controller, 'player': side,
                    'allow_zones': allow_zones, 'where': where,
                    'source': context.get('source_card_instance_id'),
                    'duration': effect.get('duration') or 'turn', **shared,
                })
            if 'catch' in contexts:
                self.state['engine'].setdefault('granted_catches', []).append({
                    'owner': side, 'allow_zones': allow_zones, 'where': where,
                    'source': context.get('source_card_instance_id'), **shared,
                })
            self.engine.emit('flexible_use_granted', side, {
                'allow_zones': allow_zones, 'usage_key': usage_key,
                'contexts': sorted(contexts),
            })
        elif op == 'end_catch':
            self.engine.end_catch()
        elif op == 'modify_combo':
            resolved_effect = copy.deepcopy(effect)
            if resolved_effect.pop('source_only', False) and context.get('source_card_instance_id'):
                resolved_effect['where'] = {
                    **copy.deepcopy(resolved_effect.get('where') or {}),
                    'instance_id': context.get('source_card_instance_id'),
                }
            if resolved_effect.pop('after_source', False) and context.get('source_card_instance_id'):
                resolved_effect['after_where'] = {
                    **copy.deepcopy(resolved_effect.get('after_where') or {}),
                    'instance_id': context.get('source_card_instance_id'),
                }
            if resolved_effect.pop('where_source_attached', False) and context.get('source_card_instance_id'):
                resolved_effect['where'] = {
                    **copy.deepcopy(resolved_effect.get('where') or {}),
                    'attached_to': context.get('source_card_instance_id'),
                }
            if resolved_effect.pop('where_event_attached', False) and context.get('event_card_instance_id'):
                resolved_effect['where'] = {
                    **copy.deepcopy(resolved_effect.get('where') or {}),
                    'attached_to': context.get('event_card_instance_id'),
                }
            self.engine.add_modifier({
                **resolved_effect, 'controller': controller,
                'player': target if target in PLAYER_SIDES else controller,
                'source': context.get('source_card_instance_id'),
                'duration': effect.get('duration') or 'battle',
            })
        elif op in {'prevent', 'negate', 'replace'}:
            resolved_effect = copy.deepcopy(effect)
            selection_key = str(resolved_effect.get('selection_key') or '')
            if selection_key and not resolved_effect.get('where'):
                selected_ids = [
                    str(instance_id) for instance_id in (
                        context.get(selection_key) or []
                    ) if str(instance_id or '')
                ]
                # A prevention tied to "the card moved by this effect" must
                # follow the actual successful operation result, not merely
                # the original choice.  No successful cards means no rule.
                if not selected_ids:
                    return
                resolved_effect['where'] = {
                    'instance_id': selected_ids,
                }
            if resolved_effect.pop('unless_event_attached', False):
                host_id = context.get('event_card_instance_id')
                if host_id:
                    attached_condition = {
                        'op': 'not_equals',
                        'left': 'context.source_card.attached_to',
                        'right': host_id,
                    }
                    if resolved_effect.get('condition'):
                        attached_condition = {
                            'op': 'all',
                            'conditions': [
                                copy.deepcopy(resolved_effect['condition']),
                                attached_condition,
                            ],
                        }
                    resolved_effect['condition'] = attached_condition
            if (
                resolved_effect.get('scope') == 'source_card'
                and not resolved_effect.get('where')
                and context.get('source_card_instance_id')
            ):
                resolved_effect['where'] = {
                    'instance_id': context.get('source_card_instance_id'),
                }
            elif (
                resolved_effect.get('scope') == 'opponent_card'
                and not resolved_effect.get('where')
                and (context.get('opponent_card') or {}).get('instance_id')
            ):
                resolved_effect['where'] = {
                    'instance_id': context['opponent_card']['instance_id'],
                }
            self.state['engine'].setdefault('replacements', []).append({
                **resolved_effect, 'controller': controller,
                'player': target if target in PLAYER_SIDES else controller,
                'source': context.get('source_card_instance_id'),
                **(
                    {'remaining_uses': int(resolved_effect['max_uses'])}
                    if resolved_effect.get('max_uses') is not None else {}
                ),
            })
        elif op == 'static_rule':
            # The executable behavior lives in validated definition metadata
            # (for example combo_rules, defense_rules, or play_costs).
            pass
        elif op == 'log':
            self.engine.emit('effect_log', controller, {'text': str(effect.get('text') or '')[:300]})
        elif op == 'set_usage_limit':
            scope = str(effect.get('scope') or 'game')
            key = str(effect.get('key') or context.get('ability_id') or '')
            self.state['engine'].setdefault('usage', {}).setdefault(scope, {}).setdefault(controller, {})[key] = int(effect.get('value', 1))
        elif op == 'set_memory':
            side = target if target in PLAYER_SIDES else controller
            key = str(effect.get('key') or '')
            resolved = resolve_value(effect.get('value'), self.state, context)
            self.state['engine'].setdefault('effect_memory', {}).setdefault(
                side, {},
            )[key] = copy.deepcopy(resolved)
            self.engine.emit(
                'effect_memory_set', side,
                {
                    'key': key, 'value': copy.deepcopy(resolved),
                    'source': context.get('source_card_instance_id'),
                },
                visibility=(
                    effect.get('visibility')
                    or context.get('ability_visibility', 'public')
                ),
            )
        elif op in {'create_token', 'delete_token'}:
            if op == 'create_token':
                repeat = int(resolve_value(effect.get('repeat', 1), self.state, context) or 0)
                token_owner = target if target in PLAYER_SIDES else controller
                token_zone = effect.get('zone') or 'passive'
                maximum = effect.get('max_zone_count')
                token_key = str(
                    (effect.get('card') or {}).get('token_key') or ''
                )
                for _index in range(max(0, min(repeat, 50))):
                    if maximum is not None:
                        matching = [
                            card for card in self.engine._zone(
                                token_owner, token_zone,
                            )
                            if (
                                not token_key
                                or str(card.get('token_key') or '') == token_key
                            )
                        ]
                        if len(matching) >= int(maximum):
                            self.engine.emit(
                                'token_creation_skipped', token_owner, {
                                    'token_key': token_key,
                                    'zone': token_zone,
                                    'maximum': int(maximum),
                                    'source': context.get(
                                        'source_card_instance_id'
                                    ),
                                },
                            )
                            break
                    self.engine.create_token(token_owner, effect)
            else:
                card_ids = (
                    list(context.get(effect.get('selection_key')) or [])
                    if effect.get('selection_key')
                    else self.engine.select_cards(effect.get('selector'), context)
                )
                deleted_ids = []
                for card_id in card_ids:
                    if self.engine.delete_token(card_id) is not None:
                        deleted_ids.append(card_id)
                if effect.get('result_key'):
                    context[str(effect['result_key'])] = deleted_ids
        else:
            raise EffectResolutionError(f'지원하지 않는 효과 명령입니다: {op}')

    def continue_choice(self, continuation, selected):
        context = copy.deepcopy(continuation.get('context') or {})
        context[continuation.get('selection_key') or 'selected'] = list(selected or [])
        self.execute_effects(continuation.get('effects') or [], context)
        deferred = self.state['engine'].pop('deferred_effects', [])
        for item in deferred:
            self.execute_effects(item.get('effects'), item.get('context') or {})
        return self.drain()

    def begin_hand_parity_guess(self, effect, context):
        selector = effect.get('selector') or {
            'kind': 'card', 'player': {'opponent': True}, 'zones': ['hand'],
        }
        options = self.engine.selector_options(selector, context)
        if not options:
            self.engine.emit('card_guess_skipped', context.get('controller'), {
                'reason': 'no_opponent_hand',
                'source': context.get('source_card_instance_id'),
            })
            return
        self.engine.create_decision(
            owner=context.get('controller'), kind='hand_guess_card',
            prompt='종류를 추측할 상대 패 1장을 선택하세요.',
            options=options, minimum=1, maximum=1, default=[],
            continuation={
                'type': 'hand_guess_card', 'effect': copy.deepcopy(effect),
                'context': copy.deepcopy(context),
            },
        )

    def continue_hand_guess_card(self, effect, context, card_instance_id):
        labels = {
            'odd': '홀수', 'even': '짝수',
            'attack': '공격 기술',
            'odd_attack': '홀수 속도 공격 기술',
            'even_attack': '짝수 속도 공격 기술',
            'defense': '수비 기술',
        }
        categories = self._effective_hand_guess_categories(effect, context)
        self.engine.create_decision(
            owner=context.get('controller'), kind='hand_guess_parity',
            prompt='선택한 카드의 종류를 선언하세요.',
            options=[{'id': item, 'label': labels[item]} for item in categories],
            minimum=1, maximum=1, default=[categories[0]],
            continuation={
                'type': 'hand_guess_parity', 'effect': copy.deepcopy(effect),
                'context': copy.deepcopy(context), 'card_instance_id': card_instance_id,
            },
        )

    def resolve_hand_parity_guess(self, effect, context, card_instance_id, guess):
        controller = context.get('controller')
        selected = self.engine._find_card(card_instance_id)
        if not selected:
            raise EffectResolutionError('홀짝 확인 대상 카드를 찾을 수 없습니다.')
        speed = selected.get('frame')
        numeric_speed = None
        try:
            numeric_speed = int(speed)
        except (TypeError, ValueError):
            pass
        card_type = str(selected.get('type') or '')
        is_attack = '공격' in card_type
        is_defense = '수비' in card_type
        correct = bool(
            (guess == 'attack' and is_attack)
            or (guess == 'defense' and is_defense)
            or (
                numeric_speed is not None
                and (
                    (guess == 'odd' and numeric_speed % 2 == 1)
                    or (guess == 'even' and numeric_speed % 2 == 0)
                    or (guess == 'odd_attack' and is_attack and numeric_speed % 2 == 1)
                    or (guess == 'even_attack' and is_attack and numeric_speed % 2 == 0)
                )
            )
        )
        inspected = self.engine._private_action_card(selected)
        inspected.update({
            'instance_id': selected.get('instance_id'),
            'owner': selected.get('owner'),
            'face_up': True, 'hidden': False,
        })
        self.engine.emit('card_inspected', controller, {
            'card_instance_id': card_instance_id, 'card': inspected,
            'source': context.get('source_card_instance_id'),
        })
        payload = {
            'controller': controller, 'guess': guess, 'correct': correct,
            'guess_correct': correct,
            'card_instance_id': card_instance_id, 'card': inspected,
            'guess_source_character': (context.get('source_card') or {}).get('character_key'),
            'source_card_instance_id': context.get('source_card_instance_id'),
            'source_card': copy.deepcopy(context.get('source_card')),
        }
        self.engine.emit('card_guess_resolved', controller, payload)
        self.engine._fire('card_guess_resolved', payload)
        branch_context = {
            **copy.deepcopy(context), 'guess_correct': correct,
            'guessed_card': copy.deepcopy(selected),
            'guessed_card_instance_id': card_instance_id,
        }
        self.execute_effects(
            effect.get('on_correct') if correct else effect.get('on_wrong'),
            branch_context,
        )
        attempt = max(1, int(context.get('hand_guess_attempt') or 1))
        maximum = max(1, int(effect.get('max_attempts') or 1))
        if (
            (
                effect.get('repeat_always')
                or (correct and effect.get('repeat_on_correct'))
            )
            and attempt < maximum
            and not self.engine.is_waiting
        ):
            self.engine.create_decision(
                owner=controller, kind='hand_guess_repeat',
                prompt='추측 효과를 다시 사용하시겠습니까?',
                options=[
                    {'id': 'accept', 'label': '다시 사용'},
                    {'id': 'decline', 'label': '종료'},
                ],
                minimum=1, maximum=1, default=['decline'],
                continuation={
                    'type': 'hand_guess_repeat',
                    'effect': copy.deepcopy(effect),
                    'context': copy.deepcopy(context),
                    'attempt': attempt,
                },
            )

    def continue_hand_guess_repeat(self, effect, context, attempt, accepted):
        if not accepted:
            return
        repeated_context = copy.deepcopy(context)
        repeated_context['hand_guess_attempt'] = max(1, int(attempt or 1)) + 1
        self.begin_hand_parity_guess(effect, repeated_context)

    def _effective_hand_guess_categories(self, effect, context):
        categories = list(effect.get('categories') or ['odd', 'even'])
        controller = context.get('controller')
        source_id = (
            context.get('source_card_instance_id')
            or (context.get('source_card') or {}).get('instance_id')
        )
        for modifier in self.state['engine'].get('modifiers') or []:
            if modifier.get('op') != 'modify_hand_guess_categories':
                continue
            player = modifier.get('player') or modifier.get('controller')
            if player in PLAYER_SIDES and player != controller:
                continue
            where = modifier.get('where') or {}
            if where.get('instance_id') != source_id:
                continue
            modified = modifier.get('categories')
            if isinstance(modified, list) and modified:
                return list(modified)
        return categories
