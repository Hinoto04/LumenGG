from django import forms
from .models import CollectionCard, Collected, Pack
from card.models import Card, Character
from django.core.validators import FileExtensionValidator

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

class CollectionCreateForm(forms.ModelForm):
    pack = forms.ModelChoiceField(
        queryset = Pack.objects.all(),
        label="팩",
        widget=forms.Select(),
    )
    rare = forms.MultipleChoiceField(
        label = "레어리티",
        choices = [
            ('N', 'N'), ('SR', 'SR'), ('EXR', 'EXR'), ('AN', 'AN'), ('AEX', 'AEX'), ('SKR', 'SKR'), ('SAEX', 'SAEX')],
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
        fields = ['name', 'code']