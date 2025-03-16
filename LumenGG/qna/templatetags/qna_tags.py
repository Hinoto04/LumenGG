import markdown
from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()

def replace_newlines_with_regex(string):
    # 정규표현식을 사용하여 여러 개의 \n 중 첫 번째를 제외하고 나머지를 <br>로 변환합니다.
    transformed_string = re.sub(r'(\n)(\n+)', lambda match: match.group(1) + '<br>' * (len(match.group(2))), string)
    return transformed_string

@register.filter
def mark(value):
    extensions = ["nl2br", "fenced_code"]
    return mark_safe(markdown.markdown(replace_newlines_with_regex(value), extensions=extensions))