"""Authenticated participant views and result submission for the native app."""
from django.db import transaction
from django.db.models import Q, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from tournament.models import Tournament, TournamentParticipant, TournamentMatch, TournamentRound
from tournament.services import set_match_result, complete_round_if_ready
from battlelog.models import BattleSession
from battlelog.services import get_or_create_tournament_session, battle_session_queryset
from battlelog.realtime import broadcast_battle_session
from .calculators import mobile_state


def my_matches(user):
    return TournamentMatch.objects.filter(Q(player1__user=user) | Q(player2__user=user)).select_related(
        'round__tournament', 'player1__user', 'player2__user', 'player1__deck__character', 'player2__deck__character',
    ).prefetch_related('player1__deck_submissions__deck__character', 'player2__deck_submissions__deck__character')


def match_payload(match, user):
    tournament = match.round.tournament
    active = tournament.status == 'running' and match.round.status == 'running' and match.status == 'pending' and not match.is_bye
    return {
        'id': match.id, 'tournament_id': tournament.id, 'round_id': match.round_id,
        'round_number': match.round.number, 'stage': match.round.stage, 'table': match.table_label,
        'round_status': match.round.status, 'round_ends_at': match.round.ends_at.isoformat(),
        'set_count': match.round.set_count, 'status': match.status, 'is_bye': match.is_bye,
        'me': 'p1' if match.player1.user_id == user.id else 'p2',
        'players': {'p1': {'id': match.player1_id, 'name': match.player1.name},
                    'p2': {'id': match.player2_id, 'name': match.player2.name} if match.player2_id else None},
        'score': {'p1': match.player1_score, 'p2': match.player2_score},
        'winner': 'draw' if match.is_draw else 'p1' if match.winner_id == match.player1_id else 'p2' if match.winner_id else '',
        'reported_at': match.reported_at.isoformat() if match.reported_at else None,
        'can_report': active, 'can_open_calculator': not match.is_bye,
    }


@api_view(['GET'])
def index(request):
    entries = TournamentParticipant.objects.filter(user=request.user).select_related('tournament').order_by('-tournament__event_date', '-id')
    return Response({'tournaments': [{
        'id': p.tournament_id, 'name': p.tournament.name, 'status': p.tournament.status,
        'format': p.tournament.format, 'event_date': p.tournament.event_date.isoformat(),
        'venue': p.tournament.venue, 'participant_name': p.name, 'dropped': p.dropped,
    } for p in entries]})


@api_view(['GET'])
def detail(request, tournament_id):
    participant = get_object_or_404(TournamentParticipant.objects.select_related('tournament'), tournament_id=tournament_id, user=request.user)
    tournament = participant.tournament
    submissions = participant.deck_submissions.select_related('deck__character').order_by('slot')
    return Response({
        'id': tournament.id, 'name': tournament.name, 'description': tournament.description,
        'status': tournament.status, 'format': tournament.format, 'venue': tournament.venue,
        'event_date': tournament.event_date.isoformat(), 'participant_name': participant.name, 'dropped': participant.dropped,
        'decks': [{'id': s.deck_id, 'submission_id': s.pk, 'slot': s.slot, 'name': s.snapshot.get('name', s.deck.name), 'validation': s.validation} for s in submissions],
        'matches': [match_payload(m, request.user) for m in my_matches(request.user).filter(round__tournament=tournament).order_by('-round__number', 'table_no')],
    })


@api_view(['POST'])
def calculator(request, tournament_id, match_id):
    match = get_object_or_404(my_matches(request.user), pk=match_id, round__tournament_id=tournament_id)
    if match.is_bye:
        raise ValidationError('BYE 매치는 계산기를 사용할 수 없습니다.')
    with transaction.atomic():
        # Round lock prevents concurrent session creation/result submission.
        TournamentRound.objects.select_for_update().get(pk=match.round_id)
        session = get_or_create_tournament_session(match, request.user)
    session = battle_session_queryset().get(pk=session.pk)
    return Response({'view_token': session.view_token, 'state': mobile_state(session, language=request.query_params.get('language', 'ko'), user=request.user)})


@api_view(['POST'])
def report(request, tournament_id, match_id):
    match = get_object_or_404(my_matches(request.user), pk=match_id, round__tournament_id=tournament_id)
    body = request.data
    if not isinstance(body, dict):
        raise ValidationError('결과 입력을 확인해주세요.')
    scores = [body.get('player1_score'), body.get('player2_score')]
    if any(isinstance(s, bool) or not isinstance(s, int) or not 0 <= s <= 32767 for s in scores):
        raise ValidationError('점수는 0 이상의 정수로 입력해주세요.')
    with transaction.atomic():
        # All calculator writes lock the session first. Serialize direct reports
        # with set confirmation without exporting a calculator control token.
        session = BattleSession.objects.select_for_update().filter(tournament_match=match).first()
        round_obj = TournamentRound.objects.select_for_update().get(pk=match.round_id)
        match = my_matches(request.user).select_for_update().get(pk=match.pk)
        winner = body.get('winner')
        winner_value = str(match.player1_id) if winner == 'p1' else str(match.player2_id) if winner == 'p2' and not match.is_bye else 'draw' if winner == 'draw' else ''
        if match.is_bye:
            raise ValidationError('결과를 제출할 수 없는 경기입니다.')
        if match.status == 'reported':
            if match.player1_score == scores[0] and match.player2_score == scores[1] and match_payload(match, request.user)['winner'] == winner:
                return Response({'match': match_payload(match, request.user), 'already_reported': True})
            return Response({'detail': '이미 결과가 제출되었습니다. 최신 경기 결과를 확인해주세요.'}, status=409)
        if match.round.tournament.status != 'running':
            raise ValidationError('결과를 제출할 수 없는 경기입니다.')
        if round_obj.status != 'running':
            raise ValidationError('이미 종료된 라운드는 결과를 수정할 수 없습니다.')
        try:
            set_match_result(match, winner_value, *scores)
        except ValueError as exc:
            raise ValidationError(str(exc))
        match.status = 'reported'
        match.reported_at = timezone.now()
        match.save(update_fields=['winner', 'is_draw', 'player1_score', 'player2_score', 'status', 'reported_at'])
        complete_round_if_ready(round_obj)
        if session:
            BattleSession.objects.filter(pk=session.pk).update(version=F('version') + 1)
            transaction.on_commit(lambda: broadcast_battle_session(battle_session_queryset().get(pk=session.pk)))
    return Response({'match': match_payload(match, request.user), 'already_reported': False})
