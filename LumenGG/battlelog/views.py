import json

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from card.models import Card, Character
from deck.models import CardInDeck, Deck

from .event_buffer import recent_battle_event_payloads
from .realtime import broadcast_battle_session
from .services import (
    battle_session_queryset,
    can_control_session,
    can_toggle_sudden_death,
    character_options_for_session,
    create_standalone_session,
    perform_session_action,
    serialize_session,
)


def _session_queryset():
    return battle_session_queryset()


def _get_session(view_token):
    return get_object_or_404(_session_queryset(), view_token=view_token)


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return {}


def sim(req):
    characters = Character.objects.order_by('id')
    if req.method == 'POST':
        player1_character = get_object_or_404(Character, id=req.POST.get('player1_character'))
        player2_character = get_object_or_404(Character, id=req.POST.get('player2_character'))
        session = create_standalone_session(
            req.POST.get('player1_name', ''),
            req.POST.get('player2_name', ''),
            player1_character,
            player2_character,
            req.user,
        )
        return redirect('battlelog:sessionControl', view_token=session.view_token, control_token=session.control_token)

    return render(req, 'battlelog/sim_v2.html', {'characters': characters})


def sessionDetail(req, view_token):
    return _render_session(req, view_token, '')


def sessionControl(req, view_token, control_token):
    return _render_session(req, view_token, control_token)


def _render_session(req, view_token, control_token):
    session = _get_session(view_token)
    state = serialize_session(session, req.user, control_token, include_events=False)
    character_options = character_options_for_session(session, req.user, control_token)
    context = {
        'session': session,
        'state': state,
        'control_token': control_token,
        'can_control': can_control_session(req.user, session, control_token),
        'can_sudden_death': can_toggle_sudden_death(req.user, session, control_token),
        'character_options': character_options,
        'view_url': req.build_absolute_uri(state['view_url']),
        'control_url': req.build_absolute_uri(state['control_url']),
    }
    return render(req, 'battlelog/session_v2.html', context)


@require_GET
def sessionState(req, view_token):
    session = _get_session(view_token)
    control_token = req.GET.get('control_token', '')
    return JsonResponse(serialize_session(session, req.user, control_token, include_events=False))


@require_GET
def sessionEvents(req, view_token):
    session = _get_session(view_token)
    return JsonResponse({'events': recent_battle_event_payloads(session.id)})


@require_POST
def sessionAction(req, view_token):
    session = _get_session(view_token)
    body = _json_body(req)
    control_token = body.get('control_token', '')

    try:
        session = perform_session_action(session, body, req.user, control_token)
    except PermissionDenied:
        return JsonResponse({'ok': False, 'error': '조작 권한이 없습니다.'}, status=403)
    except (TypeError, ValueError) as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    broadcast_battle_session(session)
    return JsonResponse({'ok': True, 'state': serialize_session(session, req.user, control_token, include_events=False)})


def cardLoad(req):
    keyword = req.GET.get('keyword', '')
    if keyword:
        q = Q(name__contains=keyword)
        data = list(Card.objects.filter(q).values('name', 'img'))
    else:
        data = []
    return JsonResponse(data, safe=False)

def deckLoad(req):
    id = req.GET.get('id', '')
    try:
        deck = Deck.objects.get(id=id)
    except Deck.DoesNotExist:
        data = {'status': '404'}
    else:
        data = {'status': '200'}
        cards = CardInDeck.objects.filter(deck=deck)
        data['deck'] = list(cards.values('hand','side','count','card__name', 'card__img'))
    return JsonResponse(data)

def stream(req):
    return render(req, 'battlelog/stream.html', {})
