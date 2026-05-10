from collections import Counter
from io import BytesIO
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from deck.models import Deck

from .forms import RoundStartForm, TournamentForm, TournamentJoinForm
from .models import (
    Tournament,
    TournamentDeckSubmission,
    TournamentMatch,
    TournamentParticipant,
    TournamentRound,
)
from .services import (
    build_standings,
    complete_round_if_ready,
    copy_deck_for_tournament_submission,
    create_round,
    get_elimination_winner,
    lock_submitted_decks,
    tag_submitted_decks,
)


def _is_operator(user, tournament):
    return user.is_authenticated and (user == tournament.organizer or user.is_staff)


def _visible_tournament_q(user):
    if user.is_staff:
        return Q()

    visible_q = Q(visibility=Tournament.VISIBILITY_PUBLIC)
    if user.is_authenticated:
        visible_q.add(Q(organizer=user), Q.OR)
        visible_q.add(Q(participants__user=user), Q.OR)
    return visible_q


def _apply_visible_tournament_filter(queryset, user):
    if user.is_staff:
        return queryset
    return queryset.filter(_visible_tournament_q(user)).distinct()


def _normalize_join_code(value):
    return ''.join(str(value or '').split()).upper()


def _normalize_tournament_tag(value):
    return str(value or '').strip().lstrip('#')


def _tournament_has_tag(tournament, tag):
    target = _normalize_tournament_tag(tag).casefold()
    return any(existing_tag.casefold() == target for existing_tag in tournament.tag_list)


def _tournament_tag_summaries(queryset):
    counts = Counter()
    for tournament in queryset.exclude(tags=''):
        for tag in tournament.tag_list:
            counts[tag] += 1
    return [
        {'name': tag, 'count': count}
        for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _join_code_url(request, tournament):
    if not tournament.join_code:
        return ''
    return request.build_absolute_uri(
        reverse('tournament:joinCodeLinkV2', kwargs={'code': tournament.join_code})
    )


def _delete_requires_superuser(tournament):
    return (
        tournament.status == Tournament.STATUS_FINISHED
        or tournament.rounds.count() >= 2
    )


def _can_delete_tournament(user, tournament):
    if not _is_operator(user, tournament):
        return False
    if _delete_requires_superuser(tournament):
        return user.is_superuser
    return True


def _can_report_match(user, tournament, match):
    if not user.is_authenticated or match.is_bye:
        return False
    if _is_operator(user, tournament):
        return True
    if match.status == TournamentMatch.STATUS_REPORTED:
        return False
    return match.player1.user_id == user.id or (match.player2 and match.player2.user_id == user.id)


def _submission_queryset():
    return TournamentDeckSubmission.objects.select_related('deck', 'deck__character').order_by('slot')


def _can_view_submitted_deck(user, tournament, deck):
    if deck.visibility in (deck.VISIBILITY_PUBLIC, deck.VISIBILITY_UNLISTED):
        return True
    if not user.is_authenticated:
        return False
    return user.is_staff or tournament.organizer_id == user.id or deck.author_id == user.id


def _visible_submission_q(user, tournament):
    if _is_operator(user, tournament):
        return Q()
    visible_q = Q(deck__visibility__in=[Deck.VISIBILITY_PUBLIC, Deck.VISIBILITY_UNLISTED])
    if user.is_authenticated:
        visible_q.add(Q(deck__author=user), Q.OR)
    return visible_q


def _attach_standing_submissions(tournament, standings, user):
    submissions_by_participant = {}
    submissions = _submission_queryset().filter(participant__tournament=tournament)
    for submission in submissions:
        submission.can_view = _can_view_submitted_deck(user, tournament, submission.deck)
        submissions_by_participant.setdefault(submission.participant_id, []).append(submission)

    for row in standings:
        participant_id = row['participant'].id
        row['deck_submissions'] = submissions_by_participant.get(participant_id, [])
        row['submitted_deck_count'] = len(row['deck_submissions'])


def _round_character_stats(tournament, user):
    result = []
    rounds = tournament.rounds.prefetch_related('matches').order_by('number')
    for round_obj in rounds:
        participant_ids = set()
        for match in round_obj.matches.all():
            participant_ids.add(match.player1_id)
            if match.player2_id:
                participant_ids.add(match.player2_id)
        stats = (
            TournamentDeckSubmission.objects.filter(participant_id__in=participant_ids)
            .filter(_visible_submission_q(user, tournament))
            .values('deck__character__name')
            .annotate(count=Count('id'), player_count=Count('participant', distinct=True))
            .order_by('-count', 'deck__character__name')
        )
        result.append({'round': round_obj, 'stats': list(stats)})
    return result


def _join_deck_slots(form, tournament):
    slots = []
    if not tournament.decklist_required_count:
        return slots

    for slot in range(1, tournament.decklist_required_count + 1):
        field_name = f'deck_{slot}'
        slots.append({
            'slot': slot,
            'field': form[field_name],
            'deck': form.selected_decks_by_slot.get(slot),
        })
    return slots


def _set_match_result(match, winner_value, player1_score, player2_score):
    if player1_score < 0 or player2_score < 0:
        raise ValueError('점수는 0 이상으로 입력해주세요.')
    if player1_score + player2_score > match.round.set_count:
        raise ValueError(f'세트 점수 합계는 {match.round.set_count}세트를 넘을 수 없습니다.')

    match.player1_score = player1_score
    match.player2_score = player2_score
    match.is_draw = winner_value == 'draw'

    if match.is_draw:
        if match.round.stage == TournamentRound.STAGE_ELIMINATION:
            raise ValueError('토너먼트 라운드는 무승부를 입력할 수 없습니다.')
        if player1_score != player2_score:
            raise ValueError('무승부는 양쪽 세트 점수가 같아야 합니다.')
        match.winner = None
    elif winner_value == str(match.player1_id):
        if player1_score <= player2_score:
            raise ValueError('승자의 세트 점수가 더 높아야 합니다.')
        match.winner = match.player1
    elif winner_value == str(match.player2_id):
        if player2_score <= player1_score:
            raise ValueError('승자의 세트 점수가 더 높아야 합니다.')
        match.winner = match.player2
    else:
        raise ValueError('승자를 선택해주세요.')


def _read_match_result(post_data, match, prefix=''):
    try:
        player1_score = int(post_data.get(f'{prefix}player1_score') or 0)
        player2_score = int(post_data.get(f'{prefix}player2_score') or 0)
    except ValueError as exc:
        raise ValueError('점수는 숫자로 입력해주세요.') from exc

    _set_match_result(match, post_data.get(f'{prefix}winner', ''), player1_score, player2_score)


def indexV2(req):
    page = req.GET.get('page', '1')
    status = req.GET.get('status', '')
    tournaments = Tournament.objects.select_related('organizer').annotate(
        participant_count=Count('participants', distinct=True),
        round_count=Count('rounds', distinct=True),
    )
    tournaments = _apply_visible_tournament_filter(tournaments, req.user)
    if status:
        tournaments = tournaments.filter(status=status)
    tournaments = tournaments.order_by('-event_date', '-created_at')
    paginator = Paginator(tournaments, 18)
    context = {
        'tournaments': paginator.get_page(page),
        'status': status,
        'status_choices': Tournament.STATUS_CHOICES,
    }
    return render(req, 'tournament/list_v2.html', context)


@login_required(login_url='common:loginV2', redirect_field_name='next')
def createV2(req):
    if req.method == 'POST':
        form = TournamentForm(req.POST)
        if form.is_valid():
            tournament = form.save(commit=False)
            tournament.organizer = req.user
            tournament.save()
            messages.success(req, '대회를 생성했습니다.')
            return redirect('tournament:detailV2', id=tournament.id)
    else:
        form = TournamentForm(initial={'event_date': timezone.now().strftime('%Y-%m-%dT%H:%M')})
    return render(req, 'tournament/create_v2.html', {'form': form})


@login_required(login_url='common:loginV2', redirect_field_name='next')
def editV2(req, id):
    tournament = get_object_or_404(Tournament.objects.select_related('organizer'), id=id)
    if not _is_operator(req.user, tournament):
        raise PermissionDenied()

    if req.method == 'POST':
        form = TournamentForm(req.POST, instance=tournament)
        if form.is_valid():
            form.save()
            messages.success(req, '대회 설정을 저장했습니다.')
            return redirect('tournament:detailV2', id=tournament.id)
    else:
        form = TournamentForm(instance=tournament)
    return render(req, 'tournament/edit_v2.html', {'form': form, 'tournament': tournament})


def joinCodeV2(req, code=''):
    if req.method == 'POST':
        code = req.POST.get('join_code', '')
    code = _normalize_join_code(code)

    if not code:
        messages.error(req, '참가 코드를 입력해주세요.')
        return redirect('tournament:indexV2')

    tournament = (
        Tournament.objects.filter(
            visibility=Tournament.VISIBILITY_UNLISTED,
            join_code__iexact=code,
        )
        .order_by('-event_date', '-created_at')
        .first()
    )
    if not tournament:
        messages.error(req, '해당 참가 코드의 대회를 찾을 수 없습니다.')
        return redirect('tournament:indexV2')

    detail_url = reverse('tournament:detailV2', kwargs={'id': tournament.id})
    return redirect(f'{detail_url}?{urlencode({"join_code": code})}')


@login_required(login_url='common:loginV2', redirect_field_name='next')
def joinQrV2(req, id):
    tournament = get_object_or_404(Tournament.objects.select_related('organizer'), id=id)
    if not _is_operator(req.user, tournament):
        raise PermissionDenied()
    if tournament.visibility != Tournament.VISIBILITY_UNLISTED or not tournament.join_code:
        raise Http404()

    try:
        import qrcode
    except ImportError as exc:
        raise Http404('QR 코드 생성 라이브러리가 설치되어 있지 않습니다.') from exc

    image_buffer = BytesIO()
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(_join_code_url(req, tournament))
    qr.make(fit=True)
    image = qr.make_image(fill_color='#111111', back_color='#f4f1ea').convert('RGB')
    image.save(image_buffer, format='PNG')
    image_buffer.seek(0)

    response = HttpResponse(image_buffer.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="tournament-{tournament.id}-join-qr.png"'
    return response


def detailV2(req, id):
    tournament = get_object_or_404(Tournament.objects.select_related('organizer'), id=id)
    is_operator = _is_operator(req.user, tournament)
    participant = None
    if req.user.is_authenticated:
        participant = (
            TournamentParticipant.objects.filter(tournament=tournament, user=req.user)
            .prefetch_related(Prefetch('deck_submissions', queryset=_submission_queryset()))
            .first()
        )

    standings = build_standings(tournament)
    _attach_standing_submissions(tournament, standings, req.user)
    rounds = list(tournament.rounds.prefetch_related(
        'matches',
        'matches__player1',
        'matches__player1__user',
        'matches__player2',
        'matches__player2__user',
        'matches__winner',
    ).order_by('-number'))
    for round_obj in rounds:
        round_obj.can_report = False
        for match in round_obj.matches.all():
            match.can_report = (
                round_obj.status == TournamentRound.STATUS_RUNNING
                and _can_report_match(req.user, tournament, match)
            )
            round_obj.can_report = round_obj.can_report or match.can_report
    current_round = next((round_obj for round_obj in rounds if round_obj.status == TournamentRound.STATUS_RUNNING), None)
    elimination_winner = get_elimination_winner(tournament)
    elimination_started = any(round_obj.stage == TournamentRound.STAGE_ELIMINATION for round_obj in rounds)
    show_top_cut_line = (
        tournament.format == Tournament.FORMAT_HYBRID
        and tournament.top_cut_count > 0
        and not elimination_started
    )
    for rank, row in enumerate(standings, start=1):
        row['rank'] = rank
        row['in_top_cut'] = show_top_cut_line and rank <= tournament.top_cut_count
        row['is_cut_line'] = show_top_cut_line and rank == tournament.top_cut_count
    active_participant = participant and not participant.dropped
    join_form_disabled = (
        tournament.status != Tournament.STATUS_REGISTRATION
        or (not tournament.can_join and not active_participant)
    )
    join_initial = {'join_code': _normalize_join_code(req.GET.get('join_code', ''))}
    join_form = TournamentJoinForm(
        user=req.user,
        tournament=tournament,
        instance=participant,
        initial=join_initial,
    )
    round_form = RoundStartForm(tournament=tournament)

    character_stats = []
    round_character_stats = []
    show_decklists = tournament.require_decklist and (tournament.status == Tournament.STATUS_FINISHED or is_operator)
    show_deck_stats = tournament.status == Tournament.STATUS_FINISHED and tournament.require_decklist
    if show_deck_stats:
        character_stats = list(
            TournamentDeckSubmission.objects.filter(participant__tournament=tournament)
            .filter(_visible_submission_q(req.user, tournament))
            .values('deck__character__name')
            .annotate(count=Count('id'), player_count=Count('participant', distinct=True))
            .order_by('-count', 'deck__character__name')
        )
        round_character_stats = _round_character_stats(tournament, req.user)

    context = {
        'tournament': tournament,
        'participant': participant,
        'join_form_disabled': join_form_disabled,
        'join_form': join_form,
        'join_deck_slots': _join_deck_slots(join_form, tournament),
        'round_form': round_form,
        'standings': standings,
        'rounds': rounds,
        'current_round': current_round,
        'elimination_winner': elimination_winner,
        'is_operator': is_operator,
        'join_code_url': _join_code_url(req, tournament),
        'can_delete_tournament': _can_delete_tournament(req.user, tournament),
        'delete_requires_superuser': _delete_requires_superuser(tournament),
        'show_decklists': show_decklists,
        'show_deck_stats': show_deck_stats,
        'show_top_cut_line': show_top_cut_line,
        'character_stats': character_stats,
        'round_character_stats': round_character_stats,
        'now': timezone.now(),
    }
    return render(req, 'tournament/detail_v2.html', context)


@login_required(login_url='common:loginV2', redirect_field_name='next')
def deckSearchV2(req):
    query = req.GET.get('q', '').strip()
    query_is_id = query.isdigit()
    if len(query) < 2 and not query_is_id:
        return JsonResponse([], safe=False)

    visible_q = Q(author=req.user) | Q(visibility=Deck.VISIBILITY_PUBLIC)
    if query_is_id:
        visible_q.add(Q(id=int(query), visibility=Deck.VISIBILITY_UNLISTED), Q.OR)

    search_q = Q(name__icontains=query) | Q(author__username__icontains=query)
    if query_is_id:
        search_q.add(Q(id=int(query)), Q.OR)

    decks = (
        Deck.objects.filter(deleted=False)
        .filter(visible_q)
        .filter(search_q)
        .select_related('author', 'character')
        .order_by('-created')[:20]
    )
    data = [
        {
            'id': deck.id,
            'name': deck.name,
            'author': deck.author.username,
            'character': deck.character.name,
            'version': deck.version,
            'visibility': deck.get_visibility_display(),
            'is_owner': deck.author_id == req.user.id,
        }
        for deck in decks
    ]
    return JsonResponse(data, safe=False)


def tagStatsV2(req):
    tag = _normalize_tournament_tag(req.GET.get('tag', ''))
    if not tag:
        messages.error(req, '통계를 확인할 대회 태그를 선택해주세요.')
        return redirect('tournament:indexV2')

    visible_tournaments = _apply_visible_tournament_filter(
        Tournament.objects.select_related('organizer').order_by('-event_date', '-created_at'),
        req.user,
    )
    tagged_tournaments = [
        tournament
        for tournament in visible_tournaments
        if _tournament_has_tag(tournament, tag)
    ]
    tournament_ids = [tournament.id for tournament in tagged_tournaments]
    finished_tournament_ids = [
        tournament.id
        for tournament in tagged_tournaments
        if tournament.status == Tournament.STATUS_FINISHED
    ]

    status_counts = Counter(tournament.status for tournament in tagged_tournaments)
    status_stats = [
        {'label': label, 'count': status_counts.get(value, 0)}
        for value, label in Tournament.STATUS_CHOICES
    ]

    format_counts = Counter(tournament.format for tournament in tagged_tournaments)
    format_stats = [
        {'label': label, 'count': format_counts.get(value, 0)}
        for value, label in Tournament.FORMAT_CHOICES
    ]

    round_stage_labels = dict(TournamentRound.STAGE_CHOICES)
    round_stage_stats = [
        {
            'label': round_stage_labels.get(row['stage'], row['stage']),
            'count': row['count'],
        }
        for row in TournamentRound.objects.filter(tournament_id__in=tournament_ids)
        .values('stage')
        .annotate(count=Count('id'))
        .order_by('stage')
    ]

    character_stats = (
        TournamentDeckSubmission.objects.filter(participant__tournament_id__in=finished_tournament_ids)
        .values('deck__character__name')
        .annotate(
            deck_count=Count('id'),
            player_count=Count('participant', distinct=True),
            tournament_count=Count('participant__tournament', distinct=True),
        )
        .order_by('-deck_count', 'deck__character__name')
    )

    context = {
        'tag': tag,
        'tournaments': tagged_tournaments,
        'status_stats': status_stats,
        'format_stats': format_stats,
        'round_stage_stats': round_stage_stats,
        'character_stats': character_stats,
        'summary': {
            'tournament_count': len(tagged_tournaments),
            'participant_count': TournamentParticipant.objects.filter(
                tournament_id__in=tournament_ids,
                dropped=False,
            ).count(),
            'round_count': TournamentRound.objects.filter(tournament_id__in=tournament_ids).count(),
            'reported_match_count': TournamentMatch.objects.filter(
                round__tournament_id__in=tournament_ids,
                status=TournamentMatch.STATUS_REPORTED,
            ).count(),
            'submitted_deck_count': TournamentDeckSubmission.objects.filter(
                participant__tournament_id__in=finished_tournament_ids,
            ).count(),
            'finished_tournament_count': len(finished_tournament_ids),
        },
        'tag_summaries': _tournament_tag_summaries(
            _apply_visible_tournament_filter(Tournament.objects.all(), req.user)
        )[:18],
    }
    return render(req, 'tournament/tag_stats_v2.html', context)


def statsV2(req):
    visible_tournaments = _apply_visible_tournament_filter(
        Tournament.objects.select_related('organizer').order_by('-event_date', '-created_at'),
        req.user,
    )
    visible_tournament_ids = list(visible_tournaments.values_list('id', flat=True))
    finished_tournament_ids = list(
        visible_tournaments.filter(status=Tournament.STATUS_FINISHED).values_list('id', flat=True)
    )

    status_counts = Counter(visible_tournaments.values_list('status', flat=True))
    status_stats = [
        {'label': label, 'count': status_counts.get(value, 0)}
        for value, label in Tournament.STATUS_CHOICES
    ]

    format_counts = Counter(visible_tournaments.values_list('format', flat=True))
    format_stats = [
        {'label': label, 'count': format_counts.get(value, 0)}
        for value, label in Tournament.FORMAT_CHOICES
    ]

    tag_summaries = _tournament_tag_summaries(visible_tournaments)
    popular_tags = tag_summaries[:24]

    character_stats = (
        TournamentDeckSubmission.objects.filter(participant__tournament_id__in=finished_tournament_ids)
        .values('deck__character__name')
        .annotate(
            deck_count=Count('id'),
            player_count=Count('participant', distinct=True),
            tournament_count=Count('participant__tournament', distinct=True),
        )
        .order_by('-deck_count', 'deck__character__name')[:24]
    )

    context = {
        'summary': {
            'tournament_count': len(visible_tournament_ids),
            'finished_tournament_count': len(finished_tournament_ids),
            'participant_count': TournamentParticipant.objects.filter(
                tournament_id__in=visible_tournament_ids,
                dropped=False,
            ).count(),
            'round_count': TournamentRound.objects.filter(tournament_id__in=visible_tournament_ids).count(),
            'reported_match_count': TournamentMatch.objects.filter(
                round__tournament_id__in=visible_tournament_ids,
                status=TournamentMatch.STATUS_REPORTED,
            ).count(),
            'submitted_deck_count': TournamentDeckSubmission.objects.filter(
                participant__tournament_id__in=finished_tournament_ids,
            ).count(),
        },
        'status_stats': status_stats,
        'format_stats': format_stats,
        'popular_tags': popular_tags,
        'character_stats': character_stats,
    }
    return render(req, 'tournament/stats_v2.html', context)


@login_required(login_url='common:loginV2', redirect_field_name='next')
def joinV2(req, id):
    tournament = get_object_or_404(Tournament, id=id)
    participant = TournamentParticipant.objects.filter(tournament=tournament, user=req.user).first()
    active_participant = participant and not participant.dropped
    if tournament.status != Tournament.STATUS_REGISTRATION:
        messages.error(req, '참가 접수 중인 대회만 참가 정보를 수정할 수 있습니다.')
        return redirect('tournament:detailV2', id=tournament.id)
    if not tournament.can_join and not active_participant:
        messages.error(req, '현재 참가할 수 없는 대회입니다.')
        return redirect('tournament:detailV2', id=tournament.id)

    if req.method != 'POST':
        return redirect('tournament:detailV2', id=tournament.id)

    form = TournamentJoinForm(req.POST, user=req.user, tournament=tournament, instance=participant)
    if form.is_valid():
        submitted_decks = form.submitted_decks()
        with transaction.atomic():
            copied_deck_count = 0
            prepared_decks = []
            for deck in submitted_decks:
                if deck.author_id == req.user.id:
                    prepared_decks.append(deck)
                    continue
                copied_deck = copy_deck_for_tournament_submission(deck, req.user, tournament)
                prepared_decks.append(copied_deck)
                copied_deck_count += 1
            entry = form.save(commit=False)
            entry.tournament = tournament
            entry.user = req.user
            entry.deck = prepared_decks[0] if prepared_decks else None
            entry.dropped = False
            entry.save()
            TournamentDeckSubmission.objects.filter(participant=entry).delete()
            TournamentDeckSubmission.objects.bulk_create([
                TournamentDeckSubmission(participant=entry, deck=deck, slot=index)
                for index, deck in enumerate(prepared_decks, start=1)
            ])
        if copied_deck_count:
            messages.success(req, f'타인의 덱 {copied_deck_count}개를 참가용 덱으로 복사한 뒤 참가 정보를 저장했습니다.')
        else:
            messages.success(req, '참가 정보를 저장했습니다.')
    else:
        messages.error(req, '참가 정보를 확인해주세요.')
    return redirect('tournament:detailV2', id=tournament.id)


@login_required(login_url='common:loginV2', redirect_field_name='next')
def dropV2(req, id):
    tournament = get_object_or_404(Tournament, id=id)
    participant = get_object_or_404(TournamentParticipant, tournament=tournament, user=req.user)
    if req.method == 'POST':
        if tournament.status != Tournament.STATUS_REGISTRATION:
            messages.error(req, '대회 시작 후에는 참가를 취소할 수 없습니다.')
            return redirect('tournament:detailV2', id=tournament.id)
        participant.dropped = True
        participant.save(update_fields=['dropped'])
        messages.success(req, '대회 참가를 취소했습니다.')
    return redirect('tournament:detailV2', id=tournament.id)


@login_required(login_url='common:loginV2', redirect_field_name='next')
def startRoundV2(req, id):
    tournament = get_object_or_404(Tournament, id=id)
    if not _is_operator(req.user, tournament):
        raise PermissionDenied()
    if req.method != 'POST':
        return redirect('tournament:detailV2', id=tournament.id)

    form = RoundStartForm(req.POST, tournament=tournament)
    if form.is_valid():
        try:
            create_round(
                tournament=tournament,
                stage=form.cleaned_data['stage'],
                duration_minutes=form.cleaned_data['duration_minutes'],
                set_count=form.cleaned_data['set_count'],
                win_points=form.cleaned_data['win_points'],
                draw_points=form.cleaned_data['draw_points'],
                loss_points=form.cleaned_data['loss_points'],
            )
            messages.success(req, '라운드를 시작했습니다.')
        except ValueError as exc:
            messages.error(req, str(exc))
    else:
        messages.error(req, '라운드 시작 설정을 확인해주세요.')
    return redirect('tournament:detailV2', id=tournament.id)


@login_required(login_url='common:loginV2', redirect_field_name='next')
def reportMatchV2(req, id, match_id):
    tournament = get_object_or_404(Tournament, id=id)
    match = get_object_or_404(
        TournamentMatch.objects.select_related('round', 'player1', 'player1__user', 'player2', 'player2__user'),
        id=match_id,
        round__tournament=tournament,
    )
    if not _can_report_match(req.user, tournament, match):
        raise PermissionDenied()
    if match.round.status != TournamentRound.STATUS_RUNNING:
        messages.error(req, '이미 종료된 라운드는 결과를 수정할 수 없습니다.')
        return redirect('tournament:detailV2', id=tournament.id)
    if req.method != 'POST' or match.is_bye:
        return redirect('tournament:detailV2', id=tournament.id)

    try:
        _read_match_result(req.POST, match)
    except ValueError as exc:
        messages.error(req, str(exc))
        return redirect('tournament:detailV2', id=tournament.id)

    match.status = TournamentMatch.STATUS_REPORTED
    match.reported_at = timezone.now()
    match.save(update_fields=['player1_score', 'player2_score', 'is_draw', 'winner', 'status', 'reported_at'])
    complete_round_if_ready(match.round)
    messages.success(req, '매치 결과를 저장했습니다.')
    return redirect('tournament:detailV2', id=tournament.id)


@login_required(login_url='common:loginV2', redirect_field_name='next')
def reportRoundV2(req, id, round_id):
    tournament = get_object_or_404(Tournament, id=id)
    round_obj = get_object_or_404(TournamentRound, id=round_id, tournament=tournament)
    if round_obj.status != TournamentRound.STATUS_RUNNING:
        messages.error(req, '이미 종료된 라운드는 결과를 수정할 수 없습니다.')
        return redirect('tournament:detailV2', id=tournament.id)
    if req.method != 'POST':
        return redirect('tournament:detailV2', id=tournament.id)

    posted_match_ids = {
        int(match_id)
        for match_id in req.POST.getlist('match_ids')
        if match_id.isdigit()
    }
    matches = list(
        TournamentMatch.objects.select_related('round', 'player1', 'player1__user', 'player2', 'player2__user')
        .filter(round=round_obj, id__in=posted_match_ids)
        .order_by('table_no')
    )
    matches = [
        match
        for match in matches
        if _can_report_match(req.user, tournament, match)
    ]

    if not matches:
        messages.error(req, '저장할 수 있는 매치 결과가 없습니다.')
        return redirect('tournament:detailV2', id=tournament.id)

    reported_at = timezone.now()
    try:
        for match in matches:
            prefix = f'match_{match.id}_'
            try:
                _read_match_result(req.POST, match, prefix)
            except ValueError as exc:
                player2_name = match.player2.name if match.player2 else 'BYE'
                raise ValueError(f'T{match.table_no} {match.player1.name} vs {player2_name}: {exc}') from exc
            match.status = TournamentMatch.STATUS_REPORTED
            match.reported_at = reported_at
    except ValueError as exc:
        messages.error(req, str(exc))
        return redirect('tournament:detailV2', id=tournament.id)

    with transaction.atomic():
        for match in matches:
            match.save(update_fields=['player1_score', 'player2_score', 'is_draw', 'winner', 'status', 'reported_at'])
        complete_round_if_ready(round_obj)

    messages.success(req, f'{round_obj.number}라운드 결과를 저장했습니다.')
    return redirect('tournament:detailV2', id=tournament.id)


@login_required(login_url='common:loginV2', redirect_field_name='next')
def finishV2(req, id):
    tournament = get_object_or_404(Tournament, id=id)
    if not _is_operator(req.user, tournament):
        raise PermissionDenied()
    if req.method == 'POST':
        with transaction.atomic():
            tournament.status = Tournament.STATUS_FINISHED
            tournament.save(update_fields=['status', 'updated_at'])
            lock_submitted_decks(tournament)
            tag_submitted_decks(tournament)
        messages.success(req, '대회를 종료했습니다.')
    return redirect('tournament:detailV2', id=tournament.id)


@login_required(login_url='common:loginV2', redirect_field_name='next')
def deleteV2(req, id):
    tournament = get_object_or_404(Tournament.objects.select_related('organizer'), id=id)
    if not _is_operator(req.user, tournament):
        raise PermissionDenied()
    if req.method != 'POST':
        return redirect('tournament:detailV2', id=tournament.id)
    if not _can_delete_tournament(req.user, tournament):
        messages.error(req, '종료되었거나 2라운드 이상 진행된 대회는 슈퍼유저만 삭제할 수 있습니다.')
        return redirect('tournament:detailV2', id=tournament.id)

    tournament_name = tournament.name
    tournament.delete()
    messages.success(req, f'{tournament_name} 대회를 삭제했습니다.')
    return redirect('tournament:indexV2')
