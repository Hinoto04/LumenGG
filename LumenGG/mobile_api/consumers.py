from channels.generic.websocket import JsonWebsocketConsumer
from asgiref.sync import async_to_sync
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from battlelog.models import BattleSession
from battlelog.services import battle_session_queryset
from battlelog.realtime import battle_session_group
from .calculators import mobile_state, perform_mobile_action, StaleCalculator


class MobileCalculatorConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.view_token = self.scope['url_route']['kwargs']['view_token']
        self.control_token = ''
        self.language = 'ko'
        self.group_name = battle_session_group(self.view_token)
        if not BattleSession.objects.filter(view_token=self.view_token, session_type='standalone').exists():
            self.close(code=4404)
            return
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        self.accept()
        self.send_state()

    def disconnect(self, code):
        if hasattr(self, 'group_name'):
            async_to_sync(self.channel_layer.group_discard)(self.group_name, self.channel_name)

    def send_state(self, request_id=None):
        session = battle_session_queryset().get(view_token=self.view_token)
        self.send_json({'type': 'state', 'request_id': request_id, 'state': mobile_state(session, self.control_token, self.language)})

    def receive_json(self, content, **kwargs):
        if not isinstance(content, dict):
            self.close(code=4400)
            return
        request_id = content.get('request_id')
        if content.get('type') == 'authenticate':
            self.control_token = str(content.get('control_token', ''))[:64]
            self.language = content.get('language') if content.get('language') in ('ko', 'en', 'ja') else 'ko'
            self.send_state(request_id)
        elif content.get('type') == 'state':
            self.send_state(request_id)
        elif content.get('type') == 'action':
            try:
                session = perform_mobile_action(self.view_token, content.get('payload'), self.control_token)
                self.send_json({'type': 'action_result', 'request_id': request_id, 'ok': True,
                                'state': mobile_state(session, self.control_token, self.language)})
            except StaleCalculator:
                self.send_json({'type': 'error', 'request_id': request_id, 'code': 'stale_state'})
                self.send_state()
            except (PermissionDenied, ValidationError, ValueError, TypeError) as exc:
                self.send_json({'type': 'error', 'request_id': request_id, 'error': str(exc)})
        else:
            self.send_json({'type': 'error', 'request_id': request_id, 'error': 'Unknown message type.'})

    def battle_changed(self, event):
        self.send_state()

    def battle_session_presence(self, event):
        pass

    def presence_changed(self, event):
        pass
