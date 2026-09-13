from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django_summernote.widgets import SummernoteWidget

from .models import (
    Rule,
    Rulebook,
    RuleTranslation,
    RuleVisualGuide,
    RuleVisualGuideTranslation,
    UserData,
)

class LoginForm(forms.Form):
    username = forms.CharField(label="아이디", max_length=150)
    password = forms.CharField(label="비밀번호", widget=forms.PasswordInput)
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.add_error('username', '존재하지 않는 아이디입니다.')
            return cleaned_data
        else:
            if not user.check_password(password):
                self.add_error('password', '비밀번호가 틀렸습니다.')
        
        return cleaned_data

class UserForm(UserCreationForm):
    email = forms.EmailField(label="이메일")
    
    class Meta:
        model = User
        fields = ("username", "password1", "password2", "email")

class UserDataForm(forms.ModelForm):
    class Meta:
        model = UserData
        fields = ("character", )


class RuleParentChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        translation = next(
            (item for item in obj.translations.all() if item.language == 'ko'),
            None,
        )
        title = translation.title if translation else obj.reference_name
        number = obj.full_number
        return f'{number} {title}'.strip()


class RuleForm(forms.ModelForm):
    parent = RuleParentChoiceField(
        queryset=Rule.objects.none(),
        required=False,
        label='상위 규칙',
        empty_label='최상위 규칙',
    )

    class Meta:
        model = Rule
        fields = (
            'rulebook',
            'parent',
            'reference_name',
            'reference_targets',
            'priority',
            'show_in_toc',
            'is_public',
        )
        labels = {
            'rulebook': '룰북',
            'reference_name': '참조명',
            'reference_targets': '참조 규칙',
            'priority': '우선순위',
            'show_in_toc': '목차에 표시',
            'is_public': '공개',
        }
        widgets = {
            'reference_name': forms.TextInput(attrs={'placeholder': '예: damage-resolution'}),
            'reference_targets': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '["rule-processing-unit", "rule-priority"]',
            }),
            'priority': forms.NumberInput(attrs={'min': 0, 'step': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rulebook_id = self.data.get('rulebook') or self.initial.get('rulebook')
        if hasattr(rulebook_id, 'pk'):
            rulebook_id = rulebook_id.pk
        if not rulebook_id and self.instance and self.instance.pk:
            rulebook_id = self.instance.rulebook_id

        parent_queryset = Rule.objects.none()
        if rulebook_id:
            parent_queryset = (
                Rule.objects
                .filter(rulebook_id=rulebook_id)
                .prefetch_related('translations')
                .select_related('parent')
                .order_by('priority', 'id')
            )
            if self.instance and self.instance.pk:
                excluded_ids = {self.instance.pk}
                pending_ids = [self.instance.pk]
                while pending_ids:
                    child_ids = list(
                        Rule.objects
                        .filter(parent_id__in=pending_ids)
                        .values_list('id', flat=True)
                    )
                    child_ids = [item for item in child_ids if item not in excluded_ids]
                    excluded_ids.update(child_ids)
                    pending_ids = child_ids
                parent_queryset = parent_queryset.exclude(pk__in=excluded_ids)
        self.fields['parent'].queryset = parent_queryset

    def clean_reference_targets(self):
        references = self.cleaned_data.get('reference_targets') or []
        if not isinstance(references, list):
            raise forms.ValidationError('참조 규칙은 JSON 문자열 배열이어야 합니다.')

        rules = Rule.objects.values_list(
            'pk', 'reference_name', 'reference_aliases'
        )
        aliases = {
            key: (rule_id, reference_name)
            for rule_id, reference_name, old_references in rules
            for key in [reference_name, *(old_references or [])]
            if key
        }
        normalized = []
        missing = []
        for reference in references:
            if not isinstance(reference, str) or not reference.strip():
                raise forms.ValidationError('각 참조 규칙은 비어 있지 않은 문자열이어야 합니다.')
            reference = reference.strip()
            target = aliases.get(reference)
            if target is None:
                missing.append(reference)
                continue
            target_id, canonical = target
            if self.instance.pk and target_id == self.instance.pk:
                raise forms.ValidationError('규칙 자신을 참조 규칙으로 지정할 수 없습니다.')
            if canonical not in normalized:
                normalized.append(canonical)
        if missing:
            raise forms.ValidationError(
                f'존재하지 않는 참조 키: {", ".join(missing)}'
            )
        return normalized

    def clean(self):
        cleaned_data = super().clean()
        rulebook = cleaned_data.get('rulebook')
        if (
            self.instance
            and self.instance.pk
            and rulebook
            and rulebook.pk != self.instance.rulebook_id
            and self.instance.children.exists()
        ):
            self.add_error('rulebook', '하위 규칙이 있는 규칙은 다른 룰북으로 직접 이동할 수 없습니다.')
        return cleaned_data


class RuleTranslationForm(forms.ModelForm):
    class Meta:
        model = RuleTranslation
        fields = ('title', 'content')
        labels = {
            'title': '규칙 제목',
            'content': '규칙 본문',
        }
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': '규칙 제목'}),
            'content': SummernoteWidget(attrs={
                'summernote': {
                    'width': '100%',
                    'height': '360px',
                },
            }),
        }

    def __init__(self, *args, language='ko', **kwargs):
        self.language = language
        super().__init__(*args, **kwargs)
        self.fields['title'].required = language == 'ko'

    def save_for_rule(self, rule):
        instance = self.save(commit=False)
        instance.rule = rule
        instance.language = self.language
        if not instance.title and not instance.content and self.language != 'ko':
            if instance.pk:
                instance.delete()
            return None
        instance.save()
        return instance


class RuleVisualGuideForm(forms.ModelForm):
    class Meta:
        model = RuleVisualGuide
        fields = ('priority', 'style_key', 'is_public', 'css', 'javascript')
        labels = {
            'priority': '우선순위',
            'style_key': '스타일 식별자',
            'is_public': '공개',
            'css': '이 가이드의 추가 CSS',
            'javascript': '이 가이드의 추가 JavaScript',
        }
        widgets = {
            'priority': forms.NumberInput(attrs={'min': 0, 'step': 1}),
            'style_key': forms.TextInput(attrs={'placeholder': '예: field, cards, phases'}),
            'css': forms.Textarea(attrs={
                'class': 'v2-rule-code-editor',
                'rows': 10,
                'spellcheck': 'false',
                'placeholder': '.my-visual { ... }',
            }),
            'javascript': forms.Textarea(attrs={
                'class': 'v2-rule-code-editor',
                'rows': 14,
                'spellcheck': 'false',
                'placeholder': 'document.querySelector(...);',
            }),
        }


class RuleVisualGuideTranslationForm(forms.ModelForm):
    class Meta:
        model = RuleVisualGuideTranslation
        fields = ('title', 'content')
        labels = {
            'title': '전환 버튼 이름',
            'content': '비주얼 가이드 HTML',
        }
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': '예: 플레이어 보드'}),
            'content': SummernoteWidget(attrs={
                'summernote': {
                    'width': '100%',
                    'height': '420px',
                },
            }),
        }

    def __init__(self, *args, language='ko', **kwargs):
        self.language = language
        super().__init__(*args, **kwargs)
        self.fields['title'].required = language == 'ko'

    def save_for_guide(self, guide):
        instance = self.save(commit=False)
        instance.guide = guide
        instance.language = self.language
        if not instance.title and not instance.content and self.language != 'ko':
            if instance.pk:
                instance.delete()
            return None
        instance.save()
        return instance


class RulebookVisualAssetsForm(forms.ModelForm):
    class Meta:
        model = Rulebook
        fields = ('visual_css', 'visual_javascript')
        labels = {
            'visual_css': '공통 CSS',
            'visual_javascript': '공통 JavaScript',
        }
        widgets = {
            'visual_css': forms.Textarea(attrs={
                'class': 'v2-rule-code-editor',
                'rows': 24,
                'spellcheck': 'false',
            }),
            'visual_javascript': forms.Textarea(attrs={
                'class': 'v2-rule-code-editor',
                'rows': 24,
                'spellcheck': 'false',
            }),
        }
