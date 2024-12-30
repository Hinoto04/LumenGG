from django.shortcuts import render
from django.http import HttpResponse, Http404
from django.core.paginator import Paginator
import openpyxl
import requests

from ..models import Card, Character
import re

def importCards(req):
    
    wb = openpyxl.load_workbook('../CardList.xlsx')
    sheet = wb['CardList']
    
    cards = []
    
    linklist = {}
    f = open('../imglinks.txt', encoding='UTF-8')
    while l:=f.readline():
        l = l.strip()
        code = l.split('/')[-1][:-4]
        linklist[code] = l
    
    for row in sheet.rows:
        if row[0].value is None: continue
        ll = list(map(lambda x: x.value, row))
        
        # if not(ll[11] is None):
        #     pat = re.sub(r" (?=[①②③④⑤⑥⑦⑧])", '\n', ll[11])
        # else:
        #     pat = ''
        # print(pat)
        
        c = Card(
            name = ll[0],
            ruby = '',
            frame = int(ll[3]) if (ll[3] and ll[3]!='-') else None,
            type = ll[2] if (ll[2] and ll[2]!='-') else None,
            pos = ll[4] if (ll[4] and ll[4]!='-') else None,
            damage = ll[5] if (ll[5] and ll[5]!='-') else None,
            body = ll[6] if (ll[6] and ll[6]!='-') else None,
            special = ll[7] if (ll[7] and ll[7]!='-') else None,
            hit = ll[8] if (ll[8] and ll[2] == "공격" and ll[8] != "X") else None,
            guard = ll[9] if (ll[9] and ll[2] == "공격" and ll[9] != "X") else None,
            counter = ll[10] if (ll[10] and ll[2] == "공격" and ll[10] != "X") else None,
            g_top = ll[8] if (ll[8] and ll[2] == "수비" and ll[8] != "X") else None,
            g_mid = ll[9] if (ll[9] and ll[2] == "수비" and ll[9] != "X") else None,
            g_bot = ll[10] if (ll[10] and ll[2] == "수비" and ll[10] != "X") else None,
            text = ll[11] if ll[11] else '',
            code = ll[12],
            img = linklist[ll[12]],
            character = Character.objects.get(name=ll[1])
        )
        
        c.save()
        cards.append(c)
    
    context = {
        'cards': cards
    }
    return render(req, 'card/import.html', context=context)

def keywordAdd(data, keyword):
    ls = data.keyword.split('/')[:-1]
    if not (keyword in ls):
        ls.append(keyword)
    s = '/'.join(ls) + '/'
    data.keyword = s

def searchAdd(data, keyword):
    ls = data.search.split('/')[:-1]
    if not (keyword in ls):
        ls.append(keyword)
    s = '/'.join(ls) + '/'
    data.search = s

def keywordSet(req):
    cards = []
    
    keyword = "콤보"
    datas = Card.objects.filter(keyword__contains=keyword)
    for data in datas:
        ls = data.keyword.split('/')[:-1]
        if (keyword in ls):
            ls[ls.index(keyword)] = "콤보 시동"
        s = '/'.join(ls) + '/'
        data.keyword = s
        cards.append(data)
        #data.save()
    
    context = {
        'cards': cards
    }
    return render(req, 'card/keywordset.html', context=context)
