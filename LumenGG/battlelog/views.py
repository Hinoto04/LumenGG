from django.shortcuts import render
from django.http import JsonResponse
from django.core import serializers
from django.db.models import Q, When, Value, CharField, Case

from card.models import Card
from deck.models import Deck, CardInDeck

# Create your views here.
def sim(req):
    return render(req, 'battlelog/sim.html', {})

def cardLoad(req):
    keyword = req.GET.get('keyword', '')
    if keyword:
        q = Q(name__contains=keyword)
        data = list(Card.objects.filter(q).values('name', 'img'))
    else:
        data = []
    return JsonResponse(data, safe=False)

def deckLoad(req):
    id = req.GET.get('id', '')
    try:
        deck = Deck.objects.get(id=id)
    except Deck.DoesNotExist:
        data = {'status': '404'}
    else:
        data = {'status': '200'}
        cards = CardInDeck.objects.filter(deck=deck)
        data['deck'] = list(cards.values('hand','side','count','card__name', 'card__img'))
    return JsonResponse(data)

def stream(req):
    return render(req, 'battlelog/stream.html', {})