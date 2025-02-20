from django.contrib import admin
from .models import QNA, QNARelation

# Register your models here.
admin.site.register(QNA)
admin.site.register(QNARelation)