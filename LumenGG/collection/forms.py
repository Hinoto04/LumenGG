from django import forms
from .models import CollectionCard, Collected, Pack
from card.models import Card, Character
from common.language import translated_card_field, translated_character_field, translated_pack_field, ui_text
from django.core.validators import FileExtensionValidator


def _translated_choices(choices, language):
    return [(value, ui_text(label, language)) for value, label in choices]


def _localize_character_field(field, language):
    field.label_from_instance = lambda character: translated_character_field(character, language, 'name')


def _localize_pack_field(field, language):
    field.label_from_instance = lambda pack: translated_pack_field(pack, language, 'name')


class CollectionForm(forms.ModelForm):
    char = forms.ModelChoiceField(
        label = "캐릭터",
        queryset = Character.objects.order_by('name'),
        widget = forms.RadioSelect(attrs = {'class': '검색체크 flex-wrap'}),
        required = False,
    )
    
    code = forms.ModelChoiceField(
        queryset = Pack.objects.order_by('released', 'code'),
        widget = forms.Select(attrs = {'class': '긴옵션 배경색2'}),
        required = False,
    )
    
    sortValue = forms.ChoiceField(
        label = "정렬",
        choices=[
            ('', '-----'),
            ('name', '이름순'),
            ('code', '코드순'),
        ],
        required=False,
        widget=forms.Select(attrs = {'class': '긴옵션 배경색2 flex-grow-1'}),
    )
    
    ascending = forms.ChoiceField(
        label = "정렬방향",
        choices=[
            ('asc', '오름차순'),
            ('desc', '내림차순')
        ],
        required=False,
        widget=forms.Select(attrs = {'class': '긴옵션 배경색2 flex-grow-1'}),
    )
    
    onlyZero = forms.BooleanField(
        label = "미수집 카드만",
        required=False,
        widget=forms.CheckboxInput(),
    )
    
    rare = forms.ChoiceField(
        choices=[
            ('', '전체'),
            ('N', 'N : 노멀'),
            ('SR', 'SR : 슈퍼 레어'),
            ('EXR', 'EXR : 익스텐드 레어'),
            ('AN', 'AN : 어나더 노멀'),
            ('AEX', 'AEX : 어나더 익스텐드 레어'),
            ('SAR', 'SAR : 시크릿 어나더 익스텐드 레어'),
            ('SP', 'SP : 스페셜')
        ],
        required=False,
        widget=forms.RadioSelect(attrs = {'class': '검색체크 flex-wrap'}),
    )
    
    """Collection Form"""
    class Meta:
        model = CollectionCard
        fields = ['code', 'rare', 'char']

    def __init__(self, *args, language=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['char'].label = ui_text('캐릭터', language)
        _localize_character_field(self.fields['char'], language)
        self.fields['code'].label = ui_text('출신 팩', language)
        _localize_pack_field(self.fields['code'], language)
        self.fields['sortValue'].label = ui_text('정렬', language)
        self.fields['sortValue'].choices = _translated_choices(self.fields['sortValue'].choices, language)
        self.fields['ascending'].label = ui_text('정렬방향', language)
        self.fields['ascending'].choices = _translated_choices(self.fields['ascending'].choices, language)
        self.fields['onlyZero'].label = ui_text('미수집 카드만', language)
        self.fields['rare'].label = ui_text('레어도', language)
        self.fields['rare'].choices = _translated_choices(self.fields['rare'].choices, language)

class CollectionCreateForm(forms.ModelForm):
    pack = forms.ModelChoiceField(
        queryset = Pack.objects.all(),
        label="팩",
        widget=forms.Select(),
    )
    rare = forms.MultipleChoiceField(
        label = "레어리티",
        choices = [
            ('N', 'N'), ('SR', 'SR'), ('EXR', 'EXR'), ('AN', 'AN'), ('AEX', 'AEX'), ('SP', 'SP'), ('SAR', 'SAR')],
        widget = forms.CheckboxSelectMultiple(attrs={'class': 'rare'}),
        required = False,
    )
    imageFile = forms.FileField(
        label = "이미지",
        required = False,
        validators=[FileExtensionValidator(allowed_extensions=['webp'])],
        widget = forms.ClearableFileInput(attrs={'multiple': False}),
    )
    card = forms.ModelChoiceField(
        queryset = Card.objects.order_by('name'),
        label= "카드",
        widget = forms.Select(),
        required = False,
    )
    
    class Meta:
        model = CollectionCard
        fields = ['name', 'code', 'character', 'item_type']

    def __init__(self, *args, language=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].label = ui_text('카드명', language)
        self.fields['code'].label = ui_text('수록 정보', language)
        self.fields['character'].label = ui_text('캐릭터', language)
        self.fields['character'].queryset = Character.objects.order_by('name')
        _localize_character_field(self.fields['character'], language)
        self.fields['item_type'].label = ui_text('분류', language)
        self.fields['item_type'].choices = _translated_choices(self.fields['item_type'].choices, language)
        self.fields['pack'].label = ui_text('팩', language)
        _localize_pack_field(self.fields['pack'], language)
        self.fields['rare'].label = ui_text('레어도', language)
        self.fields['imageFile'].label = ui_text('이미지', language)
        self.fields['card'].label = ui_text('카드', language)
        self.fields['card'].label_from_instance = lambda card: translated_card_field(card, language, 'name')
