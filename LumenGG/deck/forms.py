from django import forms

from card.models import Character
from common.language import translated_character_field, ui_text
from .models import Deck


def _translated_choices(choices, language):
    return [(value, ui_text(label, language)) for value, label in choices]


def _localize_character_field(field, language):
    field.label_from_instance = lambda character: translated_character_field(character, language, 'name')


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

    def __init__(self, *args, language=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['char'].label = ui_text('캐릭터', language)
        _localize_character_field(self.fields['char'], language)
        self.fields['keyword'].widget.attrs['placeholder'] = ui_text('키워드, 작성자 검색', language)
        self.fields['sort'].label = ui_text('정렬', language)
        self.fields['sort'].choices = _translated_choices(self.fields['sort'].choices, language)

class DeckMakeForm(forms.ModelForm):
    name = forms.CharField(
        label = "덱 이름",
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
        initial = 1,
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
    visibility = forms.ChoiceField(
        label = "공개 범위",
        choices = Deck.VISIBILITY_CHOICES,
        initial = Deck.VISIBILITY_PUBLIC,
        widget = forms.Select(attrs={'class': 'btn border 배경색1'})
    )
    
    class Meta:
        model = Deck
        fields = ['name', 'description', 'char', 'keyword', 'visibility']
        # widgets = {
        #     'description': SummernoteWidget(attrs={'class': 'w-100', 'rows':''}),
        # }

    def __init__(self, *args, language=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].label = ui_text('덱 이름', language)
        self.fields['name'].widget.attrs['placeholder'] = ui_text('덱 이름', language)
        self.fields['char'].label = ui_text('캐릭터', language)
        _localize_character_field(self.fields['char'], language)
        self.fields['keyword'].label = ui_text('태그', language)
        self.fields['keyword'].widget.attrs['placeholder'] = ui_text('검색 키워드 목록', language)
        self.fields['visibility'].label = ui_text('공개 범위', language)
        self.fields['visibility'].choices = _translated_choices(self.fields['visibility'].choices, language)

class DeckImportForm(forms.Form):
    name = forms.CharField(
        label = "덱 이름",
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
        initial = 1,
    )
    visibility = forms.ChoiceField(
        label = "공개 범위",
        choices = Deck.VISIBILITY_CHOICES,
        initial = Deck.VISIBILITY_PUBLIC,
        widget = forms.Select(attrs={'class': 'btn border 배경색1'})
    )
    deck = forms.CharField(widget=forms.Textarea(
        attrs = {
            'class': 'form-control'
        }
    ))

    def __init__(self, *args, language=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].label = ui_text('덱 이름', language)
        self.fields['name'].widget.attrs['placeholder'] = ui_text('덱 이름', language)
        self.fields['char'].label = ui_text('캐릭터', language)
        _localize_character_field(self.fields['char'], language)
        self.fields['visibility'].label = ui_text('공개 범위', language)
        self.fields['visibility'].choices = _translated_choices(self.fields['visibility'].choices, language)
