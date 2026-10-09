import copy
import uuid
from django.db import transaction
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from battlelog.models import BattleSession
from battlelog.services import (
    battle_session_queryset, can_control_session, perform_session_action,
    serialize_session, session_is_expired,
)
from battlelog.realtime import broadcast_battle_session, battle_session_group
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import CalculatorReceipt
from .passives import native_passive
from .sync import digest


class StaleCalculator(Exception):
    pass


def mobile_state(session, control_token='', language='ko'):
    state = serialize_session(session, control_token=control_token, include_events=True, language=language)
    if not state['can_control']:
        state.pop('control_url', None)
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
        if session.session_type != BattleSession.SESSION_STANDALONE:
            raise PermissionDenied('Only standalone calculators are supported.')
        if session_is_expired(session):
            raise ValidationError('Calculator session has expired.')
        if not can_control_session(None, session, control_token):
            raise PermissionDenied('A control token is required.')
        existing = CalculatorReceipt.objects.filter(session=session, action_id=action_id).first()
        if existing:
            if existing.request_hash != request_hash:
                raise ValidationError('An action ID cannot be reused with different data.')
            return session
        if body.get('expected_version') != session.version:
            raise StaleCalculator()
        allowed = {'hp', 'fp', 'fp_reset', 'undo', 'timer', 'reset_session', 'sudden_death', 'sudden_turn', 'passive', 'character'}
        if body.get('action') == 'batch':
            actions = body.get('actions')
            if not isinstance(actions, list) or not 1 <= len(actions) <= 100 or any(not isinstance(a, dict) or a.get('action') not in allowed for a in actions):
                raise ValidationError('Invalid calculator batch.')
        elif body.get('action') not in allowed:
            raise ValidationError('Unknown calculator action.')
        session = perform_session_action(session, body, user=user, control_token=control_token)
        CalculatorReceipt.objects.create(session=session, action_id=action_id, request_hash=request_hash)
        transaction.on_commit(lambda: broadcast_battle_session(session))
        return session
