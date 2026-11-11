"""Automatic simulator matches for the app.

The app picks decks natively (JWT, so private decks of the signed-in user work)
and then opens the game client page in a WebView. The WebView needs no login:
seat tokens in the returned URLs authorize the seats.

사람끼리 대전은 웹 로비와 같은 방 · 퀵 매치(battlelog/play_rooms.py)를 쓴다. 각 플레이어는 자기 덱만 고르고,
덱 권한은 JWT 계정으로 확인한다. 자리 토큰은 본문 `token`으로만 주고받는다.
"""
from functools import wraps

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from battlelog import play_rooms
from battlelog.play_views import create_play_session


@api_view(['POST'])
@permission_classes([AllowAny])
def sessions(request):
    payload, status = create_play_session(request.user, request.data)
    if payload.get('ok'):
        payload['urls'] = {role: request.build_absolute_uri(url) for role, url in payload['urls'].items()}
    return Response(payload, status=status)


def _room_endpoint(handler):
    """RoomError를 {ok: false, error} 400 응답으로 바꾼다."""

    @api_view(['POST'])
    @permission_classes([AllowAny])
    @wraps(handler)
    def wrapped(request, *args, **kwargs):
        body = request.data if isinstance(request.data, dict) else {}
        try:
            return handler(request, body, *args, **kwargs)
        except play_rooms.RoomError as exc:
            return Response({'ok': False, 'error': str(exc)}, status=400)

    return wrapped


def _room_response(request, room, token, status=200):
    view = play_rooms.room_view(room, token)
    if view.get('play_url'):
        view['play_url'] = request.build_absolute_uri(view['play_url'])
    # 방 초대 링크(사이트 로비). 앱이 없는 상대도 브라우저로 참가할 수 있다.
    if view['kind'] == 'room':
        view['invite_url'] = request.build_absolute_uri(f'/battlelog/simulator/?room={room.code}')
    return Response({'ok': True, 'token': token, 'room': view}, status=status)


def _token(body):
    return str(body.get('token') or '')


@_room_endpoint
def room_create(request, body):
    room = play_rooms.create_room(request.user, body)
    return _room_response(request, room, room.host_token, status=201)


@_room_endpoint
def room_state(request, body, code):
    return _room_response(request, play_rooms.poll_room(code, _token(body)), _token(body))


@_room_endpoint
def room_join(request, body, code):
    room, token = play_rooms.join_room(request.user, code, body)
    return _room_response(request, room, token)


@_room_endpoint
def room_deck(request, body, code):
    room = play_rooms.set_deck(request.user, code, _token(body), body.get('deck_id'))
    return _room_response(request, room, _token(body))


@_room_endpoint
def room_ready(request, body, code):
    room = play_rooms.set_ready(code, _token(body), bool(body.get('ready')))
    return _room_response(request, room, _token(body))


@_room_endpoint
def room_leave(request, body, code):
    return _room_response(request, play_rooms.leave_room(code, _token(body)), _token(body))


@_room_endpoint
def quick(request, body):
    room, token = play_rooms.quick_match(request.user, body)
    return _room_response(request, room, token, status=201)
