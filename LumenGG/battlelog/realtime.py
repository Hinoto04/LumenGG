import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


logger = logging.getLogger(__name__)


def battle_session_group(view_token):
    return f'battle_session_{view_token}'


def tournament_battle_group(tournament_id):
    return f'tournament_battle_{tournament_id}'


def simulator_session_group(view_token):
    return f'lumen_simulator_{view_token}'


def _simulator_event_count(session):
    document = session.document or {}
    events = document.get('events') if isinstance(document, dict) else []
    try:
        archived = max(0, int(document.get('archived_event_count') or 0))
    except (TypeError, ValueError):
        archived = 0
    return archived + (len(events) if isinstance(events, list) else 0)


def broadcast_battle_session(session):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    messages = [
        (battle_session_group(session.view_token), {'type': 'battle.changed'}),
    ]
    if session.tournament_match_id:
        tournament_id = session.tournament_match.round.tournament_id
        messages.append((tournament_battle_group(tournament_id), {'type': 'battle.changed'}))

    for group_name, message in messages:
        try:
            async_to_sync(channel_layer.group_send)(group_name, message)
        except Exception:
            logger.exception('Failed to broadcast battle session update to %s', group_name)


def broadcast_simulator_session(session):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    group_name = simulator_session_group(session.view_token)
    events = ((session.document or {}).get('events') or [])
    latest_event = events[-1] if events else {}
    signal = None
    if latest_event.get('type') == 'signal':
        payload = latest_event.get('payload') or {}
        signal = {
            'id': latest_event.get('id'),
            'actor': latest_event.get('actor'),
            'signal': payload.get('signal'),
            'label': payload.get('label'),
        }
    try:
        async_to_sync(channel_layer.group_send)(group_name, {
            'type': 'simulator.changed',
            'version': session.version,
            'event_count': _simulator_event_count(session),
            'signal': signal,
        })
    except Exception:
        logger.exception('Failed to broadcast simulator update to %s', group_name)
