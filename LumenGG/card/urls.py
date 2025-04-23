from django.urls import path

from .views import views
from .views import character_views
from .views import util_views

app_name = 'card'

urlpatterns = [
    path('', views.index, name='index'),
    path('detail/', views.detail, name='detailNone'),
    path('detail/<int:id>/', views.detail, name='detail'),
    path('detail/<str:name>/', views.detailName, name='detailName'),
    path('create/', views.create, name='create'),
    
    path('comment/<int:id>/', views.comment, name='comment'),
    path('commentList/', views.commentList, name='commentList'),
    
    path('character/', character_views.index, name='character'),
    path('character/<int:id>', character_views.detail, name='charDetail'),
    
    #path('import/', util_views.importCards, name='import'),
    #path('dbkeywordset/', util_views.keywordSet, name='keywordSet'),
    #path('bujeonseung', util_views.bujeonseung, name='bujeonseung'),
    #path('noSpaceAdd/', util_views.noSpaceAdd, name='noSpaceAdd'),
    #path('smallImg/', util_views.smallImgInit, name='smallImgInit'),
    
    path('tag/', views.tagList, name='tagList'),
    path('tag/<int:id>/', views.tagDetail, name='tagDetail'),
    path('tag/create/', views.tagCreate, name='tagCreate'),
    path('tag/update/<int:id>/', views.tagUpdate, name='tagUpdate'),
    path('tagUpdate/<int:id>', views.editCardTag, name='editCardTag'),
]