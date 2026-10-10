"""Account-scoped, idempotent, arrival-ordered synchronization."""
import hashlib
import json
import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import ValidationError

from card.models import Character
from collection.models import Collected, CollectionCard
from deck.models import Deck
from deck.services import (
    is_deck_locked_by_tournament, normalize_submitted_deck, merge_deck_entries,
    validate_submitted_deck_size, replace_deck_cards,
)
from deck.utils import get_deck_version_from_entries
from .models import SyncReceipt


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def deck_payload(deck):
    return {
        'id': deck.id, 'uuid': str(deck.mobile_id), 'name': deck.name,
        'character_id': deck.character_id, 'description': deck.description,
        'keyword': deck.keyword, 'tags': deck.tags, 'visibility': deck.visibility,
        'deleted': deck.deleted, 'locked': is_deck_locked_by_tournament(deck),
        'version': deck.version,
        'author': {'id': deck.author_id, 'username': deck.author.username},
        'cards': [{'card_id': c.card_id, 'count': c.count, 'hand': c.hand, 'side': c.side} for c in deck.cids.all()],
    }


def account_snapshot(user):
    return {
        'user': {'id': user.pk, 'username': user.username},
        'decks': [deck_payload(d) for d in Deck.objects.filter(author=user).select_related('author').prefetch_related('cids').order_by('id')],
        'collection': list(Collected.objects.filter(user=user).order_by('card_id').values('card_id', 'amount')),
    }


def _integer(value, name, minimum=0, maximum=32767):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValidationError({name: 'Invalid integer.'})
    return value


def _deck_operation(user, operation):
    try:
        mobile_id = uuid.UUID(str(operation['entity_id']))
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ValidationError('A valid deck UUID is required.')
    deck = Deck.objects.select_for_update().filter(author=user, mobile_id=mobile_id).first()
    if deck and is_deck_locked_by_tournament(deck):
        raise ValidationError('This deck is locked. Your local draft has been kept.')
    if operation.get('action') == 'delete':
        if deck:
            deck.deleted = True
            deck.save(update_fields=['deleted'])
        else:
            return {'uuid': str(mobile_id), 'id': None}
        return {'uuid': str(mobile_id), 'id': deck.pk}
    if operation.get('action') != 'upsert':
        raise ValidationError('Unknown deck action.')
    data = operation.get('data')
    if not isinstance(data, dict):
        raise ValidationError('Deck data is required.')
    name = data.get('name', '')
    if not isinstance(name, str) or not name.strip() or len(name) > 255:
        raise ValidationError('Deck name must contain 1 to 255 characters.')
    character_id = _integer(data.get('character_id'), 'character_id', 1, 2147483647)
    if not Character.objects.filter(pk=character_id).exists():
        raise ValidationError('Character not found.')
    cards = data.get('cards')
    if not isinstance(cards, list) or len(cards) > 1000:
        raise ValidationError('Invalid card list.')
    entries = []
    for row in cards:
        if not isinstance(row, dict):
            raise ValidationError('Invalid card entry.')
        entries.append([_integer(row.get('card_id'), 'card_id', 1, 2147483647), {
            key: _integer(row.get(key, 0), key) for key in ('count', 'hand', 'side')
        }])
    normalized, error = normalize_submitted_deck(entries)
    if error:
        raise ValidationError(error)
    normalized, error = merge_deck_entries(normalized)
    if error:
        raise ValidationError(error)
    error = validate_submitted_deck_size(normalized, character_id)
    if error:
        raise ValidationError(error)
    visibility = data.get('visibility', Deck.VISIBILITY_PRIVATE)
    if visibility not in dict(Deck.VISIBILITY_CHOICES):
        raise ValidationError('Invalid visibility.')
    if deck is None:
        # UUIDs are globally unique; never attach a different user's deck.
        if Deck.objects.filter(mobile_id=mobile_id).exists():
            raise ValidationError('Deck UUID is already in use.')
        deck = Deck(author=user, mobile_id=mobile_id)
    deck.name = name.strip()
    deck.character_id = character_id
    for field, maximum in [('description', 100000), ('keyword', 255), ('tags', 255)]:
        value = data.get(field, '')
        if not isinstance(value, str) or len(value) > maximum:
            raise ValidationError({field: 'Invalid text.'})
        setattr(deck, field, value)
    deck.visibility = visibility
    deck.version = get_deck_version_from_entries(normalized)
    deck.deleted = False
    deck.save()
    replace_deck_cards(deck, normalized)
    return {'uuid': str(deck.mobile_id), 'id': deck.pk}


def apply_sync(user, operations):
    if not isinstance(operations, list) or len(operations) > 100:
        raise ValidationError('At most 100 operations are allowed.')
    results = []
    # Serialize a batch with all web/app writes to this account. No client clock.
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        for operation in operations:
            if not isinstance(operation, dict):
                raise ValidationError('Invalid operation.')
            try:
                operation_id = uuid.UUID(str(operation['operation_id']))
            except (ValueError, KeyError, TypeError, AttributeError):
                raise ValidationError('Invalid operation ID.')
            request_hash = digest(operation)
            existing = SyncReceipt.objects.filter(user=user, operation_id=operation_id).first()
            if existing:
                if existing.request_hash != request_hash:
                    raise ValidationError('An operation ID cannot be reused with different data.')
                results.append({'operation_id': str(operation_id), **existing.result})
                continue
            try:
                with transaction.atomic():
                    if operation.get('entity') == 'deck':
                        result = _deck_operation(user, operation)
                    elif operation.get('entity') == 'collection' and operation.get('action') == 'upsert':
                        card_id = _integer(operation.get('entity_id'), 'entity_id', 1, 2147483647)
                        if not isinstance(operation.get('data'), dict):
                            raise ValidationError('Collection data is required.')
                        amount = _integer(operation['data'].get('amount'), 'amount')
                        if not CollectionCard.objects.filter(pk=card_id).exists():
                            raise ValidationError('Collection item not found.')
                        Collected.objects.update_or_create(user=user, card_id=card_id, defaults={'amount': amount})
                        result = {'card_id': card_id}
                    else:
                        raise ValidationError('Unknown synchronization operation.')
                    result = {'ok': True, **result}
            except ValidationError as exc:
                result = {'ok': False, 'error': exc.detail}
            SyncReceipt.objects.create(user=user, operation_id=operation_id, request_hash=request_hash, result=result)
            results.append({'operation_id': str(operation_id), **result})
        return {'results': results, **account_snapshot(user)}
