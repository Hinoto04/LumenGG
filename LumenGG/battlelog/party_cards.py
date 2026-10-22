"""Card artwork and separately editable text, shared by web and mobile clients."""
from django.templatetags.static import static

from .models import PartyCard
from .party_board import board_for


def card_catalog(room, refresh=False):
    if refresh or not hasattr(room, '_party_card_catalog'):
        room._party_card_catalog = {
            (card.kind, card.key): {
                'card_id': card.code, 'label': card.name, 'description': card.effect_text,
                'image': static(card.image_path), 'effect_box': card.effect_box,
            } for card in PartyCard.objects.all()
        }
    return room._party_card_catalog


def display_board(room):
    board = board_for(room)
    cards = card_catalog(room)
    return {**board,
            'shop': {key: {**item, **cards.get(('item', key), {})} for key, item in board['shop'].items()},
            'events': [{**event, **cards.get(('event', event['id']), {})} for event in board['events']],
            'card_backs': {kind: static(f'v2/party-cards/v2/back-{kind}.png') for kind in ('item', 'event')}}


def display_event(room, event):
    return {**event, **card_catalog(room).get(('event', event['id']), {})} if event else None
