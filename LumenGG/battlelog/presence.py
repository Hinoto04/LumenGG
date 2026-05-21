from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from .models import RealtimePresence


PRESENCE_TTL = timedelta(seconds=90)
BATTLE_ROLES = ('control', 'viewer')
SIMULATOR_ROLES = ('p1', 'p2', 'viewer')


def _roles_for_scope(scope):
    if scope == RealtimePresence.SCOPE_SIMULATOR:
        return SIMULATOR_ROLES
    return BATTLE_ROLES


def cleanup_stale_presence(now=None):
    now = now or timezone.now()
    RealtimePresence.objects.filter(last_seen_at__lt=now - PRESENCE_TTL).delete()


def presence_counts(scope, view_token):
    cleanup_stale_presence()
    roles = _roles_for_scope(scope)
    counts = {role: 0 for role in roles}
    rows = (
        RealtimePresence.objects
        .filter(scope=scope, view_token=view_token, role__in=roles)
        .values('role')
        .annotate(total=Count('id'))
    )
    for row in rows:
        counts[row['role']] = row['total']
    return counts


def battle_presence_counts(view_token):
    return presence_counts(RealtimePresence.SCOPE_BATTLE, view_token)


def simulator_presence_counts(view_token):
    return presence_counts(RealtimePresence.SCOPE_SIMULATOR, view_token)


def register_presence(scope, view_token, role, channel_name):
    now = timezone.now()
    cleanup_stale_presence(now)
    RealtimePresence.objects.update_or_create(
        channel_name=channel_name,
        defaults={
            'scope': scope,
            'view_token': view_token,
            'role': role,
            'last_seen_at': now,
        },
    )
    return presence_counts(scope, view_token)


def touch_presence(channel_name):
    RealtimePresence.objects.filter(channel_name=channel_name).update(last_seen_at=timezone.now())


def unregister_presence(channel_name):
    RealtimePresence.objects.filter(channel_name=channel_name).delete()
