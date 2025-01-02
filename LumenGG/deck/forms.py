from django import forms
from django_summernote.widgets import SummernoteWidget

from card.models import Character
from .models import Deck

class DeckSearchForm(forms.Form):
    char = forms.ModelMultipleChoiceField(
        label = "캐릭터",
        queryset = Character.objects.order_by('name'),
        widget = forms.CheckboxSelectMultiple(attrs = {'class': 'searchCheckbox ms-1'}),
        required = False,
    )
    keyword = forms.CharField(
        label = "",
        max_length = 50,
        required = False,
        widget = forms.TextInput(
            attrs = {
                'class': 'form-control w-100 mb-2',
                'placeholder': '키워드 검색'}),
    )

class DeckMakeForm(forms.ModelForm):
    char = forms.ModelMultipleChoiceField(
        label = "캐릭터",
        queryset = Character.objects.order_by('name'),
        widget = forms.CheckboxSelectMultiple(attrs = {'class': 'searchCheckbox ms-1'}),
        required = False,
    )
    keyword = forms.CharField(
        label = "태그",
        max_length = 255,
        required = False,
        widget = forms.TextInput(
            attrs = {
                'class': 'form-control w-100 mb-2',
                'placeholder': '키워드 검색'}),
    )
    
    class Meta:
        model = Deck
        fields = ['name', 'description', 'char', 'keyword']
        widgets = {
            'content': SummernoteWidget()
        }