"""Read-only mobile deck browsing; never expose another user's private decks."""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import NotAuthenticated, ValidationError

from deck.models import Deck
from .sync import deck_payload


def browse_payload(deck):
    return {**deck_payload(deck), 'author': {'id': deck.author_id, 'username': deck.author.username}}


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
    page_size = 30
    count = decks.count()
    rows = decks.order_by('-created', '-id')[(page - 1) * page_size:page * page_size]
    return Response({'decks': [browse_payload(d) for d in rows], 'count': count,
                     'next_page': page + 1 if page * page_size < count else None})


@api_view(['GET'])
@permission_classes([AllowAny])
def deck_detail(request, deck_id):
    visible = Q(visibility__in=[Deck.VISIBILITY_PUBLIC, Deck.VISIBILITY_UNLISTED], private=False)
    if request.user.is_authenticated:
        visible |= Q(author=request.user)
    deck = get_object_or_404(Deck.objects.filter(visible, deleted=False)
                            .select_related('author', 'regulation_version').prefetch_related('cids', 'reserve_entries'), pk=deck_id)
    return Response(browse_payload(deck))
