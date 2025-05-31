from django.shortcuts import render
from card.models import Character, Card
from deck.models import Deck
from .models import Championship, CSDeck
from .forms import CSSearchForm

from django.http import Http404, JsonResponse
from django.db.models import Q, Count, FloatField, IntegerField, F, Func, Value
from django.core import serializers

# Create your views here.
def index(req):
    form = CSSearchForm(req.GET)
    if form.is_valid():
        css = Championship.objects.filter(name__contains=form.cleaned_data['keyword'])
    else:
        css = Championship.objects.all()
    
    context = {
        'css': css,
        'form': form
    }
    return render(req, 'stat/list.html', context=context)

def detail(req, id):
    try:
        cs = Championship.objects.get(id=id)
    except Championship.DoesNotExist:
        raise Http404()
    
    decks = CSDeck.objects.filter(cs=cs).order_by('place_num')
    #print(carddata)

    context = {
        'cs': cs,
        'decks': decks,
        # 'chars': chardata,
        # 'cards': carddata,
    }
    return render(req, 'stat/detail.html', context=context)

def detailData(req, id):
    try:
        cs = Championship.objects.get(id=id)
    except Championship.DoesNotExist:
        raise Http404()

    deckCount = CSDeck.objects.filter(cs = cs).count()
    chardata = Character.objects.annotate(
        used = Count('decks__csdecks', filter=Q(decks__csdecks__cs=cs)),
    )
    chardata = chardata.filter(used__gt='0').order_by('-used')
    s_chardata = list(chardata.values('id', 'name', 'used', 'color'))
    
    carddata = Card.objects.only('name', 'cids').annotate(
        used = Cast(Count('cids', filter=Q(cids__deck__csdecks__cs=cs))/deckCount,
        FloatField())
    )
    carddata = carddata.filter(character_id=1).filter(used__gt=0).order_by('-used')
    s_carddata = list(carddata.values('id', 'name', 'used'))
    
    data = {
        'chardata': s_chardata,
        'carddata': s_carddata,
    }
    
    return JsonResponse(data=data, )