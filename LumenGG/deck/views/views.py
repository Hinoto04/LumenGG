from django.shortcuts import render, redirect
from django.db.models import Q
from django.urls import reverse
from django.core import serializers
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required

from card.models import Card, Character
from ..models import Deck, CardInDeck
from ..forms import DeckSearchForm, DeckMakeForm

import json

# Create your views here.
def index(req):
    page = req.GET.get('page', '1')
    form = DeckSearchForm(req.GET)
    
    if not form.is_valid():
        char = None
        keyword = None
    else:
        char = form.cleaned_data['char']
        keyword = form.cleaned_data['keyword']
    
    q = Q() 
    if char: q.add(Q(character__in=char), q.AND)
    if keyword: q.add(Q(keyword__in=keyword), q.AND)
    
    data = Deck.objects.filter(q).order_by('-created')
    
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
    
    cards = CardInDeck.objects.filter(deck=deck).order_by('-card__type', 'card__frame')
    hands = cards.filter(hand__gte=1)
    sides = cards.filter(side__gte=1)
    
    context = {
        'deck': deck,
        'cards': cards,
        'hands': hands,
        'sides': sides,
    }
    return render(req, 'deck/detail.html', context=context)

@login_required(login_url='common:login')
def create(req):
    if req.method == "GET":
        form = DeckMakeForm()
        return render(req, 'deck/create.html', context={'form': form})
    else:
        data = json.loads(req.body)
        errorContent = { 'status': 200 }
        if not ('char' in data.keys()) or not ('name' in data.keys()):
            errorContent['msg'] =  '형식이 올바르지 못합니다.'
            return JsonResponse(errorContent)
        if data['char'] == '' or data['name'] == '':
            errorContent['msg'] =  '존재하지 않는 데이터가 있습니다.'
            return JsonResponse(errorContent)
        if len(data['deck']) < 14 or len(data['deck']) > 23:
            errorContent['msg'] =  '덱 매수가 너무 적거나 너무 많습니다.'
            return JsonResponse(errorContent)
        
        try:
            newDeck = Deck(
                name=data['name'],
                character_id=int(data['char']),
                description=data['description'], 
                keyword=data['keyword'], 
                version=data['version'],
                author=req.user
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
        c.add(Q(name__contains=keyword), c.OR)
        c.add(Q(pos__contains=keyword), c.OR)
        q.add(c, q.AND)
    q.add(~Q(type="특성"), q.AND)
    q.add(~Q(type="토큰"), q.AND)
    
    data = Card.objects.filter(q)
    sdata = serializers.serialize('json', data)
    return JsonResponse(sdata, safe=False)

@login_required(login_url='common:login')
def update(req, id=0):
    try:
        deck = Deck.objects.get(id=id)
    except Deck.DoesNotExist:
        raise Http404()
    
    if deck.author != req.user:
        raise PermissionDenied()
    
    if req.method == "GET":
        form = DeckMakeForm(instance=deck)
        form['version'].initial = deck.version
        cid = CardInDeck.objects.filter(deck=deck)
        return render(req, 'deck/update.html', context={'form': form, 'cid': cid, 'char': deck.character.name})
    else:
        data = json.loads(req.body)
        print(data)
        errorContent = { 'status': 200 }
        if not ('char' in data.keys()) or not ('name' in data.keys()):
            errorContent['msg'] =  '형식이 올바르지 못합니다.'
            return JsonResponse(errorContent)
        if data['char'] == '' or data['name'] == '':
            errorContent['msg'] =  '존재하지 않는 데이터가 있습니다.'
            return JsonResponse(errorContent)
        if len(data['deck']) < 14 or len(data['deck']) > 23:
            errorContent['msg'] =  '덱 매수가 너무 적거나 너무 많습니다.'
            return JsonResponse(errorContent)
        
        deck.name = data['name']
        deck.character_id = int(data['char'])
        deck.version = data['version']
        deck.keyword = data['keyword']
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

@login_required(login_url='common:login')
def delete(req, id):
    try:
        deck = Deck.objects.get(id=id)
    except Deck.DoesNotExist:
        raise Http404()

    if deck.author == req.user:
        deck.delete()
        return redirect('deck:index')
    else:
        return HttpResponse("권한이 없습니다.")