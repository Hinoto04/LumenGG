from django.shortcuts import render, redirect
from django.http import HttpResponse, Http404, JsonResponse
from django.db.models import Q
from ..models import Card, Character
from collection.models import CollectionCard

def character(req):
    
    characters = Character.objects.filter(id__gt=1).order_by('pack__released')
    
    context = {
        'chars': characters
    }
    return render(req, 'character/index.html', context=context)

def detail(req, id):
    try:
        char = Character.objects.get(id=id)
    except Character.DoesNotExist:
        raise Http404()
    
    skinImgs = CollectionCard.objects.filter(Q(name__contains=char.name)&Q(rare="SKR")&Q(card_id=None))
    skins = [char.img] + [i['image'] for i in list(skinImgs.values())]
    
    context = {
        'skins': skins
    }
    return render(req, 'character/detail.html', context=context)