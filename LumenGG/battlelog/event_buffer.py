import json
import logging
import uuid

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import BattleEvent, BattleSession


logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX = 'lumengg:battlelog'
PENDING_TTL_SECONDS = 60 * 60 * 24 * 10

_redis_client = None
_redis_client_url = None


def _actor_payload(user):
    if user and user.is_authenticated:
        return user.id, user.username
    return None, '익명 조작자'


def _redis_url():
    explicit_url = getattr(settings, 'BATTLELOG_REDIS_URL', '').strip()
    if explicit_url:
        return explicit_url
    channel_url = getattr(settings, 'CHANNEL_REDIS_URL', '').strip()
    if channel_url:
        return channel_url
    if getattr(settings, 'USE_IN_MEMORY_CHANNEL_LAYER', False):
        return ''
    return 'redis://127.0.0.1:6379/0'


def _get_redis_client():
    global _redis_client, _redis_client_url

    url = _redis_url()
    if not url:
        return None
    if _redis_client is not None and _redis_client_url == url:
        return _redis_client

    try:
        from redis import Redis
    except ImportError:
        logger.warning('redis package is not available; battle events will be stored directly in DB.')
        return None

    _redis_client_url = url
    _redis_client = Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=0.2,
        socket_timeout=0.6,
    )
    return _redis_client


def _pending_events_key(session_id):
    return f'{REDIS_KEY_PREFIX}:session:{session_id}:events'


def _pending_sessions_key():
    return f'{REDIS_KEY_PREFIX}:pending_sessions'


def _serialize_datetime(value):
    if not value:
        return timezone.now().isoformat()
    return normalize_event_datetime(value).isoformat()


def _parse_datetime(value):
    if not value:
        return timezone.now()
    parsed = parse_datetime(str(value))
    if parsed is None:
        return timezone.now()
    return normalize_event_datetime(parsed)


def normalize_event_datetime(value):
    if not value:
        return timezone.now()
    if settings.USE_TZ:
        if timezone.is_naive(value):
            return timezone.make_aware(value, timezone.get_current_timezone())
        return value
    if timezone.is_aware(value):
        return timezone.make_naive(value, timezone.get_current_timezone())
    return value


def _event_record_to_model_kwargs(record):
    return {
        'session_id': int(record['session_id']),
        'event_uid': record.get('event_uid'),
        'actor_id': record.get('actor_id'),
        'actor_label': record.get('actor_label') or '',
        'event_type': record.get('event_type') or BattleEvent.EVENT_HP,
        'target': record.get('target') or BattleEvent.TARGET_GLOBAL,
        'amount': record.get('amount'),
        'hp_before': record.get('hp_before'),
        'hp_after': record.get('hp_after'),
        'payload': record.get('payload') or {},
        'undone': bool(record.get('undone')),
        'created_at': _parse_datetime(record.get('created_at')),
    }


def _create_db_event_from_record(record, undone_event_id=None):
    kwargs = _event_record_to_model_kwargs(record)
    if undone_event_id:
        kwargs['undone_event_id'] = undone_event_id
    return BattleEvent.objects.create(**kwargs)


def _safe_load_record(raw_value):
    try:
        record = json.loads(raw_value)
    except (TypeError, ValueError):
        return None
    if not isinstance(record, dict) or not record.get('event_uid') or not record.get('session_id'):
        return None
    return record


def _event_model_to_payload(event):
    return {
        'id': event.id,
        'event_uid': event.event_uid,
        'type': event.event_type,
        'target': event.target,
        'amount': event.amount,
        'hp_before': event.hp_before,
        'hp_after': event.hp_after,
        'actor': event.actor_label,
        'payload': event.payload,
        'undone': event.undone,
        'created_at': event.created_at.isoformat(),
    }


def _event_record_to_payload(record):
    return {
        'id': f'pending:{record.get("event_uid")}',
        'event_uid': record.get('event_uid'),
        'type': record.get('event_type'),
        'target': record.get('target'),
        'amount': record.get('amount'),
        'hp_before': record.get('hp_before'),
        'hp_after': record.get('hp_after'),
        'actor': record.get('actor_label') or '',
        'payload': record.get('payload') or {},
        'undone': bool(record.get('undone')),
        'created_at': record.get('created_at') or timezone.now().isoformat(),
    }


def _payload_sort_key(payload):
    return _parse_datetime(payload.get('created_at'))


def pending_event_records(session_id):
    client = _get_redis_client()
    if client is None:
        return []
    try:
        raw_events = client.lrange(_pending_events_key(session_id), 0, -1)
    except Exception:
        logger.exception('Failed to load pending battle events for session %s.', session_id)
        return []
    return [record for record in (_safe_load_record(raw) for raw in raw_events) if record]


def recent_battle_event_payloads(session_id, limit=50):
    db_events = BattleEvent.objects.filter(session_id=session_id).order_by('-created_at', '-id')[:limit]
    payloads = [_event_model_to_payload(event) for event in db_events]
    payloads.extend(_event_record_to_payload(record) for record in pending_event_records(session_id))
    payloads.sort(key=_payload_sort_key, reverse=True)
    return payloads[:limit]


def has_pending_event(session_id, event_type, target=''):
    for record in reversed(pending_event_records(session_id)):
        if record.get('event_type') != event_type:
            continue
        if target and record.get('target') != target:
            continue
        return True
    return False


def latest_pending_event(session_id, event_type, target=''):
    for record in reversed(pending_event_records(session_id)):
        if record.get('event_type') != event_type or record.get('undone'):
            continue
        if target and record.get('target') != target:
            continue
        return record
    return None


def mark_pending_event_undone(session_id, event_uid):
    client = _get_redis_client()
    if client is None or not event_uid:
        return None

    key = _pending_events_key(session_id)
    try:
        raw_events = client.lrange(key, 0, -1)
        for index, raw_event in enumerate(raw_events):
            record = _safe_load_record(raw_event)
            if not record or record.get('event_uid') != event_uid:
                continue
            record['undone'] = True
            client.lset(key, index, json.dumps(record, ensure_ascii=False, separators=(',', ':')))
            return record
    except Exception:
        logger.exception('Failed to mark pending battle event %s as undone.', event_uid)
    return None


def record_battle_event(
    session,
    user=None,
    event_type='',
    target=BattleEvent.TARGET_GLOBAL,
    amount=None,
    hp_before=None,
    hp_after=None,
    payload=None,
    undone=False,
    undone_event=None,
    undone_event_uid='',
    created_at=None,
):
    actor_id, actor_label = _actor_payload(user)
    created_at = created_at or timezone.now()
    record = {
        'event_uid': str(uuid.uuid4()),
        'session_id': session.id if isinstance(session, BattleSession) else int(session),
        'actor_id': actor_id,
        'actor_label': actor_label,
        'event_type': event_type,
        'target': target,
        'amount': amount,
        'hp_before': hp_before,
        'hp_after': hp_after,
        'payload': payload or {},
        'undone': bool(undone),
        'undone_event_id': undone_event.id if undone_event else None,
        'undone_event_uid': undone_event_uid,
        'created_at': _serialize_datetime(created_at),
    }
    if undone_event_uid:
        record['payload'] = dict(record['payload'])
        record['payload']['undone_event_uid'] = undone_event_uid

    client = _get_redis_client()
    if client is not None:
        try:
            key = _pending_events_key(record['session_id'])
            serialized = json.dumps(record, ensure_ascii=False, separators=(',', ':'))
            pipeline = client.pipeline()
            pipeline.rpush(key, serialized)
            pipeline.sadd(_pending_sessions_key(), record['session_id'])
            pipeline.expire(key, PENDING_TTL_SECONDS)
            pipeline.execute()
            return record
        except Exception:
            logger.exception('Failed to buffer battle event in Redis; storing directly in DB.')

    return _create_db_event_from_record(record, undone_event_id=record.get('undone_event_id'))


def _pending_session_ids():
    client = _get_redis_client()
    if client is None:
        return []
    try:
        return [int(session_id) for session_id in client.smembers(_pending_sessions_key())]
    except Exception:
        logger.exception('Failed to load pending battle event session ids.')
        return []


def flush_session_events(session_id):
    client = _get_redis_client()
    if client is None:
        return 0

    key = _pending_events_key(session_id)
    try:
        raw_events = client.lrange(key, 0, -1)
    except Exception:
        logger.exception('Failed to read pending battle events for flush.')
        return 0

    records = [record for record in (_safe_load_record(raw) for raw in raw_events) if record]
    if not records:
        try:
            client.srem(_pending_sessions_key(), session_id)
        except Exception:
            logger.exception('Failed to clear empty pending battle event session id.')
        return 0

    if not BattleSession.objects.filter(id=session_id).exists():
        try:
            client.delete(key)
            client.srem(_pending_sessions_key(), session_id)
        except Exception:
            logger.exception('Failed to clear pending battle events for missing session %s.', session_id)
        return 0

    event_uids = [record['event_uid'] for record in records if record.get('event_uid')]
    existing_uids = set(
        BattleEvent.objects.filter(event_uid__in=event_uids).values_list('event_uid', flat=True)
    )
    events = [
        BattleEvent(**_event_record_to_model_kwargs(record))
        for record in records
        if record.get('event_uid') not in existing_uids
    ]

    if events:
        BattleEvent.objects.bulk_create(events, ignore_conflicts=True)

    uid_to_id = dict(
        BattleEvent.objects.filter(event_uid__in=event_uids).values_list('event_uid', 'id')
    )
    for record in records:
        event_uid = record.get('event_uid')
        undone_event_uid = record.get('undone_event_uid') or (record.get('payload') or {}).get('undone_event_uid')
        if not event_uid or not undone_event_uid:
            continue
        event_id = uid_to_id.get(event_uid)
        undone_event_id = uid_to_id.get(undone_event_uid)
        if event_id and undone_event_id:
            BattleEvent.objects.filter(id=event_id, undone_event_id__isnull=True).update(undone_event_id=undone_event_id)

    try:
        client.delete(key)
        client.srem(_pending_sessions_key(), session_id)
    except Exception:
        logger.exception('Failed to clear flushed battle event Redis keys.')

    return len(events)


def flush_pending_battle_events(limit=None):
    total = 0
    session_ids = _pending_session_ids()
    if limit:
        session_ids = session_ids[:int(limit)]
    for session_id in session_ids:
        total += flush_session_events(session_id)
    return total
