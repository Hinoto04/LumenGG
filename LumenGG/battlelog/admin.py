from django.contrib import admin

from .models import BattleEvent, BattleSession, BattleSet


@admin.register(BattleSession)
class BattleSessionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'session_type',
        'player1_name',
        'player2_name',
        'tournament_match',
        'expires_at',
        'updated_at',
    ]
    list_filter = ['session_type', 'sudden_death']
    search_fields = ['player1_name', 'player2_name', 'view_token', 'control_token']
    readonly_fields = ['view_token', 'control_token', 'created_at', 'updated_at']


@admin.register(BattleEvent)
class BattleEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'event_type', 'target', 'amount', 'actor_label', 'created_at', 'undone']
    list_filter = ['event_type', 'target', 'undone']
    search_fields = ['session__player1_name', 'session__player2_name', 'actor_label', 'event_uid']
    readonly_fields = ['event_uid', 'created_at']


@admin.register(BattleSet)
class BattleSetAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'set_number', 'status', 'winner_side', 'ended_at']
    list_filter = ['status', 'winner_side']
    search_fields = ['session__player1_name', 'session__player2_name']
    readonly_fields = ['started_at', 'ended_at']
