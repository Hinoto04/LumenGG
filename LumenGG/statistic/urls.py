from django.urls import path

from . import views

app_name = 'stat'

urlpatterns = [
    path('', views.index, name='index'),
    path('detail/<int:id>', views.detail, name='detail'),
    path('detailData/<int:id>', views.detailData, name='detailData'),
    
    path('lcdcs', views.lcdcs, name='lcdcs'),
    path('lcdcsdata', views.lcdcsdata, name='lcdcsdata'),
]