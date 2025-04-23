from django.shortcuts import render

from ..models import CollectionCard, Collected
from django.db.models import OuterRef, Subquery, IntegerField, Q, Case, When
from django.http import Http404, JsonResponse
from card.models import Card
from django.core.paginator import Paginator
from ..forms import CollectionForm
import json

charname = [
    '', '세츠메이', '니아', '루트', '델피', '키스', '울프', '비올라', '타오', '리타', '레브', '린', '요한', '이제벨',
]

# Create your views here.
def index(req):
    page_number = req.GET.get('page', 1)
    
    form = CollectionForm(req.GET)
    q = Q()
    
    if form.data.get('char'):
        q1 = Q()
        q1.add(Q(card__character=form.data.get('char')), q.OR)
        q1.add(Q(name__contains=charname[int(form.data.get('char'))]), q.OR)
        q.add(q1, q.AND)
    if form.data.get('rare'):
        q.add(Q(rare=form.data.get('rare')), q.AND)
    if form.data.get('code'):
        q.add(Q(pack=form.data.get('code')), q.AND)
    
    if req.user.is_authenticated:
        collected = Collected.objects.filter(user=req.user, card=OuterRef('pk')).values('amount')
        collection = CollectionCard.objects.filter(q).annotate(
            amount=Subquery(collected, output_field=IntegerField())
        )
        if 'onlyZero' in form.data.keys():
            q = Q(amount=None) | Q(amount=0)
            collection = collection.filter(q)
        #print(collection.values())
    else:
        collection = CollectionCard.objects.filter(q)
    #filter(code__contains='CRS').order_by('code')
    
    collection = collection.annotate(
        custom_order=Case(
        When(rare='N', then=0),
        When(rare='SR', then=1),
        When(rare='EXR', then=2),
        When(rare='AN', then=3),
        When(rare='AEX', then=4),
        When(rare='SAEX', then=5),
        When(rare='SKR', then=6),
        default=7,
        output_field=IntegerField(),
        )
    )
    
    if form.data.get('sortValue'):
        if form.data.get('sortValue') == 'name':
            collection = collection.order_by('name', 'pack__released', 'code', 'custom_order')
        elif form.data.get('sortValue') == 'code':
            collection = collection.order_by('code', 'pack__released', 'custom_order')
        else:
            collection = collection.order_by('card__frame', 'name', 'pack__released', 'custom_order')
    else:
        collection = collection.order_by('card__frame', 'name', 'pack__released', 'custom_order')
    
    
    paginator = Paginator(collection, 40)  # Show 20 collection cards per page.
    page_data = paginator.get_page(page_number)
    
    context = {
        'data': page_data,
        'form': form,
    }
    
    return render(req, 'collection/index.html', context=context)

def updateCollected(req):
    if req.user.is_anonymous:
        return JsonResponse({'result': 'fail', 'message': '로그인 후 이용해주세요.'})
        
    if req.method == 'GET':
        raise Http404()
    if req.method == 'POST':
        data = json.loads(req.body)
        failed = []
        for key, value in data['collected'].items():
            try:
                c = Collected.objects.get(user=req.user, card=key)
            except:
                try:
                    c = Collected(
                        user=req.user,
                        card_id=key,
                        amount=value
                    )
                    c.save()
                except:
                    failed.append(key)
            else:
                c.amount = value
                c.save()
        return JsonResponse({'result': 'ok', 'failed': failed})