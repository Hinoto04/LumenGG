from django.shortcuts import render, redirect
from django.db.models import OuterRef, Subquery, Q, Count, Prefetch
from django.db import models
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
from ..utils import normalize_deck_version
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
    
    q.add(~Q(private=True), q.AND)
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
    }
    return render(req, template_name, context=context)

def detailV2(req, id=0):
    return detail(req, id, 'deck/detail_v2.html')

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

@login_required(login_url='common:login', redirect_field_name='next')
def create(req, template_name='deck/create.html', detail_route='deck:detail'):
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
        
        try:
            version = normalize_deck_version(data.get('version'))
            newDeck = Deck(
                name=data['name'],
                character_id=int(data['char']),
                description=data['description'], 
                keyword=data['keyword'], 
                version=version,
                author=req.user,
                private=('private' in data.keys()),
            )
            newDeck.save()
        except:
            errorContent['msg'] =  '올바르지 않은 데이터가 있습니다.'
            return JsonResponse(errorContent)
        
        for card_id, count, hand, side in normalized_deck:
            cid = CardInDeck(
                card_id = card_id,
                deck = newDeck,
                count = count,
                hand = hand,
                side = side,
            )
            cid.save()
        
        content = {
            'status': 100,
            'url': reverse(detail_route, kwargs={'id': newDeck.id})
        }
        return JsonResponse(content)

def createV2(req):
    return create(req, 'deck/create_v2.html', 'deck:detailV2')

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
    return [
        {
            'pk': cid.card.id,
            'name': cid.card.name,
            'frame': cid.card.frame,
            'img_sm': cid.card.img_sm,
            'character': cid.card.character_id,
            'ultimate': cid.card.ultimate,
            'count': cid.count,
            'hand': cid.hand,
            'side': cid.side,
        }
        for cid in card_in_deck
    ]

@login_required(login_url='common:login', redirect_field_name='next')
def update(req, id=0, template_name='deck/update.html', detail_route='deck:detail'):
    try:
        deck = Deck.objects.get(id=id)
    except Deck.DoesNotExist:
        raise Http404()
    
    if deck.author != req.user:
        raise PermissionDenied()
    
    csd = CSDeck.objects.filter(deck=deck)
    if len(csd) > 0:
        return render(req, 'error.html', context={'error':'대회에 사용된 덱은 수정하실 수 없습니다.'})
    
    if req.method == "GET":
        form = DeckMakeForm(instance=deck)
        form['version'].initial = deck.version
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
        
        deck.name = data['name']
        deck.character_id = int(data['char'])
        deck.version = normalize_deck_version(data.get('version'))
        deck.keyword = data['keyword']
        deck.private = 'private' in data.keys()
        deck.description = data['description']
        deck.save()
        
        CardInDeck.objects.filter(deck=deck).delete()
        for card_id, count, hand, side in normalized_deck:
            cid = CardInDeck(
                card_id = card_id,
                deck = deck,
                count = count,
                hand = hand,
                side = side,
            )
            cid.save()
        
        content = {
            'status': 100,
            'url': reverse(detail_route, kwargs={'id': deck.id})
        }
        return JsonResponse(content)

def updateV2(req, id=0):
    return update(req, id, 'deck/create_v2.html', 'deck:detailV2')

@login_required(login_url='common:login', redirect_field_name='next')
def delete(req, id):
    try:
        deck = Deck.objects.get(id=id)
    except Deck.DoesNotExist:
        raise Http404()
    
    csd = CSDeck.objects.filter(deck=deck)
    if len(csd) > 0:
        return render(req, 'error.html', context={'error':'대회에 사용된 덱은 삭제하실 수 없습니다.'})
    
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
