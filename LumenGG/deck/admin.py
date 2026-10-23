from django.contrib import admin
from .models import Deck, CardInDeck, ReserveCardInDeck, Regulation, RegulationVersion

class DeckAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'character', 'version', 'visibility', 'author')
    list_filter = ('character', 'version', 'visibility')
    search_fields = ('name', 'character__name', 'version', 'keyword', 'author__username')
    ordering = ('-created',)
    exclude = ('private',)

class CardInDeckAdmin(admin.ModelAdmin):
    list_display = ('deck', 'card', 'count')
    search_fields = ('deck__name', 'card__name')

# Register your models here.
admin.site.register(Deck, DeckAdmin)
admin.site.register(CardInDeck, CardInDeckAdmin)
admin.site.register(ReserveCardInDeck)
admin.site.register(Regulation)


@admin.register(RegulationVersion)
class RegulationVersionAdmin(admin.ModelAdmin):
    list_display = ('regulation', 'version', 'published_at')

    def get_readonly_fields(self, request, obj=None):
        return ('regulation', 'version', 'rules', 'effective_date', 'source', 'published_at') if obj else ()

    def has_delete_permission(self, request, obj=None):
        return False
