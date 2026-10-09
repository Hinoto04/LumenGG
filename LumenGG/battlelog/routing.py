from django.urls import path

from . import consumers
from mobile_api.consumers import MobileCalculatorConsumer


websocket_urlpatterns = [
    path('ws/mobile/v1/calculators/<str:view_token>/', MobileCalculatorConsumer.as_asgi()),
    path('ws/battlelog/session/<str:view_token>/', consumers.BattleSessionConsumer.as_asgi()),
    path('ws/battlelog/simulator/<str:view_token>/', consumers.LumenSimulatorConsumer.as_asgi()),
    path('ws/tournament/<int:tournament_id>/battle-state/', consumers.TournamentBattleStateConsumer.as_asgi()),
]
