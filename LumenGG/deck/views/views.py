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
from ..models import Deck, CardInDeck, DeckLike, DeckComment
from ..forms import DeckSearchForm, DeckMakeForm
from ..capture import generate_deck_capture, get_deck_capture_public_url
from ..utils import get_deck_version_from_entries
from collection.models import Pack
from statistic.models import CSDeck
from common.models import SiteSettings

import json

# Create your views here.
def index(req, template_name='deck/list.html'):
    page = req.GET.get('page', '1')
    form = DeckSearchForm(req.GET)
    
    if not form.is_valid():
        char = None
        keyword = None
        sort = None
    else:
        char = form.cleaned_data['char']
        keyword = form.cleaned_data['keyword']
        sort = form.cleaned_data['sort']
    
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
    
    data = Deck.objects.filter(q).select_related('author', 'character').annotate(
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
        
    data = data.filter(cardcount__gte=15)
    
    if sort == 'version':
        data = data.order_by('-version', '-created')
    elif sort == 'like':
        data = data.order_by('-likecount', '-created')
    else:
        data = data.order_by('-created')
    
    per_page = 18 if template_name == 'deck/list_v2.html' else 20
    paginator = Paginator(data, per_page)
    page_data = paginator.get_page(page)
    
    context = {
        'form': form,
        'decks': page_data,
    }
    return render(req, template_name, context=context)

def indexV2(req):
    return index(req, 'deck/list_v2.html')

def detail(req, id=0, template_name='deck/detail.html'):
    try:
        deck = Deck.objects.get(id=id)
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
        'likecount': likecount,
        'bookmarkcount': bookmarkcount,
        'liked': liked,
        'bookmarked': bookmarked,
        'deck_tournament_locked': deck_tournament_locked,
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


def is_deck_locked_by_tournament(deck):
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

def _create(req, template_name='deck/create.html', detail_route='deck:detail'):
    if req.method == "GET":
        form = DeckMakeForm()
        exceptList = str(SiteSettings.objects.get(name='갯수예외처리카드').setting)
        return render(req, template_name, context={
            'form': form,
            'exceptList': exceptList,
            'initial_cards': [],
            'is_update': False,
        })
    else:
        data = json.loads(req.body)
        errorContent = { 'status': 200 }
        if not ('char' in data.keys()) or not ('name' in data.keys()):
            errorContent['msg'] =  '형식이 올바르지 못합니다.'
            return JsonResponse(errorContent)
        if data['char'] == '' or data['name'] == '':
            errorContent['msg'] =  '존재하지 않는 데이터가 있습니다.'
            return JsonResponse(errorContent)
        if len(data['deck']) < 5 or len(data['deck']) > 40:
            errorContent['msg'] =  '덱 매수가 너무 적거나 너무 많습니다.'
            return JsonResponse(errorContent)
        normalized_deck, error_msg = normalize_submitted_deck(data['deck'])
        if error_msg:
            errorContent['msg'] = error_msg
            return JsonResponse(errorContent)
        normalized_deck, error_msg = merge_deck_entries(normalized_deck)
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
    return _create(req, 'deck/create_v2.html', 'deck:detail')

def createSearch(req):
    neutral = req.GET.get('neutral', '')
    char = req.GET.get('char', '0')
    framenum = req.GET.get('framenum', '')
    frametype = req.GET.get('frametype', '일치')
    keyword = req.GET.get('keyword', '')
    
    q = Q()
    c = Q()
    if neutral != '':
        c.add(Q(character__id=1), c.OR)
    if char == '15':
        for i in range(2, Character.objects.count()+1):
            if i != 15:
                c.add(Q(character__id=i)&Q(ultimate=False)&Q(type='공격'), c.OR)
            else:
                c.add(Q(character__id=i), c.OR)
    elif char != '':
        c.add(Q(character__id=int(char)), c.OR)
    q.add(c, q.AND)
    if framenum != '':
        if frametype == '일치': q.add(Q(frame=int(framenum)), q.AND)
        if frametype == '이상': q.add(Q(frame__gte=int(framenum)), q.AND)
        if frametype == '이하': q.add(Q(frame__lte=int(framenum)), q.AND)
    c = Q()
    if keyword != '':
        c.add(Q(keyword__contains=keyword), c.OR)
        c.add(Q(hiddenKeyword__contains=keyword), c.OR)
        c.add(Q(name__contains=keyword), c.OR)
        c.add(Q(pos__contains=keyword), c.OR)
        q.add(c, q.AND)
    q.add(~Q(type="특성"), q.AND)
    q.add(~Q(type="토큰"), q.AND)
    
    data = list(Card.objects.filter(q).values('pk', 'name', 'frame', 'img_sm', 'character', 'ultimate'))
    #sdata = serializers.serialize('json', data)
    return JsonResponse(data, safe=False)

def get_initial_cards(card_in_deck):
    cards = {}
    for cid in card_in_deck:
        key = cid.card.id
        if key not in cards:
            cards[key] = {
                'pk': cid.card.id,
                'name': cid.card.name,
                'frame': cid.card.frame,
                'img_sm': cid.card.img_sm,
                'character': cid.card.character_id,
                'ultimate': cid.card.ultimate,
                'count': 0,
                'hand': 0,
                'side': 0,
            }
        cards[key]['count'] += cid.count
        cards[key]['hand'] += cid.hand
        cards[key]['side'] += cid.side
    return list(cards.values())

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
    
    if req.method == "GET":
        form = DeckMakeForm(instance=deck)
        cid = CardInDeck.objects.filter(deck=deck).select_related('card', 'card__character')
        exceptList = str(SiteSettings.objects.get(name='갯수예외처리카드').setting)
        return render(req, template_name, context=
                    {'form': form, 
                     'cid': cid, 
                     'char': deck.character.name, 
                     'deck': deck,
                     'selected_character_id': deck.character_id,
                     'exceptList': exceptList,
                     'initial_cards': get_initial_cards(cid),
                     'is_update': True})
    else:
        data = json.loads(req.body)
        errorContent = { 'status': 200 }
        if not ('char' in data.keys()) or not ('name' in data.keys()):
            errorContent['msg'] =  '형식이 올바르지 못합니다.'
            return JsonResponse(errorContent)
        if data['char'] == '' or data['name'] == '':
            errorContent['msg'] =  '존재하지 않는 데이터가 있습니다.'
            return JsonResponse(errorContent)
        if len(data['deck']) < 5 or len(data['deck']) > 40:
            errorContent['msg'] =  '덱 매수가 너무 적거나 너무 많습니다.'
            return JsonResponse(errorContent)
        normalized_deck, error_msg = normalize_submitted_deck(data['deck'])
        if error_msg:
            errorContent['msg'] = error_msg
            return JsonResponse(errorContent)
        normalized_deck, error_msg = merge_deck_entries(normalized_deck)
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
    return _update(req, id, 'deck/create_v2.html', 'deck:detail')

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
