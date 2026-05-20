import copy
import secrets
import uuid
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
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
from deck.models import CardInDeck, Deck

from .models import LumenSimulatorSession
from .services import _passive_ui, hand_limit_for_hp, initial_hp_for_character


SIMULATOR_SESSION_LIFETIME = timedelta(hours=24)
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
CROSS_PLAYER_ZONES = {'battle', 'lumen'}
CARD_METADATA_FIELDS = (
    'name', 'code', 'type', 'frame', 'damage', 'pos', 'body', 'special',
    'hit', 'guard', 'counter', 'g_top', 'g_mid', 'g_bot', 'text',
    'detail_text', 'ultimate', 'character_id', 'img', 'img_sm',
)


def simulator_queryset():
    return LumenSimulatorSession.objects.all()


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
    return {
        'name': card.name,
        'code': card.code,
        'type': card.type,
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
        'detail_text': card.detail_text,
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


def _player_skeleton(side, name, deck):
    character = deck.character
    initial_hp = initial_hp_for_character(character)
    return {
        'name': (name or '').strip() or ('플레이어1' if side == 'p1' else '플레이어2'),
        'deck_id': deck.id,
        'deck_name': deck.name,
        'character': {
            'id': character.id,
            'name': character.name,
            'img': character.body_img or character.sd_img or character.img,
            'icon_img': character.icon_img,
            'color': character.color,
            'passive_ui': _passive_ui(character),
        },
        'initial_hp': initial_hp,
        'hp': initial_hp,
        'fp': 0,
        'passive_state': {},
        'zones': {zone: [] for zone in ZONES},
    }


def _add_deck_cards_to_player(player, side, deck):
    player['zones']['character'].append(_character_payload(deck.character, side))

    passive_cards = Card.objects.filter(character=deck.character, type='특성').order_by('id')
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
    state = {
        'turn': 1,
        'phase': 'lumen',
        'status': {
            'p1': {'requested': False, 'done': False},
            'p2': {'requested': False, 'done': False},
        },
        'timer': {
            'started_at': None,
            'duration_seconds': 10,
        },
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


def create_simulator_session(player1_name, player2_name, player1_deck, player2_deck):
    initial_state = _initial_state(player1_name, player2_name, player1_deck, player2_deck)
    document = {
        'initial_state': copy.deepcopy(initial_state),
        'state': copy.deepcopy(initial_state),
        'events': [],
    }
    return LumenSimulatorSession.objects.create(
        view_token=_unique_token('view_token'),
        player1_token=_unique_token('player1_token'),
        player2_token=_unique_token('player2_token'),
        player1_name=initial_state['players']['p1']['name'],
        player2_name=initial_state['players']['p2']['name'],
        document=document,
        expires_at=timezone.now() + SIMULATOR_SESSION_LIFETIME,
    )


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


def _find_card_location(state, instance_id):
    for player_side, player in (state.get('players') or {}).items():
        for zone, cards in (player.get('zones') or {}).items():
            for index, card in enumerate(cards):
                if card.get('instance_id') == instance_id:
                    return player_side, zone, index, card
    return None, None, None, None


def _set_card_visibility_for_zone(card, zone, state):
    if zone in PUBLIC_ON_ENTER_ZONES:
        card['face_up'] = True
        return
    if zone in PRIVATE_ON_ENTER_ZONES:
        card['face_up'] = False
        return
    if zone == 'battle':
        card['face_up'] = state.get('phase') == 'battle'


def _apply_move_card(state, payload):
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

    owner = card.get('owner') or player_side
    target_player = to_player or owner
    if target_player not in PLAYER_SIDES:
        raise ValueError('이동할 플레이어가 올바르지 않습니다.')
    if target_player != owner and to_zone not in CROSS_PLAYER_ZONES:
        raise ValueError('상대 플레이어의 루멘 존 또는 배틀 존으로만 이동할 수 있습니다.')
    state['players'][player_side]['zones'][from_zone].pop(index)
    _set_card_visibility_for_zone(card, to_zone, state)
    state['players'][target_player]['zones'][to_zone].append(card)
    payload['from_player'] = player_side
    payload['from_zone'] = from_zone
    payload['to_player'] = target_player


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
        _set_card_visibility_for_zone(card, to_zone, state)
        owner = card.get('owner') or player_side
        state['players'][owner]['zones'][to_zone].append(card)
    payload['count'] = len(cards)


def _apply_phase(state, payload):
    phase = str(payload.get('phase') or '')
    if phase not in PHASES:
        raise ValueError('페이즈가 올바르지 않습니다.')
    state['phase'] = phase
    _reset_status(state)
    if phase == 'battle':
        for player in state.get('players', {}).values():
            for card in player.get('zones', {}).get('battle', []):
                card['face_up'] = True


def _apply_next_turn(state):
    state['turn'] = int(state.get('turn') or 1) + 1
    state['phase'] = 'lumen'
    _reset_status(state)


def _apply_request_action(state, payload):
    target = str(payload.get('target') or '')
    if target not in PLAYER_SIDES:
        raise ValueError('요청 대상이 올바르지 않습니다.')
    state.setdefault('status', {}).setdefault(target, {})
    state['status'][target]['requested'] = bool(payload.get('requested', True))
    if state['status'][target]['requested']:
        state['status'][target]['done'] = False


def _apply_done(state, payload):
    target = str(payload.get('target') or '')
    if target not in PLAYER_SIDES:
        raise ValueError('완료 대상이 올바르지 않습니다.')
    state.setdefault('status', {}).setdefault(target, {})
    state['status'][target]['done'] = bool(payload.get('done', True))
    if state['status'][target]['done']:
        state['status'][target]['requested'] = False


def _apply_hp(state, payload):
    target = str(payload.get('target') or '')
    amount = int(payload.get('amount') or 0)
    if target not in PLAYER_SIDES or amount == 0 or abs(amount) > 50000:
        raise ValueError('체력 변경값이 올바르지 않습니다.')
    player = state['players'][target]
    before = int(player.get('hp') or 0)
    player['hp'] = before + amount
    payload['before'] = before
    payload['after'] = player['hp']


def _apply_fp(state, payload):
    target = str(payload.get('target') or '')
    amount = int(payload.get('amount') or 0)
    if target not in PLAYER_SIDES or amount == 0 or abs(amount) > 100:
        raise ValueError('FP 변경값이 올바르지 않습니다.')
    player = state['players'][target]
    before = int(player.get('fp') or 0)
    player['fp'] = before + amount
    payload['before'] = before
    payload['after'] = player['fp']


def _apply_fp_reset(state, payload):
    target = str(payload.get('target') or '')
    if target not in PLAYER_SIDES:
        raise ValueError('FP 초기화 대상이 올바르지 않습니다.')
    player = state['players'][target]
    before = int(player.get('fp') or 0)
    player['fp'] = 0
    payload['before'] = before
    payload['after'] = 0


def _apply_timer(state, payload):
    timer = state.setdefault('timer', {})
    if payload.get('running'):
        timer['started_at'] = payload.get('started_at')
        timer['duration_seconds'] = 10
        timer['owner'] = payload.get('owner')
        timer['timeout_reported'] = False
    else:
        timer['started_at'] = None
        timer['duration_seconds'] = 10
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
    card['face_up'] = bool(payload.get('face_up'))
    payload['owner'] = card.get('owner')


def _apply_log_note(payload):
    text = str(payload.get('text') or '').strip()
    if not text:
        raise ValueError('기록할 내용을 입력해주세요.')
    payload['text'] = text[:300]


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
    state['players'][actor].setdefault('zones', {}).setdefault('lumen', []).append(imported)


def _apply_event(state, event):
    event_type = event.get('type')
    payload = event.get('payload')
    if not isinstance(payload, dict):
        payload = {}
    event['payload'] = payload
    actor = event.get('actor')
    if event_type == 'move_card':
        _apply_move_card(state, payload)
    elif event_type == 'bulk_move':
        _apply_bulk_move(state, payload)
    elif event_type == 'set_phase':
        _apply_phase(state, payload)
    elif event_type == 'next_turn':
        _apply_next_turn(state)
    elif event_type == 'request_action':
        _apply_request_action(state, payload)
    elif event_type == 'set_done':
        _apply_done(state, payload)
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
    elif event_type == 'import_card':
        _apply_import_card(state, payload, actor)
    else:
        raise ValueError('알 수 없는 요청입니다.')


def _replay(initial_state, events):
    state = copy.deepcopy(initial_state)
    for event in events:
        _apply_event(state, copy.deepcopy(event))
    return state


def _actor_from_body(session, body):
    role = role_for_token(session, str(body.get('seat') or ''), str(body.get('seat_token') or ''))
    if role not in PLAYER_SIDES:
        raise PermissionDenied()
    return role


def perform_simulator_action(session, body):
    action = str(body.get('action') or '')
    actor = _actor_from_body(session, body)
    if simulator_session_is_expired(session):
        raise PermissionDenied()

    with transaction.atomic():
        locked = LumenSimulatorSession.objects.select_for_update().get(id=session.id)
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
            if action == 'timer':
                timer = state.get('timer') or {}
                running = _timer_is_running(timer)
                payload = {
                    'running': not running,
                    'started_at': timezone.now().isoformat() if not running else None,
                    'owner': actor if not running else timer.get('owner'),
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
            event = _make_event(action, actor, payload)
            _apply_event(state, event)
            document['state'] = state
            events.append(event)
            document['events'] = events

        locked.document = document
        locked.version += 1
        locked.save(update_fields=['document', 'version', 'updated_at'])
        return locked


def _card_visible_to(card, viewer_side):
    return viewer_side == card.get('owner') or bool(card.get('face_up'))


def _filtered_card(card, zone, viewer_side):
    if _card_visible_to(card, viewer_side):
        visible = dict(card)
        visible['zone'] = zone
        visible['hidden'] = False
        return visible
    return {
        'instance_id': card.get('instance_id'),
        'kind': card.get('kind') or 'card',
        'owner': card.get('owner'),
        'zone': zone,
        'hidden': True,
        'name': '비공개 카드',
        'face_up': False,
    }


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


def _localize_filtered_state(state, language):
    language = normalize_language(language)
    if language == DEFAULT_LANGUAGE:
        return state

    card_ids = set()
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
                    continue
                card_id = card.get('card_id')
                if card_id:
                    card_ids.add(card_id)

    cards_by_id = Card.objects.prefetch_related('translations').in_bulk(card_ids) if card_ids else {}
    characters_by_id = Character.objects.prefetch_related('translations').in_bulk(character_ids) if character_ids else {}

    for player in (state.get('players') or {}).values():
        character_payload = player.get('character') or {}
        character = characters_by_id.get(character_payload.get('id'))
        if character:
            character_payload['name'] = translated_character_field(character, language, 'name')
            character_payload['passive_ui'] = _passive_ui(character, language)

        for cards in (player.get('zones') or {}).values():
            for card in cards:
                if card.get('hidden'):
                    card['name'] = ui_text('비공개 카드', language)
                    continue
                if card.get('kind') == 'character':
                    character = characters_by_id.get(card.get('character_id'))
                    if character:
                        card['name'] = translated_character_field(character, language, 'name')
                    continue

                model_card = cards_by_id.get(card.get('card_id'))
                if model_card:
                    card['name'] = translated_card_field(model_card, language, 'name')
                    card['text'] = translated_card_field(model_card, language, 'text')
                    card['detail_text'] = translated_card_field(model_card, language, 'detail_text')
                _localized_card_term_labels(card, language)
    return state


def _filtered_state(state, viewer_side, language=DEFAULT_LANGUAGE):
    state = _with_serialized_hand_limits(state)
    state = _hydrate_serialized_card_metadata(state)
    for player_side, player in (state.get('players') or {}).items():
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


def _filtered_event(event, state, viewer_side, language=DEFAULT_LANGUAGE):
    filtered = copy.deepcopy(event)
    payload = filtered.get('payload') or {}
    event_type = filtered.get('type')
    if event_type in ('move_card', 'set_visibility'):
        payload['card_label'] = _visible_card_name(state, payload.get('card_instance_id'), viewer_side, language)
    filtered['payload'] = payload
    return filtered


def serialize_simulator_session(session, seat='', token='', language=DEFAULT_LANGUAGE):
    language = normalize_language(language)
    role = role_for_token(session, seat, token)
    document = _document(session)
    state = document['state']
    player1_url = ''
    player2_url = ''
    if role == 'p1':
        player1_url = reverse('battlelog:simulatorSeat', kwargs={
            'view_token': session.view_token,
            'seat': 'p1',
            'seat_token': session.player1_token,
        })
        player2_url = reverse('battlelog:simulatorSeat', kwargs={
            'view_token': session.view_token,
            'seat': 'p2',
            'seat_token': session.player2_token,
        })
    return {
        'id': session.id,
        'version': session.version,
        'role': role,
        'can_control': role in PLAYER_SIDES and not simulator_session_is_expired(session),
        'is_expired': simulator_session_is_expired(session),
        'view_url': reverse('battlelog:simulatorView', kwargs={'view_token': session.view_token}),
        'player1_url': player1_url,
        'player2_url': player2_url,
        'phase_labels': _localized_phase_labels(language),
        'zone_labels': _localized_zone_labels(language),
        'state': _filtered_state(state, role, language),
        'events': [
            _filtered_event(event, state, role, language)
            for event in document.get('events', [])
        ],
    }


def cleanup_expired_simulator_sessions(now=None):
    now = now or timezone.now()
    deleted, _ = LumenSimulatorSession.objects.filter(expires_at__lte=now).delete()
    return deleted
