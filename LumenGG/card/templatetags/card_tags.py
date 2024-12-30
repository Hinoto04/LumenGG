from django import template

register = template.Library()

@register.filter(name='keywords')
def keywords(value):
    return ('#' + ' #'.join(value.split('/')[:-1])) if value else '태그 없음'