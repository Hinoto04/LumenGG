from django.urls import path

from . import views

app_name = 'battlelog'

urlpatterns = [
    path('sim/', views.sim, name='sim'),
    path('session/<str:view_token>/', views.sessionDetail, name='sessionDetail'),
    path('session/<str:view_token>/control/<str:control_token>/', views.sessionControl, name='sessionControl'),
    path('session/<str:view_token>/state/', views.sessionState, name='sessionState'),
    path('session/<str:view_token>/events/', views.sessionEvents, name='sessionEvents'),
    path('session/<str:view_token>/action/', views.sessionAction, name='sessionAction'),
    path('cardLoad/', views.cardLoad, name='cardLoad'),
    path('deckLoad/', views.deckLoad, name='deckLoad'),
    #path('stream/', views.stream, name='stream'),
]
