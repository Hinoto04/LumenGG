import copy
import uuid
import secrets
from django.db import transaction
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from battlelog.models import BattleSession
from battlelog.services import (
    battle_session_queryset, can_control_session, perform_session_action,
    serialize_session, session_is_expired,
    is_match_player, can_report_set, character_options_for_session,
)
from battlelog.realtime import broadcast_battle_session, battle_session_group
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import CalculatorReceipt
from .passives import native_passive
from .sync import digest


class StaleCalculator(Exception):
    pass


def require_tournament_player(session, user):
    if session.session_type == BattleSession.SESSION_TOURNAMENT and (
        not user or not user.is_authenticated or not is_match_player(user, session.tournament_match)
    ):
        raise PermissionDenied('자신의 경기만 이용할 수 있습니다.')


def mobile_state(session, control_token='', language='ko', user=None):
    require_tournament_player(session, user)
    state = serialize_session(session, user=user, control_token=control_token, include_events=True, language=language)
    tournament = session.session_type == BattleSession.SESSION_TOURNAMENT
    if not state['can_control'] or tournament:
        state.pop('control_url', None)
    if tournament:
        match = session.tournament_match
        state['tournament'].update({'match_status': match.status, 'round_number': match.round.number, 'table': match.table_label})
        state['character_choices'] = character_options_for_session(session, user, language=language)
        if match.round.tournament.status != 'running':
            state['can_control'] = state['set']['can_report'] = False
    for target, field in [('p1', 'player1_character'), ('p2', 'player2_character')]:
        character = getattr(session, field)
        if character and state['players'][target]['character']:
            state['players'][target]['character'].pop('passive_ui', None)
            state['players'][target]['character']['passive'] = native_passive(character, language)
    return state


def perform_mobile_action(view_token, body, control_token='', user=None):
    if not isinstance(body, dict):
        raise ValidationError('Invalid calculator action.')
    try:
        action_id = uuid.UUID(str(body['action_id']))
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ValidationError('A valid action ID is required.')
    payload = copy.deepcopy(body)
    payload.pop('control_token', None)
    request_hash = digest(payload)
    with transaction.atomic():
        locked = BattleSession.objects.select_for_update().get(view_token=view_token)
        session = battle_session_queryset().get(pk=locked.pk)
        tournament = session.session_type == BattleSession.SESSION_TOURNAMENT
        if tournament:
            request_hash = digest({'user_id': getattr(user, 'pk', None), 'action': payload})
        if session.session_type not in (BattleSession.SESSION_STANDALONE, BattleSession.SESSION_PARTY, BattleSession.SESSION_TOURNAMENT):
            raise PermissionDenied('Only standalone calculators are supported.')
        if session_is_expired(session):
            raise ValidationError('Calculator session has expired.')
        require_tournament_player(session, user)
        if not tournament and (not control_token or not secrets.compare_digest(control_token, session.control_token)):
            raise PermissionDenied('A control token is required.')
        existing = CalculatorReceipt.objects.filter(session=session, action_id=action_id).first()
        if existing:
            if existing.request_hash != request_hash:
                raise ValidationError('An action ID cannot be reused with different data.')
            return session
        if tournament and session.tournament_match.round.tournament.status != 'running':
            raise PermissionDenied('종료된 대회입니다.')
        if not can_control_session(user, session, control_token) and not (tournament and body.get('action') == 'report_set' and can_report_set(user, session)):
            raise PermissionDenied('A control token is required.')
        if body.get('expected_version') != session.version:
            raise StaleCalculator()
        allowed = {'hp', 'fp', 'fp_reset', 'shield', 'shield_reset', 'undo', 'timer', 'reset_session', 'sudden_death', 'sudden_turn', 'passive', 'character', 'party_exchange'}
        if tournament:
            allowed = (allowed - {'reset_session', 'party_exchange'}) | {'report_set'}
        if body.get('action') == 'batch':
            actions = body.get('actions')
            if not isinstance(actions, list) or not 1 <= len(actions) <= 100 or any(not isinstance(a, dict) or a.get('action') not in allowed for a in actions):
                raise ValidationError('Invalid calculator batch.')
        elif body.get('action') not in allowed:
            raise ValidationError('Unknown calculator action.')
        if tournament:
            rows = body['actions'] if body.get('action') == 'batch' else [body]
            for row in rows:
                if row.get('action') == 'report_set' and body.get('action') == 'batch':
                    raise ValidationError('세트 확인은 다른 입력과 별도로 진행해주세요.')
                if row.get('action') == 'character':
                    choice = character_options_for_session(session, user).get(row.get('target'), {})
                    if not choice.get('can_choose') or row.get('character_id') not in [c['id'] for c in choice.get('options', [])]:
                        raise PermissionDenied('제출한 덱의 캐릭터만 선택할 수 있습니다.')
        session = perform_session_action(session, body, user=user, control_token=control_token)
        CalculatorReceipt.objects.create(session=session, action_id=action_id, request_hash=request_hash)
        transaction.on_commit(lambda: broadcast_battle_session(session))
        return session
