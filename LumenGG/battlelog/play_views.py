"""Game client (play/) page and its JSON endpoints.

The client itself is a static bundle built from play/ into static/play/
(``npm run build:django`` in play/). See docs/PLAY_PROTOCOL.md.
"""

import json

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from deck.models import Deck

from .models import LumenSimulatorSession
from .play_start import opens_in_game_client, session_links, start_session
from .simulator_services import role_for_token, simulator_queryset
from .views import deck_rows, deck_search_rows


def _json_body(request):
    try:
        body = json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return body if isinstance(body, dict) else {}


def _bundle_version():
    """번들 파일의 수정 시각. 주소에 붙여 배포 뒤 브라우저가 예전 번들을 계속 쓰지 않게 한다."""
    import os

    from django.contrib.staticfiles import finders

    path = finders.find('play/play.js')
    try:
        return str(int(os.path.getmtime(path))) if path else ''
    except OSError:
        return ''


@ensure_csrf_cookie
@require_GET
def play(req):
    """Single page: lobby without a query, a game with ?game=&seat=&token=."""
    context = {'bundle_version': _bundle_version()}
    if not req.GET.get('game') and 'fixtures' not in req.GET:
        # 대전 전 화면(로비)은 다른 DB 화면처럼 사이트 머리글(navbar) 아래에 둔다.
        return render(req, 'battlelog/play_lobby.html', context)
    return render(req, 'battlelog/play.html', context)


@require_GET
def play_decks(req):
    """Deck picker: ?q= searches like the start page, ?mine=1 lists the user's decks."""
    if req.GET.get('mine'):
        if not req.user.is_authenticated:
            return JsonResponse({'decks': [], 'login_required': True})
        decks = (
            Deck.objects.filter(author=req.user, deleted=False)
            .select_related('author', 'character')
            .order_by('-created', '-id')[:60]
        )
        return JsonResponse({'decks': deck_rows(req, decks)})
    return JsonResponse({'decks': deck_search_rows(req, req.GET.get('q', ''))})


def create_play_session(user, body):
    """Validate a JSON request and create a session (automatic by default). Returns (payload, status)."""
    opponent = body.get('opponent', 'ai')
    if opponent not in ('ai', 'human'):
        return {'ok': False, 'error': '상대 종류가 올바르지 않습니다.'}, 400
    mode = body.get('mode', LumenSimulatorSession.MODE_AUTOMATIC)
    if mode not in (LumenSimulatorSession.MODE_AUTOMATIC, LumenSimulatorSession.MODE_MANUAL):
        return {'ok': False, 'error': '대전 방식이 올바르지 않습니다.'}, 400
    if mode == LumenSimulatorSession.MODE_MANUAL and opponent != 'human':
        return {'ok': False, 'error': '수동 대전은 사람끼리만 할 수 있습니다.'}, 400
    try:
        session = start_session(
            user,
            player1_deck_id=body.get('p1_deck'),
            player2_deck_id=body.get('p2_deck'),
            mode=mode,
            opponent=opponent,
            player1_name=str(body.get('player1_name') or '')[:40],
            player2_name=str(body.get('player2_name') or '')[:40],
            ready_timeout_seconds=body.get('ready_timeout_seconds', 0),
            effect_timeout_seconds=body.get('effect_timeout_seconds', 0),
            regulation_version_id=body.get('regulation_version_id') or None,
        )
    except PermissionError as exc:
        return {'ok': False, 'error': ' '.join(exc.args[0])}, 403
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}, 400
    links = session_links(session)
    if not opens_in_game_client(session):
        # Character-specific passive panels exist only on the legacy page.
        links['legacy'] = True
        links['urls'] = {role: _legacy_url(session, role) for role in links['urls']}
    return {'ok': True, 'mode': session.mode, **links}, 201


def _legacy_url(session, role):
    from django.urls import reverse
    if role == 'viewer':
        return reverse('battlelog:simulatorView', kwargs={'view_token': session.view_token})
    token = session.player1_token if role == 'p1' else session.player2_token
    return reverse('battlelog:simulatorSeat', kwargs={
        'view_token': session.view_token, 'seat': role, 'seat_token': token,
    })


@require_POST
def play_new(req):
    payload, status = create_play_session(req.user, _json_body(req))
    return JsonResponse(payload, status=status)


@require_POST
def play_preparation_check(req, view_token):
    """Validate a deck preparation candidate without saving it.

    Only the seat's own registered deck is checked, so this reveals nothing
    the player does not already know.
    """
    from deck.validation import validate

    session = get_object_or_404(simulator_queryset(), view_token=view_token)
    body = _json_body(req)
    side = role_for_token(session, body.get('seat', ''), body.get('seat_token', ''))
    if side not in ('p1', 'p2'):
        raise PermissionDenied()
    preparation = (session.document or {}).get('preparation')
    if not preparation or preparation.get('status') != 'editing':
        return JsonResponse({'ok': False, 'error': '준비 중인 대전이 아닙니다.'}, status=409)
    player = preparation['players'][side]
    ruleset = session.ruleset_release.snapshot if session.ruleset_release_id else None
    try:
        report = validate(
            player['registered'], stage='setup',
            active=body.get('active', player['active']), ruleset=ruleset,
        )
    except (TypeError, ValueError, KeyError) as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    return JsonResponse({'ok': True, 'report': report})



# ---------------------------------------------------------------------------
# 방 · 퀵 매치 (play_rooms.py). 자리 토큰은 주소에 싣지 않고 POST 본문으로만 주고받는다.

def _room_endpoint(handler):
    """RoomError를 {ok: false, error} 400 응답으로 바꾼다."""
    from functools import wraps

    from .play_rooms import RoomError

    @wraps(handler)
    def wrapped(req, *args, **kwargs):
        try:
            return handler(req, _json_body(req), *args, **kwargs)
        except RoomError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    return require_POST(wrapped)


def _room_json(room, token, status=200):
    from .play_rooms import room_view

    return JsonResponse({'ok': True, 'token': token, 'room': room_view(room, token)}, status=status)


@_room_endpoint
def play_room_create(req, body):
    from .play_rooms import create_room

    room = create_room(req.user, body)
    return _room_json(room, room.host_token, status=201)


@_room_endpoint
def play_room_state(req, body, code):
    from .play_rooms import poll_room

    token = str(body.get('token') or '')
    return _room_json(poll_room(code, token), token)


@_room_endpoint
def play_room_join(req, body, code):
    from .play_rooms import join_room

    room, token = join_room(req.user, code, body)
    return _room_json(room, token)


@_room_endpoint
def play_room_deck(req, body, code):
    from .play_rooms import set_deck

    token = str(body.get('token') or '')
    return _room_json(set_deck(req.user, code, token, body.get('deck_id')), token)


@_room_endpoint
def play_room_ready(req, body, code):
    from .play_rooms import set_ready

    token = str(body.get('token') or '')
    return _room_json(set_ready(code, token, bool(body.get('ready'))), token)


@_room_endpoint
def play_room_leave(req, body, code):
    from .play_rooms import leave_room

    token = str(body.get('token') or '')
    return _room_json(leave_room(code, token), token)


@_room_endpoint
def play_quick(req, body):
    from .play_rooms import quick_match

    room, token = quick_match(req.user, body)
    return _room_json(room, token, status=201)
