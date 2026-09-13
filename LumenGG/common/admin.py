from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db import models
from django_summernote.widgets import SummernoteWidget

from .models import (
    Rule,
    Rulebook,
    RulebookTranslation,
    RuleTranslation,
    RuleVisualGuide,
    RuleVisualGuideTranslation,
    SiteSettings,
    TermTranslation,
    TranslationSource,
    TranslationValue,
    UserData,
)

# Register your models here.
class UserDataInline(admin.StackedInline):
    model = UserData
    can_delete = False
    verbose_name_plural = 'data'
    fields = ('language', 'character', 'card1', 'card2', 'card3')
    
    autocomplete_fields = ('user', 'character', 'card1', 'card2', 'card3')
class UserAdmin(BaseUserAdmin):
    inlines = [UserDataInline]

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(SiteSettings)

class TermTranslationAdmin(admin.ModelAdmin):
    list_display = ('source', 'language', 'text', 'category')
    list_filter = ('language', 'category')
    search_fields = ('source', 'text', 'note')
    ordering = ('category', 'source', 'language')

admin.site.register(TermTranslation, TermTranslationAdmin)


class TranslationValueInline(admin.TabularInline):
    model = TranslationValue
    extra = 0


class TranslationSourceAdmin(admin.ModelAdmin):
    list_display = ('key', 'category', 'field_name', 'source_text', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('key', 'source_text', 'note', 'values__text')
    readonly_fields = ('content_type', 'object_id')
    inlines = [TranslationValueInline]
    ordering = ('category', 'key')


class TranslationValueAdmin(admin.ModelAdmin):
    list_display = ('source', 'language', 'status', 'updated_at')
    list_filter = ('language', 'status', 'source__category')
    search_fields = ('source__key', 'source__source_text', 'text')
    autocomplete_fields = ('source',)


admin.site.register(TranslationSource, TranslationSourceAdmin)
admin.site.register(TranslationValue, TranslationValueAdmin)


class RulebookTranslationInline(admin.StackedInline):
    model = RulebookTranslation
    extra = 0


@admin.register(Rulebook)
class RulebookAdmin(admin.ModelAdmin):
    list_display = ('slug', 'kicker', 'sort_order', 'searchable', 'is_public', 'updated_on')
    list_editable = ('sort_order', 'is_public')
    search_fields = ('slug', 'translations__title', 'translations__summary')
    inlines = (RulebookTranslationInline,)


class RuleTranslationInline(admin.StackedInline):
    model = RuleTranslation
    extra = 0
    formfield_overrides = {
        models.TextField: {'widget': SummernoteWidget},
    }


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = (
        'reference_name',
        'display_number',
        'rulebook',
        'parent',
        'priority',
        'show_in_toc',
        'is_public',
        'updated_at',
    )
    list_filter = ('rulebook', 'show_in_toc', 'is_public')
    list_editable = ('priority', 'show_in_toc', 'is_public')
    search_fields = (
        'reference_name',
        'reference_targets',
        'translations__title',
        'translations__content',
    )
    autocomplete_fields = ('rulebook', 'parent')
    readonly_fields = ('reference_aliases',)
    inlines = (RuleTranslationInline,)

    @admin.display(description='규칙 번호')
    def display_number(self, obj):
        return obj.full_number


class RuleVisualGuideTranslationInline(admin.StackedInline):
    model = RuleVisualGuideTranslation
    extra = 0
    formfield_overrides = {
        models.TextField: {'widget': SummernoteWidget},
    }


@admin.register(RuleVisualGuide)
class RuleVisualGuideAdmin(admin.ModelAdmin):
    list_display = ('display_title', 'rulebook', 'rule', 'style_key', 'priority', 'is_public', 'updated_at')
    list_editable = ('priority', 'is_public')
    list_filter = ('is_public', 'rulebook', 'style_key')
    search_fields = ('translations__title', 'translations__content', 'rule__reference_name')
    autocomplete_fields = ('rulebook', 'rule')
    inlines = (RuleVisualGuideTranslationInline,)

    @admin.display(description='비주얼 가이드')
    def display_title(self, obj):
        translation = obj.translations.filter(language='ko').first()
        return translation.title if translation else f'비주얼 가이드 {obj.pk}'
