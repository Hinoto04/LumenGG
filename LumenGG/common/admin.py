from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserData, SiteSettings

# Register your models here.
class UserDataInline(admin.StackedInline):
    model = UserData
    can_delete = False
    verbose_name_plural = 'data'
    
    autocomplete_fields = ('user', 'character', 'card1', 'card2', 'card3')
class UserAdmin(BaseUserAdmin):
    inlines = [UserDataInline]

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(SiteSettings)