import copy
import secrets
import uuid
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from card.models import Card, Character
from card.search import card_matches_search, card_matches_search_exact
from common.language import (
    DEFAULT_LANGUAGE,
    game_term,
    normalize_language,
    translated_card_field,
    translated_character_field,
    ui_text,
)
from common.localization import render_localized_markup
from deck.models import CardInDeck, Deck

from .models import LumenSimulatorSession
from .game.card_identity import is_passive_card, normalize_passive_card
from .presence import simulator_presence_counts
from .services import _passive_ui, character_hand_table, hand_limit_for_hp, initial_hp_for_character, initial_passive_state_for_character


SIMULATOR_SESSION_LIFETIME = timedelta(hours=1)
SIMULATOR_DEFAULT_EVENT_LIMIT = 150
SIMULATOR_MAX_EVENT_LIMIT = 300
SIMULATOR_STORED_EVENT_LIMIT = 800
SIMULATOR_STORED_EVENT_KEEP = 500
SIMULATOR_HAND_SHUFFLE_COOLDOWN = timedelta(seconds=3)
PLAYER_SIDES = ('p1', 'p2')
PHASES = ('lumen', 'ready', 'battle', 'get', 'recovery')
PHASE_LABELS = {
    'lumen': 'Lumen',
    'ready': 'Ready',
    'battle': 'Battle',
    'get': 'Get',
    'recovery': 'Recovery',
}
ZONES = ('character', 'passive', 'battle', 'list', 'hand', 'side', 'break', 'lumen', 'ultimate')
ZONE_LABELS = {
    'character': 'Character Zone',
    'passive': 'Passive Zone',
    'battle': 'Battle Zone',
    'list': 'List',
    'hand': 'Hand',
    'side': 'Side Deck',
    'break': 'Break Zone',
    'lumen': 'Lumen Zone',
    'ultimate': 'Ultimate Zone',
}
PUBLIC_ON_ENTER_ZONES = {'character', 'passive', 'list', 'break', 'ultimate'}
PRIVATE_ON_ENTER_ZONES = {'hand', 'side', 'lumen'}
VISIBILITY_TOGGLE_ZONES = {'hand', 'side', 'battle', 'lumen'}
CROSS_PLAYER_ZONES = {'battle', 'lumen'}
YOHAN_DECLARATION_LABELS = {
    'odd': '홀수',
    'even': '짝수',
    'attack': '공격',
    'defense': '수비',
}
SIMULATOR_SIGNAL_LABELS = {
    'effect': '효과 발동',
    'combo': '콤보 타임',
    'catch': '캐치 타임',
}
CARD_METADATA_FIELDS = (
    'name', 'original_name', 'code', 'type', 'original_type', 'frame',
    'damage', 'pos', 'body', 'special', 'hit', 'guard', 'counter', 'g_top',
    'g_mid', 'g_bot', 'text', 'original_text', 'detail_text',
    'original_detail_text', 'ultimate', 'character_id', 'img', 'img_sm',
)


def simulator_queryset():
    return LumenSimulatorSession.objects.select_related('ruleset_release', 'ai_policy')


def simulator_session_expires_at(now=None):
    return (now or timezone.now()) + SIMULATOR_SESSION_LIFETIME


def generate_token():
    return secrets.token_urlsafe(32)


def _unique_token(field_name):
    while True:
        token = generate_token()
        if not LumenSimulatorSession.objects.filter(**{field_name: token}).exists():
            return token


def _card_image(card):
    return card.img_mid or card.img_sm or card.img


def _card_metadata(card):
    image = _card_image(card)
    card_type = '특성' if is_passive_card(card) else card.type
    return {
        'card_id': card.id,
        'name': card.name,
        'original_name': card.name,
        'code': card.code,
        'type': card_type,
        'original_type': card_type,
        'frame': card.frame,
        'damage': card.damage,
        'pos': card.pos,
        'body': card.body,
        'special': card.special,
        'hit': card.hit,
        'guard': card.guard,
        'counter': card.counter,
        'g_top': card.g_top,
        'g_mid': card.g_mid,
        'g_bot': card.g_bot,
        'text': card.text,
        'original_text': card.text,
        'detail_text': card.detail_text,
        'original_detail_text': card.detail_text,
        'ultimate': card.ultimate,
        'character_id': card.character_id,
        'img': image,
        'img_sm': card.img_sm or image,
    }


def _card_payload(card, owner, instance_id, face_up=True, kind='card'):
    return {
        'instance_id': instance_id,
        'kind': kind,
        'owner': owner,
        'card_id': card.id,
        **_card_metadata(card),
        'face_up': bool(face_up),
    }


def _character_payload(character, owner):
    return {
        'instance_id': f'{owner}-character',
        'kind': 'character',
        'owner': owner,
        'character_id': character.id,
        'name': character.name,
        'img': character.body_img or character.sd_img or character.img,
        'icon_img': character.icon_img,
        'color': character.color,
        'face_up': True,
    }


def _initial_turn_changes():
    return {
        side: {'hp': 0, 'fp': 0, 'hp_changed': False, 'fp_changed': False}
        for side in PLAYER_SIDES
    }


def _initial_counter_revisions():
    return {
        side: {'hp': 0, 'fp': 0}
        for side in PLAYER_SIDES
    }


def _player_display_name(side, name, character):
    fallback = '플레이어1' if side == 'p1' else '플레이어2'
    base_name = (name or '').strip() or fallback
    character_suffix = f'({character.name})'
    if base_name.endswith(character_suffix):
        return base_name
    if base_name.endswith(')') and '(' in base_name:
        base_name = base_name[:base_name.rfind('(')].strip() or fallback
    return f'{base_name}{character_suffix}'


def _player_skeleton(side, name, deck):
    character = deck.character
    initial_hp = initial_hp_for_character(character)
    return {
        'name': _player_display_name(side, name, character),
        'deck_id': deck.id,
        'deck_name': deck.name,
        'character': {
            'id': character.id,
            'name': character.name,
            'img': character.body_img or character.sd_img or character.img,
            'icon_img': character.icon_img,
            'color': character.color,
            'hand_table': character_hand_table(character),
            'passive_ui': _passive_ui(character, context='simulator'),
        },
        'initial_hp': initial_hp,
        'hp': initial_hp,
        'fp': 0,
        'passive_state': initial_passive_state_for_character(character),
        'zones': {zone: [] for zone in ZONES},
    }


def _add_deck_cards_to_player(player, side, deck):
    player['zones']['character'].append(_character_payload(deck.character, side))

    passive_cards = (
        Card.objects
        .filter(Q(character=deck.character), Q(type='특성') | Q(code__icontains='PS'))
        .order_by('id')
        .distinct()
    )
    for index, card in enumerate(passive_cards, start=1):
        player['zones']['passive'].append(
            _card_payload(card, side, f'{side}-passive-{index}', face_up=True)
        )

    entries = (
        CardInDeck.objects
        .filter(deck=deck)
        .select_related('card', 'card__character')
        .order_by('card__ultimate', 'card__type', 'card__frame', 'card__id')
    )
    next_index = 1
    for entry in entries:
        card = entry.card
        # Traits are character fixtures, not Technique-deck copies.  Even a
        # legacy/misclassified PS row stays in the Passive Zone exactly once.
        if is_passive_card(card):
            continue
        count = max(0, int(entry.count or 0))
        hand_count = min(count, max(0, int(entry.hand or 0)))
        side_count = min(count - hand_count, max(0, int(entry.side or 0)))
        for copy_index in range(count):
            if card.ultimate:
                zone = 'ultimate'
                face_up = True
            elif copy_index < hand_count:
                zone = 'hand'
                face_up = False
            elif copy_index < hand_count + side_count:
                zone = 'side'
                face_up = False
            else:
                zone = 'list'
                face_up = True

            player['zones'][zone].append(
                _card_payload(card, side, f'{side}-card-{next_index}', face_up=face_up)
            )
            next_index += 1


def _initial_state(player1_name, player2_name, player1_deck, player2_deck):
    first_player = secrets.choice(PLAYER_SIDES)
    state = {
        'turn': 1,
        'phase': 'lumen',
        'status': {
            side: {'requested': side == first_player, 'done': False}
            for side in PLAYER_SIDES
        },
        'priority_player': first_player,
        'timer': {
            'started_at': None,
            'duration_seconds': 10,
        },
        'turn_changes': _initial_turn_changes(),
        'counter_revisions': _initial_counter_revisions(),
        'players': {
            'p1': _player_skeleton('p1', player1_name, player1_deck),
            'p2': _player_skeleton('p2', player2_name, player2_deck),
        },
    }
    _add_deck_cards_to_player(state['players']['p1'], 'p1', player1_deck)
    _add_deck_cards_to_player(state['players']['p2'], 'p2', player2_deck)
    return state


def can_view_deck_for_simulator(user, deck):
    visibility = Deck.VISIBILITY_PRIVATE if deck.private else deck.visibility
    if visibility in (Deck.VISIBILITY_PUBLIC, Deck.VISIBILITY_UNLISTED):
        return True
    if not user or not user.is_authenticated:
        return False
    if deck.author_id == user.id or user.is_staff:
        return True
    try:
        from tournament.models import Tournament, TournamentDeckSubmission
    except ImportError:
        return False
    return TournamentDeckSubmission.objects.filter(
        deck=deck,
        participant__tournament__organizer=user,
    ).exists() or Tournament.objects.filter(
        organizer=user,
        participants__deck=deck,
    ).exists()


def create_simulator_session(
    player1_name,
    player2_name,
    player1_deck,
    player2_deck,
    *,
    mode='manual',
    player1_controller='human',
    player2_controller='human',
):
    controllers = {player1_controller, player2_controller}
    if not controllers <= {LumenSimulatorSession.CONTROLLER_HUMAN, LumenSimulatorSession.CONTROLLER_AI}:
        raise ValueError('플레이어 제어 방식이 올바르지 않습니다.')
    if LumenSimulatorSession.CONTROLLER_AI in controllers and mode != LumenSimulatorSession.MODE_AUTOMATIC:
        raise ValueError('AI 대전은 자동 규칙 모드에서만 사용할 수 있습니다.')
    if player1_controller == LumenSimulatorSession.CONTROLLER_AI and not player1_name:
        player1_name = 'Lumen AI'
    if player2_controller == LumenSimulatorSession.CONTROLLER_AI and not player2_name:
        player2_name = 'Lumen AI'
    initial_state = _initial_state(player1_name, player2_name, player1_deck, player2_deck)
    ruleset_release = None
    ai_policy = None
    view_token = _unique_token('view_token')
    if mode == LumenSimulatorSession.MODE_AUTOMATIC:
        from .automatic_services import (
            active_ai_policy,
            ai_policy_payload,
            automatic_mode_release,
            advance_ai_session,
            ensure_automatic_decks,
            initialize_automatic_document,
        )

        ruleset_release = automatic_mode_release()
        if not ruleset_release:
            raise ValueError('검증된 전체 카드 규칙 릴리스가 없어 자동 모드를 시작할 수 없습니다.')
        ensure_automatic_decks(
            player1_deck, player2_deck, ruleset=ruleset_release.snapshot,
        )
        document = initialize_automatic_document(
            initial_state,
            ruleset_release,
            seed=f'{view_token}:{ruleset_release.content_hash}',
        )
        if LumenSimulatorSession.CONTROLLER_AI in controllers:
            ai_policy = active_ai_policy()
            if not ai_policy:
                raise ValueError('검증된 활성 AI 정책이 없어 AI 대전을 시작할 수 없습니다.')
            document['ai_policy'] = ai_policy_payload(ai_policy)
    else:
        mode = LumenSimulatorSession.MODE_MANUAL
        document = {
            'initial_state': copy.deepcopy(initial_state),
            'state': copy.deepcopy(initial_state),
            'events': [],
        }
    session = LumenSimulatorSession.objects.create(
        view_token=view_token,
        player1_token=_unique_token('player1_token'),
        player2_token=_unique_token('player2_token'),
        player1_name=initial_state['players']['p1']['name'],
        player2_name=initial_state['players']['p2']['name'],
        player1_controller=player1_controller,
        player2_controller=player2_controller,
        mode=mode,
        ruleset_release=ruleset_release,
        ai_policy=ai_policy,
        document=document,
        expires_at=simulator_session_expires_at(),
    )
    if LumenSimulatorSession.CONTROLLER_AI in controllers:
        session = advance_ai_session(session)
    return session


def simulator_session_is_expired(session):
    return bool(session.expires_at and session.expires_at <= timezone.now())


def role_for_token(session, seat='', token=''):
    if seat == 'p1' and token and secrets.compare_digest(token, session.player1_token):
        return 'p1'
    if seat == 'p2' and token and secrets.compare_digest(token, session.player2_token):
        return 'p2'
    return 'viewer'


def _document(session):
    document = copy.deepcopy(session.document or {})
    initial_state = document.get('initial_state')
    state = document.get('state')
    events = document.get('events')
    if not isinstance(initial_state, dict) or not isinstance(state, dict) or not isinstance(events, list):
        initial_state = {'turn': 1, 'phase': 'lumen', 'status': {}, 'timer': {}, 'players': {}}
        document = {'initial_state': initial_state, 'state': copy.deepcopy(initial_state), 'events': []}
    return document


def _document_for_read(session):
    document = session.document or {}
    initial_state = document.get('initial_state')
    state = document.get('state')
    events = document.get('events')
    if not isinstance(initial_state, dict) or not isinstance(state, dict) or not isinstance(events, list):
        initial_state = {'turn': 1, 'phase': 'lumen', 'status': {}, 'timer': {}, 'players': {}}
        return {'initial_state': initial_state, 'state': copy.deepcopy(initial_state), 'events': []}
    return document


def _archived_event_count(document):
    try:
        return max(0, int((document or {}).get('archived_event_count') or 0))
    except (TypeError, ValueError):
        return 0


def _make_event(event_type, actor, payload):
    return {
        'id': str(uuid.uuid4()),
        'type': event_type,
        'actor': actor,
        'payload': payload,
        'created_at': timezone.now().isoformat(),
    }


def _reset_status(state):
    state.setdefault('status', {})
    for side in PLAYER_SIDES:
        state['status'][side] = {'requested': False, 'done': False}


def _priority_score(state, side):
    player = ((state.get('players') or {}).get(side) or {})
    zones = player.get('zones') or {}
    return (
        int(player.get('fp') or 0),
        int(player.get('hp') or 0),
        len(zones.get('hand') or []),
    )


def _priority_player(state):
    p1_score = _priority_score(state, 'p1')
    p2_score = _priority_score(state, 'p2')
    if p1_score > p2_score:
        return 'p1'
    if p2_score > p1_score:
        return 'p2'
    last_priority = state.get('priority_player')
    return last_priority if last_priority in PLAYER_SIDES else 'p1'


def _request_priority_for_phase(state):
    if state.get('phase') in ('ready', 'battle'):
        return None
    target = _priority_player(state)
    state['priority_player'] = target
    state.setdefault('status', {})
    for side in PLAYER_SIDES:
        state['status'][side] = {'requested': side == target, 'done': False}
    return target


def _ensure_turn_changes(state):
    changes = state.setdefault('turn_changes', {})
    for side in PLAYER_SIDES:
        side_changes = changes.setdefault(side, {})
        side_changes['hp'] = int(side_changes.get('hp') or 0)
        side_changes['fp'] = int(side_changes.get('fp') or 0)
        side_changes['hp_changed'] = bool(side_changes.get('hp_changed'))
        side_changes['fp_changed'] = bool(side_changes.get('fp_changed'))
    return changes


def _record_turn_change(state, side, kind, amount):
    if side not in PLAYER_SIDES or kind not in ('hp', 'fp') or not amount:
        return
    changes = _ensure_turn_changes(state)
    changes[side][kind] = int(changes[side].get(kind) or 0) + int(amount)
    changes[side][f'{kind}_changed'] = True


def _reset_turn_changes(state):
    state['turn_changes'] = _initial_turn_changes()


def _ensure_counter_revisions(state):
    revisions = state.setdefault('counter_revisions', {})
    for side in PLAYER_SIDES:
        side_revisions = revisions.setdefault(side, {})
        side_revisions['hp'] = int(side_revisions.get('hp') or 0)
        side_revisions['fp'] = int(side_revisions.get('fp') or 0)
    return revisions


def _advance_counter_revision(state, payload, target, kind):
    revisions = _ensure_counter_revisions(state)
    current = int(revisions[target].get(kind) or 0)
    if 'base_revision' in payload:
        try:
            base_revision = int(payload.get('base_revision'))
        except (TypeError, ValueError):
            raise ValueError('계산기 상태가 오래되었습니다.')
        if base_revision != current:
            raise ValueError('이미 다른 계산기 조작이 먼저 반영되었습니다.')
    else:
        base_revision = current
    revisions[target][kind] = current + 1
    payload['base_revision'] = base_revision
    payload['revision'] = revisions[target][kind]


def _start_battle_phase(state, payload=None):
    ready_cards = {}
    revealed_counts = {}
    revealed_cards = {side: [] for side in PLAYER_SIDES}
    for side, player in (state.get('players') or {}).items():
        if side not in PLAYER_SIDES:
            continue
        battle_cards = player.get('zones', {}).get('battle', [])
        ready_cards[side] = [
            card.get('instance_id')
            for card in battle_cards
            if card.get('instance_id')
        ]
        revealed_count = 0
        for card in battle_cards:
            if not bool(card.get('face_up')):
                revealed_count += 1
            revealed_cards[side].append({
                'card_instance_id': card.get('instance_id'),
                'card_id': card.get('card_id'),
                'card_label': _card_label(card),
                'owner': card.get('owner') or side,
            })
            card['face_up'] = True
            card['hidden'] = False
        revealed_counts[side] = revealed_count
    state['battle_phase_ready_cards'] = ready_cards
    if payload is not None:
        payload['battle_ready_cards'] = copy.deepcopy(ready_cards)
        payload['revealed_counts'] = revealed_counts
        payload['revealed_cards'] = revealed_cards


def _cleanup_battle_phase(state, payload=None):
    ready_map = state.get('battle_phase_ready_cards') or {}
    ready_ids = {
        str(instance_id)
        for instance_ids in ready_map.values()
        for instance_id in (instance_ids or [])
        if instance_id
    }
    moved_to_hand = {side: 0 for side in PLAYER_SIDES}
    moved_to_list = {side: 0 for side in PLAYER_SIDES}
    for zone_owner in PLAYER_SIDES:
        player = state.get('players', {}).get(zone_owner) or {}
        zones = player.setdefault('zones', {})
        battle_cards = list(zones.get('battle') or [])
        zones['battle'] = []
        for card in battle_cards:
            owner = card.get('owner') if card.get('owner') in PLAYER_SIDES else zone_owner
            owner_zones = state['players'][owner].setdefault('zones', {})
            if str(card.get('instance_id') or '') in ready_ids:
                card['face_up'] = False
                card['hidden'] = False
                owner_zones.setdefault('hand', []).append(card)
                moved_to_hand[owner] += 1
            else:
                _set_card_visibility_for_zone(card, 'list', state)
                owner_zones.setdefault('list', []).append(card)
                moved_to_list[owner] += 1
    for side in PLAYER_SIDES:
        for cards in state.get('players', {}).get(side, {}).get('zones', {}).values():
            for card in cards:
                card.pop('attached_to', None)
                card.pop('attachment_expires', None)
                card.pop('return_to_hand_on_attachment_expiry', None)
                card.pop('set_order', None)
    state.pop('battle_phase_ready_cards', None)
    if payload is not None:
        payload['battle_cleanup'] = {
            'hand': moved_to_hand,
            'list': moved_to_list,
        }


def _hide_all_hands(state, payload=None):
    counts = {side: 0 for side in PLAYER_SIDES}
    for side in PLAYER_SIDES:
        hand = state.get('players', {}).get(side, {}).get('zones', {}).get('hand', [])
        for card in hand:
            if card.get('kind') == 'character':
                continue
            card['face_up'] = False
            card['hidden'] = False
            counts[side] += 1
    if payload is not None:
        payload['hidden_hand_counts'] = counts


def _start_phase(state, phase, payload=None):
    previous_phase = state.get('phase')
    state['phase'] = phase
    _reset_status(state)
    if phase == 'ready':
        if previous_phase != 'ready':
            state['cmyk_ready_staged_cards'] = _collect_cmyk_ready_staged_cards(state)
            state['cmyk_ready_host_cards'] = {}
    else:
        state.pop('cmyk_ready_staged_cards', None)
        state.pop('cmyk_ready_host_cards', None)
    if phase == 'battle':
        _start_battle_phase(state, payload)
    return _request_priority_for_phase(state)


def _advance_phase(state, payload=None):
    current_phase = state.get('phase') if state.get('phase') in PHASES else 'lumen'
    from_turn = int(state.get('turn') or 1)
    if payload is not None:
        payload['from_phase'] = current_phase
        payload['from_turn'] = from_turn
    if current_phase == 'battle':
        _cleanup_battle_phase(state, payload)
    if current_phase == 'get':
        _hide_all_hands(state, payload)
    if current_phase == 'recovery':
        state['turn'] = int(state.get('turn') or 1) + 1
        _reset_turn_changes(state)
        priority = _start_phase(state, 'lumen', payload)
    else:
        next_index = min(PHASES.index(current_phase) + 1, len(PHASES) - 1)
        priority = _start_phase(state, PHASES[next_index], payload)
    if payload is not None:
        payload['to_phase'] = state.get('phase')
        payload['to_turn'] = int(state.get('turn') or 1)
        if priority:
            payload['priority_player'] = priority
    return priority


def _find_card_location(state, instance_id):
    for player_side, player in (state.get('players') or {}).items():
        for zone, cards in (player.get('zones') or {}).items():
            for index, card in enumerate(cards):
                if card.get('instance_id') == instance_id:
                    return player_side, zone, index, card
    return None, None, None, None


def _opponent_side(side):
    return 'p2' if side == 'p1' else 'p1'


def _character_name(state, side):
    return str((((state.get('players') or {}).get(side) or {}).get('character') or {}).get('name') or '')


def _require_character(state, side, *names):
    character_name = _character_name(state, side).casefold()
    if not character_name or not any(str(name).casefold() in character_name for name in names):
        raise PermissionDenied()


def _card_label(card):
    if card.get('name'):
        return card.get('name')
    card_id = card.get('card_id')
    if card_id:
        model_card = Card.objects.filter(id=card_id).only('name').first()
        if model_card:
            card['name'] = model_card.name
            return model_card.name
    return '카드'


def _card_name_contains(card, text):
    return str(text).casefold() in _card_label(card).casefold()


def _card_type(card):
    if card.get('type'):
        return str(card.get('type') or '')
    card_id = card.get('card_id')
    if card_id:
        model_card = Card.objects.filter(id=card_id).only('type').first()
        if model_card:
            card['type'] = model_card.type
            return str(model_card.type or '')
    return ''


def _is_attack_or_defense_card(card):
    card_type = _card_type(card)
    return '공격' in card_type or '수비' in card_type


def _is_technique_card(card):
    card_type = _card_type(card)
    return any(keyword in card_type for keyword in ('공격', '수비', '특수'))


def _card_character_id(card):
    character_id = card.get('character_id')
    if character_id:
        return character_id
    card_id = card.get('card_id')
    if not card_id:
        return None
    model_card = Card.objects.filter(id=card_id).only('character_id').first()
    if model_card:
        card['character_id'] = model_card.character_id
        return model_card.character_id
    return None


def _clear_attachment(card):
    card.pop('attached_to', None)
    card.pop('attachment_expires', None)
    card.pop('return_to_hand_on_attachment_expiry', None)
    card.pop('set_order', None)


def _collect_cmyk_ready_staged_cards(state):
    staged = {}
    for side in PLAYER_SIDES:
        if 'cmyk' not in _character_name(state, side).casefold():
            continue
        character_id = ((state.get('players', {}).get(side) or {}).get('character') or {}).get('id')
        candidates = []
        battle_cards = state['players'][side].get('zones', {}).get('battle', [])
        for card in battle_cards:
            if len(candidates) >= 3:
                break
            if card.get('owner') != side or card.get('face_up') or card.get('attached_to'):
                continue
            if not _is_technique_card(card) or _card_character_id(card) != character_id:
                continue
            if card.get('instance_id'):
                candidates.append(str(card.get('instance_id')))
        if candidates:
            staged[side] = candidates
    return staged


def _auto_attach_cmyk_ready_cards(state, payload, actor):
    if actor not in PLAYER_SIDES or state.get('phase') != 'ready':
        return
    if payload.get('to_player') != actor or payload.get('to_zone') != 'battle':
        return
    if payload.get('from_zone') == 'battle':
        return
    if (state.get('cmyk_ready_host_cards') or {}).get(actor):
        return

    staged_ids = list((state.get('cmyk_ready_staged_cards') or {}).get(actor) or [])
    if not staged_ids:
        return
    host_instance_id = str(payload.get('card_instance_id') or '')
    if not host_instance_id or host_instance_id in staged_ids:
        return
    host_player, host_zone, _, host = _find_card_location(state, host_instance_id)
    if (
        not host
        or host_player != actor
        or host_zone != 'battle'
        or host.get('owner') != actor
        or host.get('attached_to')
        or not _is_technique_card(host)
    ):
        return

    staged_id_set = set(staged_ids)
    character_id = (state['players'][actor].get('character') or {}).get('id')
    candidates = []
    for card in state['players'][actor].get('zones', {}).get('battle', []):
        if str(card.get('instance_id') or '') not in staged_id_set:
            continue
        if card.get('face_up') or card.get('attached_to') or card.get('owner') != actor:
            continue
        if not _is_technique_card(card) or _card_character_id(card) != character_id:
            continue
        candidates.append(card)
    if not candidates:
        return

    attached_ids = []
    for order, card in enumerate(candidates[:3], start=1):
        card['attached_to'] = host_instance_id
        card['attachment_expires'] = 'battle'
        card['return_to_hand_on_attachment_expiry'] = True
        card['set_order'] = order
        card['face_up'] = False
        card['hidden'] = False
        attached_ids.append(card.get('instance_id'))

    state.setdefault('cmyk_ready_host_cards', {})[actor] = host_instance_id
    payload['auto_attached_card_instance_ids'] = attached_ids
    payload['auto_attached_count'] = len(attached_ids)
    payload['auto_set_host_card_instance_id'] = host_instance_id


def _apply_attach_card(state, payload, actor):
    if actor not in PLAYER_SIDES:
        raise PermissionDenied()
    if state.get('phase') != 'ready':
        raise ValueError('CMYK 기술은 레디 페이즈에 세트할 수 있습니다.')
    _require_character(state, actor, 'CMYK')

    instance_id = str(payload.get('card_instance_id') or '')
    host_instance_id = str(payload.get('host_card_instance_id') or '')
    if not instance_id or not host_instance_id or instance_id == host_instance_id:
        raise ValueError('세트할 카드와 대상 기술이 올바르지 않습니다.')
    staged_ids = set((state.get('cmyk_ready_staged_cards') or {}).get(actor) or [])
    ready_host_id = (state.get('cmyk_ready_host_cards') or {}).get(actor)
    if staged_ids and instance_id not in staged_ids:
        raise ValueError('루멘 페이즈에 미리 둔 CMYK 기술만 세트할 수 있습니다.')
    if ready_host_id and host_instance_id != ready_host_id:
        raise ValueError('CMYK 기술은 레디 페이즈에 처음 올린 기술에 세트해야 합니다.')

    source_player, source_zone, _, card = _find_card_location(state, instance_id)
    host_player, host_zone, _, host = _find_card_location(state, host_instance_id)
    if not card or not host:
        raise ValueError('세트할 카드 또는 대상 기술을 찾을 수 없습니다.')
    if source_player != actor or host_player != actor or source_zone != 'battle' or host_zone != 'battle':
        raise ValueError('자신의 배틀 존에 있는 기술끼리만 세트할 수 있습니다.')
    if card.get('owner') != actor or host.get('owner') != actor:
        raise ValueError('자신이 소유한 기술끼리만 세트할 수 있습니다.')
    if not _is_technique_card(card) or not _is_technique_card(host):
        raise ValueError('기술 카드만 세트할 수 있습니다.')
    character_id = (state['players'][actor].get('character') or {}).get('id')
    if _card_character_id(card) != character_id:
        raise ValueError('CMYK 기술만 세트 카드로 사용할 수 있습니다.')
    if host.get('attached_to'):
        raise ValueError('다른 기술에 세트된 카드를 대상 기술로 사용할 수 없습니다.')
    if any(
        candidate.get('attached_to') == instance_id
        for candidate in state['players'][actor]['zones']['battle']
    ):
        raise ValueError('다른 카드가 세트된 기술을 다시 세트할 수 없습니다.')

    currently_attached = [
        candidate
        for cards in state['players'][actor]['zones'].values()
        for candidate in cards
        if candidate.get('attached_to')
    ]
    if not card.get('attached_to') and len(currently_attached) >= 3:
        raise ValueError('CMYK 기술은 3장까지만 세트할 수 있습니다.')

    next_order = max(
        (
            int(candidate.get('set_order') or 0)
            for candidate in currently_attached
            if candidate.get('attached_to') == host_instance_id
        ),
        default=0,
    ) + 1
    card['attached_to'] = host_instance_id
    card['attachment_expires'] = 'battle'
    card['return_to_hand_on_attachment_expiry'] = True
    card['set_order'] = next_order
    card['face_up'] = False
    card['hidden'] = False

    payload['owner'] = actor
    payload['card_instance_id'] = instance_id
    payload['host_card_instance_id'] = host_instance_id
    payload['card_label'] = _card_label(card)
    payload['host_card_label'] = _card_label(host)
    if card.get('card_id'):
        payload['card_id'] = card.get('card_id')
    if host.get('card_id'):
        payload['host_card_id'] = host.get('card_id')


def _set_card_visibility_for_zone(card, zone, state):
    if zone == 'hand' and state.get('phase') == 'get':
        card['face_up'] = True
        card['hidden'] = False
        return
    if zone in PUBLIC_ON_ENTER_ZONES:
        card['face_up'] = True
        return
    if zone in PRIVATE_ON_ENTER_ZONES:
        card['face_up'] = False
        return
    if zone == 'battle':
        card['face_up'] = state.get('phase') not in ('lumen', 'ready')


def _should_preserve_card_visibility(from_zone, to_zone):
    return from_zone in VISIBILITY_TOGGLE_ZONES and to_zone in VISIBILITY_TOGGLE_ZONES


def _was_public_in_zone(card, zone):
    return zone in PUBLIC_ON_ENTER_ZONES or bool(card.get('face_up'))


def _is_token_card(card):
    return card.get('kind') == 'token' or '토큰' in str(card.get('type') or '')


def _normalize_passive_zone_cards(state):
    """Repair legacy simulator documents using the printed PS code marker."""
    players = state.get('players') or {}
    relocated = {side: [] for side in PLAYER_SIDES}
    for container_side in PLAYER_SIDES:
        player = players.get(container_side) or {}
        zones = player.get('zones') or {}
        zones.setdefault('passive', [])
        for zone_name, cards in list(zones.items()):
            if not isinstance(cards, list):
                continue
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
        zones = (players.get(side) or {}).get('zones') or {}
        passive_zone = zones.setdefault('passive', [])
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
    return state


def _apply_move_card(state, payload, actor=None):
    _normalize_passive_zone_cards(state)
    instance_id = str(payload.get('card_instance_id') or '')
    to_zone = str(payload.get('to_zone') or '')
    to_player = str(payload.get('to_player') or '')
    if to_zone not in ZONES:
        raise ValueError('이동할 존이 올바르지 않습니다.')

    player_side, from_zone, index, card = _find_card_location(state, instance_id)
    if not card:
        raise ValueError('이동할 카드를 찾을 수 없습니다.')
    if card.get('kind') == 'character':
        raise ValueError('캐릭터 카드는 이동할 수 없습니다.')
    if is_passive_card(card):
        raise ValueError('PS 특성 카드는 패시브 존에서 이동할 수 없습니다.')

    owner = card.get('owner') or player_side
    target_player = to_player or owner
    if target_player not in PLAYER_SIDES:
        raise ValueError('이동할 플레이어가 올바르지 않습니다.')
    if target_player != owner and to_zone not in CROSS_PLAYER_ZONES:
        raise ValueError('상대 플레이어의 루멘 존 또는 배틀 존으로만 이동할 수 있습니다.')
    payload['owner'] = owner
    payload['card_label'] = _card_label(card)
    was_public = _was_public_in_zone(card, from_zone)
    preserve_attachment = (
        from_zone == to_zone
        or (
            state.get('phase') == 'battle'
            and from_zone == 'battle'
            and to_zone == 'list'
        )
    )
    if not preserve_attachment:
        _clear_attachment(card)
    state['players'][player_side]['zones'][from_zone].pop(index)
    if _is_token_card(card) and to_zone == 'break':
        payload['from_player'] = player_side
        payload['from_zone'] = from_zone
        payload['to_player'] = target_player
        payload['deleted_token'] = True
        payload['was_face_up'] = bool(card.get('face_up'))
        if card.get('card_id'):
            payload['card_id'] = card.get('card_id')
        return
    if to_zone == 'hand' and state.get('phase') == 'get':
        card['face_up'] = True
        card['hidden'] = False
    elif to_zone == 'battle' and state.get('phase') not in ('lumen', 'ready'):
        card['face_up'] = True
    elif not _should_preserve_card_visibility(from_zone, to_zone):
        _set_card_visibility_for_zone(card, to_zone, state)
    if was_public and not bool(card.get('face_up')):
        payload['public_card_label'] = _card_label(card)
        if card.get('card_id'):
            payload['public_card_id'] = card.get('card_id')
    state['players'][target_player]['zones'][to_zone].append(card)
    payload['from_player'] = player_side
    payload['from_zone'] = from_zone
    payload['to_player'] = target_player
    _auto_attach_cmyk_ready_cards(state, payload, actor)


def _apply_bulk_move(state, payload):
    player_side = str(payload.get('player') or '')
    from_zone = str(payload.get('from_zone') or 'battle')
    to_zone = str(payload.get('to_zone') or '')
    if player_side not in PLAYER_SIDES or from_zone not in ZONES or to_zone not in ZONES:
        raise ValueError('일괄 이동 대상이 올바르지 않습니다.')
    if from_zone != 'battle' or to_zone not in ('list', 'hand'):
        raise ValueError('지원하지 않는 일괄 이동입니다.')
    cards = state['players'][player_side]['zones'][from_zone]
    state['players'][player_side]['zones'][from_zone] = []
    for card in cards:
        if not (state.get('phase') == 'battle' and to_zone == 'list'):
            _clear_attachment(card)
        if to_zone == 'hand' and state.get('phase') == 'get':
            card['face_up'] = True
            card['hidden'] = False
        elif not _should_preserve_card_visibility(from_zone, to_zone):
            _set_card_visibility_for_zone(card, to_zone, state)
        owner = card.get('owner') or player_side
        state['players'][owner]['zones'][to_zone].append(card)
    payload['count'] = len(cards)


def _apply_shuffle_hand(state, payload):
    player_side = str(payload.get('player') or '')
    if player_side not in PLAYER_SIDES:
        raise ValueError('패 셔플 대상이 올바르지 않습니다.')

    hand = state['players'][player_side]['zones']['hand']
    current_order = [str(card.get('instance_id') or '') for card in hand]
    requested_order = payload.get('order')
    if requested_order is None:
        next_order = current_order[:]
        secrets.SystemRandom().shuffle(next_order)
        if len(next_order) > 1 and next_order == current_order:
            next_order = next_order[1:] + next_order[:1]
        requested_order = next_order
    else:
        requested_order = [str(instance_id) for instance_id in requested_order]

    if len(requested_order) != len(current_order) or set(requested_order) != set(current_order):
        raise ValueError('패 셔플 순서가 올바르지 않습니다.')

    cards_by_id = {str(card.get('instance_id') or ''): card for card in hand}
    state['players'][player_side]['zones']['hand'] = [cards_by_id[instance_id] for instance_id in requested_order]
    cooldown_until = payload.get('cooldown_until')
    if cooldown_until:
        state.setdefault('hand_shuffle_cooldowns', {})[player_side] = cooldown_until
    payload['order'] = requested_order
    payload['count'] = len(requested_order)


def _event_datetime(value):
    parsed = parse_datetime(str(value or ''))
    if not parsed:
        return timezone.now()
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def _prepare_shuffle_hand_payload(state, payload, created_at):
    player_side = str(payload.get('player') or '')
    if player_side not in PLAYER_SIDES:
        raise ValueError('패 셔플 대상이 올바르지 않습니다.')
    now = _event_datetime(created_at)
    cooldown_value = (state.get('hand_shuffle_cooldowns') or {}).get(player_side)
    cooldown_until = _event_datetime(cooldown_value) if cooldown_value else None
    if cooldown_until and cooldown_until > now:
        remaining = max(1, int((cooldown_until - now).total_seconds()))
        raise ValueError(f'패 셔플은 {remaining}초 뒤에 다시 사용할 수 있습니다.')
    payload['cooldown_until'] = (now + SIMULATOR_HAND_SHUFFLE_COOLDOWN).isoformat()
    payload['cooldown_seconds'] = int(SIMULATOR_HAND_SHUFFLE_COOLDOWN.total_seconds())


def _apply_hand_visibility(state, payload, actor):
    target = str(payload.get('target') or actor or '')
    if target not in PLAYER_SIDES:
        raise ValueError('손패 공개 대상을 찾을 수 없습니다.')
    if actor != target:
        raise PermissionDenied()

    face_up = bool(payload.get('face_up'))
    hand = state['players'][target]['zones']['hand']
    count = 0
    for card in hand:
        if card.get('kind') == 'character' or card.get('owner') != target:
            continue
        card['face_up'] = face_up
        count += 1
    payload['target'] = target
    payload['face_up'] = face_up
    payload['count'] = count


def _apply_phase(state, payload):
    phase = str(payload.get('phase') or '')
    if phase not in PHASES:
        raise ValueError('페이즈가 올바르지 않습니다.')
    from_phase = state.get('phase') if state.get('phase') in PHASES else 'lumen'
    payload['from_phase'] = from_phase
    payload['from_turn'] = int(state.get('turn') or 1)
    if from_phase == 'battle' and phase != 'battle':
        _cleanup_battle_phase(state, payload)
    if from_phase == 'get' and phase != 'get':
        _hide_all_hands(state, payload)
    priority = _start_phase(state, phase, payload)
    payload['to_phase'] = state.get('phase')
    payload['to_turn'] = int(state.get('turn') or 1)
    if priority:
        payload['priority_player'] = priority


def _apply_next_turn(state):
    if state.get('phase') == 'battle':
        _cleanup_battle_phase(state)
    if state.get('phase') == 'get':
        _hide_all_hands(state)
    state['turn'] = int(state.get('turn') or 1) + 1
    _reset_turn_changes(state)
    _start_phase(state, 'lumen')


def _apply_request_action(state, payload):
    target = str(payload.get('target') or '')
    if target not in PLAYER_SIDES:
        raise ValueError('요청 대상이 올바르지 않습니다.')
    state.setdefault('status', {}).setdefault(target, {})
    state['status'][target]['requested'] = bool(payload.get('requested', True))
    if state['status'][target]['requested']:
        state['status'][target]['done'] = False
        state['priority_player'] = target


def _apply_done(state, payload):
    target = str(payload.get('target') or '')
    if target not in PLAYER_SIDES:
        raise ValueError('완료 대상이 올바르지 않습니다.')
    state.setdefault('status', {}).setdefault(target, {})
    state['status'][target]['done'] = bool(payload.get('done', True))
    if state['status'][target]['done']:
        state['status'][target]['requested'] = False
        opponent = _opponent_side(target)
        if not state.get('status', {}).get(opponent, {}).get('done'):
            state.setdefault('status', {}).setdefault(opponent, {'requested': False, 'done': False})
            state['status'][opponent]['requested'] = True
            state['status'][opponent]['done'] = False
            payload['requested_opponent'] = opponent


def _apply_phase_advance(state, payload):
    _advance_phase(state, payload)


def _apply_hp(state, payload):
    target = str(payload.get('target') or '')
    amount = int(payload.get('amount') or 0)
    if target not in PLAYER_SIDES or amount == 0 or abs(amount) > 50000:
        raise ValueError('체력 변경값이 올바르지 않습니다.')
    player = state['players'][target]
    _advance_counter_revision(state, payload, target, 'hp')
    before = int(player.get('hp') or 0)
    player['hp'] = before + amount
    _record_turn_change(state, target, 'hp', amount)
    payload['before'] = before
    payload['after'] = player['hp']


def _apply_fp(state, payload):
    target = str(payload.get('target') or '')
    amount = int(payload.get('amount') or 0)
    if target not in PLAYER_SIDES or amount == 0 or abs(amount) > 100:
        raise ValueError('FP 변경값이 올바르지 않습니다.')
    player = state['players'][target]
    _advance_counter_revision(state, payload, target, 'fp')
    before = int(player.get('fp') or 0)
    player['fp'] = before + amount
    _record_turn_change(state, target, 'fp', amount)
    payload['before'] = before
    payload['after'] = player['fp']


def _apply_fp_reset(state, payload):
    target = str(payload.get('target') or '')
    if target not in PLAYER_SIDES:
        raise ValueError('FP 초기화 대상이 올바르지 않습니다.')
    player = state['players'][target]
    _advance_counter_revision(state, payload, target, 'fp')
    before = int(player.get('fp') or 0)
    player['fp'] = 0
    _record_turn_change(state, target, 'fp', -before)
    payload['before'] = before
    payload['after'] = 0


def _apply_timer(state, payload):
    timer = state.setdefault('timer', {})
    if payload.get('running'):
        timer['started_at'] = payload.get('started_at')
        timer['duration_seconds'] = 10
        timer['remaining_seconds'] = 10
        timer['ends_at'] = None
        timer['is_running'] = True
        timer['owner'] = payload.get('owner')
        timer['timeout_reported'] = False
    else:
        timer['started_at'] = None
        timer['duration_seconds'] = 10
        timer['remaining_seconds'] = 10
        timer['ends_at'] = None
        timer['is_running'] = False
        timer['owner'] = payload.get('owner') or timer.get('owner')
        timer['timeout_reported'] = False


def _timer_is_running(timer):
    started_at = timer.get('started_at') if isinstance(timer, dict) else None
    if not started_at:
        return False
    parsed = parse_datetime(str(started_at))
    if not parsed:
        return False
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    duration = int(timer.get('duration_seconds') or 10)
    return parsed + timedelta(seconds=duration) > timezone.now()


def _timer_is_expired(timer):
    started_at = timer.get('started_at') if isinstance(timer, dict) else None
    if not started_at:
        return False
    parsed = parse_datetime(str(started_at))
    if not parsed:
        return False
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    duration = int(timer.get('duration_seconds') or 10)
    return parsed + timedelta(seconds=duration) <= timezone.now()


def _apply_timer_timeout(state, payload, actor):
    timer = state.setdefault('timer', {})
    owner = timer.get('owner')
    if owner not in PLAYER_SIDES:
        raise ValueError('타이머 시작 플레이어를 확인할 수 없습니다.')
    if actor == owner:
        raise PermissionDenied()
    if timer.get('timeout_reported'):
        raise ValueError('이미 기록된 타이머입니다.')
    if not _timer_is_expired(timer):
        raise ValueError('아직 타이머가 종료되지 않았습니다.')
    timer['timeout_reported'] = True
    payload['target'] = owner
    payload['owner'] = owner
    payload['text'] = '10초 초과'


def _apply_passive(state, payload):
    target = str(payload.get('target') or '')
    if target not in PLAYER_SIDES:
        raise ValueError('패시브 대상이 올바르지 않습니다.')
    player = state['players'][target]
    passive_state = player.setdefault('passive_state', {})
    key = str(payload.get('key') or 'memo')[:80]
    current = dict(passive_state.get(key, {}))
    delta = int(payload.get('delta') or 0)
    if delta:
        current['count'] = max(0, int(current.get('count') or 0) + delta)
    if 'value' in payload:
        current['value'] = payload.get('value')
    if payload.get('note'):
        current['last_note'] = str(payload.get('note'))[:200]
    if payload.get('label'):
        current['label'] = str(payload.get('label'))[:80]
    passive_state[key] = current
    payload['key'] = key
    payload['state'] = current


def _apply_visibility(state, payload, actor):
    instance_id = str(payload.get('card_instance_id') or '')
    _, zone, _, card = _find_card_location(state, instance_id)
    if not card:
        raise ValueError('공개 상태를 변경할 카드를 찾을 수 없습니다.')
    if actor != card.get('owner'):
        raise PermissionDenied()
    if not bool(payload.get('face_up')) and zone in PUBLIC_ON_ENTER_ZONES:
        raise ValueError('공개 존의 카드는 비공개로 전환할 수 없습니다.')
    was_face_up = bool(card.get('face_up'))
    card['face_up'] = bool(payload.get('face_up'))
    payload['owner'] = card.get('owner')
    payload['was_face_up'] = was_face_up
    payload['card_id'] = card.get('card_id')
    payload['card_label'] = _card_label(card)


def _apply_log_note(payload):
    text = str(payload.get('text') or '').strip()
    if not text:
        raise ValueError('기록할 내용을 입력해주세요.')
    payload['text'] = text[:300]


def _apply_signal(state, payload, actor, event_id):
    signal = str(payload.get('signal') or '').strip()
    if signal not in SIMULATOR_SIGNAL_LABELS:
        raise ValueError('신호가 올바르지 않습니다.')
    payload['signal'] = signal
    payload['label'] = SIMULATOR_SIGNAL_LABELS[signal]
    state['last_signal'] = {
        'id': event_id,
        'actor': actor,
        'signal': signal,
        'label': payload['label'],
    }


def _find_external_card(query):
    query = str(query or '').strip()
    if not query:
        raise ValueError('가져올 카드명을 입력해주세요.')

    cards = list(Card.objects.prefetch_related('translations').order_by('id'))
    for card in cards:
        if card_matches_search_exact(card, query, include_keywords=False):
            return card

    matches = [
        card for card in cards
        if card_matches_search(card, query, include_keywords=False)
    ][:6]
    if not matches:
        raise ValueError('해당 이름의 카드를 찾을 수 없습니다.')
    if len(matches) > 1:
        names = ', '.join(card.name for card in matches[:5])
        raise ValueError(f'카드명이 여러 장과 일치합니다: {names}')
    return matches[0]


def _apply_import_card(state, payload, actor):
    if actor not in PLAYER_SIDES:
        raise PermissionDenied()
    imported = copy.deepcopy(payload.get('card') or {})
    if not isinstance(imported, dict):
        imported = {}

    instance_id = str(payload.get('instance_id') or imported.get('instance_id') or '').strip()
    if not instance_id:
        instance_id = f'{actor}-external-{uuid.uuid4().hex[:12]}'
        payload['instance_id'] = instance_id
    if _find_card_location(state, instance_id)[3]:
        raise ValueError('이미 생성된 카드입니다.')

    if imported:
        imported['instance_id'] = instance_id
        imported['owner'] = actor
        imported['face_up'] = True
        imported.setdefault('kind', 'card')
    else:
        card_id = payload.get('card_id')
        if card_id:
            try:
                card = Card.objects.get(id=card_id)
            except Card.DoesNotExist:
                raise ValueError('가져올 카드를 찾을 수 없습니다.')
        else:
            card = _find_external_card(payload.get('card_name') or payload.get('name'))
            payload['card_id'] = card.id
        imported = _card_payload(card, actor, instance_id, face_up=True)
        payload['card'] = copy.deepcopy(imported)

    payload['target'] = actor
    payload['instance_id'] = instance_id
    payload['card_id'] = imported.get('card_id') or payload.get('card_id')
    payload['card_name'] = imported.get('name') or payload.get('card_name') or '카드'
    payload['card_label'] = payload['card_name']
    destination = 'passive' if is_passive_card(imported) else 'lumen'
    if destination == 'passive':
        normalize_passive_card(imported)
    payload['to_zone'] = destination
    state['players'][actor].setdefault('zones', {}).setdefault(destination, []).append(imported)


def _apply_yohan_declare_reveal(state, payload, actor):
    if actor not in PLAYER_SIDES:
        raise PermissionDenied()
    _require_character(state, actor, '요한')
    target = str(payload.get('target') or actor)
    if target != actor:
        raise PermissionDenied()

    declaration = str(payload.get('declaration') or '')
    if declaration not in YOHAN_DECLARATION_LABELS:
        raise ValueError('선언 종류가 올바르지 않습니다.')

    _reveal_opponent_private_hand_card(state, payload, actor)
    payload['declaration'] = declaration
    payload['declaration_label'] = YOHAN_DECLARATION_LABELS[declaration]


def _reveal_opponent_private_hand_card(state, payload, actor):
    opponent = _opponent_side(actor)
    hand = state['players'][opponent]['zones']['hand']
    instance_id = str(payload.get('card_instance_id') or '')
    if instance_id:
        card = next((item for item in hand if item.get('instance_id') == instance_id), None)
        if not card:
            raise ValueError('공개할 카드를 찾을 수 없습니다.')
    else:
        candidates = [card for card in hand if not bool(card.get('face_up'))]
        if not candidates:
            raise ValueError('상대 손패에 공개할 비공개 카드가 없습니다.')
        card = secrets.choice(candidates)

    card['face_up'] = True
    card['hidden'] = False
    payload['target'] = actor
    payload['opponent'] = opponent
    payload['card_instance_id'] = card.get('instance_id')
    payload['card_id'] = card.get('card_id')
    payload['card_label'] = _card_label(card)
    return card, opponent


def _apply_yohan_foresight_reveal(state, payload, actor):
    if actor not in PLAYER_SIDES:
        raise PermissionDenied()
    _require_character(state, actor, '요한')
    target = str(payload.get('target') or actor)
    if target != actor:
        raise PermissionDenied()

    _reveal_opponent_private_hand_card(state, payload, actor)


def _apply_nia_lumen_cards_to_list(state, payload, actor):
    if actor not in PLAYER_SIDES:
        raise PermissionDenied()
    _require_character(state, actor, '니아')
    target = str(payload.get('target') or actor)
    if target != actor:
        raise PermissionDenied()

    lumen = state['players'][target]['zones']['lumen']
    moved = []
    kept = []
    for card in lumen:
        if card.get('kind') == 'character' or not _is_attack_or_defense_card(card):
            kept.append(card)
            continue
        moved.append(card)

    state['players'][target]['zones']['lumen'] = kept
    for card in moved:
        owner = card.get('owner') if card.get('owner') in PLAYER_SIDES else target
        _set_card_visibility_for_zone(card, 'list', state)
        state['players'][owner]['zones']['list'].append(card)
    payload['target'] = target
    payload['count'] = len(moved)


def _new_single_cards(actor, payload):
    cards = copy.deepcopy(payload.get('cards') or [])
    if cards:
        return cards

    try:
        card = _find_external_card('뉴 싱글')
    except ValueError:
        card = None

    cards = []
    for index in range(10):
        instance_id = f'{actor}-new-single-{uuid.uuid4().hex[:12]}-{index + 1}'
        if card:
            cards.append(_card_payload(card, actor, instance_id, face_up=True, kind='token'))
        else:
            cards.append({
                'instance_id': instance_id,
                'kind': 'token',
                'owner': actor,
                'name': '뉴 싱글',
                'type': '토큰',
                'face_up': True,
            })
    payload['cards'] = copy.deepcopy(cards)
    return cards


def _apply_cmyk_new_single(state, payload, actor):
    if actor not in PLAYER_SIDES:
        raise PermissionDenied()
    _require_character(state, actor, 'CMYK')
    target = str(payload.get('target') or actor)
    if target != actor:
        raise PermissionDenied()

    player = state['players'][target]
    passive_state = player.setdefault('passive_state', {})
    created_state = passive_state.get('new_single_created') or {}
    if created_state.get('value'):
        raise ValueError('뉴 싱글 토큰은 이미 생성했습니다.')

    cards = _new_single_cards(actor, payload)
    for card in cards:
        imported = copy.deepcopy(card)
        imported['owner'] = actor
        imported['face_up'] = True
        imported.setdefault('kind', 'token')
        if _find_card_location(state, imported.get('instance_id'))[3]:
            raise ValueError('이미 생성된 카드입니다.')
        player.setdefault('zones', {}).setdefault('lumen', []).append(imported)

    passive_state['new_single_created'] = {
        'value': True,
        'label': '뉴 싱글',
    }
    payload['target'] = target
    payload['count'] = len(cards)
    payload['card_label'] = '뉴 싱글'


def _apply_blackout_random_get(state, payload, actor):
    if actor not in PLAYER_SIDES:
        raise PermissionDenied()

    source_instance_id = str(payload.get('source_card_instance_id') or '')
    source_player, source_zone, _, source_card = _find_card_location(state, source_instance_id)
    if not source_card:
        raise ValueError('블랙아웃 카드를 찾을 수 없습니다.')
    if source_card.get('kind') == 'character' or source_card.get('owner') != actor:
        raise PermissionDenied()
    if not source_card.get('face_up'):
        raise ValueError('공개된 블랙아웃 카드만 사용할 수 있습니다.')
    if not _card_name_contains(source_card, '블랙아웃'):
        raise ValueError('블랙아웃 카드가 아닙니다.')

    opponent = _opponent_side(actor)
    opponent_list = state['players'][opponent]['zones']['list']
    target_instance_id = str(payload.get('target_card_instance_id') or '')
    if target_instance_id:
        target_index = next(
            (index for index, card in enumerate(opponent_list) if card.get('instance_id') == target_instance_id),
            None,
        )
        if target_index is None:
            raise ValueError('상대 리스트에서 가져올 카드를 찾을 수 없습니다.')
    else:
        if not opponent_list:
            raise ValueError('상대 리스트에 가져올 카드가 없습니다.')
        target_index = secrets.randbelow(len(opponent_list))

    target_card = opponent_list.pop(target_index)
    target_card['face_up'] = True
    state['players'][opponent]['zones']['hand'].append(target_card)

    payload['target'] = actor
    payload['opponent'] = opponent
    payload['source_player'] = source_player
    payload['source_zone'] = source_zone
    payload['source_card_instance_id'] = source_instance_id
    payload['source_card_label'] = _card_label(source_card)
    payload['target_card_instance_id'] = target_card.get('instance_id')
    payload['card_instance_id'] = target_card.get('instance_id')
    payload['card_label'] = _card_label(target_card)
    if target_card.get('card_id'):
        payload['card_id'] = target_card.get('card_id')


def _apply_event(state, event):
    _normalize_passive_zone_cards(state)
    event_type = event.get('type')
    payload = event.get('payload')
    if not isinstance(payload, dict):
        payload = {}
    event['payload'] = payload
    actor = event.get('actor')
    if event_type == 'move_card':
        _apply_move_card(state, payload, actor)
    elif event_type == 'attach_card':
        _apply_attach_card(state, payload, actor)
    elif event_type == 'bulk_move':
        _apply_bulk_move(state, payload)
    elif event_type == 'shuffle_hand':
        _apply_shuffle_hand(state, payload)
    elif event_type == 'set_hand_visibility':
        _apply_hand_visibility(state, payload, actor)
    elif event_type == 'set_phase':
        _apply_phase(state, payload)
    elif event_type == 'next_turn':
        _apply_next_turn(state)
    elif event_type == 'request_action':
        _apply_request_action(state, payload)
    elif event_type == 'set_done':
        _apply_done(state, payload)
    elif event_type == 'phase_advance':
        _apply_phase_advance(state, payload)
    elif event_type == 'hp':
        _apply_hp(state, payload)
    elif event_type == 'fp':
        _apply_fp(state, payload)
    elif event_type == 'fp_reset':
        _apply_fp_reset(state, payload)
    elif event_type == 'timer':
        _apply_timer(state, payload)
    elif event_type == 'timer_timeout':
        _apply_timer_timeout(state, payload, actor)
    elif event_type == 'passive':
        _apply_passive(state, payload)
    elif event_type == 'set_visibility':
        _apply_visibility(state, payload, actor)
    elif event_type == 'log_note':
        _apply_log_note(payload)
    elif event_type == 'signal':
        _apply_signal(state, payload, actor, event.get('id'))
    elif event_type == 'import_card':
        _apply_import_card(state, payload, actor)
    elif event_type == 'yohan_declare_reveal':
        _apply_yohan_declare_reveal(state, payload, actor)
    elif event_type == 'yohan_foresight_reveal':
        _apply_yohan_foresight_reveal(state, payload, actor)
    elif event_type == 'nia_lumen_cards_to_list':
        _apply_nia_lumen_cards_to_list(state, payload, actor)
    elif event_type == 'cmyk_new_single':
        _apply_cmyk_new_single(state, payload, actor)
    elif event_type == 'blackout_random_get':
        _apply_blackout_random_get(state, payload, actor)
    else:
        raise ValueError('알 수 없는 요청입니다.')
    _normalize_passive_zone_cards(state)


def _replay(initial_state, events):
    state = _normalize_passive_zone_cards(copy.deepcopy(initial_state))
    for event in events:
        _apply_event(state, copy.deepcopy(event))
    return state


def _compact_document_events(document):
    events = list(document.get('events') or [])
    if len(events) <= SIMULATOR_STORED_EVENT_LIMIT:
        document['events'] = events
        return document

    keep_count = min(SIMULATOR_STORED_EVENT_KEEP, len(events))
    prune_count = len(events) - keep_count
    pruned_events = events[:prune_count]
    kept_events = events[prune_count:]
    checkpoint_state = _replay(document['initial_state'], pruned_events)
    document['initial_state'] = checkpoint_state
    document['events'] = kept_events
    document['archived_event_count'] = _archived_event_count(document) + prune_count
    return document


def _actor_from_body(session, body):
    role = role_for_token(session, str(body.get('seat') or ''), str(body.get('seat_token') or ''))
    if role not in PLAYER_SIDES:
        raise PermissionDenied()
    return role


def _append_phase_advance_if_ready(state, events, actor):
    status = state.get('status') or {}
    if not all(bool((status.get(side) or {}).get('done')) for side in PLAYER_SIDES):
        return None
    event = _make_event('phase_advance', actor, {})
    _apply_event(state, event)
    events.append(event)
    return event


def perform_simulator_action(session, body):
    action = str(body.get('action') or '')
    actor = _actor_from_body(session, body)
    if simulator_session_is_expired(session):
        raise PermissionDenied()
    if session.mode != LumenSimulatorSession.MODE_MANUAL:
        raise ValueError('자동 모드에서는 command 엔드포인트를 사용해야 합니다.')

    with transaction.atomic():
        locked = LumenSimulatorSession.objects.select_for_update().get(id=session.id)
        if simulator_session_is_expired(locked):
            raise PermissionDenied()
        if locked.mode != LumenSimulatorSession.MODE_MANUAL:
            raise ValueError('자동 모드에서는 수동 action을 사용할 수 없습니다.')
        document = _document(locked)
        events = list(document.get('events') or [])

        if action == 'undo':
            if not events:
                raise ValueError('되돌릴 행동이 없습니다.')
            events.pop()
            document['events'] = events
            document['state'] = _replay(document['initial_state'], events)
        else:
            state = copy.deepcopy(document['state'])
            payload = dict(body.get('payload') or {})
            # Keep the original HTTP action contract working. Early simulator
            # clients sent action fields beside ``action`` while newer clients
            # wrap them in ``payload``.
            for key, value in body.items():
                if key not in {'action', 'seat', 'seat_token', 'payload', 'actions'}:
                    payload.setdefault(key, value)
            if action == 'batch':
                actions = body.get('actions') or payload.get('actions') or []
                if not isinstance(actions, list) or not actions:
                    raise ValueError('처리할 행동이 없습니다.')
                if len(actions) > 100:
                    raise ValueError('한 번에 처리할 행동이 너무 많습니다.')
                for item in actions:
                    if not isinstance(item, dict):
                        raise ValueError('행동 형식이 올바르지 않습니다.')
                    item_action = str(item.get('action') or '')
                    if item_action in ('batch', 'undo', 'timer', 'timer_timeout'):
                        raise ValueError('일괄 처리할 수 없는 행동입니다.')
                    item_payload = dict(item.get('payload') or {})
                    if item_action == 'set_done':
                        item_payload.setdefault('target', actor)
                    event = _make_event(item_action, actor, item_payload)
                    if item_action == 'shuffle_hand':
                        _prepare_shuffle_hand_payload(state, item_payload, event.get('created_at'))
                    _apply_event(state, event)
                    events.append(event)
                    if item_action == 'set_done' and bool(item_payload.get('done', True)):
                        _append_phase_advance_if_ready(state, events, actor)
            elif action == 'timer':
                timer = state.get('timer') or {}
                running = _timer_is_running(timer)
                expired = _timer_is_expired(timer)
                remaining = timer.get('remaining_seconds')
                try:
                    remaining_is_zero = int(remaining) <= 0
                except (TypeError, ValueError):
                    remaining_is_zero = False
                should_start = not running and not expired and not remaining_is_zero
                payload = {
                    'running': should_start,
                    'started_at': timezone.now().isoformat() if should_start else None,
                    'owner': actor if should_start else timer.get('owner'),
                }
            if action == 'timer_timeout':
                timer = state.get('timer') or {}
                if (
                    timer.get('timeout_reported')
                    or timer.get('owner') == actor
                    or not _timer_is_expired(timer)
                ):
                    return locked
            if action == 'set_done':
                payload.setdefault('target', actor)
            if action != 'batch':
                event = _make_event(action, actor, payload)
                if action == 'shuffle_hand':
                    _prepare_shuffle_hand_payload(state, payload, event.get('created_at'))
                _apply_event(state, event)
                events.append(event)
                if action == 'set_done' and bool(payload.get('done', True)):
                    _append_phase_advance_if_ready(state, events, actor)
            document['state'] = state
            document['events'] = events

        document = _compact_document_events(document)
        now = timezone.now()
        locked.document = document
        locked.version += 1
        locked.expires_at = simulator_session_expires_at(now)
        locked.save(update_fields=['document', 'version', 'expires_at', 'updated_at'])
        return locked


def _card_visible_to(card, viewer_side):
    return viewer_side == card.get('owner') or bool(card.get('face_up'))


def _filtered_card(card, zone, viewer_side):
    if _card_visible_to(card, viewer_side):
        visible = {
            'instance_id': card.get('instance_id'),
            'kind': card.get('kind') or 'card',
            'owner': card.get('owner'),
            'zone': zone,
            'hidden': False,
            'face_up': bool(card.get('face_up')),
        }
        if card.get('kind') == 'character':
            for field in ('character_id', 'name', 'img', 'icon_img', 'color'):
                if field in card:
                    visible[field] = card.get(field)
        elif card.get('card_id'):
            visible['card_id'] = card.get('card_id')
        else:
            for field in ('name', 'img', 'img_sm', 'type', 'text', 'detail_text'):
                if field in card:
                    visible[field] = card.get(field)
        for field in ('attached_to', 'set_order'):
            if field in card:
                visible[field] = card.get(field)
        return visible
    hidden = {
        'instance_id': card.get('instance_id'),
        'kind': card.get('kind') or 'card',
        'owner': card.get('owner'),
        'zone': zone,
        'hidden': True,
        'name': '비공개 카드',
        'face_up': False,
    }
    if viewer_side in PLAYER_SIDES and card.get('card_id'):
        hidden['card_id'] = card.get('card_id')
    for field in ('attached_to', 'set_order'):
        if field in card:
            hidden[field] = card.get(field)
    return hidden


def _with_serialized_hand_limits(state):
    serialized = copy.deepcopy(state)
    for side in PLAYER_SIDES:
        player = serialized.get('players', {}).get(side)
        if not player:
            continue
        character_id = (player.get('character') or {}).get('id')
        hand_limit = None
        if character_id:
            try:
                character = Character.objects.get(id=character_id)
                hand_limit = hand_limit_for_hp(character, player.get('hp'))
            except Exception:
                hand_limit = None
        player.setdefault('character', {})['hand_limit'] = hand_limit
    return serialized


def _has_metadata_value(value):
    return value is not None and value != ''


def _hydrate_serialized_card_metadata(state):
    card_ids = set()
    for player in (state.get('players') or {}).values():
        for cards in (player.get('zones') or {}).values():
            for card in cards:
                if card.get('kind') == 'character':
                    continue
                card_id = card.get('card_id')
                if not card_id:
                    continue
                if any(field not in card for field in CARD_METADATA_FIELDS):
                    card_ids.add(card_id)
    if not card_ids:
        return state

    cards_by_id = Card.objects.in_bulk(card_ids)
    for player in (state.get('players') or {}).values():
        for cards in (player.get('zones') or {}).values():
            for card in cards:
                model_card = cards_by_id.get(card.get('card_id'))
                if not model_card:
                    continue
                metadata = _card_metadata(model_card)
                for field, value in metadata.items():
                    if field not in card or (not _has_metadata_value(card.get(field)) and _has_metadata_value(value)):
                        card[field] = value
    return state


def _localized_phase_labels(language):
    return {
        phase: ui_text(label, language)
        for phase, label in PHASE_LABELS.items()
    }


def _localized_zone_labels(language):
    return {
        zone: ui_text(label, language)
        for zone, label in ZONE_LABELS.items()
    }


def _localized_card_term_labels(card, language):
    for field in ('type', 'pos', 'body', 'special', 'hit', 'guard', 'counter', 'g_top', 'g_mid', 'g_bot'):
        card[f'{field}_label'] = game_term(card.get(field), language)


def _localized_card_metadata(card, language):
    language = normalize_language(language)
    metadata = _card_metadata(card)
    # Text fields can contain semantic localization markup in every language,
    # including the Korean source text.
    metadata['text'] = translated_card_field(card, language, 'text')
    metadata['detail_text'] = translated_card_field(card, language, 'detail_text')
    if language != DEFAULT_LANGUAGE:
        metadata['name'] = translated_card_field(card, language, 'name')
        _localized_card_term_labels(metadata, language)
    return metadata


def _render_card_markup_labels(state, language):
    """Render markup embedded in serialized runtime card text."""
    for player in (state.get('players') or {}).values():
        for cards in (player.get('zones') or {}).values():
            for card in cards:
                if card.get('hidden') or card.get('kind') == 'character':
                    continue
                for field_name in ('text', 'detail_text'):
                    if field_name in card:
                        card[f'{field_name}_label'] = render_localized_markup(
                            card.get(field_name), language,
                        )
    return state


def serialize_simulator_card_metadata(card_ids, language=DEFAULT_LANGUAGE):
    normalized_ids = []
    for card_id in card_ids:
        try:
            normalized_ids.append(int(card_id))
        except (TypeError, ValueError):
            continue
    if not normalized_ids:
        return {}

    cards = Card.objects.prefetch_related('translations').in_bulk(normalized_ids)
    return {
        str(card_id): _localized_card_metadata(card, language)
        for card_id, card in cards.items()
    }


def _localize_filtered_state(state, language):
    language = normalize_language(language)

    character_ids = set()
    for player in (state.get('players') or {}).values():
        character_id = (player.get('character') or {}).get('id')
        if character_id:
            character_ids.add(character_id)
        for cards in (player.get('zones') or {}).values():
            for card in cards:
                if card.get('hidden'):
                    continue
                if card.get('kind') == 'character':
                    character_id = card.get('character_id')
                    if character_id:
                        character_ids.add(character_id)

    characters_by_id = Character.objects.prefetch_related('translations').in_bulk(character_ids) if character_ids else {}

    for player in (state.get('players') or {}).values():
        character_payload = player.get('character') or {}
        character = characters_by_id.get(character_payload.get('id'))
        if character:
            if language != DEFAULT_LANGUAGE:
                character_payload['name'] = translated_character_field(character, language, 'name')
            character_payload['passive_ui'] = _passive_ui(character, language, context='simulator')

        for cards in (player.get('zones') or {}).values():
            for card in cards:
                if card.get('hidden'):
                    if language != DEFAULT_LANGUAGE:
                        card['name'] = ui_text('비공개 카드', language)
                    continue
                if card.get('kind') == 'character':
                    character = characters_by_id.get(card.get('character_id'))
                    if character and language != DEFAULT_LANGUAGE:
                        card['name'] = translated_character_field(character, language, 'name')
    return state


def _filtered_state(state, viewer_side, language=DEFAULT_LANGUAGE):
    state = _with_serialized_hand_limits(state)
    _normalize_passive_zone_cards(state)
    _ensure_turn_changes(state)
    _ensure_counter_revisions(state)
    for player_side, player in (state.get('players') or {}).items():
        passive_state = player.get('passive_state') or {}
        for key in list(passive_state):
            entry = passive_state.get(key) or {}
            if isinstance(entry, dict) and entry.get('visibility') == 'private' and entry.get('owner') != viewer_side:
                passive_state.pop(key, None)
        zones = player.get('zones') or {}
        for zone, cards in zones.items():
            zones[zone] = [_filtered_card(card, zone, viewer_side) for card in cards]
    timer = state.setdefault('timer', {})
    started_at = timer.get('started_at')
    duration = int(timer.get('duration_seconds') or 10)
    remaining = duration
    ends_at = None
    running = False
    if started_at:
        parsed = parse_datetime(str(started_at))
        if parsed:
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            ends_at_dt = parsed + timedelta(seconds=duration)
            remaining = max(0, int((ends_at_dt - timezone.now()).total_seconds()))
            running = remaining > 0
            ends_at = ends_at_dt.isoformat()
    timer['duration_seconds'] = duration
    timer['remaining_seconds'] = remaining
    timer['ends_at'] = ends_at
    timer['is_running'] = running
    return _localize_filtered_state(state, language)


def _visible_card_name(state, instance_id, viewer_side, language=DEFAULT_LANGUAGE):
    language = normalize_language(language)
    _, zone, _, card = _find_card_location(state, instance_id)
    if not card:
        return ui_text('카드', language)
    if not _card_visible_to(card, viewer_side):
        return ui_text('비공개 카드', language)
    if card.get('kind') == 'character' and card.get('character_id'):
        character = Character.objects.prefetch_related('translations').filter(id=card.get('character_id')).first()
        if character:
            return translated_character_field(character, language, 'name')
    if card.get('card_id'):
        model_card = Card.objects.prefetch_related('translations').filter(id=card.get('card_id')).first()
        if model_card:
            return translated_card_field(model_card, language, 'name')
    return game_term(card.get('name') or '카드', language)


def _payload_card_label(payload, language=DEFAULT_LANGUAGE, label_key='card_label', card_id_key='card_id'):
    language = normalize_language(language)
    if payload.get(card_id_key) and language != DEFAULT_LANGUAGE:
        model_card = Card.objects.prefetch_related('translations').filter(id=payload.get(card_id_key)).first()
        if model_card:
            return translated_card_field(model_card, language, 'name')
    return payload.get(label_key) or ui_text('카드', language)


def _localize_revealed_cards(payload, language=DEFAULT_LANGUAGE):
    revealed_cards = payload.get('revealed_cards')
    if not isinstance(revealed_cards, dict):
        return
    for cards in revealed_cards.values():
        if not isinstance(cards, list):
            continue
        for card in cards:
            if not isinstance(card, dict):
                continue
            card['card_label'] = _payload_card_label(card, language)


def _filtered_event(event, state, viewer_side, language=DEFAULT_LANGUAGE):
    filtered = copy.deepcopy(event)
    if filtered.get('visibility') == 'private' and filtered.get('actor') != viewer_side:
        return {
            'id': filtered.get('id'),
            'type': 'private_event',
            'actor': filtered.get('actor'),
            'payload': {},
            'created_at': filtered.get('created_at'),
        }
    payload = filtered.get('payload') or {}
    event_type = filtered.get('type')
    if event_type == 'attach_card':
        for instance_key, label_key, card_id_key in (
            ('card_instance_id', 'card_label', 'card_id'),
            ('host_card_instance_id', 'host_card_label', 'host_card_id'),
        ):
            _, _, _, card = _find_card_location(state, payload.get(instance_key))
            if not card or not _card_visible_to(card, viewer_side):
                payload[label_key] = ui_text('비공개 카드', language)
                payload.pop(card_id_key, None)
            else:
                payload[label_key] = _visible_card_name(
                    state, payload.get(instance_key), viewer_side, language,
                )
    if event_type in ('move_card', 'set_visibility', 'yohan_declare_reveal', 'yohan_foresight_reveal', 'blackout_random_get'):
        _, _, _, card = _find_card_location(state, payload.get('card_instance_id'))
        if not card and payload.get('deleted_token'):
            if viewer_side == payload.get('owner') or payload.get('was_face_up'):
                if payload.get('card_id') and normalize_language(language) != DEFAULT_LANGUAGE:
                    model_card = Card.objects.prefetch_related('translations').filter(id=payload.get('card_id')).first()
                    payload['card_label'] = translated_card_field(model_card, language, 'name') if model_card else payload.get('card_label') or ui_text('카드', language)
                else:
                    payload['card_label'] = payload.get('card_label') or ui_text('카드', language)
            else:
                payload['card_label'] = ui_text('비공개 카드', language)
        elif event_type == 'move_card' and payload.get('public_card_label'):
            if payload.get('public_card_id') and normalize_language(language) != DEFAULT_LANGUAGE:
                model_card = Card.objects.prefetch_related('translations').filter(id=payload.get('public_card_id')).first()
                payload['card_label'] = translated_card_field(model_card, language, 'name') if model_card else payload.get('public_card_label') or ui_text('카드', language)
            else:
                payload['card_label'] = payload.get('public_card_label') or ui_text('카드', language)
        elif event_type == 'set_visibility' and payload.get('card_label') and (payload.get('face_up') or payload.get('was_face_up')):
            payload['card_label'] = _payload_card_label(payload, language)
        elif not card or not _card_visible_to(card, viewer_side):
            payload['card_label'] = ui_text('비공개 카드', language)
        elif payload.get('card_label') and normalize_language(language) == DEFAULT_LANGUAGE:
            payload['card_label'] = payload.get('card_label')
        else:
            payload['card_label'] = _visible_card_name(state, payload.get('card_instance_id'), viewer_side, language)
    if event_type in ('set_phase', 'phase_advance'):
        _localize_revealed_cards(payload, language)
    if event_type == 'yohan_declare_reveal':
        declaration = payload.get('declaration')
        if declaration in YOHAN_DECLARATION_LABELS:
            payload['declaration_label'] = ui_text(YOHAN_DECLARATION_LABELS[declaration], language)
    filtered['payload'] = payload
    return filtered


def _event_limit(value):
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = SIMULATOR_DEFAULT_EVENT_LIMIT
    return max(0, min(SIMULATOR_MAX_EVENT_LIMIT, limit))


def _limited_events(events, limit):
    limit = _event_limit(limit)
    if limit <= 0:
        return []
    return list(events[-limit:])


def _event_seq(archived_event_count, index):
    return archived_event_count + index + 1


def _filtered_event_with_seq(event, state, viewer_side, language, seq):
    filtered = _filtered_event(event, state, viewer_side, language)
    filtered['seq'] = seq
    return filtered


def serialize_simulator_session(session, seat='', token='', language=DEFAULT_LANGUAGE, include_events=True, event_limit=SIMULATOR_DEFAULT_EVENT_LIMIT):
    language = normalize_language(language)
    role = role_for_token(session, seat, token)
    document = _document_for_read(session)
    state = document['state']
    raw_events = document.get('events') or []
    archived_event_count = _archived_event_count(document)
    player1_url = ''
    player2_url = ''
    if role == 'p1':
        player1_url = reverse('battlelog:simulatorSeat', kwargs={
            'view_token': session.view_token,
            'seat': 'p1',
            'seat_token': session.player1_token,
        })
        if session.player2_controller != LumenSimulatorSession.CONTROLLER_AI:
            player2_url = reverse('battlelog:simulatorSeat', kwargs={
                'view_token': session.view_token,
                'seat': 'p2',
                'seat_token': session.player2_token,
            })
    payload = {
        'id': session.id,
        'version': session.version,
        'mode': session.mode,
        'controllers': {
            'p1': session.player1_controller,
            'p2': session.player2_controller,
        },
        'ai_policy_version': (
            ((session.document or {}).get('ai_policy') or {}).get('version')
            if LumenSimulatorSession.CONTROLLER_AI in {
                session.player1_controller, session.player2_controller,
            }
            else None
        ),
        'automation_failure': (
            {
                key: (session.automation_failure or {}).get(key)
                for key in ('report_id', 'error_type', 'message', 'at', 'engine_step')
                if (session.automation_failure or {}).get(key) is not None
            }
            if session.automation_failure else None
        ),
        'ruleset_version': session.ruleset_release.version if session.ruleset_release_id else None,
        'presence': simulator_presence_counts(session.view_token),
        'role': role,
        'can_control': (
            role in PLAYER_SIDES
            and (session.player1_controller if role == 'p1' else session.player2_controller)
            == LumenSimulatorSession.CONTROLLER_HUMAN
            and session.mode == LumenSimulatorSession.MODE_MANUAL
            and not simulator_session_is_expired(session)
        ),
        'can_submit_commands': (
            role in PLAYER_SIDES
            and session.mode == LumenSimulatorSession.MODE_AUTOMATIC
            and (
                session.player1_controller if role == 'p1'
                else session.player2_controller
            ) == LumenSimulatorSession.CONTROLLER_HUMAN
            and not simulator_session_is_expired(session)
        ),
        'is_expired': simulator_session_is_expired(session),
        'view_url': reverse('battlelog:simulatorView', kwargs={'view_token': session.view_token}),
        'player1_url': player1_url,
        'player2_url': player2_url,
        'phase_labels': _localized_phase_labels(language),
        'zone_labels': _localized_zone_labels(language),
        'state': _filtered_state(state, role, language),
        'event_count': archived_event_count + len(raw_events),
    }
    if include_events:
        limited_events = _limited_events(raw_events, event_limit)
        first_index = len(raw_events) - len(limited_events)
        payload['events'] = [
            _filtered_event_with_seq(event, state, role, language, _event_seq(archived_event_count, first_index + index))
            for index, event in enumerate(limited_events)
        ]
        payload['event_limit'] = _event_limit(event_limit)
    if session.mode == LumenSimulatorSession.MODE_AUTOMATIC:
        from .automatic_services import automatic_observation, sanitize_automatic_state

        observation = automatic_observation(session, role)
        if (
            role in PLAYER_SIDES
            and (
                session.player1_controller if role == 'p1'
                else session.player2_controller
            ) == LumenSimulatorSession.CONTROLLER_AI
        ):
            # The AI consumes automatic_observation() internally. Never expose
            # its action surface through a browser response, even if a seat
            # token is copied from storage or an old link.
            observation['legal_actions'] = []
        payload['state'] = sanitize_automatic_state(
            payload['state'], observation, role=role,
            ruleset=session.ruleset_release.snapshot if session.ruleset_release_id else {},
        )
        payload.update({key: value for key, value in observation.items() if key != 'state'})
    if language == DEFAULT_LANGUAGE:
        payload['state'] = _render_card_markup_labels(payload['state'], language)
    return payload


def serialize_simulator_events(session, seat='', token='', language=DEFAULT_LANGUAGE, event_limit=SIMULATOR_DEFAULT_EVENT_LIMIT):
    language = normalize_language(language)
    role = role_for_token(session, seat, token)
    document = _document_for_read(session)
    state = document['state']
    raw_events = document.get('events') or []
    archived_event_count = _archived_event_count(document)
    limited_events = _limited_events(raw_events, event_limit)
    first_index = len(raw_events) - len(limited_events)
    return {
        'id': session.id,
        'version': session.version,
        'event_count': archived_event_count + len(raw_events),
        'event_limit': _event_limit(event_limit),
        'events': [
            _filtered_event_with_seq(event, state, role, language, _event_seq(archived_event_count, first_index + index))
            for index, event in enumerate(limited_events)
        ],
        'reset': True,
    }


def serialize_simulator_events_since(session, seat='', token='', since_seq=0, language=DEFAULT_LANGUAGE, event_limit=SIMULATOR_DEFAULT_EVENT_LIMIT):
    language = normalize_language(language)
    role = role_for_token(session, seat, token)
    document = _document_for_read(session)
    state = document['state']
    raw_events = document.get('events') or []
    archived_event_count = _archived_event_count(document)
    event_count = archived_event_count + len(raw_events)
    try:
        since_seq = max(0, int(since_seq or 0))
    except (TypeError, ValueError):
        since_seq = 0

    if since_seq < archived_event_count:
        return serialize_simulator_events(session, seat, token, language=language, event_limit=event_limit)

    selected = [
        (index, event)
        for index, event in enumerate(raw_events)
        if _event_seq(archived_event_count, index) > since_seq
    ]
    if len(selected) > _event_limit(event_limit):
        return serialize_simulator_events(session, seat, token, language=language, event_limit=event_limit)

    return {
        'id': session.id,
        'version': session.version,
        'event_count': event_count,
        'event_limit': _event_limit(event_limit),
        'events': [
            _filtered_event_with_seq(event, state, role, language, _event_seq(archived_event_count, index))
            for index, event in selected
        ],
        'reset': False,
    }


def cleanup_expired_simulator_sessions(now=None):
    now = now or timezone.now()
    deleted, _ = LumenSimulatorSession.objects.filter(expires_at__lte=now).delete()
    return deleted
