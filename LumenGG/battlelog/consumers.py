import time
from collections import deque
from urllib.parse import parse_qs

from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.core.exceptions import PermissionDenied

from common.language import normalize_language, ui_text
from tournament.models import Tournament

from .automatic_services import (
    AutomaticRuntimeFailure,
    advance_ai_session,
    perform_automatic_command,
    reconcile_automatic_session,
)
from .game.engine import IllegalAction, StaleState
from .models import BattleSession, LumenSimulatorSession
from .presence import (
    battle_presence_counts,
    register_presence,
    simulator_presence_counts,
    touch_presence,
    unregister_presence,
)
from .realtime import (
    battle_session_group,
    broadcast_battle_session,
    broadcast_simulator_session,
    simulator_session_group,
    tournament_battle_group,
)
from .services import (
    battle_session_queryset,
    can_control_session,
    perform_session_action,
    serialize_session,
    serialize_tournament_battle_state,
)
from .simulator_services import (
    perform_simulator_action,
    role_for_token,
    serialize_simulator_events_since,
    serialize_simulator_session,
    simulator_queryset,
)


def _query_value(scope, key, default=''):
    params = parse_qs(scope.get('query_string', b'').decode('utf-8'))
    values = params.get(key)
    return values[0] if values else default


class RequestRateWarningMixin:
    RATE_WINDOW_SECONDS = 10
    MESSAGE_WARNING_LIMIT = 80
    ACTION_WARNING_LIMIT = 20
    WARNING_COOLDOWN_SECONDS = 10

    def init_rate_warning(self):
        self._rate_warning_messages = deque()
        self._rate_warning_actions = deque()
        self._rate_warning_last_sent_at = 0

    def maybe_send_rate_warning(self, message_type):
        now = time.monotonic()
        self._trim_rate_window(self._rate_warning_messages, now)
        self._rate_warning_messages.append(now)
        if message_type in {'action', 'command'}:
            self._trim_rate_window(self._rate_warning_actions, now)
            self._rate_warning_actions.append(now)

        if now - self._rate_warning_last_sent_at < self.WARNING_COOLDOWN_SECONDS:
            return
        if len(self._rate_warning_actions) > self.ACTION_WARNING_LIMIT:
            self._rate_warning_last_sent_at = now
            self.send_warning('조작 요청이 너무 빠르게 반복되고 있습니다. 잠시 천천히 조작해주세요.')
            return
        if len(self._rate_warning_messages) > self.MESSAGE_WARNING_LIMIT:
            self._rate_warning_last_sent_at = now
            self.send_warning('요청이 너무 빠르게 반복되고 있습니다. 잠시 기다려주세요.')

    def _trim_rate_window(self, queue, now):
        cutoff = now - self.RATE_WINDOW_SECONDS
        while queue and queue[0] < cutoff:
            queue.popleft()

    def send_warning(self, message):
        self.send_json({
            'type': 'warning',
            'message': ui_text(message, self.language),
        })


class BattleSessionConsumer(RequestRateWarningMixin, JsonWebsocketConsumer):
    def connect(self):
        self.view_token = self.scope['url_route']['kwargs']['view_token']
        self.control_token = _query_value(self.scope, 'control_token')
        self.language = normalize_language(_query_value(self.scope, 'language'))
        self.group_name = battle_session_group(self.view_token)
        self.init_rate_warning()

        try:
            self.session = battle_session_queryset().get(view_token=self.view_token)
        except BattleSession.DoesNotExist:
            self.close(code=4404)
            return

        self.presence_role = (
            'control'
            if can_control_session(self.scope.get('user'), self.session, self.control_token)
            else 'viewer'
        )
        register_presence('battle', self.view_token, self.presence_role, self.channel_name)
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        self.accept()
        self.send_state()
        self.broadcast_presence()

    def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            unregister_presence(self.channel_name)
            async_to_sync(self.channel_layer.group_discard)(self.group_name, self.channel_name)
            self.broadcast_presence()

    def receive_json(self, content, **kwargs):
        message_type = content.get('type')
        request_id = content.get('request_id')
        self.maybe_send_rate_warning(message_type)

        if message_type == 'state':
            self.send_state(request_id=request_id)
            return
        if message_type == 'presence':
            touch_presence(self.channel_name)
            self.send_presence()
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

    def presence_changed(self, event):
        self.send_presence()

    def broadcast_presence(self):
        async_to_sync(self.channel_layer.group_send)(self.group_name, {'type': 'presence.changed'})

    def send_presence(self):
        self.send_json({
            'type': 'presence',
            'presence': battle_presence_counts(self.view_token),
        })

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
                language=self.language,
            ),
        })

    def send_error(self, message, request_id=None):
        self.send_json({
            'type': 'error',
            'request_id': request_id,
            'ok': False,
            'error': ui_text(message, self.language),
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


class LumenSimulatorConsumer(RequestRateWarningMixin, JsonWebsocketConsumer):
    def connect(self):
        self.view_token = self.scope['url_route']['kwargs']['view_token']
        self.seat = _query_value(self.scope, 'seat')
        self.seat_token = _query_value(self.scope, 'seat_token')
        self.language = normalize_language(_query_value(self.scope, 'language'))
        self.group_name = simulator_session_group(self.view_token)
        self.log_subscribed = False
        self.log_since_seq = 0
        self.init_rate_warning()

        try:
            self.session = simulator_queryset().get(view_token=self.view_token)
        except LumenSimulatorSession.DoesNotExist:
            self.close(code=4404)
            return

        role = role_for_token(self.session, self.seat, self.seat_token)
        self.presence_role = role if role in ('p1', 'p2') else 'viewer'
        register_presence('simulator', self.view_token, self.presence_role, self.channel_name)
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        self.accept()
        self.send_state()
        self.broadcast_presence()

    def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            unregister_presence(self.channel_name)
            async_to_sync(self.channel_layer.group_discard)(self.group_name, self.channel_name)
            self.broadcast_presence()

    def receive_json(self, content, **kwargs):
        message_type = content.get('type')
        request_id = content.get('request_id')
        self.maybe_send_rate_warning(message_type)

        if message_type == 'state':
            self.send_state(request_id=request_id)
            return
        if message_type == 'presence':
            touch_presence(self.channel_name)
            self.send_presence()
            return
        if message_type == 'log_subscribe':
            self.log_subscribed = True
            self.log_since_seq = self._safe_int(content.get('since_seq'))
            self.send_log_events(self.log_since_seq)
            return
        if message_type == 'log_unsubscribe':
            self.log_subscribed = False
            return

        if message_type not in {'action', 'command'}:
            self.send_error('알 수 없는 요청입니다.', request_id=request_id)
            return

        body = dict(content.get('payload') or {})
        body.setdefault('seat', self.seat)
        body.setdefault('seat_token', self.seat_token)

        try:
            session = simulator_queryset().get(view_token=self.view_token)
            if message_type == 'command':
                was_automatic = session.mode == LumenSimulatorSession.MODE_AUTOMATIC
                session = reconcile_automatic_session(session, both_players_disconnected=False)
                if was_automatic and session.mode != LumenSimulatorSession.MODE_AUTOMATIC:
                    self.send_error(
                        '타이머 정산 오류로 세션을 수동 모드로 전환했습니다.',
                        request_id=request_id, code='automatic_fallback',
                    )
                    broadcast_simulator_session(session)
                    return
                session = perform_automatic_command(session, body)
                session = advance_ai_session(session)
            else:
                session = perform_simulator_action(session, body)
        except LumenSimulatorSession.DoesNotExist:
            self.send_error('시뮬레이터 세션을 찾을 수 없습니다.', request_id=request_id)
            return
        except PermissionDenied:
            self.send_error('조작 권한이 없습니다.', request_id=request_id)
            return
        except StaleState as exc:
            latest = simulator_queryset().get(view_token=self.view_token)
            self.send_error(
                str(exc), request_id=request_id, code='stale_state',
                state=serialize_simulator_session(
                    latest, self.seat, self.seat_token,
                    language=self.language, include_events=False,
                ),
            )
            return
        except IllegalAction as exc:
            self.send_error(str(exc), request_id=request_id, code='illegal_action')
            return
        except AutomaticRuntimeFailure as exc:
            self.send_error(str(exc), request_id=request_id, code='automatic_fallback')
            session = simulator_queryset().get(view_token=self.view_token)
            broadcast_simulator_session(session)
            return
        except (TypeError, ValueError) as exc:
            self.send_error(str(exc), request_id=request_id)
            return

        self.send_json({'type': f'{message_type}_ack', 'request_id': request_id, 'ok': True})
        broadcast_simulator_session(session)

    def simulator_changed(self, event):
        signal = event.get('signal')
        if signal:
            self.send_json({
                'type': 'signal',
                'id': signal.get('id'),
                'actor': signal.get('actor'),
                'signal': signal.get('signal'),
                'label': ui_text(signal.get('label') or '', self.language),
            })
        self.send_json({
            'type': 'state_dirty',
            'version': event.get('version'),
            'event_count': event.get('event_count'),
        })
        if self.log_subscribed:
            self.send_log_events(self.log_since_seq)

    def presence_changed(self, event):
        self.send_presence()

    def broadcast_presence(self):
        async_to_sync(self.channel_layer.group_send)(self.group_name, {'type': 'presence.changed'})

    def send_presence(self):
        self.send_json({
            'type': 'presence',
            'presence': simulator_presence_counts(self.view_token),
        })

    def send_state(self, request_id=None):
        session = simulator_queryset().get(view_token=self.view_token)
        if self.presence_role in ('p1', 'p2'):
            was_automatic = session.mode == LumenSimulatorSession.MODE_AUTOMATIC
            session = reconcile_automatic_session(session, both_players_disconnected=False)
            if session.mode == LumenSimulatorSession.MODE_AUTOMATIC:
                session = advance_ai_session(session)
            if was_automatic and session.mode != LumenSimulatorSession.MODE_AUTOMATIC:
                broadcast_simulator_session(session)
        self.send_json({
            'type': 'state',
            'request_id': request_id,
            'state': serialize_simulator_session(session, self.seat, self.seat_token, language=self.language, include_events=False),
        })

    def send_log_events(self, since_seq=0):
        try:
            session = simulator_queryset().get(view_token=self.view_token)
        except LumenSimulatorSession.DoesNotExist:
            return
        payload = serialize_simulator_events_since(
            session,
            self.seat,
            self.seat_token,
            since_seq=since_seq,
            language=self.language,
        )
        self.log_since_seq = self._safe_int(payload.get('event_count'))
        if payload.get('events') or payload.get('reset'):
            self.send_json({
                'type': 'log_events',
                **payload,
            })

    @staticmethod
    def _safe_int(value):
        try:
            return max(0, int(value or 0))
        except (TypeError, ValueError):
            return 0

    def send_error(self, message, request_id=None, code=None, state=None):
        payload = {
            'type': 'error',
            'request_id': request_id,
            'ok': False,
            'error': ui_text(message, self.language),
        }
        if code:
            payload['code'] = code
        if state is not None:
            payload['state'] = state
        self.send_json(payload)
