"""Run AI seats after the human's move has already reached the screens.

The websocket consumer broadcasts a human command first and then calls
``kick_ai``. With ``LUMEN_AI_BACKGROUND`` (default on) the AI thinks in a
background thread, so the human sees the phase/turn change immediately and
can choose their own Ready while the AI evaluates; each AI command is
broadcast as it lands. Before each Ready the AI also "thinks" for a
moment (``LUMEN_AI_READY_DELAY``, default 2~4.5 seconds, at most half the
time left on the Ready clock), so it does not ready the instant the phase
opens. Tests and tools that need the AI to have moved before
the call returns set ``LUMEN_AI_BACKGROUND = False``.

One loop per session runs at a time: a process-local guard plus a cache lock
for multi-process servers. A kick that arrives while a loop is running asks
it to run once more.
"""

import threading

from django.conf import settings
from django.core.cache import cache
from django.db import close_old_connections

from .automatic_services import _ai_roles, advance_ai_session
from .models import LumenSimulatorSession
from .realtime import broadcast_simulator_session

LOCK_SECONDS = 300
_guard = threading.Lock()
_running = set()
_rerun = set()


def _lock_key(session_id):
    return f'battlelog:ai-advance:{session_id}'


def _needs_ai(session):
    return (
        session.mode == LumenSimulatorSession.MODE_AUTOMATIC
        and bool(_ai_roles(session))
        and (session.document or {}).get('preparation', {}).get('status') != 'editing'
    )


def kick_ai(session):
    """Let AI seats act. Returns the session (already advanced when synchronous)."""
    if not _needs_ai(session):
        return session
    if not getattr(settings, 'LUMEN_AI_BACKGROUND', True):
        return advance_ai_session(session, on_command=broadcast_simulator_session)
    with _guard:
        if session.id in _running:
            _rerun.add(session.id)
            return session
        _running.add(session.id)
    threading.Thread(target=_worker, args=(session.id,), daemon=True, name=f'ai-{session.id}').start()
    return session


def _worker(session_id):
    try:
        while True:
            if cache.add(_lock_key(session_id), 1, LOCK_SECONDS):
                try:
                    session = LumenSimulatorSession.objects.select_related('ai_policy').get(pk=session_id)
                    advance_ai_session(session, on_command=broadcast_simulator_session, think=True)
                finally:
                    cache.delete(_lock_key(session_id))
            with _guard:
                if session_id in _rerun:
                    _rerun.discard(session_id)
                    continue
                _running.discard(session_id)
                return
    except Exception:  # noqa: BLE001 - advance_ai_session already reports engine faults
        with _guard:
            _running.discard(session_id)
            _rerun.discard(session_id)
    finally:
        close_old_connections()
