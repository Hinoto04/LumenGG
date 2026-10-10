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
@permission_classes([AllowAny])
def deck_list(request):
    scope = request.query_params.get('scope', 'public')
    if scope not in ('mine', 'public'):
        raise ValidationError('Invalid deck scope.')
    decks = Deck.objects.filter(deleted=False).select_related('author').prefetch_related('cids')
    if scope == 'mine':
        if not request.user.is_authenticated:
            raise NotAuthenticated()
        decks = decks.filter(author=request.user)
    else:
        decks = decks.filter(visibility=Deck.VISIBILITY_PUBLIC, private=False)
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
                            .select_related('author').prefetch_related('cids'), pk=deck_id)
    return Response(browse_payload(deck))
