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
    path('deckImport', util_views.deckMake, name='deckMakeUtil'),
    path('delete', views.delete, name='deleteEmpty'),
    path('delete/<int:id>', views.delete, name='delete'),
]