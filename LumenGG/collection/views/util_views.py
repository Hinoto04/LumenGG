import openpyxl
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse

from card.models import Card, Character
from ..models import CollectionCard, Collected

rare_table = {
    '노멀': 'N',
    '슈퍼레어': 'SR',
    '익스텐드레어': 'EXR',
    '어나더노멀': 'AN',
    '어나더익스텐드레어': 'AEX',
    '시크릿어나더익스텐드레어': 'SAEX',
    '스킨레어': 'SKR'
}

#짬통함수 << 원래는 익스포트였는데 그냥 할거있으면 수정해서 여기서하면됨
#지금은 import함수인상태
def export_cards(req):
    
    linklist = {}
    
    f = open('../imglinks.txt', encoding='UTF-8')
    while l:=f.readline():
        l = l.strip()
        code = l.split('/')[-1][:-4]
        linklist[code] = l
        
    
    workbook = openpyxl.load_workbook('../CRS루멘콘덴서_공유용.xlsx')
    worksheet = workbook.active
    
    for row in worksheet.rows:
        card_code = row[1].value
        if card_code in [None, '번호', 'Tables 번호']:
            continue
        
        card_name = row[2].value
        try:
            card = Card.objects.get(name=card_name)
        except:
            card = None
            print('Card Not Found : ', card_name)
            
        try:
            card_image = linklist[card_code]
        except KeyError:
            if card is None:
                card_image = ''
                print('Image Not Found : ', card_name)
            else:
                card_image = card.img
        
        card_rare_raw = row[4].value
        for i in card_rare_raw.split('/'):
            newCC = CollectionCard(
                code=card_code,
                card=card,
                image=card_image,
                rare=rare_table[i],
            )
            #newCC.save()
            #print(card_code, card_name, card_image, rare_table[i])
    
    
    return HttpResponse('Cards exported successfully.')

def initinit(req):
    pool1 = ['스탠딩 가드', '다운 가드', '구르기', '점프', '대쉬', '커팅' ,'카운터 랫', '세츠 슬래시', '캐치 드롭', '이판사판태클']
    pool2 = ['스탠딩 가드', '다운 가드', '구르기', '점프', '대쉬', '커팅' ,'다운 슬래쉬', '세츠메이 킥', '캐치 드롭', '이판사판태클']
    
    pack = 'ST5'
    for i in range(11, 21):
        card = Card.objects.get(name=pool1[i-11])
        newCC = CollectionCard(
            code=pack + '-0' + str(i),
            card=card,
            image=card.img,
            rare='N',
            name=card.name
        )
        print(newCC.code, newCC.card.name, newCC.image, newCC.rare)
        newCC.save()