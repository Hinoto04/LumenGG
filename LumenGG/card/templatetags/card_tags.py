from django import template

register = template.Library()

@register.filter(name='keywords')
def keywords(value):
    return ('#' + ' #'.join(value.split('/')[:-1])) if value else '태그 없음'

packnameDict = {
    'ST1': '스타터 덱 - 지식의 은묘 니아',
    'ST2': '스타터 덱 - 뇌전의 헌터 루트',
    'ST3': '스타터 덱 - 열혈! 정비 소녀 델피',
    'ST4': '스타터 덱 - 괴도 키스 더 래빗',
    'ST5': '스타터 덱 - 제국의 칼날 울프',
    'ST6': '스타터 덱 - 매혹의 무희 비올라',
    'SP1': '스페셜 팩 - 지식의 은묘 니아',
    'SP2': '스페셜 팩 - 뇌전의 헌터 루트',
    'SP3': '스페셜 팩 - 열혈! 정비 소녀 델피',
    'SP4': '스페셜 팩 - 괴도 키스 더 래빗',
    'SP5': '스페셜 팩 - 제국의 칼날 울프',
    'SP6': '스페셜 팩 - 매혹의 무희 비올라',
    'AWL': '어웨이크닝 루멘',
    'UNC': '유니즌 챌린저',
    'LMI': '루미너스 이노센스',
    'CRS': '크림슨 스트라이커즈',
    'CS': '챔피언십 팩',
    'PR': '프로모',
}

@register.filter(name="packname")
def packname(code):
    c = code.split('-')[:-1]
    name = ''
    for i in c:
        if i in packnameDict.keys():
            name += packnameDict[i] + ' '
    return name

@register.filter(name="toStar")
def toStar(value):
    return "★"*value + "☆"*(10-value)