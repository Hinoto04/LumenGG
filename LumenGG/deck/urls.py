from django.urls import path

from .views import views
from .views import util_views

app_name = 'deck'

urlpatterns = [
    path('', views.indexV2, name='index'),
    path('v2/', views.indexV2, name='indexV2'),
    path('legacy/', views.index, name='legacyIndex'),
    path('legacy/detail', views.detail, name='legacyDetailEmpty'),
    path('legacy/detail/<int:id>', views.detail, name='legacyDetail'),
    path('legacy/capture/<int:id>', views.capture, name='legacyCapture'),
    path('legacy/copy/<int:id>', views.copyLegacy, name='legacyCopy'),
    path('legacy/create', views.createLegacy, name='legacyCreate'),
    path('legacy/update/<int:id>', views.updateLegacy, name='legacyUpdate'),
    path('legacy/update', views.updateLegacy, name='legacyUpdateEmpty'),
    path('v2/detail/<int:id>/', views.detailV2, name='detailV2'),
    path('v2/capture/<int:id>/', views.captureV2, name='captureV2'),
    path('v2/copy/<int:id>/', views.copyV2, name='copyV2'),
    path('v2/create', views.createV2, name='createV2'),
    path('v2/update/<int:id>', views.updateV2, name='updateV2'),
    path('detail', views.detailV2, name='detailEmpty'),
    path('detail/<int:id>', views.detailV2, name='detail'),
    path('capture/<int:id>', views.captureV2, name='capture'),
    path('copy/<int:id>', views.copyV2, name='copy'),
    path('create', views.createV2, name='create'),
    path('createSearch', views.createSearch, name='createSearch'),
    path('update/<int:id>', views.updateV2, name='update'),
    path('update', views.updateV2, name='updateEmpty'),
    
    path('deckImport', util_views.deckImport, name='deckImport'),
    path('delete', views.delete, name='deleteEmpty'),
    path('delete/<int:id>', views.delete, name='delete'),
    
    #path('statistics', util_views.statistics, name='statistics'),'
    path('checkCardName', views.check_cardname, name='checkName'),
    path('detailHoverImg', views.detail_hoverImg, name='detailHoverImg'),
    
    path('like/<int:id>', views.like, name='like'),
    path('bookmark/<int:id>', views.bookmark, name='bookmark'),
]
