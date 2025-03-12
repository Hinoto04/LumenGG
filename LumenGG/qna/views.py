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

def qnaPreprocess(string: str):
    text = string.lstrip("Q").lstrip('A').\
        lstrip('1').lstrip('2').lstrip('3').lstrip('4').lstrip('5')\
            .lstrip('6').lstrip('7').lstrip('8').lstrip('9').lstrip('0')\
                .lstrip('.').lstrip(' ')
    text = text.replace('\\n', '').replace('.', '.\n')\
        .replace('??', '?').replace('?', '?\n')\
        .replace('!!', '!').replace('!', '!\n')\
        .replace('\n ', '\n').strip()
    ex = ['라이', '레피', '파이어', '바운스', '촙', '봄버', '드릴', '러시', '스위치', '울트라', '스크류', '캐치', '아아앗', '캐논']
    for e in ex:
        text = text.replace(e+'!\n', e+'! ')
    return text
    
def xlsxImport(req):
    wb = openpyxl.load_workbook('../QNA NEW.xlsx')
    sheet = wb.active
    
    for row in sheet.rows:
        newQNA = QNA(
            title = row[0].value,
            question = qnaPreprocess(row[1].value),
            answer = qnaPreprocess(row[2].value),
            faq = False,
        )
        #print("질문: ", newQNA.question)
        #print("답변: ", newQNA.answer)
        newQNA.save()
        if row[3].value == '없음':
            continue
        
        ps = ['팔괘엔진', '장막을 두른 칼날', '어쌔신', '가디언', '팔라딘']
        
        for c in row[3].value.split(', '):
            for p in ps:
                c = c.replace(p, '「'+p+'」')
            try:
                card = Card.objects.get(name=c)
            except Card.DoesNotExist:
                print(newQNA.question, " 카드 이름 오류 : ", c)
                continue
            newRelation = QNARelation(
                qna = newQNA,
                card = card
            )
            #print(newRelation)
            newRelation.save()
    
    return redirect('qna:index')