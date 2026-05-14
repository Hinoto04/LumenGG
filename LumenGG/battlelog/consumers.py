from urllib.parse import parse_qs

from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.core.exceptions import PermissionDenied

from tournament.models import Tournament

from .models import BattleSession
from .realtime import battle_session_group, broadcast_battle_session, tournament_battle_group
from .services import (
    battle_session_queryset,
    perform_session_action,
    serialize_session,
    serialize_tournament_battle_state,
)


def _query_value(scope, key, default=''):
    params = parse_qs(scope.get('query_string', b'').decode('utf-8'))
    values = params.get(key)
    return values[0] if values else default


class BattleSessionConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.view_token = self.scope['url_route']['kwargs']['view_token']
        self.control_token = _query_value(self.scope, 'control_token')
        self.group_name = battle_session_group(self.view_token)

        try:
            self.session = battle_session_queryset().get(view_token=self.view_token)
        except BattleSession.DoesNotExist:
            self.close(code=4404)
            return

        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        self.accept()
        self.send_state()

    def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            async_to_sync(self.channel_layer.group_discard)(self.group_name, self.channel_name)

    def receive_json(self, content, **kwargs):
        message_type = content.get('type')
        request_id = content.get('request_id')

        if message_type == 'state':
            self.send_state(request_id=request_id)
            return

        if message_type != 'action':
            self.send_error('알 수 없는 요청입니다.', request_id=request_id)
            return

        body = dict(content.get('payload') or {})
        body.setdefault('control_token', self.control_token)
        control_token = body.get('control_token', '')

        try:
            session = battle_session_queryset().get(view_token=self.view_token)
            session = perform_session_action(session, body, self.scope.get('user'), control_token)
        except BattleSession.DoesNotExist:
            self.send_error('계산기 세션을 찾을 수 없습니다.', request_id=request_id)
            return
        except PermissionDenied:
            self.send_error('조작 권한이 없습니다.', request_id=request_id)
            return
        except (TypeError, ValueError) as exc:
            self.send_error(str(exc), request_id=request_id)
            return

        self.send_json({'type': 'action_ack', 'request_id': request_id, 'ok': True})
        broadcast_battle_session(session)

    def battle_changed(self, event):
        self.send_state()

    def send_state(self, request_id=None):
        session = battle_session_queryset().get(view_token=self.view_token)
        self.send_json({
            'type': 'state',
            'request_id': request_id,
            'state': serialize_session(
                session,
                self.scope.get('user'),
                self.control_token,
                include_events=False,
            ),
        })

    def send_error(self, message, request_id=None):
        self.send_json({
            'type': 'error',
            'request_id': request_id,
            'ok': False,
            'error': message,
        })


class TournamentBattleStateConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.tournament_id = self.scope['url_route']['kwargs']['tournament_id']
        self.group_name = tournament_battle_group(self.tournament_id)

        if not Tournament.objects.filter(id=self.tournament_id).exists():
            self.close(code=4404)
            return

        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        self.accept()
        self.send_state()

    def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            async_to_sync(self.channel_layer.group_discard)(self.group_name, self.channel_name)

    def receive_json(self, content, **kwargs):
        if content.get('type') == 'state':
            self.send_state()

    def battle_changed(self, event):
        self.send_state()

    def send_state(self):
        tournament = Tournament.objects.get(id=self.tournament_id)
        self.send_json({
            'type': 'state',
            'state': serialize_tournament_battle_state(tournament),
        })
