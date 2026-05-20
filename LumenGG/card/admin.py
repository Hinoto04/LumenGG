from django.contrib import admin
from .models import Character, CharacterTranslation, Card, CardTranslation, CardComment, CharacterComment

class CharacterTranslationInline(admin.StackedInline):
    model = CharacterTranslation
    extra = 0

class CharacterAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'group')
    list_filter = ('group',)
    search_fields = ('name',)
    inlines = [CharacterTranslationInline]

class CardTranslationInline(admin.StackedInline):
    model = CardTranslation
    extra = 0

class CardAdmin(admin.ModelAdmin):
    list_display = ('name', 'character', 'type')
    list_filter = ('character', 'type')
    search_fields = ('name', 'pos', 'special', 'frame', 'code', 'detail_text', 'translations__name', 'translations__text')
    inlines = [CardTranslationInline]

class CharCommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'character', 'power', 'combo', 'reversal', 'safety', 'tempo')
    list_filter = ('character',)
    search_fields = ('author__username',)

class CardCommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'card', 'score')
    search_fields = ('card__name', 'author__username')

# Register your models here.
admin.site.register(Character, CharacterAdmin)
admin.site.register(Card, CardAdmin)
admin.site.register(CharacterTranslation)
admin.site.register(CardTranslation)
admin.site.register(CardComment, CardCommentAdmin)
admin.site.register(CharacterComment, CharCommentAdmin)
