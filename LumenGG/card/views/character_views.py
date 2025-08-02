from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404, JsonResponse
from django.db.models import Q, F
from ..models import Card, Character, CharacterComment
from collection.models import CollectionCard
from django.forms.models import model_to_dict
from django.utils import timezone
from django.core import serializers
from ..forms import CharacterCommentForm

import json, math

def index(req):
    id = req.GET.get('id', '2')
    chars = Character.objects.filter(Q(pack__released__lte=timezone.now())).order_by('pack__released')
    charnum = len(chars)+1
    charnum2 = math.ceil(len(chars)/2)+2
    form = CharacterCommentForm()
    
    context = {
        'chars': chars,
        'charnum': charnum,
        'charnum2': charnum2,
        'id': id,
        'form': form,
    }
    return render(req, 'character/index.html', context=context)

def character(req):
    
    characters = Character.objects.filter(Q(id__gt=1)).order_by('pack__released')
    
    context = {
        'chars': characters,
    }
    return render(req, 'character/list.html', context=context)

def detail(req, id):
    try:
        char = Character.objects.get(id=id)
    except Character.DoesNotExist:
        raise Http404()
    
    data = char.datas.copy()
    for i in data['identity']:
        i['card'] = list(Card.objects.only('img_mid').filter(id=i['card']).values('id', 'name', 'img_mid'))
    
    skinImgs = CollectionCard.objects.filter(Q(name__contains=char.name)&Q(card_id=None)&(~Q(rare="N"))).order_by('pack__released')
    passive = list(Card.objects.filter(type="특성", character=char).values('id', 'name', 'img'))
    selfComment = None
    if req.user.is_authenticated:
        try:
            selfComment = model_to_dict(CharacterComment.objects.get(author=req.user, character=id))
        except CharacterComment.DoesNotExist:
            pass
    
    comments = list(CharacterComment.objects.annotate(
                        author_name=F('author__username')
                    ).filter(character=id).order_by('-created').values())
            
    jsons = {
        'char': model_to_dict(char),
        "passive": passive,
        "skin": [char.img] + [i.image for i in skinImgs],
        "selfComment": selfComment,
        "comments": comments,
    }
    return JsonResponse(jsons, safe=False)

def writeComment(req):
    if req.method == 'POST':
        if req.user.is_authenticated:
            form = CharacterCommentForm(req.POST)
            if form.is_valid():
                print(form.cleaned_data['comment'])
                keys = ['power', 'combo', 'reversal', 'safety', 'tempo']
                dt = {}
                for key in keys:
                    if form.cleaned_data[key] == None: dt[key] = None
                    elif form.cleaned_data[key]<0: dt[key] = None
                    elif form.cleaned_data[key]>10: dt[key] = 10
                    else: dt[key] = int(form.cleaned_data[key])
                try:
                    cc = CharacterComment.objects.get(author=req.user, character=form.cleaned_data['character'])
                except CharacterComment.DoesNotExist:
                    cc = CharacterComment(
                        character = form.cleaned_data['character'],
                        author = req.user,
                        comment = form.cleaned_data['comment'],
                        power = dt['power'],
                        combo = dt['combo'],
                        reversal = dt['reversal'],
                        safety = dt['safety'],
                        tempo = dt['tempo'],
                    )
                else:
                    cc.comment = form.cleaned_data['comment']
                    cc.power = dt['power']
                    cc.combo = dt['combo']
                    cc.reversal = dt['reversal']
                    cc.safety = dt['safety']
                    cc.tempo = dt['tempo']
                cc.save()
                return HttpResponse("성공")
            return HttpResponse("실패")
        else:
            raise PermissionError()
    else:
        raise Http404()