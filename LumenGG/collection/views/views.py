from django.shortcuts import render

from ..models import CollectionCard, Collected
from django.db.models import OuterRef, Subquery, IntegerField, Q
from card.models import Card
from django.core.paginator import Paginator
from ..forms import CollectionForm

# Create your views here.
def index(req):
    page_number = req.GET.get('page', 1)
    
    form = CollectionForm(req.GET)
    q = Q()
    
    if form.data.get('char'):
        q.add(Q(card__character=form.data.get('char')), q.AND)
    if form.data.get('rare'):
        q.add(Q(rare=form.data.get('rare')), q.AND)
    if form.data.get('code'):
        q.add(Q(pack=form.data.get('code')), q.AND)
    
    if req.user.is_authenticated:
        collected = Collected.objects.filter(user=req.user, card=OuterRef('pk')).values('amount')
        collection = CollectionCard.objects.filter(q).annotate(
            amount=Subquery(collected, output_field=IntegerField())
        )
        
        #print(collection.values())
    else:
        collection = CollectionCard.objects.filter(q)
    #filter(code__contains='CRS').order_by('code')
    
    if form.data.get('char'):
        collection = collection.order_by('card__frame', 'card__name')
    
    paginator = Paginator(collection, 40)  # Show 20 collection cards per page.
    page_data = paginator.get_page(page_number)
    
    context = {
        'data': page_data,
        'form': form,
    }
    
    return render(req, 'collection/index.html', context=context)