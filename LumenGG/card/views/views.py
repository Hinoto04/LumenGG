from django.shortcuts import render
from django.http import HttpResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q

from ..models import Card, Character
from ..forms import CardForm
import re

# Create your views here.
def index(req):
    page = req.GET.get('page', '1')
    
    form = CardForm(req.GET)
    
    if not form.is_valid():
        char = None
        stype = None
        pos = None
        body = None
        specialpos = None
        specialtype = None
        keyword = None
        pack = None
        framenum = None
        frametype = None
        sort = None
    else:
        char = form.cleaned_data['char']
        stype = form.cleaned_data['type']
        pos = form.cleaned_data['pos']
        body = form.cleaned_data['body']
        specialpos = form.cleaned_data['specialpos']
        specialtype = form.cleaned_data['specialtype']
        keyword = form.cleaned_data['keyword']
        pack = form.cleaned_data['pack']
        framenum = form.cleaned_data['framenum']
        frametype = form.cleaned_data['frametype']
        sort = form.cleaned_data['sort']
    
    q = Q()
    
    if char: 
        q.add(Q(character__in=char), q.AND)
    if stype: q.add(Q(type__in=stype), q.AND)
    if pos: q.add(Q(pos__in=pos), q.AND)
    if body: q.add(Q(body__in=body), q.AND)
    if specialtype: 
        qtemp = Q()
        for sp in specialtype:
            qtemp.add(Q(special__contains=sp), q.OR)
        q.add(qtemp, q.AND)
    if specialpos: 
        qtemp = Q()
        for sp in specialpos:
            qtemp.add(Q(special__contains=sp), qtemp.OR)
        q.add(qtemp, q.AND)
    if pack: q.add(Q(code__contains=pack), q.AND)
    if framenum:
        if frametype == '일치': q.add(Q(frame=int(framenum)), q.AND)
        elif frametype == '이상': q.add(Q(frame__gte=int(framenum)), q.AND)
        elif frametype == '이하': q.add(Q(frame__lte=int(framenum)), q.AND)
    if keyword:
        q1 = Q()
        q1.add(Q(name__contains=keyword), q.OR)
        q1.add(Q(keyword__contains=keyword), q.OR)
        q.add(q1, q.AND)
    
    data = Card.objects.filter(q)
    
    if sort:
        if sort == '-속도':
            data = data.order_by('-frame')
        elif sort == '+속도':
            data = data.order_by('frame')
        elif sort == '-데미지':
            data = data.order_by('-damage')
        elif sort == '+데미지':
            data = data.order_by('damage')
    else:
        data = data.order_by('id')
    
    paginator = Paginator(data, 12)
    page_data = paginator.get_page(page)
    
    form = CardForm(req.GET)
    
    context = {
        'form': form,
        'cards': page_data
    }
    return render(req, 'card/list.html', context=context)

def detail(req, id=0):
    try:
        card = Card.objects.get(id = id)
    except Card.DoesNotExist:
        raise Http404("카드가 존재하지 않습니다.")
    
    relation = {}
    
    kws = card.search.split('/')[:-1]
    for kw in kws:
        relation[kw] = Card.objects.filter(keyword__contains=kw)
        relation[kw] = relation[kw].exclude(id = id)
    
    context = {
        'card': card,
        'relation': relation,
    }
    return render(req, 'card/detail.html', context=context)
