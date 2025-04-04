from django.contrib import admin
from .models import CollectionCard, Collected, Pack

# Register your models here.
class CollectionCardAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'pack', 'rare')
    list_filter = ('pack', 'rare')
    search_fields = ('name', 'code')
    ordering = ('pack__released', 'code')

class CollectedAdmin(admin.ModelAdmin):
    list_display = ('user', 'card', 'amount')
    search_fields = ('user__username', 'card__name')
    ordering = ('user', 'card')

class PackAdmin(admin.ModelAdmin):
    list_display = ('code', 'released')
    search_fields = ('code', )
    ordering = ('released', )

admin.site.register(CollectionCard, CollectionCardAdmin)
admin.site.register(Collected, CollectedAdmin)
admin.site.register(Pack, PackAdmin)