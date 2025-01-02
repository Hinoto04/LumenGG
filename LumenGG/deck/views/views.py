from django.shortcuts import render
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import Http404

from ..models import Deck, CardInDeck
from ..forms import DeckSearchForm

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