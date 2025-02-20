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
    name = forms.CharField(
        label = "덱 이름",
        max_length = 25,
        widget = forms.TextInput(
            attrs = {
                'class': 'ms-1',
                'placeholder': '덱 이름'}),
    )
    char = forms.ModelChoiceField(
        label = "캐릭터",
        queryset = Character.objects.order_by('name'),
        widget = forms.RadioSelect(attrs = {'class': 'charSelect searchCheckbox ms-1'}),
        required = False,
        initial = Character.objects.get(id=1),
    )
    version = forms.ChoiceField(
        label = "버전",
        choices = [
            ('ST', 'ST'),
            ('AWL', 'AWL'),
            ('UNC', 'UNC'),
            ('LMI', 'LMI'),
            ('CRS', 'CRS'),
            ('N/A', 'N/A'),
        ],
        initial = 'N/A'
    )
    keyword = forms.CharField(
        label = "태그",
        max_length = 255,
        required = False,
        widget = forms.TextInput(
            attrs = {
                'class': 'w-100',
                'placeholder': '검색 키워드 목록'}),
    )
    
    class Meta:
        model = Deck
        fields = ['name', 'description', 'char', 'keyword']
        widgets = {
            'description': SummernoteWidget(attrs={'class': 'w-100'}),
        }