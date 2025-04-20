from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404, JsonResponse
from django.db.models import Q
from ..models import Card, Character
from collection.models import CollectionCard
from django.forms.models import model_to_dict

import json

def index(req):
    chars = Character.objects.filter(Q(id__gt=1)&Q(id__lt=13)).order_by('pack__released')
    
    context = {
        'chars': chars
    }
    return render(req, 'character/index.html', context=context)

def character(req):
    
    characters = Character.objects.filter(Q(id__gt=1)&Q(id__lt=13)).order_by('pack__released')
    
    context = {
        'chars': characters
    }
    return render(req, 'character/index.html', context=context)

def detail(req, id):
    try:
        char = Character.objects.get(id=id)
    except Character.DoesNotExist:
        raise Http404()
    
    data = char.datas.copy()
    for i in data['identity']:
        i['card'] = list(Card.objects.only('img_mid').filter(id=i['card']).values('id', 'name', 'img_mid'))
    
    skinImgs = CollectionCard.objects.filter(Q(name__contains=char.name)&Q(rare="SKR")&Q(card_id=None))
    passive = list(Card.objects.filter(type="특성", character=char).values('id', 'name', 'img'))
    
    json = {
        'char': model_to_dict(char),
        "passive": passive,
        "skin": [char.img] + [i.image for i in skinImgs],
    }
    return JsonResponse(json)