from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserData, SiteSettings, TermTranslation

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
