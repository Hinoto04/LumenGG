from django.urls import path

from .views import views
from .views import util_views

app_name = 'collection'

urlpatterns = [
    path('', views.index, name='index'),
    path('update/', views.updateCollected, name='update_collected'),
    #path('export/', util_views.export_cards, name='export_cards'),
    #path('initinit/', util_views.initinit, name='initinit'),
]