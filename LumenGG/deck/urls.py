from django.urls import path

from .views import views
from .views import util_views

app_name = 'deck'

urlpatterns = [
    path('', views.index, name='index'),
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
    
    path('like/<int:id>', views.like, name='like'),
    path('bookmark/<int:id>', views.bookmark, name='bookmark'),
]