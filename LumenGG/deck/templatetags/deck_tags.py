from django import template

register = template.Library()

@register.filter(name='times')
def times(number):
    return range(number)

@register.filter(name="listcard")
def listcard(card):
    return range(max(card.count - card.hand - card.side, 0))

@register.filter(name='deckkeywords')
def deckkeywords(value):
    if not value:
        return '태그 없음'
    tags = [tag.strip().lstrip('#') for tag in str(value).split('/') if tag.strip()]
    if not tags:
        return '태그 없음'
    return '#' + ' #'.join(tags)
