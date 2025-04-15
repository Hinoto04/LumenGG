from django import forms
from django_summernote.widgets import SummernoteWidget

from card.models import Character
from .models import Championship

class CSSearchForm(forms.Form):
    keyword = forms.CharField(
        label = "",
        max_length = 50,
        required = False,
        widget = forms.TextInput(
            attrs = {
                'class': 'form-control 배경색1 w-100',
                'placeholder': '대회명 검색'}),
    )