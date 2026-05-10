from django.contrib import admin

from .models import (
    Tournament,
    TournamentDeckSubmission,
    TournamentMatch,
    TournamentParticipant,
    TournamentRound,
)


class TournamentParticipantInline(admin.TabularInline):
    model = TournamentParticipant
    extra = 0
    autocomplete_fields = ['user', 'deck']


class TournamentDeckSubmissionInline(admin.TabularInline):
    model = TournamentDeckSubmission
    extra = 0
    autocomplete_fields = ['deck']


class TournamentRoundInline(admin.TabularInline):
    model = TournamentRound
    extra = 0


class TournamentMatchInline(admin.TabularInline):
    model = TournamentMatch
    extra = 0
    autocomplete_fields = ['player1', 'player2', 'winner']


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'event_date',
        'format',
        'elimination_mode',
        'status',
        'visibility',
        'tags',
        'decklist_required_count',
        'swiss_round_count',
        'top_cut_count',
        'tiebreaker',
        'round_set_count',
        'organizer',
    ]
    list_filter = ['format', 'elimination_mode', 'status', 'visibility', 'tiebreaker']
    search_fields = ['name', 'organizer__username', 'tags']
    autocomplete_fields = ['organizer']
    inlines = [TournamentParticipantInline, TournamentRoundInline]


@admin.register(TournamentRound)
class TournamentRoundAdmin(admin.ModelAdmin):
    list_display = ['tournament', 'number', 'stage', 'status', 'started_at', 'duration_minutes', 'set_count']
    list_filter = ['stage', 'status']
    search_fields = ['tournament__name', 'number']
    autocomplete_fields = ['tournament']
    inlines = [TournamentMatchInline]


@admin.register(TournamentParticipant)
class TournamentParticipantAdmin(admin.ModelAdmin):
    list_display = ['tournament', 'name', 'deck', 'dropped', 'joined_at']
    list_filter = ['dropped']
    search_fields = ['tournament__name', 'user__username', 'display_name', 'deck__name']
    autocomplete_fields = ['tournament', 'user', 'deck']
    inlines = [TournamentDeckSubmissionInline]


@admin.register(TournamentDeckSubmission)
class TournamentDeckSubmissionAdmin(admin.ModelAdmin):
    list_display = ['participant', 'slot', 'deck', 'submitted_at']
    search_fields = ['participant__tournament__name', 'participant__user__username', 'participant__display_name', 'deck__name']
    autocomplete_fields = ['participant', 'deck']


@admin.register(TournamentMatch)
class TournamentMatchAdmin(admin.ModelAdmin):
    list_display = ['round', 'table_no', 'player1', 'player2', 'winner', 'is_draw', 'status']
    list_filter = ['status', 'is_draw']
    autocomplete_fields = ['round', 'player1', 'player2', 'winner']
