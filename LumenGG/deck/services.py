"""Deck writing rules shared by web and mobile clients."""
from card.models import Card
from deck.models import CardInDeck, Deck, is_forced_side_card
from statistic.models import CSDeck

def is_deck_locked_by_tournament(deck):
    if CSDeck.objects.filter(deck=deck).exists():
        return True
    if deck.locked:
        return True
    try:
        from tournament.models import Tournament, TournamentDeckSubmission
    except ImportError:
        return False
    return TournamentDeckSubmission.objects.filter(
        deck=deck,
        participant__tournament__status__in=[
            Tournament.STATUS_RUNNING,
            Tournament.STATUS_FINISHED,
        ],
    ).exists()


def normalize_deck_visibility(value):
    valid_values = {choice[0] for choice in Deck.VISIBILITY_CHOICES}
    if value in valid_values:
        return value
    if value in (True, 'true', 'True', '1', 1):
        return Deck.VISIBILITY_PRIVATE
    return Deck.VISIBILITY_PUBLIC

def get_max_deck_size(character_id):
    try:
        character_id = int(character_id)
    except (TypeError, ValueError):
        return 21
    if character_id == 5:
        return 24
    if character_id == 15:
        return 33
    if character_id == 16:
        return 26
    if character_id == 17:
        return 25
    return 21

def count_main_deck_cards(deck_entries):
    card_ids = [card_id for card_id, _count, _hand, _side in deck_entries]
    ultimate_card_ids = set(
        Card.objects.filter(id__in=card_ids, ultimate=True).values_list('id', flat=True)
    )
    return sum(
        count
        for card_id, count, _hand, _side in deck_entries
        if card_id not in ultimate_card_ids
    )

def validate_submitted_deck_size(deck_entries, character_id):
    main_deck_count = count_main_deck_cards(deck_entries)
    if main_deck_count < 5:
        return '덱 매수가 너무 적습니다.'
    max_deck_size = get_max_deck_size(character_id)
    if main_deck_count > max_deck_size:
        return f'덱 매수는 최대 {max_deck_size}장입니다.'
    return None

def normalize_submitted_deck(deck_data):
    card_ids = []
    for item in deck_data:
        try:
            card_ids.append(int(item[0]))
        except (IndexError, TypeError, ValueError):
            return None, '존재하지 않는 카드가 있습니다.'
    
    cards = Card.objects.in_bulk(card_ids)
    normalized = []
    ultimate_count = 0
    
    for item in deck_data:
        card_id = int(item[0])
        if card_id not in cards:
            return None, '존재하지 않는 카드가 있습니다.'
        
        card = cards[card_id]
        values = item[1]
        try:
            count = int(values.get('count', 0))
            hand = int(values.get('hand', 0))
            side = int(values.get('side', 0))
        except (AttributeError, TypeError, ValueError):
            return None, '덱 데이터가 올바르지 않습니다.'
        
        if count <= 0:
            continue
        
        if card.ultimate:
            ultimate_count += count
            hand = 0
            side = 0
        elif is_forced_side_card(card):
            hand = 0
            side = count
        elif hand + side > count:
            return None, '손패와 사이드의 카드 갯수가 덱에 들어간 카드보다 많을 수 없습니다.'
        
        normalized.append((card_id, count, hand, side))
    
    if ultimate_count > 1:
        return None, '얼티밋 카드는 1장까지만 넣을 수 있습니다.'
    
    return normalized, None

def merge_deck_entries(deck_entries):
    merged = {}
    for card_id, count, hand, side in deck_entries:
        if card_id not in merged:
            merged[card_id] = {'count': 0, 'hand': 0, 'side': 0}
        merged[card_id]['count'] += count
        merged[card_id]['hand'] += hand
        merged[card_id]['side'] += side

    result = []
    for card_id, values in merged.items():
        count = values['count']
        hand = values['hand']
        side = values['side']
        if hand + side > count:
            return None, '손패와 사이드의 카드 갯수가 덱에 들어간 카드보다 많을 수 없습니다.'
        result.append((card_id, count, hand, side))
    return result, None

def build_card_in_deck(deck, deck_entries):
    return [
        CardInDeck(
            card_id=card_id,
            deck=deck,
            count=count,
            hand=hand,
            side=side,
        )
        for card_id, count, hand, side in deck_entries
    ]

def replace_deck_cards(deck, deck_entries):
    CardInDeck.objects.filter(deck_id=deck.id).delete()
    CardInDeck.objects.bulk_create(build_card_in_deck(deck, deck_entries))

