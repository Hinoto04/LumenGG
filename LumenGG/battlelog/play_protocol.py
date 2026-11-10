"""Client contract for the automatic-mode game client (``play/``).

The envelope itself is produced by ``serialize_simulator_session``; this
module only pins its version and checks its shape so the Python side and the
TypeScript types in ``play/src/protocol.ts`` cannot drift apart silently.
See ``docs/PLAY_PROTOCOL.md``.
"""

from .game.engine import ACTION_UI_KINDS, ACTION_UI_DEFAULT_KIND

PLAY_PROTOCOL_VERSION = 1

PLAY_ROLES = ('p1', 'p2', 'viewer')
PLAY_SIDES = ('p1', 'p2')
PLAY_ZONES = (
    'character', 'passive', 'battle', 'list', 'hand', 'side', 'break',
    'lumen', 'ultimate',
)
ACTION_UI_KIND_VALUES = frozenset({*ACTION_UI_KINDS.values(), ACTION_UI_DEFAULT_KIND})
HIDDEN_CARD_FORBIDDEN_FIELDS = (
    'instance_id', 'card_id', 'code', 'type', 'frame', 'damage', 'pos',
    'special', 'text', 'detail_text', 'img', 'img_sm',
)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _slot(state, ref):
    players = (state or {}).get('players') or {}
    cards = ((players.get(ref.get('owner')) or {}).get('zones') or {}).get(ref.get('zone'))
    index = ref.get('index')
    if not isinstance(cards, list) or not _is_int(index) or not 0 <= index < len(cards):
        return None
    return cards[index]


def _check_card_ref(errors, where, state, ref):
    if not isinstance(ref, dict):
        errors.append(f'{where}: card ref must be an object')
        return
    if ref.get('owner') not in PLAY_SIDES or ref.get('zone') not in PLAY_ZONES:
        errors.append(f'{where}: invalid owner/zone {ref.get("owner")}/{ref.get("zone")}')
        return
    slot = _slot(state, ref)
    if slot is None:
        errors.append(f'{where}: no card at {ref.get("owner")}.{ref.get("zone")}[{ref.get("index")}]')
        return
    if slot.get('hidden'):
        if 'instance_id' in ref:
            errors.append(f'{where}: ref exposes instance_id of a hidden card')
    elif ref.get('instance_id') != slot.get('instance_id'):
        errors.append(
            f'{where}: ref instance_id {ref.get("instance_id")} does not match '
            f'slot {slot.get("instance_id")}'
        )


def _check_state(errors, state):
    if not isinstance(state, dict):
        errors.append('state must be an object')
        return
    if not _is_int(state.get('turn')):
        errors.append('state.turn must be an integer')
    if not isinstance(state.get('phase'), str):
        errors.append('state.phase must be a string')
    players = state.get('players')
    if not isinstance(players, dict):
        errors.append('state.players must be an object')
        return
    for side in PLAY_SIDES:
        player = players.get(side)
        if not isinstance(player, dict):
            errors.append(f'state.players.{side} is missing')
            continue
        for key in ('hp', 'fp'):
            if not isinstance(player.get(key), (int, float)) or isinstance(player.get(key), bool):
                errors.append(f'state.players.{side}.{key} must be a number')
        if not isinstance(player.get('passive_state', {}), dict):
            errors.append(f'state.players.{side}.passive_state must be an object')
        zones = player.get('zones')
        if not isinstance(zones, dict):
            errors.append(f'state.players.{side}.zones must be an object')
            continue
        for zone in PLAY_ZONES:
            cards = zones.get(zone)
            if not isinstance(cards, list):
                errors.append(f'state.players.{side}.zones.{zone} must be a list')
                continue
            for index, card in enumerate(cards):
                where = f'state.players.{side}.zones.{zone}[{index}]'
                if not isinstance(card, dict) or not isinstance(card.get('hidden'), bool):
                    errors.append(f'{where}: card.hidden must be a boolean')
                    continue
                if card['hidden']:
                    leaked = [field for field in HIDDEN_CARD_FORBIDDEN_FIELDS if field in card]
                    if leaked:
                        errors.append(f'{where}: hidden card exposes {", ".join(leaked)}')
                elif not card.get('instance_id'):
                    errors.append(f'{where}: visible card needs instance_id')
    if not isinstance(state.get('engine'), dict):
        errors.append('state.engine must be an object')


def _check_actions(errors, envelope, state):
    actions = envelope.get('legal_actions')
    if not isinstance(actions, list):
        errors.append('legal_actions must be a list')
        return
    for index, action in enumerate(actions):
        where = f'legal_actions[{index}]'
        if not isinstance(action, dict):
            errors.append(f'{where} must be an object')
            continue
        for key in ('action_id', 'type', 'label'):
            if not isinstance(action.get(key), str) or not action.get(key):
                errors.append(f'{where}.{key} must be a non-empty string')
        if not isinstance(action.get('payload'), dict):
            errors.append(f'{where}.payload must be an object')
        ui = action.get('ui')
        if not isinstance(ui, dict):
            errors.append(f'{where}.ui must be an object')
            continue
        if ui.get('kind') not in ACTION_UI_KIND_VALUES:
            errors.append(f'{where}.ui.kind is invalid: {ui.get("kind")}')
        if not isinstance(ui.get('cards'), list):
            errors.append(f'{where}.ui.cards must be a list')
        else:
            for card_index, ref in enumerate(ui['cards']):
                _check_card_ref(errors, f'{where}.ui.cards[{card_index}]', state, ref)
            if ui.get('kind') == 'card' and not ui['cards']:
                errors.append(f'{where}: card action is not bound to any card')
        _check_options(errors, f'{where}.options', state, action.get('options'))


def _check_options(errors, where, state, options):
    if options is None:
        return
    if not isinstance(options, list):
        errors.append(f'{where} must be a list')
        return
    for index, option in enumerate(options):
        if not isinstance(option, dict) or not isinstance(option.get('id'), str):
            errors.append(f'{where}[{index}].id must be a string')
            continue
        ui = option.get('ui')
        if not isinstance(ui, dict):
            errors.append(f'{where}[{index}].ui must be an object')
        elif 'card' in ui:
            _check_card_ref(errors, f'{where}[{index}].ui.card', state, ui['card'])


def _check_events(errors, events):
    if not isinstance(events, list):
        errors.append('events must be a list')
        return
    previous = None
    for index, event in enumerate(events):
        where = f'events[{index}]'
        if not isinstance(event, dict):
            errors.append(f'{where} must be an object')
            continue
        if not isinstance(event.get('type'), str):
            errors.append(f'{where}.type must be a string')
        if not isinstance(event.get('payload'), dict):
            errors.append(f'{where}.payload must be an object')
        seq = event.get('seq')
        if not _is_int(seq) or (previous is not None and seq <= previous):
            errors.append(f'{where}.seq must be an increasing integer')
        previous = seq if _is_int(seq) else previous
        if event.get('type') == 'private_event':
            payload = event.get('payload') or {}
            if payload.get('redacted') is not True:
                errors.append(f'{where}: private_event payload must be redacted')
            for key in ('card_instance_id', 'card_id', 'card_code', 'card_label', 'reason'):
                if key in payload:
                    errors.append(f'{where}: private_event leaks {key}')


def validate_play_envelope(envelope):
    """Return a list of contract violations (empty when the envelope is valid)."""
    errors = []
    if not isinstance(envelope, dict):
        return ['envelope must be an object']
    if envelope.get('protocol_version') != PLAY_PROTOCOL_VERSION:
        errors.append(f'protocol_version must be {PLAY_PROTOCOL_VERSION}')
    if envelope.get('mode') != 'automatic':
        errors.append('mode must be automatic')
    if envelope.get('role') not in PLAY_ROLES:
        errors.append(f'role is invalid: {envelope.get("role")}')
    for key in ('id', 'version', 'event_count'):
        if not _is_int(envelope.get(key)):
            errors.append(f'{key} must be an integer')
    state = envelope.get('state')
    _check_state(errors, state)
    _check_actions(errors, envelope, state if isinstance(state, dict) else {})
    decision = envelope.get('pending_decision')
    if decision is not None:
        if not isinstance(decision, dict) or decision.get('owner') not in PLAY_SIDES:
            errors.append('pending_decision.owner must be p1 or p2')
        else:
            _check_options(
                errors, 'pending_decision.options',
                state if isinstance(state, dict) else {}, decision.get('options'),
            )
    status = envelope.get('engine_status')
    if not isinstance(status, dict) or not isinstance(status.get('status'), str):
        errors.append('engine_status.status must be a string')
    if 'events' in envelope:
        _check_events(errors, envelope['events'])
    return errors
