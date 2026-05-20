from django import forms
from .models import Character, Card, CardTranslation, Tag, CardComment, CharacterComment
from collection.models import Pack
from django.core.validators import FileExtensionValidator
from common.models import SiteSettings
from common.language import (
    DEFAULT_LANGUAGE,
    game_term,
    translated_character_field,
    translated_choice_label,
    ui_text,
)
from django.utils import timezone
from django.db.models import Q


def _localized_choices(choices, language):
    return [
        (value, translated_choice_label(label, language))
        for value, label in choices
    ]


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
    ultimate = forms.BooleanField(
        label = "얼티밋",
        required = False,
        widget = forms.CheckboxInput(attrs = {'class': '검색체크'}),
    )
    pos = forms.MultipleChoiceField(
        label = "판정",
        choices = [('상단', '상단'), ('중단', '중단'), ('하단', '하단')],
        widget = forms.CheckboxSelectMultiple(attrs = {'class': '검색체크'}),
        required = False,
    )
    body = forms.MultipleChoiceField(
        label = "부위",
        choices = [],
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
        choices = [],
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
            ('출시일', '출시일 느린 순'), ('+출시일', '출시일 빠른 순'),
            ('-속도', '속도 내림차순'), ('+속도', '속도 오름차순'), 
            ('-데미지', '데미지 내림차순'), ('+데미지', '데미지 오름차순'),
            ('-히트', '히트 내림차순'), ('+히트', '히트 오름차순'),
            ('-카운터', '카운터 내림차순'), ('+카운터', '카운터 오름차순'),
            ('-가드', '가드 내림차순'), ('+가드', '가드 오름차순'),
            ('-평점', '평점 내림차순'), ('+평점', '평점 오름차순')],
        widget = forms.Select(attrs = {'class': 'btn btn-sm border'}),
    )
    
    def __init__(self, *args, **kwargs):
        language = kwargs.pop('language', DEFAULT_LANGUAGE)
        super().__init__(*args, **kwargs)
        self.fields['char'].label = ui_text('캐릭터', language)
        self.fields['char'].label_from_instance = lambda obj: translated_character_field(obj, language, 'name')
        self.fields['type'].label = ui_text('분류', language)
        self.fields['type'].choices = _localized_choices([
            ('특성', '특성'), ('공격', '공격'), ('수비', '수비'), ('특수', '특수')
        ], language)
        self.fields['ultimate'].label = ui_text('얼티밋', language)
        self.fields['pos'].label = ui_text('판정', language)
        self.fields['pos'].choices = _localized_choices([
            ('상단', '상단'), ('중단', '중단'), ('하단', '하단')
        ], language)
        self.fields['body'].label = ui_text('부위', language)
        self.fields['specialpos'].label = ui_text('특수 판정', language)
        self.fields['specialpos'].choices = _localized_choices([
            ('상단', '상단'), ('중단', '중단'), ('하단', '하단')
        ], language)
        self.fields['specialtype'].label = ui_text('특수 판정', language)
        self.fields['specialtype'].choices = _localized_choices([
            ('회피', '회피'), ('상쇄', '상쇄'), ('그랩', '그랩')
        ], language)
        self.fields['pack'].label = ui_text('출신 팩', language)
        self.fields['framenum'].label = ui_text('속도', language)
        self.fields['framenum'].widget.attrs['placeholder'] = ui_text('속도', language)
        self.fields['frametype'].label = ui_text('속도 분류', language)
        self.fields['frametype'].choices = _localized_choices([
            ('일치', '일치'), ('이상', '이상'), ('이하', '이하')
        ], language)
        self.fields['keyword'].widget.attrs['placeholder'] = ui_text('카드명, 키워드 검색', language)
        self.fields['sort'].label = ui_text('정렬', language)
        self.fields['sort'].choices = [
            ('', ui_text('정렬', language)),
            ('출시일', ui_text('출시일 느린 순', language)), ('+출시일', ui_text('출시일 빠른 순', language)),
            ('-속도', ui_text('속도 내림차순', language)), ('+속도', ui_text('속도 오름차순', language)),
            ('-데미지', ui_text('데미지 내림차순', language)), ('+데미지', ui_text('데미지 오름차순', language)),
            ('-히트', ui_text('히트 내림차순', language)), ('+히트', ui_text('히트 오름차순', language)),
            ('-카운터', ui_text('카운터 내림차순', language)), ('+카운터', ui_text('카운터 오름차순', language)),
            ('-가드', ui_text('가드 내림차순', language)), ('+가드', ui_text('가드 오름차순', language)),
            ('-평점', ui_text('평점 내림차순', language)), ('+평점', ui_text('평점 오름차순', language))
        ]
        try:
            site_setting = SiteSettings.objects.get(name='검색필터 팩')
            self.fields['pack'].choices = _localized_choices(site_setting.setting["data"], language)
            site_setting = SiteSettings.objects.get(name='부위판정종류')
            self.fields['body'].choices = [
                (value, game_term(label, language))
                for value, label in site_setting.setting["data"]
            ]
        except SiteSettings.DoesNotExist:
            self.fields['pack'].choices = []

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

class CardCreateForm(forms.ModelForm):
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
    body = forms.ChoiceField(
        label = "부위",
        choices = [],
        widget = forms.Select(attrs = {'class': '검색체크'}),
        required = False,
    )
    class Meta:
        model = Card
        fields = ['name', 'ruby', 'type', 'ultimate', 'frame', 
                  'damage', 'pos', 'body', 'special', 'code',
                  'hit', 'guard', 'counter', 
                  'g_top', 'g_mid', 'g_bot', 
                  'character', 'text', 'detail_text']
        widgets = {
            "pos": forms.Select(choices = [
                ('', ''), ('상단', '상단'), ('중단', '중단'), ('하단', '하단')]),
            "type": forms.Select(choices = [
                ('공격', '공격'), ('수비', '수비'), ('특수', '특수'), ('특성', '특성'), ('토큰', '토큰')],),
            'g_top': forms.Select(choices = [
                ('', ''), ('방어', '방어'), ('상쇄', '상쇄'), ('회피', '회피')]),
            'g_mid': forms.Select(choices = [
                ('', ''), ('방어', '방어'), ('상쇄', '상쇄'), ('회피', '회피')]),
            'g_bot': forms.Select(choices = [
                ('', ''), ('방어', '방어'), ('상쇄', '상쇄'), ('회피', '회피')]),
        }
        labels = {
            "name": "카드명", "ruby": "루비", "type": "카드 분류", "frame": "속도",
            "damage": "데미지", "pos": "판정", "body": "부위",
            "special": "특수", "code": "최초 수록", "hit": "히트",
            "guard": "가드", "counter": "카운터",
            "character": "캐릭터", "img": "이미지(링크)", "text": "텍스트",
            "detail_text": "보충 설명",
            "g_top": "상단 방어", "g_mid": "중단 방어", "g_bot": "하단 방어",
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            site_setting = SiteSettings.objects.get(name='부위판정종류')
            self.fields['body'].choices = site_setting.setting["data"]
        except SiteSettings.DoesNotExist:
            self.fields['pack'].choices = []


class CardUpdateForm(CardCreateForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('pack', None)
        self.fields.pop('rare', None)


CARD_TRANSLATION_UPDATE_FIELDS = [
    'name',
    'ruby',
    'text',
    'detail_text',
    'keyword',
    'hiddenKeyword',
    'search',
]


class CardTranslationUpdateForm(forms.ModelForm):
    class Meta:
        model = CardTranslation
        fields = CARD_TRANSLATION_UPDATE_FIELDS
        labels = {
            'name': '카드명',
            'ruby': '루비',
            'text': '효과',
            'detail_text': '보충 설명',
            'keyword': '이 카드가 가진 태그',
            'hiddenKeyword': '숨겨진 검색어',
            'search': '이 카드가 찾는 태그',
        }
        widgets = {
            'text': forms.Textarea(attrs={'rows': 6}),
            'detail_text': forms.Textarea(attrs={'rows': 6}),
            'keyword': forms.TextInput(),
            'hiddenKeyword': forms.TextInput(),
            'search': forms.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        self.card = kwargs.pop('card')
        self.language = kwargs.pop('language')
        super().__init__(*args, **kwargs)

        for field_name in CARD_TRANSLATION_UPDATE_FIELDS:
            field = self.fields[field_name]
            field.required = False
            source_value = getattr(self.card, field_name, '')
            if source_value:
                field.widget.attrs.setdefault('placeholder', source_value)

    def save(self, commit=True):
        self.instance.card = self.card
        self.instance.language = self.language
        return super().save(commit=commit)

class CardCommentForm(forms.ModelForm):
    class Meta:
        model = CardComment
        fields = ['score', 'comment']
        
        widgets = {
            "comment": forms.TextInput(attrs={
                "class": "form-control 긴옵션 배경색2",
                "placeholder": "코멘트 작성/수정(200자 까지)"})
        }

selectOptions = [('-1', '미평가')]+[(i, str(i)) for i in range(1, 11)]
class CharacterCommentForm(forms.ModelForm):
    character = forms.ModelChoiceField(
        queryset = Character.objects.filter(Q(pack__released__lt=timezone.now())).order_by('pack__released'),
        required = True
    )
    class Meta:
        model = CharacterComment
        fields = ['character', 'comment', 'power', 'combo', 'reversal', 'safety', 'tempo']
        widgets = {
            'power': forms.Select(choices=selectOptions, attrs={'class': '배경색2'}),
            'combo': forms.Select(choices=selectOptions, attrs={'class': '배경색2'}),
            'reversal': forms.Select(choices=selectOptions, attrs={'class': '배경색2'}),
            'safety': forms.Select(choices=selectOptions, attrs={'class': '배경색2'}),
            'tempo': forms.Select(choices=selectOptions, attrs={'class': '배경색2'}),
            'comment': forms.Textarea(attrs={'class': '배경색2'})
        }
