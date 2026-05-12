from django.urls import path

from .views import views
from .views import util_views

app_name = 'collection'

urlpatterns = [
    path('', views.indexV2, name='index'),
    path('v2/', views.indexV2, name='indexV2'),
    path('legacy/', views.index, name='legacyIndex'),
    path('legacy/create/', views.create, name='legacyCreate'),
    path('v2/create/', views.createV2, name='createV2'),
    path('create/', views.createV2, name='create'),
    path('update/', views.updateCollected, name='update_collected'),
    #path('export/', util_views.export_cards, name='export_cards'),
    #path('initinit/', util_views.initinit, name='initinit'),
]
