from django.utils import timezone

from deck.models import CardInDeck, Deck

from .models import Tournament, TournamentDeckSubmission, TournamentMatch, TournamentParticipant, TournamentRound


def _split_tag_text(value):
    return [
        tag.strip().lstrip('#')
        for tag in str(value or '').replace(',', '/').split('/')
        if tag.strip().lstrip('#')
    ]


def _append_tag_text(value, tag):
    normalized_tag = str(tag or '').strip().lstrip('#')
    if not normalized_tag:
        return value or ''

    tags = _split_tag_text(value)
    existing_tags = {existing_tag.casefold() for existing_tag in tags}
    if normalized_tag.casefold() not in existing_tags:
        tags.append(normalized_tag)
    return '/'.join(tags)


def copy_deck_for_tournament_submission(deck, user, tournament):
    copied_deck = Deck.objects.create(
        name=f'[{tournament.name}] 참가용 from {deck.author.username}',
        author=user,
        character=deck.character,
        version=deck.version,
        keyword=deck.keyword,
        description=deck.description,
        visibility=Deck.VISIBILITY_UNLISTED,
        private=False,
        tags=deck.tags,
    )
    CardInDeck.objects.bulk_create([
        CardInDeck(
            deck=copied_deck,
            card_id=card_in_deck.card_id,
            count=card_in_deck.count,
            hand=card_in_deck.hand,
            side=card_in_deck.side,
        )
        for card_in_deck in CardInDeck.objects.filter(deck=deck)
    ])
    return copied_deck


def copy_external_submitted_decks(tournament):
    copied_count = 0
    submissions = TournamentDeckSubmission.objects.filter(participant__tournament=tournament).select_related(
        'participant',
        'participant__user',
        'deck',
        'deck__author',
        'deck__character',
    )
    for submission in submissions:
        if submission.deck.author_id == submission.participant.user_id:
            continue
        original_deck_id = submission.deck_id
        copied_deck = copy_deck_for_tournament_submission(
            submission.deck,
            submission.participant.user,
            tournament,
        )
        submission.deck = copied_deck
        submission.save(update_fields=['deck'])
        if submission.participant.deck_id == original_deck_id:
            submission.participant.deck = copied_deck
            submission.participant.save(update_fields=['deck'])
        copied_count += 1
    return copied_count


def lock_submitted_decks(tournament):
    copy_external_submitted_decks(tournament)
    Deck.objects.filter(
        tournament_submissions__participant__tournament=tournament,
    ).distinct().update(locked=True)


def tag_submitted_decks(tournament):
    tournament_tag = tournament.name
    decks = Deck.objects.filter(
        tournament_submissions__participant__tournament=tournament,
    ).distinct()
    for deck in decks:
        update_fields = []
        next_keyword = _append_tag_text(deck.keyword, tournament_tag)
        if next_keyword != deck.keyword:
            deck.keyword = next_keyword
            update_fields.append('keyword')
        next_tags = _append_tag_text(deck.tags, tournament_tag)
        if next_tags != deck.tags:
            deck.tags = next_tags
            update_fields.append('tags')
        if not deck.locked:
            deck.locked = True
            update_fields.append('locked')
        if update_fields:
            deck.save(update_fields=update_fields)


def get_reported_matches(tournament):
    return list(
        TournamentMatch.objects.filter(
            round__tournament=tournament,
            status=TournamentMatch.STATUS_REPORTED,
        ).select_related('player1', 'player2', 'winner', 'round')
    )


def build_standings(tournament):
    participants = list(
        TournamentParticipant.objects.filter(tournament=tournament, dropped=False)
        .select_related('user', 'deck', 'deck__character')
    )
    rows = {
        participant.id: {
            'participant': participant,
            'points': 0,
            'wins': 0,
            'draws': 0,
            'losses': 0,
            'byes': 0,
            'matches': 0,
            'opponent_ids': set(),
        }
        for participant in participants
    }

    for match in get_reported_matches(tournament):
        if match.player1_id not in rows:
            continue
        win_points = match.round.win_points
        draw_points = match.round.draw_points
        loss_points = match.round.loss_points
        if match.player2_id is None:
            rows[match.player1_id]['points'] += win_points
            rows[match.player1_id]['byes'] += 1
            continue

        if match.player2_id not in rows:
            continue

        rows[match.player1_id]['matches'] += 1
        rows[match.player2_id]['matches'] += 1
        rows[match.player1_id]['opponent_ids'].add(match.player2_id)
        rows[match.player2_id]['opponent_ids'].add(match.player1_id)

        if match.is_draw:
            rows[match.player1_id]['points'] += draw_points
            rows[match.player2_id]['points'] += draw_points
            rows[match.player1_id]['draws'] += 1
            rows[match.player2_id]['draws'] += 1
        elif match.winner_id == match.player1_id:
            rows[match.player1_id]['points'] += win_points
            rows[match.player2_id]['points'] += loss_points
            rows[match.player1_id]['wins'] += 1
            rows[match.player2_id]['losses'] += 1
        elif match.winner_id == match.player2_id:
            rows[match.player2_id]['points'] += win_points
            rows[match.player1_id]['points'] += loss_points
            rows[match.player2_id]['wins'] += 1
            rows[match.player1_id]['losses'] += 1

    for row in rows.values():
        if row['matches']:
            row['match_win_percentage'] = (row['wins'] + (row['draws'] * 0.5)) / row['matches']
        else:
            row['match_win_percentage'] = 0

    for row in rows.values():
        opponent_rows = [
            rows[opponent_id]
            for opponent_id in row['opponent_ids']
            if opponent_id in rows
        ]
        row['buchholz'] = sum(opponent_row['points'] for opponent_row in opponent_rows)
        if opponent_rows:
            row['owm_percentage'] = (
                sum(opponent_row['match_win_percentage'] for opponent_row in opponent_rows)
                / len(opponent_rows)
            )
        else:
            row['owm_percentage'] = 0
        if tournament.tiebreaker == Tournament.TIEBREAKER_OWM:
            row['tiebreaker_score'] = row['owm_percentage']
            row['tiebreaker_display'] = f'{row["owm_percentage"] * 100:.1f}%'
        else:
            row['tiebreaker_score'] = row['buchholz']
            row['tiebreaker_display'] = str(row['buchholz'])

    standings = list(rows.values())
    standings.sort(
        key=lambda row: (
            -row['points'],
            -row['tiebreaker_score'],
            -row['wins'],
            row['participant'].seed or 9999,
            row['participant'].joined_at,
        )
    )
    return standings


def has_open_round(tournament):
    return TournamentRound.objects.filter(
        tournament=tournament,
        status=TournamentRound.STATUS_RUNNING,
    ).exists()


def _next_round_number(tournament):
    latest_round = tournament.rounds.order_by('-number').first()
    return latest_round.number + 1 if latest_round else 1


def _create_bye(round_obj, table_no, participant):
    return TournamentMatch.objects.create(
        round=round_obj,
        table_no=table_no,
        player1=participant,
        winner=participant,
        status=TournamentMatch.STATUS_REPORTED,
        reported_at=timezone.now(),
    )


def _elimination_rounds(tournament):
    return tournament.rounds.filter(stage=TournamentRound.STAGE_ELIMINATION)


def _initial_elimination_players(tournament):
    matched_player_ids = []
    seen_ids = set()
    elimination_matches = TournamentMatch.objects.filter(
        round__tournament=tournament,
        round__stage=TournamentRound.STAGE_ELIMINATION,
    ).order_by('round__number', 'table_no')
    for match in elimination_matches:
        for participant_id in [match.player1_id, match.player2_id]:
            if participant_id and participant_id not in seen_ids:
                matched_player_ids.append(participant_id)
                seen_ids.add(participant_id)

    if matched_player_ids:
        participants_by_id = TournamentParticipant.objects.select_related('user', 'deck', 'deck__character').in_bulk(matched_player_ids)
        return [
            participants_by_id[participant_id]
            for participant_id in matched_player_ids
            if participant_id in participants_by_id
        ]

    players = [row['participant'] for row in build_standings(tournament)]
    if tournament.format == Tournament.FORMAT_HYBRID and tournament.top_cut_count:
        players = players[:tournament.top_cut_count]
    return players


def _elimination_loss_map(tournament):
    losses = {}
    matches = TournamentMatch.objects.filter(
        round__tournament=tournament,
        round__stage=TournamentRound.STAGE_ELIMINATION,
        status=TournamentMatch.STATUS_REPORTED,
    )
    for match in matches:
        if not match.player2_id or not match.winner_id:
            continue
        if match.winner_id == match.player1_id:
            loser_id = match.player2_id
        elif match.winner_id == match.player2_id:
            loser_id = match.player1_id
        else:
            continue
        losses[loser_id] = losses.get(loser_id, 0) + 1
    return losses


def get_elimination_winner(tournament):
    elimination_rounds = _elimination_rounds(tournament)
    if not elimination_rounds.exists() or elimination_rounds.filter(status=TournamentRound.STATUS_RUNNING).exists():
        return None

    if tournament.elimination_mode == Tournament.ELIMINATION_DOUBLE:
        losses = _elimination_loss_map(tournament)
        active_players = [
            participant
            for participant in _initial_elimination_players(tournament)
            if losses.get(participant.id, 0) < 2
        ]
        return active_players[0] if len(active_players) == 1 else None

    latest_round = elimination_rounds.order_by('-number').first()
    if not latest_round or latest_round.matches.filter(status=TournamentMatch.STATUS_PENDING).exists():
        return None
    winners = [
        match.winner
        for match in latest_round.matches.select_related('winner').order_by('table_no')
        if match.winner_id
    ]
    return winners[0] if len(winners) == 1 else None


def _pair_swiss_players(tournament):
    rows = build_standings(tournament)
    players = [row['participant'] for row in rows]
    opponent_map = {row['participant'].id: row['opponent_ids'] for row in rows}
    bye_ids = {
        match.player1_id
        for match in TournamentMatch.objects.filter(
            round__tournament=tournament,
            player2__isnull=True,
            status=TournamentMatch.STATUS_REPORTED,
        )
    }

    bye_player = None
    if len(players) % 2 == 1:
        for participant in reversed(players):
            if participant.id not in bye_ids:
                bye_player = participant
                break
        if bye_player is None:
            bye_player = players[-1]
        players.remove(bye_player)

    pairs = []
    while players:
        player1 = players.pop(0)
        player2_index = None
        for index, candidate in enumerate(players):
            if candidate.id not in opponent_map.get(player1.id, set()):
                player2_index = index
                break
        if player2_index is None:
            player2_index = 0
        player2 = players.pop(player2_index)
        pairs.append((player1, player2))

    return pairs, bye_player


def _pair_single_elimination_players(tournament):
    previous_rounds = _elimination_rounds(tournament)
    previous_elimination_round = previous_rounds.order_by('-number').first()
    if previous_elimination_round:
        players = [
            match.winner
            for match in previous_elimination_round.matches.select_related('winner').order_by('table_no')
            if match.winner_id
        ]
    else:
        players = _initial_elimination_players(tournament)

    if len(players) <= 1:
        return [], None

    bye_player = None
    if len(players) % 2 == 1 and players:
        bye_player = players.pop(0)

    pairs = []
    while players:
        player1 = players.pop(0)
        player2 = players.pop(-1) if players else None
        if player2:
            pairs.append((player1, player2))
        else:
            bye_player = player1
    return pairs, bye_player


def _pair_double_elimination_players(tournament):
    players = _initial_elimination_players(tournament)
    losses = _elimination_loss_map(tournament)
    order_index = {participant.id: index for index, participant in enumerate(players)}
    active_players = [
        participant
        for participant in players
        if losses.get(participant.id, 0) < 2
    ]
    if len(active_players) <= 1:
        return [], None

    active_players.sort(key=lambda participant: (losses.get(participant.id, 0), order_index.get(participant.id, 9999)))
    bye_player = None
    if len(active_players) % 2 == 1:
        bye_player = active_players.pop(0)

    pairs = []
    while active_players:
        player1 = active_players.pop(0)
        player1_losses = losses.get(player1.id, 0)
        player2_index = None
        for index, candidate in enumerate(active_players):
            if losses.get(candidate.id, 0) == player1_losses:
                player2_index = index
                break
        if player2_index is None:
            player2_index = 0
        player2 = active_players.pop(player2_index)
        pairs.append((player1, player2))
    return pairs, bye_player


def _pair_elimination_players(tournament):
    if tournament.elimination_mode == Tournament.ELIMINATION_DOUBLE:
        return _pair_double_elimination_players(tournament)
    return _pair_single_elimination_players(tournament)


def create_round(
    tournament,
    stage,
    duration_minutes=None,
    set_count=None,
    win_points=None,
    draw_points=None,
    loss_points=None,
):
    if tournament.status == Tournament.STATUS_FINISHED:
        raise ValueError('종료된 대회에서는 라운드를 시작할 수 없습니다.')
    winner = get_elimination_winner(tournament)
    if winner:
        raise ValueError(f'이미 우승자가 결정되었습니다: {winner.name}')
    if has_open_round(tournament):
        raise ValueError('진행 중인 라운드가 있습니다.')

    participants = TournamentParticipant.objects.filter(tournament=tournament, dropped=False)
    if participants.count() < 2:
        raise ValueError('참가자가 2명 이상 필요합니다.')
    if stage == TournamentRound.STAGE_SWISS and tournament.swiss_round_count:
        started_swiss_rounds = tournament.rounds.filter(stage=TournamentRound.STAGE_SWISS).count()
        if started_swiss_rounds >= tournament.swiss_round_count:
            raise ValueError(f'설정된 스위스 라운드 수({tournament.swiss_round_count}라운드)를 모두 진행했습니다.')
    if stage == TournamentRound.STAGE_ELIMINATION and tournament.format == Tournament.FORMAT_HYBRID:
        if tournament.top_cut_count < 2:
            raise ValueError('토너먼트 진출자 수를 2명 이상으로 설정해야 합니다.')
        if tournament.swiss_round_count:
            finished_swiss_rounds = tournament.rounds.filter(
                stage=TournamentRound.STAGE_SWISS,
                status=TournamentRound.STATUS_FINISHED,
            ).count()
            if finished_swiss_rounds < tournament.swiss_round_count:
                raise ValueError(
                    f'스위스 {tournament.swiss_round_count}라운드를 모두 종료한 뒤 토너먼트를 시작할 수 있습니다.'
                )

    if stage == TournamentRound.STAGE_ELIMINATION:
        pairs, bye_player = _pair_elimination_players(tournament)
    else:
        pairs, bye_player = _pair_swiss_players(tournament)

    if not pairs:
        raise ValueError('새 라운드를 만들 수 있는 매칭 대상이 없습니다.')

    lock_submitted_decks(tournament)

    round_obj = TournamentRound.objects.create(
        tournament=tournament,
        number=_next_round_number(tournament),
        stage=stage,
        duration_minutes=duration_minutes or tournament.round_duration_minutes,
        set_count=set_count or tournament.round_set_count,
        win_points=tournament.win_points if win_points is None else win_points,
        draw_points=tournament.draw_points if draw_points is None else draw_points,
        loss_points=tournament.loss_points if loss_points is None else loss_points,
        started_at=timezone.now(),
    )

    table_no = 1
    for player1, player2 in pairs:
        TournamentMatch.objects.create(
            round=round_obj,
            table_no=table_no,
            player1=player1,
            player2=player2,
        )
        table_no += 1

    if bye_player:
        _create_bye(round_obj, table_no, bye_player)

    tournament.status = Tournament.STATUS_RUNNING
    tournament.save(update_fields=['status', 'updated_at'])
    return round_obj


def complete_round_if_ready(round_obj):
    if not round_obj.matches.filter(status=TournamentMatch.STATUS_PENDING).exists():
        round_obj.status = TournamentRound.STATUS_FINISHED
        round_obj.ended_at = timezone.now()
        round_obj.save(update_fields=['status', 'ended_at'])
        return True
    return False
