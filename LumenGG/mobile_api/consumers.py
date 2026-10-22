from channels.generic.websocket import JsonWebsocketConsumer
from asgiref.sync import async_to_sync
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from battlelog.models import BattleSession
from battlelog.services import battle_session_queryset
from battlelog.realtime import battle_session_group
from .calculators import mobile_state, perform_mobile_action, StaleCalculator


class MobileCalculatorConsumer(JsonWebsocketConsumer):
    def connect(self):
        self.view_token = self.scope['url_route']['kwargs']['view_token']
        self.control_token = ''
        self.language = 'ko'
        self.access_token = ''
        self.group_name = battle_session_group(self.view_token)
        self.tournament = BattleSession.objects.filter(view_token=self.view_token, session_type='tournament').exists()
        if not BattleSession.objects.filter(view_token=self.view_token, session_type__in=['standalone', 'party', 'tournament']).exists():
            self.close(code=4404)
            return
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        self.accept()
        if self.tournament:
            self.send_json({'type': 'authentication_required'})
        else:
            self.send_state()

    def current_user(self):
        if not self.tournament:
            return None
        auth = JWTAuthentication()
        return auth.get_user(auth.get_validated_token(self.access_token))

    def disconnect(self, code):
        if hasattr(self, 'group_name'):
            async_to_sync(self.channel_layer.group_discard)(self.group_name, self.channel_name)

    def send_state(self, request_id=None):
        try:
            user = self.current_user()
            session = battle_session_queryset().get(view_token=self.view_token)
            self.send_json({'type': 'state', 'request_id': request_id, 'state': mobile_state(session, self.control_token, self.language, user)})
        except (InvalidToken, TokenError, AuthenticationFailed):
            self.close(code=4401)
        except PermissionDenied:
            self.close(code=4403)

    def receive_json(self, content, **kwargs):
        if not isinstance(content, dict):
            self.close(code=4400)
            return
        request_id = content.get('request_id')
        if content.get('type') == 'authenticate':
            self.control_token = str(content.get('control_token', ''))[:64]
            self.access_token = str(content.get('access_token', ''))[:4096]
            self.language = content.get('language') if content.get('language') in ('ko', 'en', 'ja') else 'ko'
            self.send_state(request_id)
        elif content.get('type') == 'state':
            self.send_state(request_id)
        elif content.get('type') == 'action':
            try:
                user = self.current_user()
                session = perform_mobile_action(self.view_token, content.get('payload'), self.control_token, user)
                self.send_json({'type': 'action_result', 'request_id': request_id, 'ok': True,
                                'state': mobile_state(session, self.control_token, self.language, user)})
            except (InvalidToken, TokenError, AuthenticationFailed):
                self.close(code=4401)
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
