from django.shortcuts import render, redirect
from django.urls import reverse
from django.core import serializers
from django.core.paginator import Paginator
from django.http import HttpResponse, Http404, JsonResponse
from django.db.models import Q, Count

from .models import QNA, QNARelation
from .forms import QnaSearchForm, QnaForm
from card.models import Card
from decorators import permission_required

import openpyxl, json

# Create your views here.
def index(req):
    page = req.GET.get('page', 1)
    
    form = QnaSearchForm(req.GET)
    if not form.is_valid():
        query = None
        faq = None
    else:
        query = form.cleaned_data['query']
        faq = form.cleaned_data['faq']

    if query:
        q = Q(title__contains=query) | Q(tags__contains=query)
        qna = QNA.objects.filter(q).order_by('-faq', '-created_at')
    else:
        qna = QNA.objects.all().order_by('-faq', '-created_at')
    
    if faq:
        qna = qna.filter(faq=True)
    
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

@permission_required('qna.manage')
def create(req):
    if req.method == 'GET':
        form = QnaForm()
        
        print(form.fields['question'].widget)
        return render(req, 'qna/create.html', {'form': form})
    else:
        data = json.loads(req.body)
        errorContent = {'status': 200}
        try:
            newQNA = QNA(
                title = data['title'],
                question = data['question'],
                answer = data['answer'],
                tags = data['tags'],
                faq = ('faq' in data.keys())
            )
            newQNA.save()
        except:
            errorContent['msg'] =  '올바르지 않은 데이터가 있습니다.'
            return JsonResponse(errorContent)
        else:
            for cards in data['related']:
                rc = QNARelation(
                    qna = newQNA,
                    card_id = cards[0]
                )
                rc.save()
            
            content = {
                'status': 100,
                'url': reverse('qna:detail', kwargs={'id': newQNA.id})
            }
            return JsonResponse(content)

def createSearch(req):
    keyword = req.GET.get('keyword', '')
    
    if keyword != '':
        q = Q()
        q.add(Q(name__contains=keyword), q.OR)
        q.add(Q(keyword__contains=keyword), q.OR)
        cards = Card.objects.filter(q)
        
        sdata = serializers.serialize('json', cards)
        return JsonResponse(sdata, safe=False)
    else:
        return JsonResponse([], safe=False)

@permission_required('qna.manage')
def update(req, id=0):
    try:
        qna = QNA.objects.get(id=id)
    except QNA.DoesNotExist:
        raise Http404('QNA가 존재하지 않습니다.')
    
    if req.method == 'GET':
        form = QnaForm(instance=qna)
        related = QNARelation.objects.filter(qna=qna)
        return render(req, 'qna/update.html', {'form': form, 'related': related})
    else:
        data = json.loads(req.body)
        errorContent = {'status': 200}
        try:
            qna.title = data['title']
            qna.question = data['question']
            qna.answer = data['answer']
            qna.tags = data['tags']
            qna.faq = ('faq' in data.keys())
            qna.save()
        except:
            errorContent['msg'] =  '올바르지 않은 데이터가 있습니다.'
            return JsonResponse(errorContent)
        else:
            QNARelation.objects.filter(qna=qna).delete()
            for cards in data['related']:
                rc = QNARelation(
                    qna = qna,
                    card_id = cards[0]
                )
                rc.save()
            
            content = {
                'status': 100,
                'url': reverse('qna:detail', kwargs={'id': qna.id})
            }
            return JsonResponse(content)

@permission_required('qna.manage')
def delete(req, id=0):
    try:
        qna = QNA.objects.get(id=id)
    except QNA.DoesNotExist:
        raise Http404('QNA가 존재하지 않습니다.')
    
    qna.delete()
    
    return redirect('qna:index')
    
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

def special(req):
    page = req.GET.get('page', 1)
    
    form = QnaSearchForm(req.GET)
    if not form.is_valid():
        query = None
        faq = None
    else:
        query = form.cleaned_data['query']
        faq = form.cleaned_data['faq']

    if query:
        q = Q(title__contains=query) | Q(tags__contains=query)
        qna = QNA.objects.filter(q).order_by('-faq', '-created_at')
    else:
        qna = QNA.objects.all().order_by('-faq', '-created_at')
    
    if faq:
        qna = qna.filter(faq=True)
    
    qna = qna.annotate(num_related=Count('cards')).filter(num_related=0)
    
    paginator = Paginator(qna, 30)
    page_data = paginator.get_page(page)
    
    context = {
        'form': form,
        'data': page_data
    }
    
    return render(req, 'qna/index.html', context=context)