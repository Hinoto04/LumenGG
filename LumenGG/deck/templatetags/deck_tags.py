from django import template

register = template.Library()

@register.filter(name='times')
def times(number):
    return range(number)

@register.filter(name="listcard")
def listcard(card):
    return range(card.count - card.hand - card.side)