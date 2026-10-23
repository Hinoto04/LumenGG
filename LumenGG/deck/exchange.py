"""Portable v2 deck files. Imported data never supplies executable effects."""
import json
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from card.models import Character
from .models import Deck
from .extensions import apply_extensions
from .services import normalize_submitted_deck, replace_deck_cards, merge_deck_entries


def export(request, id):
    from .views.views import can_view_deck
    from mobile_api.sync import deck_payload
    deck = get_object_or_404(Deck, pk=id, deleted=False)
    if not can_view_deck(request.user, deck):
        raise PermissionDenied()
    payload = deck_payload(deck)
    payload['schema_version'] = 2
    for key in ('id', 'uuid', 'author', 'locked', 'deleted'):
        payload.pop(key, None)
    response = JsonResponse(payload, json_dumps_params={'ensure_ascii': False})
    response['Content-Disposition'] = f'attachment; filename="lumen-deck-{deck.pk}.json"'
    return response


@login_required
def import_deck(request):
    error = ''
    if request.method == 'POST':
        try:
            if request.FILES.get('file'):
                if request.FILES['file'].size > 1024 * 1024:
                    raise ValueError('덱 파일이 너무 큽니다.')
                raw = request.FILES['file'].read().decode('utf-8-sig')
            else:
                raw = request.POST.get('payload', '')
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get('schema_version') != 2:
                raise ValueError('지원하는 덱 파일을 선택해주세요.')
            if data.get('regulation'):
                data['imported_regulation'] = data['regulation']
            character = Character.objects.get(pk=data.get('character_id'))
            rows, message = normalize_submitted_deck([[r['card_id'], r] for r in data.get('cards', [])])
            if message:
                raise ValueError(message)
            rows, message = merge_deck_entries(rows)
            if message:
                raise ValueError(message)
            with transaction.atomic():
                deck = Deck.objects.create(name=str(data.get('name') or '가져온 덱')[:255], author=request.user, character=character, visibility='private', description=str(data.get('description') or ''), keyword=str(data.get('keyword') or '')[:255])
                replace_deck_cards(deck, rows)
                apply_extensions(deck, data, request.user)
            return redirect('deck:update', id=deck.pk)
        except (ValueError, TypeError, KeyError, Character.DoesNotExist, ValidationError) as exc:
            error = str(exc)
    return render(request, 'deck/import_v2.html', {'error': error})
