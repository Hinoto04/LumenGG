from django.shortcuts import render, redirect
from django.urls import reverse
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required

from ..models import Deck, CardInDeck
from card.models import Card
from ..forms import DeckSearchForm, DeckImportForm

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

@login_required(login_url='common:login', redirect_field_name='next')
def deckImport(req):
    if req.method == 'GET':
        form = DeckImportForm()
        return render(req, 'deck/importForm.html', context={'form': form})
    elif req.method == 'POST':
        form = DeckImportForm(req.POST)
        if form.is_valid():
            deckListText = form.cleaned_data['deck'].replace('\r', '').split('\n')
            deckListText = [i.split('.')[-1].strip() for i in deckListText]
            print(deckListText)
            deckList = []
            for card in deckListText:
                if card == '': continue
                try:
                    card_obj = Card.objects.get(name=card)
                except:
                    cards = Card.objects.filter(Q(name__contains=card)|Q(keyword__contains=card)|Q(hiddenKeyword__contains=card))
                    hubos = [i.name for i in cards]
                    form.add_error('deck', f'{card}는 존재하지 않는 카드명입니다.\n검색된 추천 카드명 [{','.join(hubos)}]')
                else:
                    deckList.append(card_obj)
            char = form.cleaned_data['char']
            if (char.name == '키스' and len(deckList) == 23) \
                or (char.name != '키스' and len(deckList) == 20):
                deck = Deck(
                    name = form.cleaned_data['name'],
                    author = req.user,
                    character = char,
                    version = form.cleaned_data['version'],
                    private = form.cleaned_data['private'],
                )
                deck.save()
                for card in deckList:
                    deck.add_card(card)
                
                return redirect(reverse('deck:detail', kwargs={'id': deck.id}))
            else:
                form.add_error('deck', '올바른 카드만을 포함한 덱 매수가 올바르지 않습니다.')
                
            return render(req, 'deck/importForm.html', context={'form': form})
        else:
            return render(req, 'deck/importForm.html', context={'form': form})
    else:
        raise Http404()