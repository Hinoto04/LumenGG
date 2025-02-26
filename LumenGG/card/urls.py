from django.urls import path

from .views import views
from .views import util_views

app_name = 'card'

urlpatterns = [
    path('', views.index, name='index'),
    path('detail/', views.detail, name='detailNone'),
    path('detail/<int:id>/', views.detail, name='detail'),
    #path('import/', util_views.importCards, name='import'),
    #path('dbkeywordset/', util_views.keywordSet, name='keywordSet'),
    #path('bujeonseung', util_views.bujeonseung, name='bujeonseung'),
    
    path('tag/', views.tagList, name='tagList'),
    path('tag/<int:id>/', views.tagDetail, name='tagDetail'),
    path('tag/create/', views.tagCreate, name='tagCreate'),
    path('tag/update/<int:id>/', views.tagUpdate, name='tagUpdate'),
    path('tagUpdate/<int:id>', views.editCardTag, name='editCardTag'),
]