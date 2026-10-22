import json

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from card.models import Character
from .models import PartyRoom
from .party_services import PartyConflict, create_room, join_room, perform_party_action, serialize_room, test_player_seat
from .services import initial_hp_for_character


def body(request):
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError('입력 형식이 올바르지 않습니다.')
    if not isinstance(data, dict):
        raise ValueError('입력 형식이 올바르지 않습니다.')
    return data


def player_token(request):
    return request.headers.get('X-Party-Player', '')[:64]


def error_response(exc):
    return JsonResponse({'error': str(exc)}, status=403 if isinstance(exc, PermissionDenied)
                        else 409 if isinstance(exc, PartyConflict) else 400)


@require_GET
@ensure_csrf_cookie
def party_home(request):
    characters = [{'id': c.pk, 'name': c.name, 'hp': initial_hp_for_character(c)}
                  for c in Character.objects.order_by('id')]
    return render(request, 'battlelog/party_home_v2.html', {'characters': characters})


@require_GET
def party_board(request):
    return render(request, 'battlelog/party_board_3d.html')


@require_GET
@ensure_csrf_cookie
def party_room(request, code):
    room = get_object_or_404(PartyRoom, code=code.upper())
    characters = [{'id': c.pk, 'name': c.name, 'hp': initial_hp_for_character(c)}
                  for c in Character.objects.order_by('id')]
    return render(request, 'battlelog/party_room_v2.html', {
        'room': room, 'state': serialize_room(room), 'characters': characters,
    })


@require_POST
def party_create(request):
    try:
        room, player = create_room(body(request))
    except ValueError as exc:
        return error_response(exc)
    return JsonResponse({'token': player.token, 'state': serialize_room(room, player.token)}, status=201)


@require_POST
def party_join(request, code):
    get_object_or_404(PartyRoom, code=code.upper())
    try:
        room, player = join_room(code.upper(), body(request))
    except ValueError as exc:
        return error_response(exc)
    return JsonResponse({'token': player.token, 'state': serialize_room(room, player.token)}, status=201)


@require_GET
def party_state(request, code):
    room = get_object_or_404(PartyRoom, code=code.upper())
    response = JsonResponse(serialize_room(room, player_token(request)))
    response['Cache-Control'] = 'no-store'
    return response


@require_POST
def party_action(request, code):
    get_object_or_404(PartyRoom, code=code.upper())
    try:
        room = perform_party_action(code.upper(), player_token(request), body(request))
    except (ValueError, PermissionDenied) as exc:
        return error_response(exc)
    return JsonResponse({'state': serialize_room(room, player_token(request))})


@require_POST
def party_test_seat(request, code):
    room = get_object_or_404(PartyRoom, code=code.upper())
    try:
        player = test_player_seat(room, body(request))
    except ValueError as exc:
        return error_response(exc)
    token = player.token if player else ''
    response = JsonResponse({'token': token, 'state': serialize_room(room, token)})
    response['Cache-Control'] = 'no-store'
    return response
