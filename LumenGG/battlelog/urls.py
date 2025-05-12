from django.urls import path

from . import views

app_name = 'battlelog'

urlpatterns = [
    path('sim/', views.sim, name='sim'),
    path('cardLoad/', views.cardLoad, name='cardLoad'),
    path('deckLoad/', views.deckLoad, name='deckLoad'),
    #path('stream/', views.stream, name='stream'),
]