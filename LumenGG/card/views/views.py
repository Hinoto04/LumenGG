from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, IntegerField, Avg
from django.conf import settings

from ..models import Card, Character, Tag, CardComment
from collection.models import CollectionCard, Pack
from ..forms import CardForm, TagCreateForm, CardTagEditForm, CardCreateForm, CardCommentForm
from decorators import permission_required
import re, random, os

from PIL import Image

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
        elif sort == "-점수":
            data = data.order_by('-score')
    else:
        data = data.order_by('id')
    
    if req.GET.get('random', None):
        data = random.choices(k=int(req.GET.get('random', 1)), population=data)
    
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
    
    cc = CollectionCard.objects.filter(card = card)
    cc = cc.annotate(
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
    cc = cc.order_by('pack__released', 'code', 'custom_order')
    
    context = {
        'card': card,
        'relation': relation,
        'cc': cc,
    }
    return render(req, 'card/detail.html', context=context)

@permission_required('card.add_card')
def create(req):
    if req.method == 'GET':
        form = CardCreateForm()
        
        return render(req, 'card/create.html', context={'form': form})
    else:
        form = CardCreateForm(req.POST, req.FILES)
        if form.is_valid():
            path = os.path.join(settings.MEDIA_ROOT, 'webp', (form.cleaned_data['code']+'.webp'))
            handle_uploaded_file(req.FILES['imageFile'], 
                path)
            
            compress_image(path, os.path.join(settings.MEDIA_ROOT, 
                                            'webpsm', 
                                            (form.cleaned_data['code']+'.webp')), 319, 100)
            compress_image(path, os.path.join(settings.MEDIA_ROOT, 
                                            'webpmin', 
                                            (form.cleaned_data['code']+'.webp')), 213, 100)
            
            try:
                card = Card.objects.get(name = form.cleaned_data['name'])
                return redirect('card:detail', card.id)
            except:
                card = form.save(commit=False)
                card.img = 'https://images.hinoto.kr/lumendb/webp/' + card.code + '.webp'
                card.img_mid = 'https://images.hinoto.kr/lumendb/webpsm/' + card.code + '.webp'
                card.img_sm = 'https://images.hinoto.kr/lumendb/webpmin/' + card.code + '.webp'
                card.save()
                
            for r in form.data.getlist('rare'):
                newCC = CollectionCard(
                    card = card,
                    pack = Pack.objects.get(id = form.data.get('pack')),
                    code = card.code,
                    image = card.img,
                    img_sm = card.img_mid,
                    name = card.name,
                    rare = r)
                print(newCC.__dict__)
                newCC.save()
            return redirect('card:detail', card.id)
        else:
            return render(req, 'card/create.html', context={'form': form})

def handle_uploaded_file(f, filePath):
    print(filePath)
    with open(filePath, "wb+") as destination:
        for chunk in f.chunks():
            destination.write(chunk)

#mid = 235, #sm = 157
def compress_image(filePath: str, newFilePath: str, max_width: int = 235, quality = 100):
    with Image.open(filePath) as img:
        width, height = img.size
        if width > max_width:
            img.thumbnail((max_width, max_width))
        img.save(newFilePath, quality=quality)
            
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

def comment(req, id=0):
    try:
        card = Card.objects.get(id = id)
    except Card.DoesNotExist:
        raise Http404("카드가 존재하지 않습니다.")
    
    comments = CardComment.objects.filter(card=card).order_by('-created_at')
    
    if req.method == 'POST':
        if not req.user.is_authenticated:
            return redirect('card:comment', card.id)
        form = CardCommentForm(req.POST)
        if form.is_valid():
            try:
                comment = comments.get(author=req.user)
                comment.score = form.cleaned_data['score']
                comment.comment = form.cleaned_data['comment']
            except CardComment.DoesNotExist:
                comment = CardComment(
                    author = req.user,
                    score = form.cleaned_data['score'],
                    comment = form.cleaned_data['comment'],
                    card = card
                )
            comment.save()
            return redirect('card:comment', card.id)
    else:
        form = CardCommentForm()
        
    page = req.GET.get('page', '1')
    
    context = {
        'card': card,
        'comments': comments,
        'form': form,
    }
    return render(req, 'card/comment.html', context = context)