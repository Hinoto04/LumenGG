from django.contrib import admin
from .models import QNA, QNARelation
from django.db import models
from martor.widgets import AdminMartorWidget, MartorWidget


class QNARelationInline(admin.TabularInline):
    model = QNARelation
    extra = 0
    autocomplete_fields = ('card',)


class QNAAdmin(admin.ModelAdmin):
    list_display = ['title', 'faq', 'created_at']
    list_filter = ['faq']
    search_fields = ['title', 'question', 'answer']
    inlines = [QNARelationInline]

    def save_model(self, request, obj, form, change):
        # Editing only an inline relation must not refresh QNA.created_at.
        # Source digests intentionally include that timestamp, so an otherwise
        # harmless relation edit would force every still-related card through
        # review again.
        if change and not form.changed_data:
            return
        super().save_model(request, obj, form, change)
    
class QNARelationAdmin(admin.ModelAdmin):
    list_display = ['qna', 'card']
    search_fields = ['qna__title', 'card__name']

# Register your models here.
admin.site.register(QNA, QNAAdmin)
admin.site.register(QNARelation, QNARelationAdmin)
