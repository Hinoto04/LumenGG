import secrets
import posixpath
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.contrib.staticfiles import finders
from django.db import transaction
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from card.models import Card, Character

from .event_buffer import (
    flush_pending_battle_events,
    flush_session_events,
    latest_pending_event,
    mark_pending_event_undone,
    normalize_event_datetime,
    pending_event_records,
    recent_battle_event_payloads,
    record_battle_event,
)
from .models import BattleEvent, BattleSession, BattleSet


STANDALONE_SESSION_LIFETIME = timedelta(hours=1)
TOURNAMENT_SESSION_LIFETIME_AFTER_FINISH = timedelta(days=7)
PASSIVE_UI_TEMPLATE_PREFIX = 'battlelog/passive_ui/'
PASSIVE_UI_STATIC_PREFIX = 'battlelog/passive_ui/'


def battle_session_queryset():
    return BattleSession.objects.select_related(
        'player1_character',
        'player2_character',
        'tournament_match',
        'tournament_match__round',
        'tournament_match__round__tournament',
        'tournament_match__player1',
        'tournament_match__player1__user',
        'tournament_match__player1__deck',
        'tournament_match__player1__deck__character',
        'tournament_match__player2',
        'tournament_match__player2__user',
        'tournament_match__player2__deck',
        'tournament_match__player2__deck__character',
    ).prefetch_related(
        'tournament_match__player1__deck_submissions__deck__character',
        'tournament_match__player2__deck_submissions__deck__character',
        'sets',
    )


def generate_token():
    return secrets.token_urlsafe(32)


def character_hand_table(character):
    if not character:
        return {}
    raw_table = (character.datas or {}).get('hand', {})
    table = {}
    for hp, limit in raw_table.items():
        try:
            table[int(hp)] = int(limit)
        except (TypeError, ValueError):
            continue
    return table


def initial_hp_for_character(character):
    table = character_hand_table(character)
    return max(table.keys()) if table else 5000


def hand_limit_for_hp(character, hp):
    table = character_hand_table(character)
    if not table:
        return None
    for threshold in sorted(table.keys()):
        if hp <= threshold:
            return table[threshold]
    return table[max(table.keys())]


def _actor_label(user):
    if user and user.is_authenticated:
        return user.username
    return '익명 조작자'


def _session_token_pair():
    return generate_token(), generate_token()


def _set_player_character(session, target, character):
    initial_hp = initial_hp_for_character(character)
    if target == BattleEvent.TARGET_PLAYER1:
        session.player1_character = character
        session.player1_initial_hp = initial_hp
        session.player1_hp = initial_hp
        session.player1_fp = 0
        return
    session.player2_character = character
    session.player2_initial_hp = initial_hp
    session.player2_hp = initial_hp
    session.player2_fp = 0


def _round_ends_at(session):
    if not session.tournament_match_id:
        return None
    return session.tournament_match.round.ends_at + timedelta(seconds=session.round_extra_seconds or 0)


def _round_remaining_seconds(session, now=None):
    ends_at = _round_ends_at(session)
    if not ends_at:
        return None
    now = now or timezone.now()
    return max(0, int((ends_at - now).total_seconds()))


def _set_start_payload(session):
    return {
        'player1_start_hp': session.player1_hp,
        'player2_start_hp': session.player2_hp,
        'player1_start_fp': session.player1_fp,
        'player2_start_fp': session.player2_fp,
    }


def _current_set(session):
    return session.sets.filter(status=BattleSet.STATUS_RUNNING).order_by('-set_number').first()


def _set_score(session):
    finished_sets = session.sets.filter(status=BattleSet.STATUS_FINISHED)
    return {
        BattleEvent.TARGET_PLAYER1: finished_sets.filter(winner_side=BattleEvent.TARGET_PLAYER1).count(),
        BattleEvent.TARGET_PLAYER2: finished_sets.filter(winner_side=BattleEvent.TARGET_PLAYER2).count(),
    }


def _required_set_wins(session):
    if not session.tournament_match_id:
        return 0
    return (session.tournament_match.round.set_count // 2) + 1


def _max_set_count(session):
    return session.tournament_match.round.set_count if session.tournament_match_id else 0


def ensure_current_set(session):
    current_set = _current_set(session)
    if current_set:
        return current_set
    latest_number = session.sets.order_by('-set_number').values_list('set_number', flat=True).first() or 0
    return BattleSet.objects.create(
        session=session,
        set_number=latest_number + 1,
        **_set_start_payload(session),
    )


def _winner_candidate(session):
    p1_dead = session.player1_hp <= 0
    p2_dead = session.player2_hp <= 0
    if p1_dead and not p2_dead:
        return BattleEvent.TARGET_PLAYER2
    if p2_dead and not p1_dead:
        return BattleEvent.TARGET_PLAYER1
    return ''


def _reporting_player_side(user, session):
    if not user or not user.is_authenticated or not session.tournament_match_id:
        return ''
    match = session.tournament_match
    if match.player1.user_id == user.id:
        return BattleEvent.TARGET_PLAYER1
    if match.player2_id and match.player2.user_id == user.id:
        return BattleEvent.TARGET_PLAYER2
    return ''


def can_report_set(user, session):
    if not session.tournament_match_id or not tournament_match_is_open(session):
        return False
    return bool(_reporting_player_side(user, session))


def can_force_set_result(user, session):
    if not session.tournament_match_id or not tournament_match_is_open(session):
        return False
    return is_tournament_operator(user, session.tournament_match.round.tournament)


def can_add_extra_time(user, session):
    if not session.tournament_match_id or not tournament_match_is_open(session):
        return False
    return is_tournament_operator(user, session.tournament_match.round.tournament)


def create_standalone_session(player1_name, player2_name, player1_character, player2_character, user=None):
    view_token, control_token = _session_token_pair()
    session = BattleSession(
        session_type=BattleSession.SESSION_STANDALONE,
        view_token=view_token,
        control_token=control_token,
        created_by=user if user and user.is_authenticated else None,
        player1_name=(player1_name or '').strip() or '플레이어1',
        player2_name=(player2_name or '').strip() or '플레이어2',
        expires_at=timezone.now() + STANDALONE_SESSION_LIFETIME,
    )
    _set_player_character(session, BattleEvent.TARGET_PLAYER1, player1_character)
    _set_player_character(session, BattleEvent.TARGET_PLAYER2, player2_character)
    session.save()
    ensure_current_set(session)
    record_battle_event(
        session,
        user,
        event_type=BattleEvent.EVENT_CHARACTER,
        target=BattleEvent.TARGET_PLAYER1,
        payload={'character': player1_character.name if player1_character else ''},
    )
    record_battle_event(
        session,
        user,
        event_type=BattleEvent.EVENT_CHARACTER,
        target=BattleEvent.TARGET_PLAYER2,
        payload={'character': player2_character.name if player2_character else ''},
    )
    return session


def _unique_character_candidates(participant):
    submissions = (
        participant.deck_submissions.select_related('deck__character').order_by('slot')
        if hasattr(participant, 'deck_submissions')
        else []
    )
    candidates = []
    seen_ids = set()
    for submission in submissions.all() if hasattr(submissions, 'all') else submissions:
        character = submission.deck.character if submission.deck_id else None
        if character and character.id not in seen_ids:
            candidates.append(character)
            seen_ids.add(character.id)

    if not candidates and participant.deck_id:
        character = participant.deck.character
        if character:
            candidates.append(character)
    return candidates


def _auto_character_for_participant(participant):
    candidates = _unique_character_candidates(participant)
    return candidates[0] if len(candidates) == 1 else None


def _player_participant_for_target(session, target):
    if not session.tournament_match_id:
        return None
    if target == BattleEvent.TARGET_PLAYER1:
        return session.tournament_match.player1
    if target == BattleEvent.TARGET_PLAYER2 and session.tournament_match.player2_id:
        return session.tournament_match.player2
    return None


def _reset_player_for_next_set(session, target):
    participant = _player_participant_for_target(session, target)
    character_candidates = _unique_character_candidates(participant) if participant else []
    character = character_candidates[0] if len(character_candidates) == 1 else None

    if character:
        _set_player_character(session, target, character)
        return

    if target == BattleEvent.TARGET_PLAYER1:
        session.player1_character = None
        session.player1_initial_hp = 0
        session.player1_hp = 0
        session.player1_fp = 0
        return

    session.player2_character = None
    session.player2_initial_hp = 0
    session.player2_hp = 0
    session.player2_fp = 0


def get_or_create_tournament_session(match, user=None):
    view_token, control_token = _session_token_pair()
    defaults = {
        'session_type': BattleSession.SESSION_TOURNAMENT,
        'view_token': view_token,
        'control_token': control_token,
        'created_by': user if user and user.is_authenticated else None,
        'player1_name': match.player1.name,
        'player2_name': match.player2.name if match.player2_id else 'BYE',
    }
    session, created = BattleSession.objects.get_or_create(
        tournament_match=match,
        defaults=defaults,
    )
    if created:
        player1_character = _auto_character_for_participant(match.player1)
        player2_character = _auto_character_for_participant(match.player2) if match.player2_id else None
        if player1_character:
            _set_player_character(session, BattleEvent.TARGET_PLAYER1, player1_character)
        if player2_character:
            _set_player_character(session, BattleEvent.TARGET_PLAYER2, player2_character)
        session.save(update_fields=[
            'player1_character',
            'player2_character',
            'player1_initial_hp',
            'player2_initial_hp',
            'player1_hp',
            'player2_hp',
            'player1_fp',
            'player2_fp',
            'updated_at',
        ])
        ensure_current_set(session)
    return session


def ensure_tournament_sessions_for_round(round_obj):
    matches = (
        round_obj.matches.filter(player2__isnull=False)
        .select_related(
            'player1',
            'player1__deck',
            'player1__deck__character',
            'player2',
            'player2__deck',
            'player2__deck__character',
        )
        .prefetch_related('player1__deck_submissions__deck__character', 'player2__deck_submissions__deck__character')
    )
    for match in matches:
        get_or_create_tournament_session(match)


def is_tournament_operator(user, tournament):
    return user.is_authenticated and (user == tournament.organizer or user.is_staff)


def is_match_player(user, match):
    return (
        user.is_authenticated
        and (
            match.player1.user_id == user.id
            or (match.player2_id and match.player2.user_id == user.id)
        )
    )


def session_is_expired(session):
    return bool(session.expires_at and session.expires_at <= timezone.now())


def tournament_match_is_open(session):
    match = session.tournament_match
    return (
        match
        and match.round.status == 'running'
        and match.status == 'pending'
        and not match.is_bye
    )


def can_control_session(user, session, control_token=''):
    if session_is_expired(session):
        return False
    if session.session_type == BattleSession.SESSION_STANDALONE:
        return bool(control_token and secrets.compare_digest(control_token, session.control_token))
    if not session.tournament_match_id or not tournament_match_is_open(session):
        return False
    match = session.tournament_match
    if is_tournament_operator(user, match.round.tournament):
        return True
    if not is_match_player(user, match):
        return False
    return (_round_remaining_seconds(session) or 0) > 0


def can_toggle_sudden_death(user, session, control_token=''):
    if session.session_type == BattleSession.SESSION_STANDALONE:
        return can_control_session(user, session, control_token)
    if not session.tournament_match_id or not tournament_match_is_open(session):
        return False
    return is_tournament_operator(user, session.tournament_match.round.tournament)


def can_choose_character(user, session, target, control_token=''):
    if not can_control_session(user, session, control_token):
        return False
    if session.session_type == BattleSession.SESSION_STANDALONE:
        return True
    match = session.tournament_match
    if is_tournament_operator(user, match.round.tournament):
        return True
    if target == BattleEvent.TARGET_PLAYER1:
        return match.player1.user_id == user.id
    if target == BattleEvent.TARGET_PLAYER2 and match.player2_id:
        return match.player2.user_id == user.id
    return False


def character_options_for_session(session, user=None, control_token=''):
    def option_payload(character):
        return {
            'id': character.id,
            'name': character.name,
            'color': character.color,
        }

    def all_characters():
        return list(Character.objects.order_by('id'))

    if session.session_type == BattleSession.SESSION_STANDALONE or not session.tournament_match_id:
        characters = all_characters()
        return {
            'p1': {
                'can_choose': can_choose_character(user, session, BattleEvent.TARGET_PLAYER1, control_token),
                'options': [option_payload(character) for character in characters],
            },
            'p2': {
                'can_choose': can_choose_character(user, session, BattleEvent.TARGET_PLAYER2, control_token),
                'options': [option_payload(character) for character in characters],
            },
        }

    match = session.tournament_match
    p1_candidates = _unique_character_candidates(match.player1) or all_characters()
    p2_candidates = _unique_character_candidates(match.player2) if match.player2_id else []
    if match.player2_id and not p2_candidates:
        p2_candidates = all_characters()
    return {
        'p1': {
            'can_choose': can_choose_character(user, session, BattleEvent.TARGET_PLAYER1, control_token),
            'options': [option_payload(character) for character in p1_candidates],
        },
        'p2': {
            'can_choose': can_choose_character(user, session, BattleEvent.TARGET_PLAYER2, control_token),
            'options': [option_payload(character) for character in p2_candidates],
        },
    }


def _passive_cards(character):
    if not character:
        return []
    return list(
        Card.objects.filter(character=character, type='특성')
        .order_by('id')
        .values('id', 'name', 'img', 'img_sm')
    )


def _safe_passive_ui_path(value, prefix, suffix):
    raw_path = str(value or '').replace('\\', '/').lstrip('/')
    normalized_path = posixpath.normpath(raw_path)
    if normalized_path in ('', '.'):
        return ''
    if normalized_path.startswith('../') or '/../' in f'/{normalized_path}/':
        return ''
    if not normalized_path.startswith(prefix) or not normalized_path.endswith(suffix):
        return ''
    return normalized_path


def _render_passive_ui_template(path, character):
    safe_path = _safe_passive_ui_path(path, PASSIVE_UI_TEMPLATE_PREFIX, '.html')
    if not safe_path:
        return ''
    try:
        return render_to_string(safe_path, {'character': character})
    except TemplateDoesNotExist:
        return ''


def _read_passive_ui_static(path, suffix):
    safe_path = _safe_passive_ui_path(path, PASSIVE_UI_STATIC_PREFIX, suffix)
    if not safe_path:
        return ''
    found_path = finders.find(safe_path)
    if isinstance(found_path, (list, tuple)):
        found_path = found_path[0] if found_path else ''
    candidate_paths = []
    if found_path:
        candidate_paths.append(found_path)
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root:
        candidate_paths.append(Path(static_root) / safe_path)
    candidate_paths.append(Path(settings.BASE_DIR) / 'static' / safe_path)

    for candidate_path in candidate_paths:
        if not candidate_path:
            continue
        try:
            with open(candidate_path, encoding='utf-8') as static_file:
                return static_file.read()
        except OSError:
            continue
    return ''


def _is_passive_ui_static_reference(value, suffix):
    return bool(_safe_passive_ui_path(value, PASSIVE_UI_STATIC_PREFIX, suffix))


def _passive_ui_text_or_static(raw_ui, key, suffix):
    explicit_path = raw_ui.get(f'{key}_path') or raw_ui.get(f'{key}Path') or raw_ui.get(f'{key}_file') or raw_ui.get(f'{key}File')
    if explicit_path:
        return _read_passive_ui_static(explicit_path, suffix)

    value = str(raw_ui.get(key) or '')
    loaded = _read_passive_ui_static(value, suffix)
    if loaded:
        return loaded
    if _is_passive_ui_static_reference(value, suffix):
        return ''
    return value


def _passive_ui(character):
    if not character:
        return {}
    datas = character.datas or {}
    battle_calculator = datas.get('battle_calculator') if isinstance(datas.get('battle_calculator'), dict) else {}
    battle_calculator_camel = datas.get('battleCalculator') if isinstance(datas.get('battleCalculator'), dict) else {}
    battle = datas.get('battle') if isinstance(datas.get('battle'), dict) else {}
    raw_ui = (
        datas.get('battle_passive_ui')
        or datas.get('battlePassiveUi')
        or battle_calculator.get('passive_ui')
        or battle_calculator_camel.get('passiveUi')
        or battle.get('passive_ui')
    )
    if not isinstance(raw_ui, dict):
        return {}
    options = raw_ui.get('options', {})
    template_path = raw_ui.get('template') or raw_ui.get('template_path') or raw_ui.get('templatePath') or raw_ui.get('html_path') or raw_ui.get('htmlPath')
    html = _render_passive_ui_template(template_path, character) if template_path else str(raw_ui.get('html') or '')
    return {
        'html': html,
        'css': _passive_ui_text_or_static(raw_ui, 'css', '.css'),
        'js': _passive_ui_text_or_static(raw_ui, 'js', '.js'),
        'options': options if isinstance(options, (dict, list)) else {},
    }


def _character_payload(character, hp):
    if not character:
        return None
    return {
        'id': character.id,
        'name': character.name,
        'img': character.body_img or character.sd_img or character.img,
        'icon_img': character.icon_img,
        'color': character.color,
        'hand_limit': hand_limit_for_hp(character, hp),
        'passive_ui': _passive_ui(character),
        'passive_cards': _passive_cards(character),
        'passives': _passive_cards(character),
    }


def _event_payload(event):
    return {
        'id': event.id,
        'type': event.event_type,
        'target': event.target,
        'amount': event.amount,
        'hp_before': event.hp_before,
        'hp_after': event.hp_after,
        'actor': event.actor_label,
        'payload': event.payload,
        'undone': event.undone,
        'created_at': event.created_at.isoformat(),
    }


def serialize_session(session, user=None, control_token='', include_events=True):
    now = timezone.now()
    can_control = can_control_session(user, session, control_token)
    can_sudden_death = can_toggle_sudden_death(user, session, control_token)
    timer_ends_at = None
    timer_remaining = session.timer_duration_seconds
    timer_running = False
    if session.timer_started_at:
        timer_ends_at = session.timer_started_at + timedelta(seconds=session.timer_duration_seconds)
        timer_remaining = max(0, int((timer_ends_at - now).total_seconds()))
        timer_running = timer_remaining > 0

    round_ends_at = None
    round_remaining = None
    tournament = None
    match = None
    if session.tournament_match_id:
        match = session.tournament_match
        tournament = match.round.tournament
        round_ends_at = _round_ends_at(session)
        round_remaining = max(0, int((round_ends_at - now).total_seconds()))

    suggested_winner = ''
    if session.player1_hp <= 0 < session.player2_hp:
        suggested_winner = 'p2'
    elif session.player2_hp <= 0 < session.player1_hp:
        suggested_winner = 'p1'

    current_set = _current_set(session)
    display_set = current_set or session.sets.order_by('-set_number').first()
    set_score = _set_score(session) if session.tournament_match_id else {
        BattleEvent.TARGET_PLAYER1: 0,
        BattleEvent.TARGET_PLAYER2: 0,
    }
    current_set_number = (
        display_set.set_number
        if display_set
        else 1
    )
    winner_candidate = _winner_candidate(session)
    ambiguous_result = session.player1_hp <= 0 and session.player2_hp <= 0

    data = {
        'id': session.id,
        'type': session.session_type,
        'is_expired': session_is_expired(session),
        'can_control': can_control,
        'can_sudden_death': can_sudden_death,
        'sudden_death': session.sudden_death,
        'suggested_winner': suggested_winner,
        'view_url': reverse('battlelog:sessionDetail', kwargs={'view_token': session.view_token}),
        'control_url': reverse('battlelog:sessionControl', kwargs={
            'view_token': session.view_token,
            'control_token': session.control_token,
        }),
        'players': {
            'p1': {
                'name': session.player1_name,
                'hp': session.player1_hp,
                'fp': session.player1_fp,
                'initial_hp': session.player1_initial_hp,
                'passive_state': session.player1_passive_state,
                'character': _character_payload(session.player1_character, session.player1_hp),
            },
            'p2': {
                'name': session.player2_name,
                'hp': session.player2_hp,
                'fp': session.player2_fp,
                'initial_hp': session.player2_initial_hp,
                'passive_state': session.player2_passive_state,
                'character': _character_payload(session.player2_character, session.player2_hp),
            },
        },
        'timer': {
            'started_at': session.timer_started_at.isoformat() if session.timer_started_at else None,
            'ends_at': timer_ends_at.isoformat() if timer_ends_at else None,
            'remaining_seconds': timer_remaining,
            'duration_seconds': session.timer_duration_seconds,
            'is_running': timer_running,
        },
        'round_timer': {
            'ends_at': round_ends_at.isoformat() if round_ends_at else None,
            'remaining_seconds': round_remaining,
            'extra_seconds': session.round_extra_seconds,
            'is_over': round_remaining == 0 if round_remaining is not None else False,
        },
        'set': {
            'current_number': current_set_number,
            'max_sets': _max_set_count(session),
            'required_wins': _required_set_wins(session),
            'score': {
                'p1': set_score[BattleEvent.TARGET_PLAYER1],
                'p2': set_score[BattleEvent.TARGET_PLAYER2],
            },
            'winner_candidate': winner_candidate,
            'ambiguous_result': ambiguous_result,
            'can_report': can_report_set(user, session),
            'report_side': _reporting_player_side(user, session),
            'can_force': can_force_set_result(user, session),
            'can_add_time': can_add_extra_time(user, session),
            'player1_confirmed': bool(current_set and current_set.player1_confirmed_at),
            'player2_confirmed': bool(current_set and current_set.player2_confirmed_at),
            'status': display_set.status if display_set else 'running',
        },
        'tournament': {
            'id': tournament.id if tournament else None,
            'name': tournament.name if tournament else '',
            'match_id': match.id if match else None,
            'table_no': match.table_no if match else None,
        },
    }
    if include_events:
        data['events'] = recent_battle_event_payloads(session.id)
    return data


def _pending_event_created_at(record):
    parsed = parse_datetime(str(record.get('created_at') or ''))
    if parsed is None:
        return timezone.now()
    return normalize_event_datetime(parsed)


def _has_hp_events_in_current_set(session, target):
    current_set = _current_set(session)
    if not current_set:
        return session.events.filter(event_type=BattleEvent.EVENT_HP, target=target).exists()

    started_at = current_set.started_at
    if session.events.filter(
        event_type=BattleEvent.EVENT_HP,
        target=target,
        created_at__gte=started_at,
    ).exists():
        return True

    for record in pending_event_records(session.id):
        if record.get('event_type') != BattleEvent.EVENT_HP:
            continue
        if record.get('target') != target:
            continue
        if _pending_event_created_at(record) >= started_at:
            return True
    return False


def select_character(session, target, character, user=None):
    with transaction.atomic():
        locked = BattleSession.objects.select_for_update().get(id=session.id)
        if _has_hp_events_in_current_set(locked, target):
            raise ValueError('현재 세트에서 체력 변경 이력이 있는 플레이어의 캐릭터는 변경할 수 없습니다.')
        _set_player_character(locked, target, character)
        locked.save(update_fields=[
            f'player{1 if target == BattleEvent.TARGET_PLAYER1 else 2}_character',
            f'player{1 if target == BattleEvent.TARGET_PLAYER1 else 2}_initial_hp',
            f'player{1 if target == BattleEvent.TARGET_PLAYER1 else 2}_hp',
            f'player{1 if target == BattleEvent.TARGET_PLAYER1 else 2}_fp',
            'updated_at',
        ])
        current_set = _current_set(locked)
        if current_set:
            if target == BattleEvent.TARGET_PLAYER1:
                current_set.player1_start_hp = locked.player1_hp
                current_set.player1_start_fp = locked.player1_fp
            else:
                current_set.player2_start_hp = locked.player2_hp
                current_set.player2_start_fp = locked.player2_fp
            current_set.save(update_fields=[
                'player1_start_hp',
                'player1_start_fp',
                'player2_start_hp',
                'player2_start_fp',
            ])
        record_battle_event(
            locked,
            user,
            event_type=BattleEvent.EVENT_CHARACTER,
            target=target,
            payload={'character_id': character.id, 'character': character.name},
        )
        return locked


def _clear_current_set_confirmations(session):
    current_set = _current_set(session)
    if not current_set:
        return
    if not current_set.player1_confirmed_at and not current_set.player2_confirmed_at:
        return
    current_set.player1_confirmed_at = None
    current_set.player2_confirmed_at = None
    current_set.player1_confirmed_by = None
    current_set.player2_confirmed_by = None
    current_set.save(update_fields=[
        'player1_confirmed_at',
        'player2_confirmed_at',
        'player1_confirmed_by',
        'player2_confirmed_by',
    ])


def apply_hp_delta(session, target, amount, user=None):
    if target not in (BattleEvent.TARGET_PLAYER1, BattleEvent.TARGET_PLAYER2):
        raise ValueError('대상 플레이어가 올바르지 않습니다.')
    if amount == 0 or abs(amount) > 50000:
        raise ValueError('체력 변경값이 올바르지 않습니다.')

    with transaction.atomic():
        locked = BattleSession.objects.select_for_update().get(id=session.id)
        field = 'player1_hp' if target == BattleEvent.TARGET_PLAYER1 else 'player2_hp'
        before = getattr(locked, field)
        after = before + amount
        setattr(locked, field, after)
        locked.save(update_fields=[field, 'updated_at'])
        _clear_current_set_confirmations(locked)
        record_battle_event(
            locked,
            user,
            event_type=BattleEvent.EVENT_HP,
            target=target,
            amount=amount,
            hp_before=before,
            hp_after=after,
        )
        return locked


def apply_fp_delta(session, target, amount, user=None):
    if target not in (BattleEvent.TARGET_PLAYER1, BattleEvent.TARGET_PLAYER2):
        raise ValueError('대상 플레이어가 올바르지 않습니다.')
    if amount == 0 or abs(amount) > 100:
        raise ValueError('FP 변경값이 올바르지 않습니다.')

    with transaction.atomic():
        locked = BattleSession.objects.select_for_update().get(id=session.id)
        field = 'player1_fp' if target == BattleEvent.TARGET_PLAYER1 else 'player2_fp'
        before = getattr(locked, field)
        after = before + amount
        setattr(locked, field, after)
        locked.save(update_fields=[field, 'updated_at'])
        record_battle_event(
            locked,
            user,
            event_type=BattleEvent.EVENT_FP,
            target=target,
            amount=amount,
            payload={'before': before, 'after': after},
        )
        return locked


def reset_fp(session, target, user=None):
    if target not in (BattleEvent.TARGET_PLAYER1, BattleEvent.TARGET_PLAYER2):
        raise ValueError('대상 플레이어가 올바르지 않습니다.')

    with transaction.atomic():
        locked = BattleSession.objects.select_for_update().get(id=session.id)
        field = 'player1_fp' if target == BattleEvent.TARGET_PLAYER1 else 'player2_fp'
        before = getattr(locked, field)
        setattr(locked, field, 0)
        locked.save(update_fields=[field, 'updated_at'])
        record_battle_event(
            locked,
            user,
            event_type=BattleEvent.EVENT_FP,
            target=target,
            amount=-before,
            payload={'before': before, 'after': 0, 'reset': True},
        )
        return locked


def undo_last_hp_event(session, user=None):
    with transaction.atomic():
        locked = BattleSession.objects.select_for_update().get(id=session.id)
        db_event = (
            locked.events.select_for_update()
            .filter(event_type=BattleEvent.EVENT_HP, undone=False)
            .order_by('-created_at', '-id')
            .first()
        )
        pending_event = latest_pending_event(locked.id, BattleEvent.EVENT_HP)
        use_pending_event = bool(pending_event)
        if pending_event and db_event:
            use_pending_event = _pending_event_created_at(pending_event) >= db_event.created_at

        if not pending_event and not db_event:
            raise ValueError('되돌릴 체력 변경 이력이 없습니다.')

        if use_pending_event:
            target = pending_event.get('target')
            hp_before = pending_event.get('hp_before')
            amount = pending_event.get('amount') or 0
            marked_event = mark_pending_event_undone(locked.id, pending_event.get('event_uid')) or pending_event
            undone_event_uid = marked_event.get('event_uid') or pending_event.get('event_uid')
        else:
            target = db_event.target
            hp_before = db_event.hp_before
            amount = db_event.amount or 0
            db_event.undone = True
            db_event.save(update_fields=['undone'])
            undone_event_uid = ''

        field = 'player1_hp' if target == BattleEvent.TARGET_PLAYER1 else 'player2_hp'
        current_hp = getattr(locked, field)
        setattr(locked, field, hp_before)
        locked.save(update_fields=[field, 'updated_at'])
        record_battle_event(
            locked,
            user,
            event_type=BattleEvent.EVENT_UNDO,
            target=target,
            amount=-amount,
            hp_before=current_hp,
            hp_after=hp_before,
            undone_event=None if use_pending_event else db_event,
            undone_event_uid=undone_event_uid,
            payload={'undone_event_id': None if use_pending_event else db_event.id},
        )
        return locked


def start_ten_second_timer(session, user=None):
    with transaction.atomic():
        locked = BattleSession.objects.select_for_update().get(id=session.id)
        now = timezone.now()
        timer_running = False
        if locked.timer_started_at:
            timer_ends_at = locked.timer_started_at + timedelta(seconds=locked.timer_duration_seconds)
            timer_running = timer_ends_at > now
        locked.timer_started_at = None if timer_running else now
        locked.timer_duration_seconds = 10
        locked.save(update_fields=['timer_started_at', 'timer_duration_seconds', 'updated_at'])
        record_battle_event(
            locked,
            user,
            event_type=BattleEvent.EVENT_TIMER,
            target=BattleEvent.TARGET_GLOBAL,
            payload={'duration_seconds': 10, 'running': not timer_running},
        )
        return locked


def set_sudden_death(session, enabled, user=None):
    with transaction.atomic():
        locked = BattleSession.objects.select_for_update().get(id=session.id)
        locked.sudden_death = bool(enabled)
        locked.save(update_fields=['sudden_death', 'updated_at'])
        record_battle_event(
            locked,
            user,
            event_type=BattleEvent.EVENT_SUDDEN_DEATH,
            target=BattleEvent.TARGET_GLOBAL,
            payload={'enabled': locked.sudden_death},
        )
        return locked


def add_extra_time(session, seconds, user=None):
    seconds = int(seconds or 0)
    if seconds <= 0 or seconds > 60 * 60:
        raise ValueError('추가 시간이 올바르지 않습니다.')
    if not can_add_extra_time(user, session):
        raise PermissionDenied()

    with transaction.atomic():
        locked = BattleSession.objects.select_for_update().get(id=session.id)
        locked.round_extra_seconds = (locked.round_extra_seconds or 0) + seconds
        locked.save(update_fields=['round_extra_seconds', 'updated_at'])
        record_battle_event(
            locked,
            user,
            event_type=BattleEvent.EVENT_EXTRA_TIME,
            target=BattleEvent.TARGET_GLOBAL,
            amount=seconds,
            payload={'seconds': seconds, 'round_extra_seconds': locked.round_extra_seconds},
        )
        return locked


def _finalize_match_from_sets(session):
    from tournament.services import complete_round_if_ready

    match = session.tournament_match
    score = _set_score(session)
    p1_score = score[BattleEvent.TARGET_PLAYER1]
    p2_score = score[BattleEvent.TARGET_PLAYER2]
    required_wins = _required_set_wins(session)
    max_sets = _max_set_count(session)
    finished_count = p1_score + p2_score

    should_finish = (
        p1_score >= required_wins
        or p2_score >= required_wins
        or finished_count >= max_sets
    )
    if not should_finish:
        return False

    match.player1_score = p1_score
    match.player2_score = p2_score
    match.is_draw = p1_score == p2_score
    if p1_score > p2_score:
        match.winner = match.player1
    elif p2_score > p1_score:
        match.winner = match.player2
    else:
        match.winner = None
    match.status = match.STATUS_REPORTED
    match.reported_at = timezone.now()
    match.save(update_fields=[
        'player1_score',
        'player2_score',
        'is_draw',
        'winner',
        'status',
        'reported_at',
    ])
    complete_round_if_ready(match.round)
    return True


def _start_next_set(session, user=None):
    _reset_player_for_next_set(session, BattleEvent.TARGET_PLAYER1)
    _reset_player_for_next_set(session, BattleEvent.TARGET_PLAYER2)
    session.player1_passive_state = {}
    session.player2_passive_state = {}
    session.timer_started_at = None
    session.timer_duration_seconds = 10
    session.sudden_death = False
    session.save(update_fields=[
        'player1_character',
        'player2_character',
        'player1_initial_hp',
        'player2_initial_hp',
        'player1_hp',
        'player2_hp',
        'player1_fp',
        'player2_fp',
        'player1_passive_state',
        'player2_passive_state',
        'timer_started_at',
        'timer_duration_seconds',
        'sudden_death',
        'updated_at',
    ])
    next_set = ensure_current_set(session)
    record_battle_event(
        session,
        user,
        event_type=BattleEvent.EVENT_SET_START,
        target=BattleEvent.TARGET_GLOBAL,
        payload={'set_number': next_set.set_number},
    )
    return session


def _finish_current_set(session, current_set, winner_side, user=None, forced=False):
    current_set.status = BattleSet.STATUS_FINISHED
    current_set.winner_side = winner_side
    current_set.player1_end_hp = session.player1_hp
    current_set.player2_end_hp = session.player2_hp
    current_set.player1_end_fp = session.player1_fp
    current_set.player2_end_fp = session.player2_fp
    current_set.ended_at = timezone.now()
    if forced and user and user.is_authenticated:
        current_set.forced_by = user
    current_set.save(update_fields=[
        'status',
        'winner_side',
        'player1_end_hp',
        'player2_end_hp',
        'player1_end_fp',
        'player2_end_fp',
        'ended_at',
        'forced_by',
    ])
    record_battle_event(
        session,
        user,
        event_type=BattleEvent.EVENT_SET_REPORT,
        target=winner_side,
        payload={
            'set_number': current_set.set_number,
            'winner_side': winner_side,
            'forced': forced,
        },
    )
    match_finished = _finalize_match_from_sets(session)
    if not match_finished:
        _start_next_set(session, user)
    transaction.on_commit(lambda session_id=session.id: flush_session_events(session_id))
    return session


def report_current_set(session, user=None):
    if not can_report_set(user, session):
        raise PermissionDenied()

    with transaction.atomic():
        locked = BattleSession.objects.select_for_update().get(id=session.id)
        winner_side = _winner_candidate(locked)
        if not winner_side:
            raise ValueError('자동 판정이 어렵습니다. 운영자 판정 또는 서든 데스를 진행해주세요.')
        current_set = ensure_current_set(locked)
        side = _reporting_player_side(user, locked)
        now = timezone.now()
        if side == BattleEvent.TARGET_PLAYER1:
            current_set.player1_confirmed_at = now
            current_set.player1_confirmed_by = user if user and user.is_authenticated else None
        elif side == BattleEvent.TARGET_PLAYER2:
            current_set.player2_confirmed_at = now
            current_set.player2_confirmed_by = user if user and user.is_authenticated else None
        else:
            raise PermissionDenied()
        current_set.save(update_fields=[
            'player1_confirmed_at',
            'player2_confirmed_at',
            'player1_confirmed_by',
            'player2_confirmed_by',
        ])
        record_battle_event(
            locked,
            user,
            event_type=BattleEvent.EVENT_SET_REPORT,
            target=side,
            payload={
                'set_number': current_set.set_number,
                'confirmed': True,
                'winner_candidate': winner_side,
            },
        )
        if current_set.player1_confirmed_at and current_set.player2_confirmed_at:
            _finish_current_set(locked, current_set, winner_side, user)
        return locked


def force_current_set_result(session, winner_side, user=None):
    if not can_force_set_result(user, session):
        raise PermissionDenied()
    if winner_side not in (BattleEvent.TARGET_PLAYER1, BattleEvent.TARGET_PLAYER2):
        raise ValueError('승자를 선택해주세요.')
    with transaction.atomic():
        locked = BattleSession.objects.select_for_update().get(id=session.id)
        current_set = ensure_current_set(locked)
        return _finish_current_set(locked, current_set, winner_side, user, forced=True)


def update_passive(session, target, card_id=None, delta=0, note='', key='', value=None, label='', user=None):
    if target not in (BattleEvent.TARGET_PLAYER1, BattleEvent.TARGET_PLAYER2):
        raise ValueError('대상 플레이어가 올바르지 않습니다.')
    with transaction.atomic():
        locked = BattleSession.objects.select_for_update().get(id=session.id)
        state_field = 'player1_passive_state' if target == BattleEvent.TARGET_PLAYER1 else 'player2_passive_state'
        state = getattr(locked, state_field) or {}
        key = str(key or card_id or 'memo')[:80]
        current = dict(state.get(key, {}))
        if card_id or delta:
            current['count'] = max(0, int(current.get('count', 0)) + int(delta or 0))
        if value is not None:
            current['value'] = value
        if note:
            current['last_note'] = note[:200]
        if label:
            current['label'] = label[:80]
        state[key] = current
        setattr(locked, state_field, state)
        locked.save(update_fields=[state_field, 'updated_at'])
        record_battle_event(
            locked,
            user,
            event_type=BattleEvent.EVENT_PASSIVE,
            target=target,
            amount=int(delta or 0),
            payload={
                'key': key,
                'card_id': card_id,
                'label': label[:80],
                'value': value,
                'note': note[:200],
                'state': current,
            },
        )
        return locked


def perform_session_action(session, body, user=None, control_token=''):
    action = body.get('action', '')

    if action == 'hp':
        if not can_control_session(user, session, control_token):
            raise PermissionDenied()
        session = apply_hp_delta(session, body.get('target'), int(body.get('amount') or 0), user)
    elif action == 'fp':
        if not can_control_session(user, session, control_token):
            raise PermissionDenied()
        session = apply_fp_delta(session, body.get('target'), int(body.get('amount') or 0), user)
    elif action == 'fp_reset':
        if not can_control_session(user, session, control_token):
            raise PermissionDenied()
        session = reset_fp(session, body.get('target'), user)
    elif action == 'undo':
        if not can_control_session(user, session, control_token):
            raise PermissionDenied()
        session = undo_last_hp_event(session, user)
    elif action == 'timer':
        if not can_control_session(user, session, control_token):
            raise PermissionDenied()
        session = start_ten_second_timer(session, user)
    elif action == 'sudden_death':
        if not can_toggle_sudden_death(user, session, control_token):
            raise PermissionDenied()
        session = set_sudden_death(session, bool(body.get('enabled')), user)
    elif action == 'extra_time':
        session = add_extra_time(session, int(body.get('seconds') or 0), user)
    elif action == 'report_set':
        session = report_current_set(session, user)
    elif action == 'force_set_result':
        session = force_current_set_result(session, body.get('winner'), user)
    elif action == 'passive':
        if not can_control_session(user, session, control_token):
            raise PermissionDenied()
        session = update_passive(
            session,
            body.get('target'),
            card_id=body.get('card_id'),
            delta=int(body.get('delta') or 0),
            note=str(body.get('note') or ''),
            key=str(body.get('key') or ''),
            value=body.get('value') if 'value' in body else None,
            label=str(body.get('label') or ''),
            user=user,
        )
    elif action == 'character':
        target = body.get('target')
        if not can_choose_character(user, session, target, control_token):
            raise PermissionDenied()
        try:
            character = Character.objects.get(id=body.get('character_id'))
        except (Character.DoesNotExist, ValueError, TypeError):
            raise ValueError('캐릭터를 찾을 수 없습니다.')
        session = select_character(session, target, character, user)
    else:
        raise ValueError('알 수 없는 요청입니다.')

    return battle_session_queryset().get(id=session.id)


def battle_summary_for_match(match):
    try:
        session = match.battle_session
    except BattleSession.DoesNotExist:
        return None
    set_score = _set_score(session)
    current_set = _current_set(session)
    return {
        'session_id': session.id,
        'view_token': session.view_token,
        'p1_ready': bool(session.player1_character_id),
        'p2_ready': bool(session.player2_character_id),
        'p1_hp': session.player1_hp if session.player1_character_id else None,
        'p2_hp': session.player2_hp if session.player2_character_id else None,
        'p1_initial_hp': session.player1_initial_hp if session.player1_character_id else None,
        'p2_initial_hp': session.player2_initial_hp if session.player2_character_id else None,
        'p1_fp': session.player1_fp if session.player1_character_id else None,
        'p2_fp': session.player2_fp if session.player2_character_id else None,
        'p1_character_img': (
            (session.player1_character.body_img or session.player1_character.sd_img or session.player1_character.img)
            if session.player1_character_id else ''
        ),
        'p2_character_img': (
            (session.player2_character.body_img or session.player2_character.sd_img or session.player2_character.img)
            if session.player2_character_id else ''
        ),
        'p1_hand_limit': hand_limit_for_hp(session.player1_character, session.player1_hp),
        'p2_hand_limit': hand_limit_for_hp(session.player2_character, session.player2_hp),
        'set_number': current_set.set_number if current_set else None,
        'p1_set_score': set_score[BattleEvent.TARGET_PLAYER1],
        'p2_set_score': set_score[BattleEvent.TARGET_PLAYER2],
        'p1_confirmed': bool(current_set and current_set.player1_confirmed_at),
        'p2_confirmed': bool(current_set and current_set.player2_confirmed_at),
        'sudden_death': session.sudden_death,
    }


def serialize_tournament_battle_state(tournament):
    matches = (
        tournament.rounds.prefetch_related(
            'matches__battle_session',
            'matches__battle_session__player1_character',
            'matches__battle_session__player2_character',
        )
        .filter(status='running')
        .first()
    )
    if not matches:
        return {}
    data = {}
    for match in matches.matches.all():
        if match.is_bye:
            continue
        summary = battle_summary_for_match(match)
        if summary:
            data[str(match.id)] = summary
    return data


def cleanup_expired_sessions(now=None):
    now = now or timezone.now()
    standalone_qs = BattleSession.objects.filter(
        session_type=BattleSession.SESSION_STANDALONE,
        expires_at__lte=now,
    )
    standalone_ids = list(standalone_qs.values_list('id', flat=True))
    for session_id in standalone_ids:
        flush_session_events(session_id)
    standalone_deleted, _ = standalone_qs.delete()

    tournament_cutoff = now - TOURNAMENT_SESSION_LIFETIME_AFTER_FINISH
    tournament_qs = BattleSession.objects.filter(
        session_type=BattleSession.SESSION_TOURNAMENT,
        tournament_match__round__tournament__status='finished',
        tournament_match__round__tournament__updated_at__lte=tournament_cutoff,
    )
    tournament_ids = list(tournament_qs.values_list('id', flat=True))
    for session_id in tournament_ids:
        flush_session_events(session_id)
    tournament_deleted, _ = tournament_qs.delete()
    flush_pending_battle_events()
    return standalone_deleted + tournament_deleted
