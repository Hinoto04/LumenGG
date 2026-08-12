from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import SiteSettings, TermTranslation, TranslationSource, TranslationValue, UserData

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
