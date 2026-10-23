from django.shortcuts import render, redirect
from django.db.models import OuterRef, Subquery, Q, Count, Prefetch
from django.db import models, transaction
from django.urls import reverse
from django.core import serializers
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Case, When

from card.models import Card, Character
from card.search import card_matches_search
from common.language import DEFAULT_LANGUAGE, get_language, translated_card_field
from ..models import Deck, CardInDeck, DeckLike, DeckComment, is_forced_side_card
from ..forms import DeckSearchForm, DeckMakeForm
from ..capture import generate_deck_capture, get_deck_capture_public_url
from ..utils import get_deck_version_from_entries
from collection.models import Pack
from statistic.models import CSDeck
from common.models import SiteSettings

import json
import math

MOBILE_UA_KEYWORDS = (
    'android',
    'iphone',
    'ipod',
    'ipad',
    'mobile',
    'tablet',
    'windows phone',
)

NEUTRAL_CHARACTER_ID = 1
KIMERA_CHARACTER_ID = 15
KIMERA_SHARED_CARD_TYPES = ('공격',)


def is_mobile_deck_builder_request(req):
    if req.GET.get('mobile') in ('1', 'true', 'yes'):
        return True
    if req.GET.get('desktop') in ('1', 'true', 'yes'):
        return False
    if req.META.get('HTTP_SEC_CH_UA_MOBILE') == '?1':
        return True
    platform = req.META.get('HTTP_SEC_CH_UA_PLATFORM', '').strip('"').lower()
    if platform in ('android', 'ios'):
        return True
    user_agent = req.META.get('HTTP_USER_AGENT', '').lower()
    return any(keyword in user_agent for keyword in MOBILE_UA_KEYWORDS)


def should_redirect_to_mobile_builder(req):
    return req.method == 'GET' and is_mobile_deck_builder_request(req)

# Create your views here.
def index(req, template_name='deck/list.html'):
    page = req.GET.get('page', '1')
    form = DeckSearchForm(req.GET, language=get_language(req))
    
    if not form.is_valid():
        char = None
        keyword = None
        sort = None
    else:
        char = form.cleaned_data['char']
        keyword = form.cleaned_data['keyword']
        sort = form.cleaned_data['sort'] or 'recent'
    
    q = Q(deleted=False)
    if char: q.add(Q(character__in=char), q.AND)
    if keyword: 
        qq = Q()
        qq.add(Q(keyword__contains=keyword), qq.OR)
        qq.add(Q(author__username=keyword), qq.OR)
        q.add(qq, q.AND)
    
    visible_q = Q(visibility=Deck.VISIBILITY_PUBLIC)
    if req.user.is_authenticated:
        visible_q.add(
            Q(
                author=req.user,
                visibility__in=[Deck.VISIBILITY_UNLISTED, Deck.VISIBILITY_PRIVATE],
            ),
            Q.OR,
        )
    q.add(visible_q, q.AND)
    like_subquery = DeckLike.objects.filter(
        deck=OuterRef('pk'),
        like=True
    ).values('deck').annotate(
        cnt=Count('id')
    ).values('cnt')
    
    data = Deck.objects.filter(q).select_related('author', 'character', 'trait_card').annotate(
        cardcount=Count('cids', distinct=True),
        likecount=Subquery(like_subquery, output_field=models.IntegerField()),
        )
    
    if template_name == 'deck/list_v2.html':
        ultimate_cards = CardInDeck.objects.select_related('card').filter(
            card__ultimate=True
        ).order_by('card__name')
        data = data.prefetch_related(
            Prefetch('cids', queryset=ultimate_cards, to_attr='ultimate_cards')
        )
        
    trait_filter = req.GET.get('trait_card_id', '')
    selected_character_ids = {character.pk for character in char} if char else set()
    if selected_character_ids and trait_filter.isdigit():
        trait = Card.objects.filter(
            pk=int(trait_filter),
            character_id__in=selected_character_ids,
        ).filter(Q(type='특성') | Q(code__icontains='PS')).first()
        if trait:
            data = data.filter(trait_card_id=trait.pk)
        else:
            trait_filter = ''
    else:
        trait_filter = ''

    regulation_filter = req.GET.get('regulation_version_id', '')
    if regulation_filter == 'unrestricted':
        data = data.filter(regulation_version__isnull=True)
    elif regulation_filter.isdigit():
        data = data.filter(regulation_version_id=int(regulation_filter))
    else:
        regulation_filter = ''
    data = data.filter(Q(cardcount__gte=15) | Q(author=req.user) if req.user.is_authenticated else Q(cardcount__gte=15))
    
    if sort == 'version':
        data = data.order_by('-version', '-created')
    elif sort == 'like':
        data = data.order_by('-likecount', '-created')
    else:
        data = data.order_by('-created')
    
    per_page = 18 if template_name == 'deck/list_v2.html' else 20
    paginator = Paginator(data, per_page)
    page_data = paginator.get_page(page)
    
    search_characters = list(form.fields['char'].queryset.prefetch_related('translations'))

    context = {
        'form': form,
        'decks': page_data,
        'trait_filter': trait_filter,
        'regulation_filter': regulation_filter,
        'search_characters': search_characters,
        'selected_character_ids': selected_character_ids,
        'search_character_picker_columns': len(search_characters) + 1,
        'search_character_picker_stagger': math.ceil(len(search_characters) / 2) + 2,
    }
    return render(req, template_name, context=context)

def indexV2(req):
    return index(req, 'deck/list_v2.html')

def detail(req, id=0, template_name='deck/detail.html'):
    try:
        deck = Deck.objects.select_related(
            'author',
            'character',
            'trait_card',
            'regulation_version__regulation',
        ).get(id=id)
    except Deck.DoesNotExist:
        raise Http404()
    
    if deck.deleted:
        raise Http404()
    if not can_view_deck(req.user, deck):
        raise PermissionDenied()
    
    likecount = DeckLike.objects.filter(deck=deck, like=True).count()
    bookmarkcount = DeckLike.objects.filter(deck=deck, bookmark=True).count()
    cards = CardInDeck.objects.filter(deck=deck).select_related('card', 'card__character').order_by('-card__type', 'card__frame')
    
    codes = Pack.objects.filter(released__gt=timezone.now())
    for code in codes:
        cards = cards.annotate(
            unReleased = Case(When(card__code__contains=code.code, then=True), default=False)
        )
        
    main_cards = cards.filter(card__ultimate=False)
    hands = main_cards.filter(hand__gte=1)
    sides = main_cards.filter(side__gte=1)
    ultimate_cards = cards.filter(card__ultimate=True)
    main_list_count = sum(max(card.count - card.hand - card.side, 0) for card in main_cards)
    hand_count = sum(card.hand for card in hands)
    side_count = sum(card.side for card in sides)
    reserve_cards = deck.reserve_entries.select_related('card').order_by('card__name')
    reserve_count = sum(entry.count for entry in reserve_cards)
    if req.user.is_authenticated:
        liked = DeckLike.objects.filter(deck=deck, author=req.user, like=True).exists()
        bookmarked = DeckLike.objects.filter(deck=deck, author=req.user, bookmark=True).exists()
    else:
        liked = False
        bookmarked = False
    deck_tournament_locked = is_deck_locked_by_tournament(deck)
    
    context = {
        'deck': deck,
        'cards': cards,
        'main_cards': main_cards,
        'hands': hands,
        'sides': sides,
        'ultimate_cards': ultimate_cards,
        'main_list_count': main_list_count,
        'hand_count': hand_count,
        'side_count': side_count,
        'reserve_count': reserve_count,
        'likecount': likecount,
        'bookmarkcount': bookmarkcount,
        'liked': liked,
        'bookmarked': bookmarked,
        'deck_tournament_locked': deck_tournament_locked,
        'reserve_cards': reserve_cards,
    }
    return render(req, template_name, context=context)

def detailV2(req, id=0):
    return detail(req, id, 'deck/detail_v2.html')

def capture(req, id=0):
    try:
        deck = Deck.objects.select_related('author', 'character').get(id=id)
    except Deck.DoesNotExist:
        raise Http404()
    
    if deck.deleted:
        raise Http404()
    if not can_view_deck(req.user, deck):
        raise PermissionDenied()
    
    capture_path = generate_deck_capture(deck)
    return redirect(get_deck_capture_public_url(capture_path))

def captureV2(req, id=0):
    return capture(req, id)

def copy_deck_instance(deck, user):
    with transaction.atomic():
        copied_deck = Deck.objects.create(
            name=f'{deck.name} 복사본'[:255],
            author=user,
            character=deck.character,
            version=deck.version,
            keyword=deck.keyword,
            description=deck.description,
            visibility=Deck.VISIBILITY_PRIVATE,
            private=True,
            tags=deck.tags,
        )
        CardInDeck.objects.bulk_create([
            CardInDeck(
                deck=copied_deck,
                card_id=card_in_deck.card_id,
                count=card_in_deck.count,
                hand=card_in_deck.hand,
                side=card_in_deck.side,
            )
            for card_in_deck in CardInDeck.objects.filter(deck=deck)
        ])
        from deck.extensions import copy_extensions
        copy_extensions(deck, copied_deck)
    return copied_deck

def _copy(req, id=0, update_route='deck:update'):
    if req.method != 'POST':
        raise Http404()
    
    try:
        deck = Deck.objects.select_related('author', 'character').get(id=id)
    except Deck.DoesNotExist:
        raise Http404()
    
    if deck.deleted:
        raise Http404()
    if not can_view_deck(req.user, deck):
        raise PermissionDenied()
    
    copied_deck = copy_deck_instance(deck, req.user)
    return redirect(reverse(update_route, kwargs={'id': copied_deck.id}))

@login_required(login_url='common:login', redirect_field_name='next')
def copy(req, id=0):
    return _copy(req, id)

@login_required(login_url='common:legacyLogin', redirect_field_name='next')
def copyLegacy(req, id=0):
    return _copy(req, id, 'deck:legacyUpdate')

@login_required(login_url='common:login', redirect_field_name='next')
def copyV2(req, id=0):
    return _copy(req, id, 'deck:update')

def can_view_deck(user, deck):
    visibility = Deck.VISIBILITY_PRIVATE if deck.private else deck.visibility
    if visibility in (Deck.VISIBILITY_PUBLIC, Deck.VISIBILITY_UNLISTED):
        return True
    if not user.is_authenticated:
        return False
    if deck.author_id == user.id:
        return True
    if user.is_staff:
        return True
    try:
        from tournament.models import Tournament, TournamentDeckSubmission
    except ImportError:
        return False
    return TournamentDeckSubmission.objects.filter(
        deck=deck,
        participant__tournament__organizer=user,
    ).exists() or Tournament.objects.filter(
        organizer=user,
        participants__deck=deck,
    ).exists()


from deck.services import (
    is_deck_locked_by_tournament, normalize_deck_visibility, get_max_deck_size,
    count_main_deck_cards, validate_submitted_deck_size, normalize_submitted_deck,
    merge_deck_entries, build_card_in_deck, replace_deck_cards,
)


def deck_validation_response(view):
    from functools import wraps
    from django.core.exceptions import ValidationError
    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except ValidationError as exc:
            return JsonResponse({'status': 200, 'msg': '; '.join(exc.messages)}, status=400)
    return wrapped


def _deck_body(request):
    from django.core.exceptions import ValidationError
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeError) as exc:
        raise ValidationError('덱 데이터가 올바르지 않습니다.') from exc
    if not isinstance(data, dict) or not isinstance(data.get('deck'), list):
        raise ValidationError('카드 목록이 올바르지 않습니다.')
    if any(not isinstance(row, list) or len(row) != 2 or not isinstance(row[1], dict) for row in data['deck']):
        raise ValidationError('카드 항목이 올바르지 않습니다.')
    for key, maximum in [('name', 255), ('description', 100000), ('keyword', 255)]:
        value = data.get(key, '')
        if not isinstance(value, str) or len(value) > maximum:
            raise ValidationError('덱 정보가 올바르지 않습니다.')
        data[key] = value
    try:
        character_id = int(data.get('char'))
    except (ValueError, TypeError) as exc:
        raise ValidationError('캐릭터를 선택해주세요.') from exc
    if not Character.objects.filter(pk=character_id).exists():
        raise ValidationError('캐릭터를 찾을 수 없습니다.')
    return data


@deck_validation_response
def _create(req, template_name='deck/create.html', detail_route='deck:detail'):
    if req.method == "GET":
        form = DeckMakeForm(language=get_language(req))
        exceptList = str(SiteSettings.objects.get(name='갯수예외처리카드').setting)
        character_count = form.fields['char'].queryset.count()
        return render(req, template_name, context={
            'form': form,
            'exceptList': exceptList,
            'initial_cards': [],
            'is_update': False,
            'selected_character_id': form.fields['char'].initial,
            'character_picker_columns': character_count + 1,
            'character_picker_stagger': math.ceil(character_count / 2) + 2,
        })
    else:
        data = _deck_body(req)
        errorContent = { 'status': 200 }
        if not ('char' in data.keys()) or not ('name' in data.keys()) or not ('deck' in data.keys()):
            errorContent['msg'] =  '형식이 올바르지 못합니다.'
            return JsonResponse(errorContent)
        if data['char'] == '' or data['name'] == '':
            errorContent['msg'] =  '존재하지 않는 데이터가 있습니다.'
            return JsonResponse(errorContent)
        normalized_deck, error_msg = normalize_submitted_deck(data['deck'])
        if error_msg:
            errorContent['msg'] = error_msg
            return JsonResponse(errorContent)
        normalized_deck, error_msg = merge_deck_entries(normalized_deck)
        if error_msg:
            errorContent['msg'] = error_msg
            return JsonResponse(errorContent)
        error_msg = validate_submitted_deck_size(normalized_deck, data['char']) if data.get('schema_version') != 2 else None
        if error_msg:
            errorContent['msg'] = error_msg
            return JsonResponse(errorContent)
        
        try:
            with transaction.atomic():
                version = get_deck_version_from_entries(normalized_deck)
                visibility = normalize_deck_visibility(data.get('visibility', data.get('private')))
                newDeck = Deck(
                    name=data['name'],
                    character_id=int(data['char']),
                    description=data['description'], 
                    keyword=data['keyword'], 
                    version=version,
                    author=req.user,
                    visibility=visibility,
                    private=(visibility == Deck.VISIBILITY_PRIVATE),
                )
                newDeck.save()
                CardInDeck.objects.bulk_create(build_card_in_deck(newDeck, normalized_deck))
                from deck.extensions import apply_extensions
                apply_extensions(newDeck, data, req.user)
        except:
            errorContent['msg'] =  '올바르지 않은 데이터가 있습니다.'
            return JsonResponse(errorContent)
        
        content = {
            'status': 100,
            'url': reverse(detail_route, kwargs={'id': newDeck.id})
        }
        return JsonResponse(content)

@login_required(login_url='common:login', redirect_field_name='next')
def create(req):
    return _create(req)

@login_required(login_url='common:legacyLogin', redirect_field_name='next')
def createLegacy(req):
    return _create(req, 'deck/create.html', 'deck:legacyDetail')

@login_required(login_url='common:login', redirect_field_name='next')
def createV2(req):
    if should_redirect_to_mobile_builder(req):
        return redirect('deck:createMobileV2')
    return _create(req, 'deck/create_v2.html', 'deck:detail')

@login_required(login_url='common:login', redirect_field_name='next')
def createMobileV2(req):
    return _create(req, 'deck/create_mobile_v2.html', 'deck:detail')

def createSearch(req):
    language = get_language(req)
    neutral = req.GET.get('neutral', '')
    char = req.GET.get('char', '0')
    framenum = req.GET.get('framenum', '')
    frametype = req.GET.get('frametype', '일치')
    keyword = req.GET.get('keyword', '')
    
    q = Q()
    c = Q()
    if neutral != '':
        c.add(Q(character__id=NEUTRAL_CHARACTER_ID), c.OR)
    if char == str(KIMERA_CHARACTER_ID):
        other_character_ids = Character.objects.exclude(
            id__in=[NEUTRAL_CHARACTER_ID, KIMERA_CHARACTER_ID],
        ).values_list('id', flat=True)
        c.add(Q(character__id=KIMERA_CHARACTER_ID), c.OR)
        c.add(
            Q(character__id__in=other_character_ids)
            & Q(ultimate=False)
            & Q(type__in=KIMERA_SHARED_CARD_TYPES),
            c.OR,
        )
    elif char != '':
        c.add(Q(character__id=int(char)), c.OR)
    if req.GET.get('all_cards') != '1':
        q.add(c, q.AND)
    if framenum != '':
        if frametype == '일치': q.add(Q(frame=int(framenum)), q.AND)
        if frametype == '이상': q.add(Q(frame__gte=int(framenum)), q.AND)
        if frametype == '이하': q.add(Q(frame__lte=int(framenum)), q.AND)
    q.add(~Q(type="특성"), q.AND)
    q.add(~Q(type="토큰"), q.AND)

    cards = Card.objects.filter(q).prefetch_related('translations').order_by('id')
    if keyword != '':
        cards = [
            card for card in cards
            if card_matches_search(card, keyword, include_keywords=True) or keyword in (card.pos or '')
        ]

    data = [
        {
            'pk': card.pk,
            'name': translated_card_field(card, language, 'name'),
            'frame': card.frame,
            'img_sm': card.img_sm,
            'character': card.character_id,
            'type': card.type,
            'ultimate': card.ultimate,
        }
        for card in cards
    ]
    #sdata = serializers.serialize('json', data)
    return JsonResponse(data, safe=False)

def get_initial_cards(card_in_deck):
    return get_initial_cards_for_language(card_in_deck, DEFAULT_LANGUAGE)


def get_initial_cards_for_language(card_in_deck, language):
    cards = {}
    for cid in card_in_deck:
        key = cid.card.id
        if key not in cards:
            cards[key] = {
                'pk': cid.card.id,
                'name': translated_card_field(cid.card, language, 'name'),
                'frame': cid.card.frame,
                'img_sm': cid.card.img_sm,
                'character': cid.card.character_id,
                'type': cid.card.type,
                'ultimate': cid.card.ultimate,
                'count': 0,
                'hand': 0,
                'side': 0,
            }
        cards[key]['count'] += cid.count
        cards[key]['hand'] += cid.hand
        cards[key]['side'] += cid.side
    return list(cards.values())

@deck_validation_response
def _update(req, id=0, template_name='deck/update.html', detail_route='deck:detail'):
    try:
        deck = Deck.objects.get(id=id)
    except Deck.DoesNotExist:
        raise Http404()
    
    if deck.author != req.user:
        raise PermissionDenied()
    
    csd = CSDeck.objects.filter(deck=deck)
    if len(csd) > 0:
        return render(req, 'error.html', context={'error':'대회에 사용된 덱은 수정하실 수 없습니다.'})
    if is_deck_locked_by_tournament(deck):
        return render(req, 'error.html', context={'error':'진행 중이거나 종료된 대회에 제출된 덱은 수정하실 수 없습니다.'})
    
    if req.method != 'GET':
        incoming = _deck_body(req)
        if deck.schema_version >= 2 and incoming.get('schema_version') != 2:
            return JsonResponse({'status': 200, 'msg': '최신 덱 작성기를 사용해주세요.'}, status=400)

    if req.method == "GET":
        form = DeckMakeForm(instance=deck, language=get_language(req))
        cid = CardInDeck.objects.filter(deck=deck).select_related('card', 'card__character')
        exceptList = str(SiteSettings.objects.get(name='갯수예외처리카드').setting)
        character_count = form.fields['char'].queryset.count()
        return render(req, template_name, context=
                    {'form': form, 
                     'cid': cid, 
                     'char': deck.character.name, 
                     'deck': deck,
                     'selected_character_id': deck.character_id,
                     'character_picker_columns': character_count + 1,
                     'character_picker_stagger': math.ceil(character_count / 2) + 2,
                     'exceptList': exceptList,
                     'initial_cards': get_initial_cards_for_language(cid, get_language(req)),
                     'is_update': True})
    else:
        data = _deck_body(req)
        errorContent = { 'status': 200 }
        if not ('char' in data.keys()) or not ('name' in data.keys()) or not ('deck' in data.keys()):
            errorContent['msg'] =  '형식이 올바르지 못합니다.'
            return JsonResponse(errorContent)
        if data['char'] == '' or data['name'] == '':
            errorContent['msg'] =  '존재하지 않는 데이터가 있습니다.'
            return JsonResponse(errorContent)
        normalized_deck, error_msg = normalize_submitted_deck(data['deck'])
        if error_msg:
            errorContent['msg'] = error_msg
            return JsonResponse(errorContent)
        normalized_deck, error_msg = merge_deck_entries(normalized_deck)
        if error_msg:
            errorContent['msg'] = error_msg
            return JsonResponse(errorContent)
        error_msg = validate_submitted_deck_size(normalized_deck, data['char']) if data.get('schema_version') != 2 else None
        if error_msg:
            errorContent['msg'] = error_msg
            return JsonResponse(errorContent)
        
        with transaction.atomic():
            deck.name = data['name']
            deck.character_id = int(data['char'])
            deck.version = get_deck_version_from_entries(normalized_deck)
            deck.keyword = data['keyword']
            deck.visibility = normalize_deck_visibility(data.get('visibility', data.get('private')))
            deck.private = deck.visibility == Deck.VISIBILITY_PRIVATE
            deck.description = data['description']
            deck.save()
            replace_deck_cards(deck, normalized_deck)
            from deck.extensions import apply_extensions
            apply_extensions(deck, data, req.user)
        
        content = {
            'status': 100,
            'url': reverse(detail_route, kwargs={'id': deck.id})
        }
        return JsonResponse(content)

@login_required(login_url='common:login', redirect_field_name='next')
def update(req, id=0):
    return _update(req, id)

@login_required(login_url='common:legacyLogin', redirect_field_name='next')
def updateLegacy(req, id=0):
    return _update(req, id, 'deck/update.html', 'deck:legacyDetail')

@login_required(login_url='common:login', redirect_field_name='next')
def updateV2(req, id=0):
    if should_redirect_to_mobile_builder(req):
        return redirect('deck:updateMobileV2', id=id)
    return _update(req, id, 'deck/create_v2.html', 'deck:detail')

@login_required(login_url='common:login', redirect_field_name='next')
def updateMobileV2(req, id=0):
    return _update(req, id, 'deck/create_mobile_v2.html', 'deck:detail')

@login_required(login_url='common:login', redirect_field_name='next')
def delete(req, id):
    try:
        deck = Deck.objects.get(id=id)
    except Deck.DoesNotExist:
        raise Http404()
    
    csd = CSDeck.objects.filter(deck=deck)
    if len(csd) > 0:
        return render(req, 'error.html', context={'error':'대회에 사용된 덱은 삭제하실 수 없습니다.'})
    if is_deck_locked_by_tournament(deck):
        return render(req, 'error.html', context={'error':'진행 중이거나 종료된 대회에 제출된 덱은 삭제하실 수 없습니다.'})
    
    if deck.author == req.user:
        deck.deleted = True
        deck.save()
        return redirect('deck:index')
    else:
        raise PermissionDenied()

@login_required(login_url='common:login', redirect_field_name='next')
def like(req, id):
    try:
        deck = Deck.objects.get(id=id)
    except Deck.DoesNotExist:
        raise Http404()
    if not can_view_deck(req.user, deck):
        raise PermissionDenied()
    
    if req.method == "POST":
        try:
            dl = DeckLike.objects.get(deck=deck, author=req.user)
            dl.like = not dl.like
        except DeckLike.DoesNotExist:
            dl = DeckLike(deck=deck, author=req.user, like=True)
        dl.save()
        return redirect(reverse('deck:detail', kwargs={'id': id}))
    else:
        raise Http404()

@login_required(login_url='common:login', redirect_field_name='next')
def bookmark(req, id):
    try:
        deck = Deck.objects.get(id=id)
    except Deck.DoesNotExist:
        raise Http404()
    if not can_view_deck(req.user, deck):
        raise PermissionDenied()
    
    if req.method == "POST":
        try:
            dl = DeckLike.objects.get(deck=deck, author=req.user)
            dl.bookmark = not dl.bookmark
        except DeckLike.DoesNotExist:
            dl = DeckLike(deck=deck, author=req.user, bookmark=True)
        dl.save()
        return redirect(reverse('deck:detail', kwargs={'id': id}))
    else:
        raise Http404()

def check_cardname(req):
    name = req.GET.get('name', '')
    try:
        Card.objects.get(name=name)
    except Card.DoesNotExist:
        raise Http404()
    else:
        return HttpResponse("존재")

def detail_hoverImg(req):
    name = req.GET.get('name', '')
    try:
        card = Card.objects.get(name=name)
    except:
        try:
            card = Card.objects.get(id=name)
        except:
            raise Http404()
        else:
            return HttpResponse(card.img_mid)
    else:
        return HttpResponse(card.img_mid)
