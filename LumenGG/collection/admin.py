from django.contrib import admin
from .models import CollectionCard, Collected, Pack, PackTranslation

# Register your models here.
class CollectionCardAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'pack', 'rare', 'character', 'item_type')
    list_filter = ('pack', 'rare', 'item_type', 'character')
    search_fields = ('name', 'code', 'card__name', 'character__name')
    ordering = ('pack__released', 'code')

class CollectedAdmin(admin.ModelAdmin):
    list_display = ('user', 'card', 'amount')
    search_fields = ('user__username', 'card__name')
    ordering = ('user', 'card')

class PackAdmin(admin.ModelAdmin):
    list_display = ('code', 'released')
    search_fields = ('code', 'name', 'translations__name')
    ordering = ('released', )

class PackTranslationAdmin(admin.ModelAdmin):
    list_display = ('pack', 'language', 'name')
    list_filter = ('language',)
    search_fields = ('pack__code', 'pack__name', 'name')

admin.site.register(CollectionCard, CollectionCardAdmin)
admin.site.register(Collected, CollectedAdmin)
admin.site.register(Pack, PackAdmin)
admin.site.register(PackTranslation, PackTranslationAdmin)
