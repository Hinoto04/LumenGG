import threading
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone

from .services import cleanup_expired_sessions


class ExpiredBattleSessionCleanupMiddleware:
    _lock = threading.Lock()
    _next_cleanup_at = None

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self.cleanup_if_due()
        return self.get_response(request)

    @classmethod
    def cleanup_interval(cls):
        raw_seconds = getattr(settings, 'BATTLELOG_EXPIRED_SESSION_CLEANUP_INTERVAL_SECONDS', 300)
        try:
            seconds = max(1, int(raw_seconds))
        except (TypeError, ValueError):
            seconds = 300
        return timedelta(seconds=seconds)

    @classmethod
    def cleanup_if_due(cls):
        now = timezone.now()
        if cls._next_cleanup_at and cls._next_cleanup_at > now:
            return
        if not cls._lock.acquire(blocking=False):
            return
        try:
            now = timezone.now()
            if cls._next_cleanup_at and cls._next_cleanup_at > now:
                return
            cls._next_cleanup_at = now + cls.cleanup_interval()
            try:
                cleanup_expired_sessions(now)
            except DatabaseError:
                return
        finally:
            cls._lock.release()
