from django import forms
from .models import Character, Card, Tag

class CardForm(forms.Form):
    char = forms.ModelMultipleChoiceField(
        label = "캐릭터",
        queryset = Character.objects.order_by('name'),
        widget = forms.CheckboxSelectMultiple(attrs = {'class': '검색체크 flex-wrap'}),
        required = False,
    )
    type = forms.MultipleChoiceField(
        label = "분류",
        choices = [('특성', '특성'), ('공격', '공격'), ('수비', '수비'), ('특수', '특수')],
        widget = forms.CheckboxSelectMultiple(attrs = {'class': '검색체크'}),
        required = False,
    )
    pos = forms.MultipleChoiceField(
        label = "판정",
        choices = [('상단', '상단'), ('중단', '중단'), ('하단', '하단')],
        widget = forms.CheckboxSelectMultiple(attrs = {'class': '검색체크'}),
        required = False,
    )
    body = forms.MultipleChoiceField(
        label = "부위",
        choices = [('없음', '없음'), ('손', '손'), ('발', '발')],
        widget = forms.CheckboxSelectMultiple(attrs = {'class': '검색체크'}),
        required = False,
    )
    specialpos = forms.MultipleChoiceField(
        label = "특수",
        required = False,
        choices = [
            ('상단', '상단'), ('중단', '중단'), ('하단', '하단')], 
        widget = forms.CheckboxSelectMultiple(attrs = {'class': '검색체크'}),
    )
    specialtype = forms.MultipleChoiceField(
        label = "특수",
        required = False,
        choices = [
            ('회피', '회피'), ('상쇄', '상쇄'), ('그랩', '그랩')],
        widget = forms.CheckboxSelectMultiple(attrs = {'class': '검색체크'}),
    )
    pack = forms.ChoiceField(
        label = "출신 팩",
        choices = [
            ('', '출신 팩'), 
            ('ST', '스타터 덱'), 
            ('AWL', '어웨이크닝 루멘'),
            ('UNC', '유니즌 챌린저'), 
            ('LMI', '루미너스 이노센스'),
            ('CRS', '크림슨 스트라이커즈')],
        widget = forms.Select(attrs = {'class': '긴옵션 배경색2'}),
        required = False,
    )
    framenum = forms.IntegerField(
        max_value = 14,
        min_value = 1,
        label = "속도",
        required = False,
        widget = forms.NumberInput(
            attrs = {
                'class': '긴옵션 배경색2',
                'placeholder': '속도'}),
    )
    frametype = forms.ChoiceField(
        label = "속도 분류",
        required = False,
        choices = [
            ('일치', '일치'), ('이상', '이상'), ('이하', '이하')],
        widget = forms.RadioSelect(attrs = {'class': '검색체크 작은버튼'}),
        initial = '일치',
    )
    keyword = forms.CharField(
        label = "",
        max_length = 50,
        required = False,
        widget = forms.TextInput(
            attrs = {
                'class': 'form-control 배경색1 w-100',
                'placeholder': '카드명, 키워드 검색'}),
    )
    sort = forms.ChoiceField(
        label = "정렬",
        required = False,
        choices = [
            ('', '정렬'), 
            ('-속도', '속도 내림차순'), ('+속도', '속도 오름차순'), 
            ('-데미지', '데미지 내림차순'), ('+데미지', '데미지 오름차순'),],
        widget = forms.Select(attrs = {'class': 'btn btn-sm border'}),
    )

class TagCreateForm(forms.ModelForm):
    name = forms.CharField(
        label = "태그명",
        max_length = 20,
        widget = forms.TextInput(attrs = {'class': 'form-control'}),
    )
    description = forms.CharField(
        label = "태그 설명",
        widget = forms.Textarea(attrs = {'class': 'form-control'}),
    )
    
    class Meta:
        model = Tag
        fields = ['name', 'description']

class CardTagEditForm(forms.Form):
    keyword = forms.CharField(
        label = '이 카드의 태그',
        max_length = 255,
        widget = forms.TextInput(attrs = {'class': 'form-control'})
    )
    search = forms.CharField(
        label = '이 카드가 찾는 태그',
        max_length = 255,
        widget = forms.TextInput(attrs = {'class': 'form-control'})
    )