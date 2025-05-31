from django.shortcuts import render
from card.models import Character, Card
from deck.models import Deck
from .models import Championship, CSDeck
from .forms import CSSearchForm

from django.http import Http404, JsonResponse
from django.db.models import Q, Count, FloatField, IntegerField, F, Func, Value
from django.db.models.functions import Cast
from django.core import serializers
from django.utils import timezone

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

def lcdcs(req):
    css = Championship.objects.filter(name__contains='LCDCS')
    decks = None
    for cs in css:
        temp_decks = CSDeck.objects.filter(cs=cs)
        decks = decks | temp_decks if not (decks is None) else temp_decks
    
    decks = decks.order_by('place_num')
    context = {
        'cs': Championship(
            name = 'LCDCS 종합',
            description = 'LCDCS 종합 데이터 모으기',
            datetime = timezone.now(),
        ),
        'decks': decks,
    }
    return render(req, 'stat/lcdcs.html', context=context)

def lcdcsdata(req):
    css = Championship.objects.filter(name__contains='LCDCS')
    decks = None
    chardata = None
    carddata = None
    for cs in css:
        temp_decks = CSDeck.objects.filter(cs=cs)
        decks = decks | temp_decks if not (decks is None) else temp_decks
    
    decks = decks.order_by('place_num')
    
    deckCount = decks.count()
    chardata = Character.objects.annotate(
        used = Count('decks__csdecks', filter=Q(decks__csdecks__cs__in=css)),
    )
    chardata = chardata.filter(used__gt='0').order_by('-used')
    s_chardata = list(chardata.values('id', 'name', 'used', 'color'))
    
    carddata = Card.objects.only('name', 'cids').annotate(
        used = Cast(Count('cids', filter=Q(cids__deck__csdecks__cs__in=css))/deckCount,
        FloatField())
    )
    carddata = carddata.filter(character_id=1).filter(used__gt=0).order_by('-used')
    s_carddata = list(carddata.values('id', 'name', 'used'))
    
    data = {
        'chardata': s_chardata,
        'carddata': s_carddata,
    }
    
    return JsonResponse(data=data, )

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