from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404, JsonResponse
from django.db.models import Q, F
from ..models import Card, Character, CharacterComment
from collection.models import CollectionCard
from django.forms.models import model_to_dict
from django.utils import timezone
from django.core import serializers
from ..forms import CharacterCommentForm
from common.language import (
    get_language,
    translated_card_field,
    translated_character_datas,
    translated_character_field,
)

import json, math

def index(req, template_name='character/index.html'):
    id = req.GET.get('id', '2')
    chars = Character.objects.filter(Q(pack__released__lte=timezone.now())).prefetch_related('translations').order_by('pack__released')
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
    return render(req, template_name, context=context)

def indexV2(req):
    return index(req, 'character/index_v2.html')

def character(req):
    
    characters = Character.objects.filter(Q(id__gt=1)).order_by('pack__released')
    
    context = {
        'chars': characters,
    }
    return render(req, 'character/list.html', context=context)

def detail(req, id):
    language = get_language(req)
    try:
        char = Character.objects.prefetch_related('translations').get(id=id)
    except Character.DoesNotExist:
        raise Http404()
    
    data = translated_character_datas(char, language)
    for i in data['identity']:
        cards = Card.objects.prefetch_related('translations').only('id', 'name', 'img_mid').filter(id=i['card'])
        i['card'] = [
            {
                'id': card.id,
                'name': translated_card_field(card, language, 'name'),
                'img_mid': card.img_mid,
            }
            for card in cards
        ]
    
    skinImgs = list(CollectionCard.objects.filter(
        character=char,
        card_id=None,
        item_type=CollectionCard.ITEM_TYPE_SKIN,
    ).order_by('pack__released'))
    tokenImgs = list(CollectionCard.objects.filter(
        character=char,
        card_id=None,
        item_type=CollectionCard.ITEM_TYPE_TOKEN,
    ).order_by('pack__released'))

    skin_ids = [collection_card.id for collection_card in skinImgs]
    token_ids = [collection_card.id for collection_card in tokenImgs]
    skinImgs += list(CollectionCard.objects.filter(
        Q(name__contains=char.name)
        & Q(card_id=None)
        & ~Q(rare="N")
        & ~Q(name__contains="토큰")
    ).exclude(id__in=skin_ids).order_by('pack__released'))
    tokenImgs += list(CollectionCard.objects.filter(
        Q(name__contains=char.name)
        & Q(card_id=None)
        & Q(name__contains="토큰")
    ).exclude(id__in=token_ids).order_by('pack__released'))
    passive = [
        {
            'id': card.id,
            'name': translated_card_field(card, language, 'name'),
            'img': card.img,
        }
        for card in Card.objects.prefetch_related('translations').filter(type="특성", character=char)
    ]
    selfComment = None
    if req.user.is_authenticated:
        try:
            selfComment = model_to_dict(CharacterComment.objects.get(author=req.user, character=id))
        except CharacterComment.DoesNotExist:
            pass
    
    comments = list(CharacterComment.objects.annotate(
                        author_name=F('author__username')
                    ).filter(character=id).order_by('-created').values())
            
    char_data = model_to_dict(char)
    char_data['name'] = translated_character_field(char, language, 'name')
    char_data['description'] = translated_character_field(char, language, 'description')
    char_data['group'] = translated_character_field(char, language, 'group')
    char_data['datas'] = data

    jsons = {
        'char': char_data,
        "passive": passive,
        "skin": [char.img] + [i.image for i in skinImgs],
        "token": [i.image for i in tokenImgs],
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
