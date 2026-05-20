from django.urls import path

from . import views

app_name = 'battlelog'

urlpatterns = [
    path('simulator/', views.simulatorStart, name='simulatorStart'),
    path('simulator/<str:view_token>/state/', views.simulatorState, name='simulatorState'),
    path('simulator/<str:view_token>/action/', views.simulatorAction, name='simulatorAction'),
    path('simulator/<str:view_token>/<str:seat>/<str:seat_token>/', views.simulatorSeat, name='simulatorSeat'),
    path('simulator/<str:view_token>/', views.simulatorView, name='simulatorView'),
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
