"""Automatic simulator matches for the app.

The app picks decks natively (JWT, so private decks of the signed-in user work)
and then opens the game client page in a WebView. The WebView needs no login:
seat tokens in the returned URLs authorize the seats.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from battlelog.play_views import create_play_session


@api_view(['POST'])
@permission_classes([AllowAny])
def sessions(request):
    payload, status = create_play_session(request.user, request.data)
    if payload.get('ok'):
        payload['urls'] = {role: request.build_absolute_uri(url) for role, url in payload['urls'].items()}
    return Response(payload, status=status)
