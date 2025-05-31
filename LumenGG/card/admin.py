from django.contrib import admin
from .models import Character, Card, CardComment, CharacterComment

class CharacterAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'group')
    list_filter = ('group',)
    search_fields = ('name',)
class CardAdmin(admin.ModelAdmin):
    list_display = ('name', 'character', 'type')
    list_filter = ('character', 'type')
    search_fields = ('name', 'character', 'pos', 'body', 'special', 'frame', 'code')

class CharCommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'character', 'power', 'combo', 'reversal', 'safety', 'tempo')
    list_filter = ('character',)
    search_fields = ('author',)

class CardCommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'card', 'score')
    search_fields = ('card', 'author')

# Register your models here.
admin.site.register(Character, CharacterAdmin)
admin.site.register(Card, CardAdmin)
admin.site.register(CardComment, CardCommentAdmin)
admin.site.register(CharacterComment, CharCommentAdmin)
