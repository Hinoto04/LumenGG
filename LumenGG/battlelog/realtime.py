import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


logger = logging.getLogger(__name__)


def battle_session_group(view_token):
    return f'battle_session_{view_token}'


def tournament_battle_group(tournament_id):
    return f'tournament_battle_{tournament_id}'


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
