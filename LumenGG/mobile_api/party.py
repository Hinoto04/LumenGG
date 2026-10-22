from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from battlelog.models import PartyRoom
from battlelog.party_services import PartyConflict, create_room, join_room, perform_party_action, serialize_room, test_player_seat


class PartyThrottle(AnonRateThrottle):
    # Several guests share the same Wi-Fi address at an offline table.
    rate = '300/min'


def _token(request):
    return request.headers.get('X-Party-Player', '')[:64]


def _error(exc):
    return Response({'error': str(exc)}, status=403 if isinstance(exc, PermissionDenied)
                    else 409 if isinstance(exc, PartyConflict) else 400)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PartyThrottle])
def create(request):
    if not isinstance(request.data, dict):
        return Response({'error': '입력 형식이 올바르지 않습니다.'}, status=400)
    try:
        room, player = create_room(request.data)
    except ValueError as exc:
        return _error(exc)
    return Response({'token': player.token, 'state': serialize_room(room, player.token)}, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PartyThrottle])
def join(request, code):
    get_object_or_404(PartyRoom, code=code.upper())
    if not isinstance(request.data, dict):
        return Response({'error': '입력 형식이 올바르지 않습니다.'}, status=400)
    try:
        room, player = join_room(code.upper(), request.data)
    except ValueError as exc:
        return _error(exc)
    return Response({'token': player.token, 'state': serialize_room(room, player.token)}, status=201)


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PartyThrottle])
def state(request, code):
    room = get_object_or_404(PartyRoom, code=code.upper())
    return Response(serialize_room(room, _token(request)), headers={'Cache-Control': 'no-store'})


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PartyThrottle])
def action(request, code):
    get_object_or_404(PartyRoom, code=code.upper())
    if not isinstance(request.data, dict):
        return Response({'error': '입력 형식이 올바르지 않습니다.'}, status=400)
    try:
        room = perform_party_action(code.upper(), _token(request), request.data)
    except (ValueError, PermissionDenied) as exc:
        return _error(exc)
    return Response({'state': serialize_room(room, _token(request))})


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PartyThrottle])
def test_seat(request, code):
    room = get_object_or_404(PartyRoom, code=code.upper())
    if not isinstance(request.data, dict):
        return Response({'error': '입력 형식이 올바르지 않습니다.'}, status=400)
    try:
        player = test_player_seat(room, request.data)
    except ValueError as exc:
        return _error(exc)
    token = player.token if player else ''
    return Response({'token': token, 'state': serialize_room(room, token)}, headers={'Cache-Control': 'no-store'})
