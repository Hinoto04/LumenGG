from django.contrib import admin
from .models import QNA, QNARelation

class QNAAdmin(admin.ModelAdmin):
    list_display = ['title', 'faq', 'created_at']
    list_filter = ['faq']
    search_fields = ['title', 'question', 'answer']
    
class QNARelationAdmin(admin.ModelAdmin):
    list_display = ['qna', 'card']
    search_fields = ['qna__title', 'card__name']

# Register your models here.
admin.site.register(QNA, QNAAdmin)
admin.site.register(QNARelation, QNARelationAdmin)