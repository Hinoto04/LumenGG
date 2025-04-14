from django.shortcuts import render
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse

from ..models import Deck, CardInDeck
from card.models import Card
from ..forms import DeckSearchForm, StatForm

def deckMake(req):
    deckList = ['스탠딩 가드', '다운 가드', '구르기', '세츠메이 킥',
                '스플릿 커터', '씬 녹턴', '퀵 악센트', '스피어 주테', '쉐도우 컷',
                '니들 스파이크', '플리에 셰이드', '블랙 다트', '배드 캐쳐', '아리나 바트망',
                '캐치 드롭', '레그 돌', '나이트메어 주테', '페인 프리즌', '포르티시모', '그랑 크레센도']
    
    deck = Deck.objects.get(id=3)
    for cardName in deckList:
        try:
            card = Card.objects.get(name=cardName)
        except Card.DoesNotExist:
            print(cardName, "Not Found")
        deck.card.add(card)
    
    print(deck.card.all())
    return render(req, 'deck/import.html', context={'deck': deck})
