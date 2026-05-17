from django.urls import path

from .views import views
from .views import character_views
from .views import util_views

app_name = 'card'

urlpatterns = [
    path('', views.indexV2, name='index'),
    path('v2/', views.indexV2, name='indexV2'),
    path('legacy/', views.index, name='legacyIndex'),
    path('legacy/detail/', views.detail, name='legacyDetailNone'),
    path('legacy/detail/<int:id>/', views.detail, name='legacyDetail'),
    path('legacy/detail/<str:name>/', views.detailNameLegacy, name='legacyDetailName'),
    path('legacy/create/', views.create, name='legacyCreate'),
    path('legacy/update/<int:id>/', views.update, name='legacyUpdate'),
    path('v2/detail/<int:id>/', views.detailV2, name='detailV2'),
    path('v2/create/', views.createV2, name='createV2'),
    path('v2/update/<int:id>/', views.updateV2, name='updateV2'),
    path('detail-text-import/', views.detailTextImport, name='detailTextImport'),
    path('detail/', views.detailV2, name='detailNone'),
    path('detail/<int:id>/', views.detailV2, name='detail'),
    path('detail/<str:name>/', views.detailName, name='detailName'),
    path('create/', views.createV2, name='create'),
    path('update/<int:id>/', views.updateV2, name='update'),
    
    path('comment/<int:id>/', views.comment, name='comment'),
    path('commentList/', views.commentList, name='commentList'),
    
    path('character/', character_views.indexV2, name='character'),
    path('v2/character/', character_views.indexV2, name='characterV2'),
    path('legacy/character/', character_views.index, name='legacyCharacter'),
    path('character/<int:id>', character_views.detail, name='charDetail'),
    path('writeCharComment/', character_views.writeComment, name='writeCharComment'),
    
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
