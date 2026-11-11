"""Read-only mobile deck browsing; never expose another user's private decks."""
from django.db import transaction
from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import NotAuthenticated, ValidationError

from deck.models import Deck, DeckLike
from .sync import deck_payload


def browse_payload(deck):
    return {**deck_payload(deck), 'author': {'id': deck.author_id, 'username': deck.author.username}}


def _bookmark_annotation(request):
    if not request.user.is_authenticated:
        return None
    return Exists(DeckLike.objects.filter(deck=OuterRef('pk'), author=request.user, bookmark=True))


def _visible_decks(request):
    visible = Q(visibility__in=[Deck.VISIBILITY_PUBLIC, Deck.VISIBILITY_UNLISTED], private=False)
    if request.user.is_authenticated:
        visible |= Q(author=request.user)
    return Deck.objects.filter(visible, deleted=False)


@api_view(['GET'])
def submitted_deck(request, submission_id):
    from tournament.models import TournamentDeckSubmission
    from rest_framework.exceptions import PermissionDenied
    submission = get_object_or_404(TournamentDeckSubmission.objects.select_related('participant__tournament', 'deck__author'), pk=submission_id)
    if submission.participant.user_id != request.user.id and submission.participant.tournament.organizer_id != request.user.id and not request.user.is_staff:
        raise PermissionDenied()
    from deck.validation import snapshot_deck
    snapshot = submission.snapshot or snapshot_deck(submission.deck)
    from deck.models import RegulationVersion
    from deck.regulations import version_payload
    version = RegulationVersion.objects.filter(pk=snapshot.get('regulation_version_id')).select_related('regulation').first()
    return Response({'id': submission.deck_id, 'uuid': f'submission:{submission.pk}', 'name': snapshot.get('name', submission.deck.name),
                     'schema_version': 2, 'character_id': snapshot['character_id'], 'trait_card_id': snapshot.get('trait_card_id'),
                     'regulation_version_id': snapshot.get('regulation_version_id'), 'regulation_rules': snapshot['regulation_rules'], 'regulation': version_payload(version) if version else None,
                     'cards': snapshot['cards'], 'reserve_cards': snapshot['reserve_cards'], 'snapshot_catalog': snapshot['catalog'],
                     'validation': submission.validation, 'description': '', 'keyword': '', 'tags': '', 'visibility': 'private', 'locked': True})


# 웹 덱 목록(deck/views/views.py index)과 같은 정렬. 값이 없으면 예전 앱과 같은 최신순이다.
DECK_SORTS = {
    'recent': ('-created', '-id'),
    'version': ('-version', '-created', '-id'),
    'like': ('-like_count', '-created', '-id'),
}


@api_view(['GET'])
@permission_classes([AllowAny])
def deck_list(request):
    scope = request.query_params.get('scope', 'public')
    if scope not in ('mine', 'public'):
        raise ValidationError('Invalid deck scope.')
    decks = Deck.objects.filter(deleted=False).select_related('author', 'regulation_version').prefetch_related('cids', 'reserve_entries')
    if scope == 'mine':
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        decks = decks.filter(author=request.user)
    else:
        decks = decks.filter(visibility=Deck.VISIBILITY_PUBLIC, private=False)
    bookmarked = request.query_params.get('bookmarked', '')
    if bookmarked not in ('', '0', '1'):
        raise ValidationError('Invalid bookmark filter.')
    if bookmarked == '1':
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        # 북마크 목록은 링크 공개 덱과 내 비공개 덱까지 함께 보여준다.
        base = _visible_decks(request) if scope == 'public' else Deck.objects.filter(deleted=False, author=request.user)
        decks = base.select_related('author', 'regulation_version').prefetch_related('cids', 'reserve_entries').filter(
            pk__in=DeckLike.objects.filter(author=request.user, bookmark=True).values('deck_id'))
    for field in ('trait_card_id', 'regulation_version_id'):
        value = request.query_params.get(field)
        if value:
            if not value.isdigit() or int(value) < 1:
                raise ValidationError('Invalid deck filter.')
            decks = decks.filter(**{field: int(value)})
    query = request.query_params.get('q', '').strip()[:255]
    if query:
        decks = decks.filter(Q(name__icontains=query) | Q(keyword__icontains=query)
                             | Q(tags__icontains=query) | Q(author__username__icontains=query))
    try:
        page = int(request.query_params.get('page', '1'))
        if not 1 <= page <= 1000000:
            raise ValueError
        character = request.query_params.get('character_id')
        if character:
            character = int(character)
            if character <= 0:
                raise ValueError
            decks = decks.filter(character_id=character)
    except (ValueError, TypeError):
        raise ValidationError('Invalid page or character.')
    sort = request.query_params.get('sort') or 'recent'
    if sort not in DECK_SORTS:
        raise ValidationError('Invalid deck sort.')
    likes = DeckLike.objects.filter(deck=OuterRef('pk'), like=True).values('deck').annotate(cnt=Count('id')).values('cnt')
    decks = decks.annotate(like_count=Subquery(likes, output_field=IntegerField()))
    bookmark = _bookmark_annotation(request)
    if bookmark is not None:
        decks = decks.annotate(is_bookmarked=bookmark)
    page_size = 30
    count = decks.count()
    rows = decks.order_by(*DECK_SORTS[sort])[(page - 1) * page_size:page * page_size]
    return Response({'decks': [{**browse_payload(d), 'like_count': d.like_count or 0,
                                'bookmarked': bool(getattr(d, 'is_bookmarked', False))} for d in rows], 'count': count,
                     'next_page': page + 1 if page * page_size < count else None})


@api_view(['GET'])
@permission_classes([AllowAny])
def deck_detail(request, deck_id):
    decks = _visible_decks(request).select_related('author', 'regulation_version').prefetch_related('cids', 'reserve_entries')
    bookmark = _bookmark_annotation(request)
    if bookmark is not None:
        decks = decks.annotate(is_bookmarked=bookmark)
    deck = get_object_or_404(decks, pk=deck_id)
    return Response({**browse_payload(deck), 'bookmarked': bool(getattr(deck, 'is_bookmarked', False)),
                     'bookmark_count': DeckLike.objects.filter(deck=deck, bookmark=True).count()})


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def deck_bookmark(request, deck_id):
    """웹의 토글과 달리 원하는 상태를 받아 저장하므로 같은 요청을 다시 보내도 결과가 같다."""
    value = request.data.get('bookmarked') if isinstance(request.data, dict) else None
    if not isinstance(value, bool):
        raise ValidationError('bookmarked must be true or false.')
    deck = get_object_or_404(_visible_decks(request), pk=deck_id)
    with transaction.atomic():
        rows = list(DeckLike.objects.select_for_update().filter(deck=deck, author=request.user).order_by('id'))
        if rows:
            DeckLike.objects.filter(pk__in=[row.pk for row in rows]).update(bookmark=value)
        elif value:
            DeckLike.objects.create(deck=deck, author=request.user, bookmark=True)
    return Response({'id': deck.pk, 'bookmarked': value,
                     'bookmark_count': DeckLike.objects.filter(deck=deck, bookmark=True).count()})
