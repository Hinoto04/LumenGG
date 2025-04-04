from django import forms
from .models import CollectionCard, Collected, Pack
from card.models import Card, Character

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
    
    rare = forms.ChoiceField(
        choices=[
            ('', '전체'),
            ('N', 'N : 노멀'),
            ('SR', 'SR : 슈퍼 레어'),
            ('EXR', 'EXR : 익스텐드 레어'),
            ('AN', 'AN : 어나더 노멀'),
            ('AEX', 'AEX : 어나더 익스텐드 레어'),
            ('SAEX', 'SAEX : 시크릿 어나더 익스텐드 레어'),
            ('SKR', 'SKR : 스킨 레어')
        ],
        required=False,
        widget=forms.RadioSelect(attrs = {'class': '검색체크 flex-wrap'}),
    )
    
    """Collection Form"""
    class Meta:
        model = CollectionCard
        fields = ['code', 'rare', 'char']