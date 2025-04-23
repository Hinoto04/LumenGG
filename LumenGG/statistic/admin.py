from django.contrib import admin
from .models import Championship, CSDeck

# Register your models here.
class CSAdmin(admin.ModelAdmin):
    list_display = ('name', 'datetime')
    search_fields = ('name',)
    ordering = ('-datetime',)

class CSDeckAdmin(admin.ModelAdmin):
    list_display = ('cs', 'deck')
    search_fields = ('cs__name', 'deck__name')
    autocomplete_fields = ('deck', 'user_model')

admin.site.register(Championship, CSAdmin)
admin.site.register(CSDeck, CSDeckAdmin)