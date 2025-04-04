from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q

from ..models import Card, Character, Tag
from collection.models import CollectionCard
from ..forms import CardForm, TagCreateForm, CardTagEditForm
from decorators import permission_required
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
        q1.add(Q(hiddenKeyword__contains=keyword), q.OR)
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
    
    cc = CollectionCard.objects.filter(card = card).order_by('pack__released', 'code')
    
    context = {
        'card': card,
        'relation': relation,
        'cc': cc,
    }
    return render(req, 'card/detail.html', context=context)

def tagList(req):
    page = req.GET.get('page', '1')
    keyword = req.GET.get('keyword', '')
    
    q = Q()
    q.add(Q(name__contains=keyword), q.OR)
    q.add(Q(description__contains=keyword), q.OR)
    tags = Tag.objects.filter(q)
    
    paginator = Paginator(tags, 30)
    page_data = paginator.get_page(page)
    
    if req.method == 'GET':
        return render(req, 'card/tagList.html', context={'tags': page_data})

def tagDetail(req, id=0):
    try:
        tag = Tag.objects.get(id = id)
    except Tag.DoesNotExist:
        raise Http404("태그가 존재하지 않습니다.")
    
    keyword = Card.objects.filter(keyword__contains=tag.name)
    search = Card.objects.filter(search__contains=tag.name)
    
    context = {
        'tag': tag,
        'keyword': keyword,
        'search': search,
    }
    return render(req, 'card/tagDetail.html', context=context)

@permission_required('card.tag_update')
def tagCreate(req):
    if req.method == 'POST':
        form = TagCreateForm(req.POST)
        if form.is_valid():
            tag = form.save()
            return redirect('card:tagDetail', tag.id)
    else:
        form = TagCreateForm()
    
    return render(req, 'card/tagCreate.html', context={'form': form})

@permission_required('card.tag_update')
def tagUpdate(req, id=0):
    try:
        tag = Tag.objects.get(id = id)
    except Tag.DoesNotExist:
        raise Http404("태그가 존재하지 않습니다.")
    
    if req.method == 'POST':
        form = TagCreateForm(req.POST, instance=tag)
        if form.is_valid():
            tag = form.save()
            return render(req, 'card/tagDetail.html', context={'tag': tag})
    else:
        form = TagCreateForm(instance=tag)
    
    return render(req, 'card/tagUpdate.html', context={'form': form})


@permission_required('card.tag_update')
def editCardTag(req, id=0):
    try:
        card = Card.objects.get(id = id)
    except Card.DoesNotExist:
        raise Http404("카드가 존재하지 않습니다.")
    
    card.hiddenKeyword = req.POST['hidden']
    card.keyword = req.POST['keyword']
    card.search = req.POST['search']
    card.save()
    
    return redirect('card:detail', id)
