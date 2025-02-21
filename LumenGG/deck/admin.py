from django.contrib import admin
from .models import Deck, CardInDeck

class DeckAdmin(admin.ModelAdmin):
    list_display = ('name', 'character', 'version', 'author')
    list_filter = ('character', 'version')
    search_fields = ('name', 'character__name', 'version', 'keyword', 'author__username')
    ordering = ('-created',)

class CardInDeckAdmin(admin.ModelAdmin):
    list_display = ('deck', 'card', 'count')
    list_filter = ('deck', 'card')
    search_fields = ('deck__name', 'card__name')

# Register your models here.
admin.site.register(Deck, DeckAdmin)
admin.site.register(CardInDeck, CardInDeckAdmin)