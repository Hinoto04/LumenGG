from django import forms
from .models import QNA
from martor.fields import MartorFormField
from martor.widgets import MartorWidget

class QnaSearchForm(forms.Form):
    query = forms.CharField(max_length=255, required=False, label='Search', 
                            widget=forms.TextInput(attrs={'class': 'form-control 배경색1', 'placeholder': '검색'}))
    faq = forms.BooleanField(required=False, label='FAQ', widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

class QnaForm(forms.ModelForm):
    class Meta:
        model = QNA
        fields = ['title', 'question', 'answer', 'faq']