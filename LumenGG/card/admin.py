from django.contrib import admin
from .models import Character, Card

class CharacterAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'group')
    list_filter = ('group',)
    search_fields = ('name',)
class CardAdmin(admin.ModelAdmin):
    list_display = ('name', 'character', 'type')
    list_filter = ('character', 'type')
    search_fields = ('name', 'character__name', 'pos', 'body', 'special', 'frame', 'code')

# Register your models here.
admin.site.register(Character, CharacterAdmin)
admin.site.register(Card, CardAdmin)
