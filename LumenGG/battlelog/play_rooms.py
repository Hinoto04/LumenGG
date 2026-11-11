"""사람끼리 대전 대기실: 방(코드로 참가)과 퀵 매치.

화면은 대전 클라이언트 로비(play/src/Lobby.tsx)이고, 각 플레이어는 자기 덱만 고른다.
- 방: 방장이 방을 만들고 코드·링크를 보낸다. 참가자가 들어와 각자 덱을 고르고 둘 다 준비하면 대전을 만든다.
- 퀵 매치: 덱을 정하고 기다리면, 같은 때 기다리는 다른 플레이어와 짝을 지어 바로 대전을 만든다.

자리마다 토큰을 주고 브라우저가 보관한다(로그인하지 않아도 된다). 덱 권한은 그 덱을 고른 플레이어의
계정으로 확인한다. 대전이 만들어지면 요청한 플레이어에게만 자기 좌석 주소를 준다.
"""

import secrets
from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from deck.models import Deck

from .models import LumenSimulatorSession, SimulatorRoom
from .play_start import opens_in_game_client, play_url, start_session
from .simulator_services import can_view_deck_for_simulator

ROOM_LIFETIME = timedelta(hours=2)
QUICK_LIFETIME = timedelta(minutes=15)
# 퀵 매치 대기자는 화면이 이만큼 소식이 없으면 떠난 것으로 본다(짝을 짓지 않는다).
QUICK_STALE = timedelta(seconds=20)
CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
TIMER_DEFAULTS = {'ready_timeout_seconds': 10, 'effect_timeout_seconds': 30}


class RoomError(ValueError):
    """사용자에게 보여 줄 오류(한국어)."""


def _new_code():
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def _new_token():
    return secrets.token_urlsafe(24)


def _display_name(user, fallback):
    if user is not None and getattr(user, 'is_authenticated', False):
        return (getattr(user, 'nickname', '') or user.get_username() or fallback)[:40]
    return fallback


def _user_or_none(user):
    return user if user is not None and getattr(user, 'is_authenticated', False) else None


def _load_deck(user, deck_id):
    try:
        deck = Deck.objects.select_related('character').get(id=int(deck_id), deleted=False)
    except (Deck.DoesNotExist, TypeError, ValueError):
        raise RoomError('덱을 찾을 수 없습니다.') from None
    if not can_view_deck_for_simulator(user or AnonymousUser(), deck):
        raise RoomError('이 덱을 쓸 권한이 없습니다.')
    return deck


def _options(body):
    mode = body.get('mode') or LumenSimulatorSession.MODE_AUTOMATIC
    if mode not in (LumenSimulatorSession.MODE_AUTOMATIC, LumenSimulatorSession.MODE_MANUAL):
        raise RoomError('대전 방식이 올바르지 않습니다.')
    options = {'mode': mode}
    for key, default in TIMER_DEFAULTS.items():
        value = body.get(key, default)
        options[key] = 0 if value in (None, '', 'none') else value
    return options


def _seat(room, token):
    if token and token == room.host_token:
        return 'host'
    if token and room.guest_token and token == room.guest_token:
        return 'guest'
    return None


def _deck_summary(deck, *, mine):
    """상대 덱은 캐릭터만 알려 준다(덱 구성은 대전에서 드러난다)."""
    if not deck:
        return None
    summary = {'character': deck.character.name if deck.character_id else ''}
    if mine:
        summary.update({'id': deck.id, 'name': deck.name})
    return summary


def room_view(room, token):
    """요청한 플레이어 시점의 방 상태."""
    seat = _seat(room, token)
    expired = room.status == SimulatorRoom.STATUS_WAITING and room.expires_at <= timezone.now()

    def seat_view(name):
        present = name == 'host' or bool(room.guest_token)
        return {
            'present': present,
            'name': getattr(room, f'{name}_name') if present else '',
            'deck': _deck_summary(getattr(room, f'{name}_deck'), mine=seat == name),
            'ready': bool(getattr(room, f'{name}_ready')) if present else False,
            'me': seat == name,
        }

    payload = {
        'code': room.code,
        'kind': room.kind,
        'status': SimulatorRoom.STATUS_CLOSED if expired else room.status,
        'options': room.options,
        'seat': seat,
        'seats': {'host': seat_view('host'), 'guest': seat_view('guest')},
        'error': room.error,
    }
    if room.status == SimulatorRoom.STATUS_STARTED and room.session_id and seat:
        session = room.session
        role = 'p1' if seat == 'host' else 'p2'
        token_value = session.player1_token if role == 'p1' else session.player2_token
        if opens_in_game_client(session):
            payload['play_url'] = play_url(session.view_token, role, token_value)
        else:
            # 전용 패시브가 아직 예전 화면에만 있는 수동 대전
            payload['play_url'] = reverse('battlelog:simulatorSeat', kwargs={
                'view_token': session.view_token, 'seat': role, 'seat_token': token_value,
            })
        payload['view_token'] = session.view_token
        payload['seat_role'] = role
        payload['seat_token'] = token_value
    return payload


def _touch(room, seat):
    now = timezone.now()
    field = f'{seat}_seen_at'
    setattr(room, field, now)
    SimulatorRoom.objects.filter(pk=room.pk).update(**{field: now})


def create_room(user, body):
    options = _options(body)
    user = _user_or_none(user)
    deck = _load_deck(user, body['deck_id']) if body.get('deck_id') else None
    for _ in range(8):
        try:
            room = SimulatorRoom.objects.create(
                code=_new_code(), kind=SimulatorRoom.KIND_ROOM, options=options,
                host_token=_new_token(), host_user=user,
                host_name=_display_name(user, str(body.get('name') or '플레이어 1')[:40]),
                host_deck=deck, expires_at=timezone.now() + ROOM_LIFETIME,
            )
            return room
        except IntegrityError:
            continue
    raise RoomError('방을 만들지 못했습니다. 다시 시도해 주세요.')


def get_room(code):
    room = (
        SimulatorRoom.objects.select_related('host_deck__character', 'guest_deck__character', 'session')
        .filter(code=str(code or '').upper()).first()
    )
    if not room:
        raise RoomError('방을 찾을 수 없습니다. 코드를 확인해 주세요.')
    return room


def join_room(user, code, body):
    user = _user_or_none(user)
    with transaction.atomic():
        room = SimulatorRoom.objects.select_for_update().get(pk=get_room(code).pk)
        if room.kind != SimulatorRoom.KIND_ROOM:
            raise RoomError('퀵 매치에는 코드로 들어갈 수 없습니다.')
        if room.status != SimulatorRoom.STATUS_WAITING or room.expires_at <= timezone.now():
            raise RoomError('이미 시작했거나 닫힌 방입니다.')
        if room.guest_token:
            raise RoomError('이미 상대가 들어온 방입니다.')
        room.guest_token = _new_token()
        room.guest_user = user
        room.guest_name = _display_name(user, str(body.get('name') or '플레이어 2')[:40])
        room.guest_seen_at = timezone.now()
        if body.get('deck_id'):
            room.guest_deck = _load_deck(user, body['deck_id'])
        room.save()
    return room, room.guest_token


def _seat_or_error(room, token):
    seat = _seat(room, token)
    if not seat:
        raise RoomError('이 방의 참가자가 아닙니다.')
    return seat


def set_deck(user, code, token, deck_id):
    user = _user_or_none(user)
    with transaction.atomic():
        room = SimulatorRoom.objects.select_for_update().get(pk=get_room(code).pk)
        seat = _seat_or_error(room, token)
        if room.status != SimulatorRoom.STATUS_WAITING:
            raise RoomError('대전이 이미 시작되었습니다.')
        # 덱 권한은 지금 덱을 고르는 플레이어 계정으로 확인한다.
        setattr(room, f'{seat}_deck', _load_deck(user, deck_id))
        setattr(room, f'{seat}_user', user or getattr(room, f'{seat}_user'))
        setattr(room, f'{seat}_ready', False)
        room.save()
    return room


def set_ready(code, token, ready):
    with transaction.atomic():
        room = SimulatorRoom.objects.select_for_update().get(pk=get_room(code).pk)
        seat = _seat_or_error(room, token)
        if room.status != SimulatorRoom.STATUS_WAITING:
            return room
        if ready and not getattr(room, f'{seat}_deck'):
            raise RoomError('먼저 덱을 고르세요.')
        setattr(room, f'{seat}_ready', bool(ready))
        room.save()
        if room.host_ready and room.guest_ready and room.host_deck_id and room.guest_deck_id:
            _start(room)
    return room


def leave_room(code, token):
    with transaction.atomic():
        room = SimulatorRoom.objects.select_for_update().get(pk=get_room(code).pk)
        seat = _seat_or_error(room, token)
        if room.status != SimulatorRoom.STATUS_WAITING:
            return room
        if seat == 'host':
            room.status = SimulatorRoom.STATUS_CLOSED
        else:
            room.guest_token = None
            room.guest_user = None
            room.guest_name = ''
            room.guest_deck = None
            room.guest_ready = False
            room.guest_seen_at = None
            room.host_ready = False
        room.save()
    return room


def poll_room(code, token):
    room = get_room(code)
    seat = _seat(room, token)
    if seat:
        _touch(room, seat)
    return room


def _start(room):
    """두 자리가 준비되면 대전을 만든다(방장 p1, 참가자 p2). 잠근 방 안에서 부른다."""
    options = room.options or {}
    try:
        session = start_session(
            room.host_user or AnonymousUser(),
            player1_deck_id=room.host_deck_id,
            player2_deck_id=room.guest_deck_id,
            mode=options.get('mode') or LumenSimulatorSession.MODE_AUTOMATIC,
            opponent='human',
            player1_name=room.host_name,
            player2_name=room.guest_name,
            ready_timeout_seconds=options.get('ready_timeout_seconds', TIMER_DEFAULTS['ready_timeout_seconds']),
            effect_timeout_seconds=options.get('effect_timeout_seconds', TIMER_DEFAULTS['effect_timeout_seconds']),
            player2_user=room.guest_user or AnonymousUser(),
        )
    except (PermissionError, ValueError) as exc:
        message = ' '.join(exc.args[0]) if isinstance(exc, PermissionError) else str(exc)
        room.error = message[:200]
        room.host_ready = False
        room.guest_ready = False
        room.save()
        return
    room.session = session
    room.status = SimulatorRoom.STATUS_STARTED
    room.error = ''
    room.save()


def quick_match(user, body):
    """덱을 정해 퀵 매치를 기다린다. 기다리는 다른 플레이어가 있으면 바로 짝을 짓는다.

    돌려주는 값: (방, 내 토큰). 짝이 지어졌으면 방은 이미 시작 상태다.
    """
    user = _user_or_none(user)
    deck = _load_deck(user, body.get('deck_id'))
    name = _display_name(user, str(body.get('name') or '플레이어')[:40])
    now = timezone.now()
    with transaction.atomic():
        waiting = (
            SimulatorRoom.objects.select_for_update()
            .filter(
                kind=SimulatorRoom.KIND_QUICK, status=SimulatorRoom.STATUS_WAITING,
                guest_token__isnull=True, expires_at__gt=now,
                host_seen_at__gte=now - QUICK_STALE,
            )
            .order_by('created_at')
        )
        if user is not None:
            # 같은 계정끼리는 짝을 짓지 않는다(같은 사람이 두 창에서 기다리는 경우).
            waiting = waiting.exclude(host_user=user)
        partner = waiting.first()
        if partner:
            partner.guest_token = _new_token()
            partner.guest_user = user
            partner.guest_name = name
            partner.guest_deck = deck
            partner.guest_ready = True
            partner.guest_seen_at = now
            partner.save()
            _start(partner)
            return partner, partner.guest_token
    for _ in range(8):
        try:
            room = SimulatorRoom.objects.create(
                code=_new_code(), kind=SimulatorRoom.KIND_QUICK,
                options={'mode': LumenSimulatorSession.MODE_AUTOMATIC, **TIMER_DEFAULTS},
                host_token=_new_token(), host_user=user, host_name=name,
                host_deck=deck, host_ready=True,
                expires_at=now + QUICK_LIFETIME,
            )
            return room, room.host_token
        except IntegrityError:
            continue
    raise RoomError('매칭을 시작하지 못했습니다. 다시 시도해 주세요.')
