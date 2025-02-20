from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.http import HttpResponse, Http404
from django.db.models import Q

from .models import QNA, QNARelation
from .forms import QnaSearchForm
from card.models import Card

import openpyxl

# Create your views here.
def index(req):
    page = req.GET.get('page', 1)
    
    form = QnaSearchForm(req.GET)
    if not form.is_valid():
        query = None
    else:
        query = form.cleaned_data['query']

    if query:
        qna = QNA.objects.filter(title__contains=query).order_by('-created_at')
    else:
        qna = QNA.objects.all().order_by('-created_at')
    
    paginator = Paginator(qna, 30)
    page_data = paginator.get_page(page)
    
    context = {
        'form': form,
        'data': page_data
    }
    
    return render(req, 'qna/index.html', context=context)

def detail(req, id=0):
    try:
        qna = QNA.objects.get(id=id)
    except QNA.DoesNotExist:
        raise Http404('QNA가 존재하지 않습니다.')
    
    context = {
        'qna': qna
    }
    
    return render(req, 'qna/detail.html', context=context)

def xlsxImport(req):
    wb = openpyxl.load_workbook('../루멘 QNA.xlsx')
    sheet = wb.active
    
    for row in sheet.rows:
        newQNA = QNA(
            title = row[0].value,
            question = row[1].value,
            answer = row[2].value,
            faq = True,
        )
        newQNA.save()
        
        for c in row[3].value.split(' / '):
            card = Card.objects.filter(name__contains=c)
            for relatedCard in card:
                newRelation = QNARelation(
                    qna = newQNA,
                    card = relatedCard
                )
                print(newRelation)
                newRelation.save()
    
    return redirect('qna:index')