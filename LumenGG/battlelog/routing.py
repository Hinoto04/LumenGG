from django.urls import path

from . import consumers


websocket_urlpatterns = [
    path('ws/battlelog/session/<str:view_token>/', consumers.BattleSessionConsumer.as_asgi()),
    path('ws/tournament/<int:tournament_id>/battle-state/', consumers.TournamentBattleStateConsumer.as_asgi()),
]
