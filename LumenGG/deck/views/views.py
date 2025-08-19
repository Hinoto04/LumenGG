from django.shortcuts import render, redirect
from django.db.models import OuterRef, Subquery, Q, Count
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
from collection.models import Pack
from statistic.models import CSDeck
from common.models import SiteSettings

import json

# Create your views here.
def index(req):
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
    
    data = Deck.objects.filter(q).annotate(
        cardcount=Count('cids', distinct=True),
        likecount=Subquery(like_subquery, output_field=models.IntegerField())
        )
        
    data = data.filter(cardcount__gte=15)
    
    if sort == 'version':
        data = data.order_by('-version', '-created')
    elif sort == 'like':
        data = data.order_by('-likecount', '-created')
    else:
        data = data.order_by('-created')
    
    paginator = Paginator(data, 20)
    page_data = paginator.get_page(page)
    
    context = {
        'form': form,
        'decks': page_data,
    }
    return render(req, 'deck/list.html', context=context)

def detail(req, id=0):
    try:
        deck = Deck.objects.get(id=id)
    except Deck.DoesNotExist:
        raise Http404()
    
    if deck.deleted:
        raise Http404()
    
    likecount = DeckLike.objects.filter(deck=deck, like=True).count()
    bookmarkcount = DeckLike.objects.filter(deck=deck, bookmark=True).count()
    cards = CardInDeck.objects.filter(deck=deck).order_by('-card__type', 'card__frame')
    
    codes = Pack.objects.filter(released__gt=timezone.now())
    for code in codes:
        cards = cards.annotate(
            unReleased = Case(When(card__code__contains=code.code, then=True), default=False)
        )
        
    hands = cards.filter(hand__gte=1)
    sides = cards.filter(side__gte=1)
    if req.user.is_authenticated:
        liked = DeckLike.objects.filter(deck=deck, author=req.user, like=True).exists()
        bookmarked = DeckLike.objects.filter(deck=deck, author=req.user, bookmark=True).exists()
    else:
        liked = False
        bookmarked = False
    
    context = {
        'deck': deck,
        'cards': cards,
        'hands': hands,
        'sides': sides,
        'likecount': likecount,
        'bookmarkcount': bookmarkcount,
        'liked': liked,
        'bookmarked': bookmarked,
    }
    return render(req, 'deck/detail.html', context=context)

@login_required(login_url='common:login', redirect_field_name='next')
def create(req):
    if req.method == "GET":
        form = DeckMakeForm()
        exceptList = str(SiteSettings.objects.get(name='갯수예외처리카드').setting)
        return render(req, 'deck/create.html', context={
            'form': form,
            'exceptList': exceptList})
    else:
        data = json.loads(req.body)
        errorContent = { 'status': 200 }
        if not ('char' in data.keys()) or not ('name' in data.keys()):
            errorContent['msg'] =  '형식이 올바르지 못합니다.'
            return JsonResponse(errorContent)
        if data['char'] == '' or data['name'] == '':
            errorContent['msg'] =  '존재하지 않는 데이터가 있습니다.'
            return JsonResponse(errorContent)
        if len(data['deck']) < 5 or len(data['deck']) > 24:
            errorContent['msg'] =  '덱 매수가 너무 적거나 너무 많습니다.'
            return JsonResponse(errorContent)
        
        try:
            newDeck = Deck(
                name=data['name'],
                character_id=int(data['char']),
                description=data['description'], 
                keyword=data['keyword'], 
                version=data['version'],
                author=req.user,
                private=('private' in data.keys()),
            )
            newDeck.save()
        except:
            errorContent['msg'] =  '올바르지 않은 데이터가 있습니다.'
            return JsonResponse(errorContent)
        
        for cards in data['deck']:
            cid = CardInDeck(
                card_id = cards[0],
                deck = newDeck,
                count = cards[1]['count'],
                hand = cards[1]['hand'],
                side = cards[1]['side'],
            )
            cid.save()
        
        content = {
            'status': 100,
            'url': reverse('deck:detail', kwargs={'id': newDeck.id})
        }
        return JsonResponse(content)

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
    if char != '':
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
    
    data = list(Card.objects.filter(q).values('pk', 'name', 'frame', 'img_sm', 'character'))
    #sdata = serializers.serialize('json', data)
    return JsonResponse(data, safe=False)

@login_required(login_url='common:login', redirect_field_name='next')
def update(req, id=0):
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
        cid = CardInDeck.objects.filter(deck=deck)
        exceptList = str(SiteSettings.objects.get(name='갯수예외처리카드').setting)
        return render(req, 'deck/update.html', context=
                    {'form': form, 
                     'cid': cid, 
                     'char': deck.character.name, 
                     'exceptList': exceptList})
    else:
        data = json.loads(req.body)
        errorContent = { 'status': 200 }
        if not ('char' in data.keys()) or not ('name' in data.keys()):
            errorContent['msg'] =  '형식이 올바르지 못합니다.'
            return JsonResponse(errorContent)
        if data['char'] == '' or data['name'] == '':
            errorContent['msg'] =  '존재하지 않는 데이터가 있습니다.'
            return JsonResponse(errorContent)
        if len(data['deck']) < 5 or len(data['deck']) > 24:
            errorContent['msg'] =  '덱 매수가 너무 적거나 너무 많습니다.'
            return JsonResponse(errorContent)
        
        deck.name = data['name']
        deck.character_id = int(data['char'])
        deck.version = data['version']
        deck.keyword = data['keyword']
        deck.private = 'private' in data.keys()
        deck.description = data['description']
        deck.save()
        
        CardInDeck.objects.filter(deck=deck).delete()
        for cards in data['deck']:
            cid = CardInDeck(
                card_id = cards[0],
                deck = deck,
                count = cards[1]['count'],
                hand = cards[1]['hand'],
                side = cards[1]['side'],
            )
            cid.save()
        
        content = {
            'status': 100,
            'url': reverse('deck:detail', kwargs={'id': deck.id})
        }
        return JsonResponse(content)

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