from django.urls import path

from .views import views
from .views import util_views

app_name = 'deck'

urlpatterns = [
    path('', views.index, name='index'),
    path('v2/', views.indexV2, name='indexV2'),
    path('v2/detail/<int:id>/', views.detailV2, name='detailV2'),
    path('v2/create', views.createV2, name='createV2'),
    path('v2/update/<int:id>', views.updateV2, name='updateV2'),
    path('detail', views.detail, name='detailEmpty'),
    path('detail/<int:id>', views.detail, name='detail'),
    path('create', views.create, name='create'),
    path('createSearch', views.createSearch, name='createSearch'),
    path('update/<int:id>', views.update, name='update'),
    path('update', views.update, name='updateEmpty'),
    
    path('deckImport', util_views.deckImport, name='deckImport'),
    path('delete', views.delete, name='deleteEmpty'),
    path('delete/<int:id>', views.delete, name='delete'),
    
    #path('statistics', util_views.statistics, name='statistics'),'
    path('checkCardName', views.check_cardname, name='checkName'),
    path('detailHoverImg', views.detail_hoverImg, name='detailHoverImg'),
    
    path('like/<int:id>', views.like, name='like'),
    path('bookmark/<int:id>', views.bookmark, name='bookmark'),
]
