from django.urls import path

from . import views

app_name = 'tournament'

urlpatterns = [
    path('v2/', views.indexV2, name='indexV2'),
    path('v2/create/', views.createV2, name='createV2'),
    path('v2/deck-search/', views.deckSearchV2, name='deckSearchV2'),
    path('v2/join-code/', views.joinCodeV2, name='joinCodeV2'),
    path('v2/join-code/<str:code>/', views.joinCodeV2, name='joinCodeLinkV2'),
    path('v2/stats/', views.statsV2, name='statsV2'),
    path('v2/tag-stats/', views.tagStatsV2, name='tagStatsV2'),
    path('v2/<int:id>/', views.detailV2, name='detailV2'),
    path('v2/<int:id>/edit/', views.editV2, name='editV2'),
    path('v2/<int:id>/join/', views.joinV2, name='joinV2'),
    path('v2/<int:id>/join-qr.png', views.joinQrV2, name='joinQrV2'),
    path('v2/<int:id>/drop/', views.dropV2, name='dropV2'),
    path('v2/<int:id>/delete/', views.deleteV2, name='deleteV2'),
    path('v2/<int:id>/start-round/', views.startRoundV2, name='startRoundV2'),
    path('v2/<int:id>/round/<int:round_id>/report/', views.reportRoundV2, name='reportRoundV2'),
    path('v2/<int:id>/match/<int:match_id>/report/', views.reportMatchV2, name='reportMatchV2'),
    path('v2/<int:id>/finish/', views.finishV2, name='finishV2'),
]
