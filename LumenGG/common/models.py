from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

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
