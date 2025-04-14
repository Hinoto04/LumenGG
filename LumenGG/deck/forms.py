from django import forms
from django_summernote.widgets import SummernoteWidget

from card.models import Character
from .models import Deck

class DeckSearchForm(forms.Form):
    char = forms.ModelMultipleChoiceField(
        label = "캐릭터",
        queryset = Character.objects.order_by('name'),
        widget = forms.CheckboxSelectMultiple(attrs = {'class': '검색체크 flex-wrap'}),
        required = False,
    )
    keyword = forms.CharField(
        label = "",
        max_length = 50,
        required = False,
        widget = forms.TextInput(
            attrs = {
                'class': 'form-control 배경색1 w-100',
                'placeholder': '키워드, 작성자 검색'}),
    )
    sort = forms.ChoiceField(
        label = "정렬",
        choices = [
            ('recent', '최신순'),
            ('version', '버전순'),
            ('like', '좋아요순'),
        ],
        initial = 'recent', 
        widget = forms.Select(attrs={'class': 'btn border 배경색1'})
    )

class DeckMakeForm(forms.ModelForm):
    name = forms.CharField(
        label = "덱 이름",
        max_length = 25,
        widget = forms.TextInput(
            attrs = {
                'class': 'form-control 배경색1',
                'placeholder': '덱 이름'}),
    )
    char = forms.ModelChoiceField(
        label = "캐릭터",
        queryset = Character.objects.order_by('name'),
        widget = forms.RadioSelect(attrs = {'class': '검색체크 flex-wrap charSelect'}),
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
            ('PMP', 'PMP'),
            ('N/A', 'N/A'),
        ],
        initial = 'N/A',
        widget = forms.Select(attrs={'class': 'btn border 배경색1'})
    )
    keyword = forms.CharField(
        label = "태그",
        max_length = 255,
        required = False,
        widget = forms.TextInput(
            attrs = {
                'class': 'form-control 배경색1',
                'placeholder': '검색 키워드 목록'}),
    )
    private = forms.BooleanField(
        label = "비공개",
        required = False,
        initial = False,
        widget = forms.CheckboxInput(attrs={'class': 'form-check-input mt-auto mb-auto'}),
    )
    
    class Meta:
        model = Deck
        fields = ['name', 'description', 'char', 'keyword']
        widgets = {
            'description': SummernoteWidget(attrs={'class': 'w-100'}),
        }
