from pathlib import Path
import re
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError, PermissionDenied
from django.db import transaction, IntegrityError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from card.models import Character, CharacterComment
from common.models import UserData
from battlelog.services import create_standalone_session, battle_session_queryset
from battlelog.models import BattleSession
from .catalog import client_version
from .models import CatalogRelease
from .sync import apply_sync
from .calculators import mobile_state, perform_mobile_action, StaleCalculator


def language(request):
    value = request.query_params.get('language', 'ko')
    return value if value in ('ko', 'en', 'ja') else 'ko'


def token(request):
    return request.headers.get('X-Calculator-Control', '')


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    username, password, email = (request.data.get(k, '') for k in ('username', 'password', 'email'))
    if not isinstance(username, str) or not re.fullmatch(r'[\w.@+-]{1,150}', username) or not isinstance(password, str):
        raise ValidationError('Invalid username or password.')
    User = get_user_model()
    candidate = User(username=username, email=email)
    try:
        validate_password(password, candidate)
        candidate.full_clean(exclude=['password'])
        with transaction.atomic():
            candidate.set_password(password)
            candidate.save()
            UserData.objects.get_or_create(user=candidate)
    except (DjangoValidationError, IntegrityError) as exc:
        raise ValidationError(getattr(exc, 'messages', ['Username is already in use.']))
    refresh = RefreshToken.for_user(candidate)
    return Response({'access': str(refresh.access_token), 'refresh': str(refresh)}, status=201)


@api_view(['POST'])
def logout(request):
    try:
        refresh = RefreshToken(request.data.get('refresh', ''))
        if str(refresh['user_id']) != str(request.user.pk):
            raise ValidationError('Token does not belong to this account.')
        refresh.blacklist()
    except TokenError:
        pass
    return Response({'ok': True})


@api_view(['DELETE'])
def account(request):
    if not request.user.check_password(request.data.get('password', '')):
        raise ValidationError('Password confirmation failed.')
    try:
        with transaction.atomic():
            CharacterComment.objects.filter(author=request.user).delete()
            request.user.delete()
    except IntegrityError:
        raise ValidationError('Account has protected data and could not be deleted.')
    return Response({'ok': True})


@api_view(['GET'])
@permission_classes([AllowAny])
def manifest(request):
    try:
        version = client_version(request.query_params.get('client_version', '1.0.0'))
        schema = int(request.query_params.get('schema_version', '1'))
    except (ValueError, TypeError):
        raise ValidationError('Invalid client compatibility information.')
    candidates = CatalogRelease.objects.filter(active=True, schema_version=schema)
    release = next((r for r in candidates if client_version(r.min_client_version) <= version), None)
    if release is None:
        # Keep old supported releases available when an incompatible version is published.
        release = next((r for r in CatalogRelease.objects.filter(schema_version=schema) if client_version(r.min_client_version) <= version), None)
    if release is None:
        return Response({'code': 'catalog_unavailable'}, status=503)
    if request.headers.get('If-None-Match') == '"' + release.version + '"':
        return Response(status=304, headers={'ETag': '"' + release.version + '"'})
    return Response({'release_version': release.version, 'schema_version': release.schema_version,
                     'min_client_version': release.min_client_version, 'published_at': release.published_at.isoformat(),
                     'download_url': '/api/mobile/v1/catalog/files/' + release.version,
                     'size_bytes': release.size_bytes, 'sha256': release.sha256},
                    headers={'ETag': '"' + release.version + '"', 'Cache-Control': 'no-cache'})


@api_view(['GET'])
@permission_classes([AllowAny])
def catalog_file(request, version):
    release = get_object_or_404(CatalogRelease, version=version)
    path = Path(settings.MOBILE_CATALOG_ROOT) / release.filename
    if not path.is_file():
        raise Http404()
    response = FileResponse(path.open('rb'), content_type='application/vnd.sqlite3')
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    response['ETag'] = '"' + release.sha256 + '"'
    response['Content-Length'] = release.size_bytes
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
def catalog_image(request, filename):
    if not re.fullmatch(r'[0-9a-f]{64}\.(webp|png|jpg|jpeg|gif)', filename):
        raise Http404()
    path = Path(settings.MOBILE_CATALOG_ROOT) / 'images' / filename
    if not path.is_file():
        raise Http404()
    response = FileResponse(path.open('rb'))
    response['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


@api_view(['GET', 'POST'])
def sync(request):
    return Response(apply_sync(request.user, [] if request.method == 'GET' else request.data.get('operations', [])))


@api_view(['POST'])
@permission_classes([AllowAny])
def calculators(request):
    characters = []
    for key in ('player1_character', 'player2_character'):
        characters.append(get_object_or_404(Character, pk=request.data.get(key)))
    session = create_standalone_session(str(request.data.get('player1_name', ''))[:60], str(request.data.get('player2_name', ''))[:60],
                                        *characters, user=request.user)
    return Response({'view_token': session.view_token, 'control_token': session.control_token,
                     'state': mobile_state(session, session.control_token, language(request))}, status=201)


def standalone(view_token):
    return get_object_or_404(battle_session_queryset(), view_token=view_token, session_type=BattleSession.SESSION_STANDALONE)


@api_view(['GET'])
@permission_classes([AllowAny])
def calculator_state(request, view_token):
    return Response(mobile_state(standalone(view_token), token(request), language(request)))


@api_view(['GET'])
@permission_classes([AllowAny])
def calculator_events(request, view_token):
    return Response({'events': mobile_state(standalone(view_token), token(request), language(request)).get('events', [])})


@api_view(['POST'])
@permission_classes([AllowAny])
def calculator_action(request, view_token):
    standalone(view_token)
    try:
        session = perform_mobile_action(view_token, request.data, token(request), request.user)
    except StaleCalculator:
        return Response({'code': 'stale_state', 'state': mobile_state(standalone(view_token), token(request), language(request))}, status=409)
    except PermissionDenied:
        return Response({'code': 'permission_denied'}, status=403)
    except (ValueError, TypeError) as exc:
        raise ValidationError(str(exc))
    return Response({'ok': True, 'state': mobile_state(session, token(request), language(request))})
