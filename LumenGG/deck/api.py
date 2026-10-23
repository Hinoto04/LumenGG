import copy
import datetime
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction, IntegrityError
from django.db.models import DateField, Min, Q, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.response import Response
from card.models import Card, Character
from .models import Deck, Regulation, RegulationVersion
from .regulations import accessible_versions, version_payload, normalize_regulation_rules
from .validation import snapshot_deck, validate


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def regulations(request):
    if request.method == 'GET':
        return Response({'versions': [version_payload(v) for v in accessible_versions(request.user)]})
    if not request.user.is_authenticated:
        raise PermissionDenied('로그인이 필요합니다.')
    body = request.data
    try:
        rules = normalize_regulation_rules(body.get('rules', {}))
        ids = {pk for key in ('bans', 'combinations') for row in rules[key] for pk in row['card_ids']}
        if Card.objects.filter(pk__in=ids).count() != len(ids):
            raise DjangoValidationError('존재하지 않는 카드입니다.')
        name, version_name = body.get('name', ''), body.get('version', '')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120 or not isinstance(version_name, str) or not 1 <= len(version_name.strip()) <= 64:
            raise DjangoValidationError('규정 이름과 버전을 입력해주세요.')
        with transaction.atomic():
            if body.get('regulation_id'):
                regulation = get_object_or_404(Regulation.objects.select_for_update(), pk=body['regulation_id'])
                if regulation.owner_id != request.user.id and not (regulation.owner_id is None and request.user.is_staff):
                    raise PermissionDenied('자신의 규정만 수정할 수 있습니다.')
            else:
                regulation = Regulation.objects.create(name=name.strip(), owner=request.user)
            published = RegulationVersion.objects.create(regulation=regulation, version=version_name.strip(), rules=rules,
                effective_date=body.get('effective_date') or None, source=body.get('source') or '')
        return Response(version_payload(published), status=201)
    except (DjangoValidationError, IntegrityError, TypeError, ValueError) as exc:
        raise ValidationError(str(exc)) from exc


@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def options(request):
    from common.language import translated_card_field, normalize_language
    language = normalize_language(request.query_params.get('lang', 'ko'))
    cards = Card.objects.filter(Q(type='특성') | Q(code__icontains='PS')).annotate(
        earliest_release=Coalesce(
            Min('collection_card__pack__released'),
            Value(datetime.date.max),
            output_field=DateField(),
        ),
    ).prefetch_related('translations').order_by('character_id', 'earliest_release', 'id')
    selected = {}
    if request.query_params.get('deck_id') and not request.query_params['deck_id'].isdigit():
        raise ValidationError('덱 번호가 올바르지 않습니다.')
    if request.query_params.get('deck_id'):
        from .views.views import can_view_deck
        deck = get_object_or_404(Deck, pk=request.query_params['deck_id'], deleted=False)
        if not can_view_deck(request.user, deck):
            raise PermissionDenied()
        selected = {'trait_card_id': deck.trait_card_id, 'regulation_version_id': deck.regulation_version_id,
                    'reserve_cards': [{'card_id': e.card_id, 'count': e.count} for e in deck.reserve_entries.all()]}
    versions = list(accessible_versions(request.user).exclude(regulation__name='기본 규정'))
    if (selected.get('regulation_version_id') and deck.regulation_version.regulation.name != '기본 규정'
            and not any(v.pk == selected['regulation_version_id'] for v in versions)):
        versions.append(deck.regulation_version)
    return Response({'traits': [{'id': c.pk, 'character_id': c.character_id, 'name': translated_card_field(c, language, 'name'), 'code': c.code, 'img': c.img_sm or c.img,
                                'trait_config': c.trait_config, 'deck_rules': (c.effect_definition or {}).get('deck_rules', {})} for c in cards],
                     'selected': selected,
                     'reserve_candidates': [{'id': c.pk, 'name': translated_card_field(c, language, 'name'), 'code': c.code, 'character_id': c.character_id, 'type': c.type,
                                             'ultimate': c.ultimate, 'frame': c.frame, 'img': c.img, 'img_sm': c.img_sm} for c in Card.objects.exclude(type='토큰').prefetch_related('translations')],
                     'versions': [version_payload(v) for v in versions]})


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([JWTAuthentication, SessionAuthentication])
def validation(request):
    from .views.views import can_view_deck
    if request.data.get('candidate') is not None:
        from .validation import snapshot_candidate
        try:
            return Response(validate(snapshot_candidate(request.data['candidate'], request.user), stage='draft'))
        except (ValueError, TypeError, KeyError, Card.DoesNotExist, Character.DoesNotExist) as exc:
            raise ValidationError('검사 요청이 올바르지 않습니다.') from exc
    deck = get_object_or_404(Deck, pk=request.data.get('deck_id'), deleted=False)
    if not can_view_deck(request.user, deck):
        raise PermissionDenied()
    version = deck.regulation_version
    if request.data.get('regulation_version_id'):
        version = get_object_or_404(accessible_versions(request.user), pk=request.data['regulation_version_id'])
    snapshot = snapshot_deck(deck, version)
    try:
        return Response(validate(snapshot, stage=request.data.get('stage', 'registration'), active=request.data.get('active')))
    except (ValueError, TypeError, KeyError) as exc:
        raise ValidationError('검사 요청이 올바르지 않습니다.') from exc
