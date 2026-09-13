from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db.models import Q

from card.models import Character, Card

# Create your models here.
def getUsername(self):
    return self.username

User.add_to_class("__str__", getUsername)

class UserData(models.Model):
    LANGUAGE_KOREAN = 'ko'
    LANGUAGE_ENGLISH = 'en'
    LANGUAGE_JAPANESE = 'ja'
    LANGUAGE_CHOICES = [
        (LANGUAGE_KOREAN, '한국어'),
        (LANGUAGE_ENGLISH, 'English'),
        (LANGUAGE_JAPANESE, '日本語'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='data')
    character = models.ForeignKey(Character, on_delete=models.SET_NULL, null=True, related_name="mosted")
    card1 = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True, related_name="most1ed")
    card2 = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True, related_name="most2ed")
    card3 = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True, related_name="most3ed")
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default=LANGUAGE_KOREAN)
    
    def __str__(self):
        return self.user.username

class SiteSettings(models.Model):
    name = models.CharField(max_length=30)
    setting = models.JSONField()
    
    def __str__(self):
        return self.name

class TermTranslation(models.Model):
    LANGUAGE_ENGLISH = 'en'
    LANGUAGE_JAPANESE = 'ja'
    LANGUAGE_CHOICES = [
        (LANGUAGE_ENGLISH, 'English'),
        (LANGUAGE_JAPANESE, '日本語'),
    ]
    CATEGORY_GENERAL = 'general'
    CATEGORY_CARD_TYPE = 'card_type'
    CATEGORY_POSITION = 'position'
    CATEGORY_BODY = 'body'
    CATEGORY_SPECIAL = 'special'
    CATEGORY_RESULT = 'result'
    CATEGORY_TAG = 'tag'
    CATEGORY_UI = 'ui'
    CATEGORY_CHOICES = [
        (CATEGORY_GENERAL, '공통'),
        (CATEGORY_CARD_TYPE, '카드 분류'),
        (CATEGORY_POSITION, '위치 판정'),
        (CATEGORY_BODY, '부위 판정'),
        (CATEGORY_SPECIAL, '특수 판정'),
        (CATEGORY_RESULT, '판정 결과'),
        (CATEGORY_TAG, '태그'),
        (CATEGORY_UI, 'UI'),
    ]

    source = models.CharField(max_length=80)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    text = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_GENERAL)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['source', 'language'], name='unique_term_translation_language'),
        ]
        ordering = ['category', 'source', 'language']
        verbose_name = '공통 용어 번역'
        verbose_name_plural = '공통 용어 번역'

    def __str__(self):
        return f'{self.source} / {self.language} -> {self.text}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from common.language import clear_term_translation_cache
        clear_term_translation_cache()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        from common.language import clear_term_translation_cache
        clear_term_translation_cache()
        return result


class TranslationSource(models.Model):
    CATEGORY_CARD = 'card'
    CATEGORY_CHARACTER = 'character'
    CATEGORY_GENERAL = 'general'
    CATEGORY_CARD_TYPE = 'card_type'
    CATEGORY_POSITION = 'position'
    CATEGORY_BODY = 'body'
    CATEGORY_SPECIAL = 'special'
    CATEGORY_RESULT = 'result'
    CATEGORY_TAG = 'tag'
    CATEGORY_UI = 'ui'
    CATEGORY_PACK = 'pack'
    CATEGORY_KEYWORD = 'keyword'
    CATEGORY_STATE = 'state'
    CATEGORY_TOKEN = 'token'
    CATEGORY_CHOICES = [
        (CATEGORY_CARD, 'Card'),
        (CATEGORY_CHARACTER, 'Character'),
        (CATEGORY_GENERAL, 'General'),
        (CATEGORY_CARD_TYPE, 'Card type'),
        (CATEGORY_POSITION, 'Position'),
        (CATEGORY_BODY, 'Body'),
        (CATEGORY_SPECIAL, 'Special'),
        (CATEGORY_RESULT, 'Result'),
        (CATEGORY_TAG, 'Tag'),
        (CATEGORY_UI, 'UI'),
        (CATEGORY_PACK, 'Pack'),
        (CATEGORY_KEYWORD, 'Keyword'),
        (CATEGORY_STATE, 'State'),
        (CATEGORY_TOKEN, 'Token / counter'),
    ]

    key = models.CharField(max_length=160, unique=True)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default=CATEGORY_GENERAL)
    source_text = models.TextField(blank=True)
    source_data = models.JSONField(default=dict, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    field_name = models.CharField(max_length=60, blank=True)
    note = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category', 'key']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return self.key

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from common.localization import clear_localization_cache
        clear_localization_cache()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        from common.localization import clear_localization_cache
        clear_localization_cache()
        return result


class TranslationValue(models.Model):
    STATUS_TRANSLATED = 'translated'
    STATUS_MISSING = 'missing'
    STATUS_NEEDS_REVIEW = 'needs_review'
    STATUS_CHOICES = [
        (STATUS_TRANSLATED, 'Translated'),
        (STATUS_MISSING, 'Missing'),
        (STATUS_NEEDS_REVIEW, 'Needs review'),
    ]
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('ja', '日本語'),
    ]

    source = models.ForeignKey(TranslationSource, on_delete=models.CASCADE, related_name='values')
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    text = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRANSLATED)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['source', 'language'], name='unique_translation_value_language'),
        ]
        ordering = ['source__key', 'language']

    def __str__(self):
        return f'{self.source.key} / {self.language}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from common.localization import clear_localization_cache
        clear_localization_cache()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        from common.localization import clear_localization_cache
        clear_localization_cache()
        return result


class Rulebook(models.Model):
    slug = models.SlugField(max_length=40, unique=True)
    url_name = models.CharField(max_length=80, blank=True)
    kicker = models.CharField(max_length=80, blank=True)
    version = models.CharField(max_length=80, blank=True)
    updated_on = models.DateField(null=True, blank=True)
    visual_file = models.CharField(max_length=160, blank=True)
    visual_css = models.TextField(
        blank=True,
        help_text='룰북 상단 비주얼 가이드들이 공통으로 사용하는 CSS입니다.',
    )
    visual_javascript = models.TextField(
        blank=True,
        help_text='룰북 상단 비주얼 가이드들이 공통으로 사용하는 JavaScript입니다.',
    )
    searchable = models.BooleanField(default=False)
    anchor_prefix = models.CharField(max_length=40, default='rule-')
    sort_order = models.PositiveIntegerField(default=0)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order', 'id']
        verbose_name = '룰북'
        verbose_name_plural = '룰북'

    def __str__(self):
        translation = self.translations.filter(language='ko').first()
        return translation.title if translation and translation.title else self.slug


class RulebookTranslation(models.Model):
    LANGUAGE_KOREAN = 'ko'
    LANGUAGE_ENGLISH = 'en'
    LANGUAGE_JAPANESE = 'ja'
    LANGUAGE_CHOICES = [
        (LANGUAGE_KOREAN, '한국어'),
        (LANGUAGE_ENGLISH, 'English'),
        (LANGUAGE_JAPANESE, '日本語'),
    ]

    rulebook = models.ForeignKey(Rulebook, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    title = models.CharField(max_length=200)
    short_title = models.CharField(max_length=100, blank=True)
    summary = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['rulebook', 'language'],
                name='unique_rulebook_translation_language',
            ),
        ]
        ordering = ['rulebook__sort_order', 'language']
        verbose_name = '룰북 번역'
        verbose_name_plural = '룰북 번역'

    def __str__(self):
        return f'{self.rulebook.slug} / {self.language}'


class Rule(models.Model):
    rulebook = models.ForeignKey(Rulebook, on_delete=models.CASCADE, related_name='rules')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    reference_name = models.SlugField(
        max_length=120,
        unique=True,
        allow_unicode=True,
        help_text='다른 규칙에서 [[참조명]]으로 연결할 고유 이름입니다.',
    )
    reference_aliases = models.JSONField(
        default=list,
        blank=True,
        help_text='참조명 변경 전 딥링크를 유지하기 위한 이전 참조명입니다.',
    )
    reference_targets = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            '이 규칙이 정의·절차·예외를 가져와 사용하는 다른 규칙의 참조명 목록입니다. '
            '예: ["rule-processing-unit", "rule-priority"]'
        ),
    )
    priority = models.PositiveIntegerField(
        default=0,
        help_text='같은 상위 규칙 아래에서 숫자가 낮을수록 먼저 표시됩니다.',
    )
    show_in_toc = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['rulebook__sort_order', 'priority', 'id']
        indexes = [
            models.Index(
                fields=['rulebook', 'parent', 'priority'],
                name='common_rule_parent_prio_idx',
            ),
            models.Index(fields=['rulebook', 'is_public']),
        ]
        verbose_name = '규칙'
        verbose_name_plural = '규칙'

    def __str__(self):
        translation = self.translations.filter(language='ko').first()
        title = translation.title if translation and translation.title else self.reference_name
        number = self.full_number
        return f'{number} {title}'.strip()

    @property
    def depth(self):
        depth = 0
        current = self.parent
        seen = {self.pk} if self.pk else set()
        while current is not None and current.pk not in seen:
            seen.add(current.pk)
            depth += 1
            current = current.parent
        return depth

    @property
    def full_number(self):
        segments = []
        current = self
        seen = set()
        while current is not None and current.pk not in seen:
            if not current.pk:
                break
            seen.add(current.pk)
            preceding_siblings = Rule.objects.filter(
                rulebook_id=current.rulebook_id,
                parent_id=current.parent_id,
            ).filter(
                Q(priority__lt=current.priority)
                | Q(priority=current.priority, pk__lt=current.pk)
            )
            segments.append(str(preceding_siblings.count() + 1))
            current = current.parent
        return '.'.join(reversed(segments))

    def clean(self):
        super().clean()
        self.reference_name = (self.reference_name or '').strip()

        if not isinstance(self.reference_targets, list):
            raise ValidationError({'reference_targets': '참조 규칙은 JSON 문자열 배열이어야 합니다.'})
        normalized_targets = []
        for reference in self.reference_targets:
            if not isinstance(reference, str) or not reference.strip():
                raise ValidationError({'reference_targets': '각 참조 규칙은 비어 있지 않은 문자열이어야 합니다.'})
            reference = reference.strip()
            if reference == self.reference_name or reference in (self.reference_aliases or []):
                raise ValidationError({'reference_targets': '규칙 자신을 참조 규칙으로 지정할 수 없습니다.'})
            if reference not in normalized_targets:
                normalized_targets.append(reference)
        self.reference_targets = normalized_targets

        if self.parent_id:
            if self.pk and self.parent_id == self.pk:
                raise ValidationError({'parent': '규칙 자신을 상위 규칙으로 지정할 수 없습니다.'})
            if self.parent.rulebook_id != self.rulebook_id:
                raise ValidationError({'parent': '같은 룰북의 규칙만 상위 규칙으로 지정할 수 있습니다.'})

            current = self.parent
            seen = {self.pk} if self.pk else set()
            while current is not None:
                if current.pk in seen:
                    raise ValidationError({'parent': '자신의 하위 규칙을 상위 규칙으로 지정할 수 없습니다.'})
                seen.add(current.pk)
                current = current.parent

class RuleTranslation(models.Model):
    LANGUAGE_CHOICES = RulebookTranslation.LANGUAGE_CHOICES

    rule = models.ForeignKey(Rule, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    title = models.CharField(max_length=240)
    content = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['rule', 'language'],
                name='unique_rule_translation_language',
            ),
        ]
        ordering = ['rule__priority', 'language']
        verbose_name = '규칙 번역'
        verbose_name_plural = '규칙 번역'

    def __str__(self):
        return f'{self.rule.reference_name} / {self.language}'


class RuleVisualGuide(models.Model):
    rulebook = models.ForeignKey(
        Rulebook,
        on_delete=models.CASCADE,
        related_name='visual_guides',
    )
    rule = models.ForeignKey(
        Rule,
        on_delete=models.CASCADE,
        related_name='visual_guides',
        null=True,
        blank=True,
    )
    style_key = models.SlugField(
        max_length=40,
        blank=True,
        help_text='비주얼 가이드에 적용할 CSS 식별자입니다. 예: field, cards, phases',
    )
    priority = models.PositiveIntegerField(
        default=0,
        help_text='숫자가 낮을수록 비주얼 가이드 전환 버튼의 앞쪽에 표시됩니다.',
    )
    css = models.TextField(blank=True)
    javascript = models.TextField(blank=True)
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', 'id']
        indexes = [
            models.Index(
                fields=['rulebook', 'rule', 'is_public', 'priority'],
                name='common_visual_owner_public_idx',
            ),
        ]
        verbose_name = '규칙 비주얼 가이드'
        verbose_name_plural = '규칙 비주얼 가이드'

    def __str__(self):
        translation = self.translations.filter(language='ko').first()
        title = translation.title if translation and translation.title else f'비주얼 가이드 {self.pk}'
        owner = self.rule if self.rule_id else self.rulebook
        return f'{owner} / {title}'

    def clean(self):
        super().clean()
        if self.rule_id and self.rule.rulebook_id != self.rulebook_id:
            raise ValidationError({'rule': '같은 룰북의 규칙만 지정할 수 있습니다.'})

    def save(self, *args, **kwargs):
        if self.rule_id:
            self.rulebook_id = self.rule.rulebook_id
        super().save(*args, **kwargs)


class RuleVisualGuideTranslation(models.Model):
    LANGUAGE_CHOICES = RulebookTranslation.LANGUAGE_CHOICES

    guide = models.ForeignKey(RuleVisualGuide, on_delete=models.CASCADE, related_name='translations')
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES)
    title = models.CharField(max_length=160)
    content = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['guide', 'language'],
                name='unique_rule_visual_translation_language',
            ),
        ]
        ordering = ['guide__priority', 'language']
        verbose_name = '규칙 비주얼 가이드 번역'
        verbose_name_plural = '규칙 비주얼 가이드 번역'

    def __str__(self):
        return f'{self.guide_id} / {self.language}'
