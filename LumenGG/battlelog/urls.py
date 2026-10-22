from django.urls import path

from . import views, party_views

app_name = 'battlelog'

urlpatterns = [
    path('party/', party_views.party_home, name='partyHome'),
    path('party/create/', party_views.party_create, name='partyCreate'),
    path('party/board/', party_views.party_board, name='partyBoard'),
    path('party/<str:code>/', party_views.party_room, name='partyRoom'),
    path('party/<str:code>/join/', party_views.party_join, name='partyJoin'),
    path('party/<str:code>/state/', party_views.party_state, name='partyState'),
    path('party/<str:code>/action/', party_views.party_action, name='partyAction'),
    path('party/<str:code>/test-seat/', party_views.party_test_seat, name='partyTestSeat'),
    path('simulator/', views.simulatorStart, name='simulatorStart'),
    path('simulator/guide/', views.simulatorGuide, name='simulatorGuide'),
    path('simulator/deck-search/', views.simulatorDeckSearch, name='simulatorDeckSearch'),
    path('simulator/<str:view_token>/state/', views.simulatorState, name='simulatorState'),
    path('simulator/<str:view_token>/events/', views.simulatorEvents, name='simulatorEvents'),
    path('simulator/<str:view_token>/card-metadata/', views.simulatorCardMetadata, name='simulatorCardMetadata'),
    path('simulator/<str:view_token>/action/', views.simulatorAction, name='simulatorAction'),
    path('simulator/<str:view_token>/command/', views.simulatorCommand, name='simulatorCommand'),
    path('simulator/<str:view_token>/scenario/', views.simulatorScenarioClone, name='simulatorScenarioClone'),
    path('simulator/<str:view_token>/report/', views.simulatorReportIssue, name='simulatorReportIssue'),
    path('simulator/<str:view_token>/mobile/<str:seat>/<str:seat_token>/', views.simulatorMobileSeat, name='simulatorMobileSeat'),
    path('simulator/<str:view_token>/mobile/', views.simulatorMobileView, name='simulatorMobileView'),
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
