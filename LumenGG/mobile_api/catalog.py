"""Immutable, validated SQLite catalogs published independently of app builds."""
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import uuid
from contextlib import closing
from urllib.parse import urlparse, unquote

import requests
from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from card.models import Card, Character
from card.search import card_search_values
from common.language import translated_card_field, translated_character_field, translated_pack_field, javascript_i18n
from common.text_search import normalize_search_text
from common.localization import clear_localization_cache
from common.language import clear_term_translation_cache
from common.models import SiteSettings
from collection.models import CollectionCard, Pack
from deck.services import get_max_deck_size
from qna.models import QNA
from battlelog.services import character_hand_table, initial_hp_for_character, initial_passive_state_for_character
from .models import CatalogRelease
from .passives import native_passive
from .sync import digest

logger = logging.getLogger(__name__)
LANGUAGES = ('ko', 'en', 'ja')
SCHEMA_VERSION = 1


def read_snapshot():
    # Admin edits happen in another process; clear this publisher's cached
    # translations on every scan, including bulk/import updates.
    clear_localization_cache()
    clear_term_translation_cache()
    rows, relations = [], []
    if connection.vendor == 'mysql' and not connection.in_atomic_block:
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
    with transaction.atomic():
        characters = list(Character.objects.prefetch_related('translations').order_by('id'))
        cards = list(Card.objects.select_related('character').prefetch_related('translations').order_by('id'))
        packs = list(Pack.objects.prefetch_related('translations').order_by('id'))
        for character in characters:
            data = {'id': character.pk, 'color': character.color, 'img': character.body_img or character.img,
                    'img_sm': character.icon_img or character.sd_img or character.img,
                    'hand_table': character_hand_table(character), 'initial_hp': initial_hp_for_character(character),
                    'initial_passive_state': initial_passive_state_for_character(character),
                    'localized': {lang: {**{key: translated_character_field(character, lang, key) for key in ('name', 'description', 'group')},
                                         'passive': native_passive(character, lang)} for lang in LANGUAGES}}
            rows.append(('character', character.pk, data, ''))
        card_fields = ('code', 'character_id', 'frame', 'damage', 'pos', 'body', 'hit', 'guard', 'counter', 'special',
                       'g_top', 'g_mid', 'g_bot', 'type', 'ultimate', 'img', 'img_mid', 'img_sm')
        localized_fields = ('name', 'ruby', 'text', 'detail_text', 'keyword', 'hiddenKeyword', 'search')
        for card in cards:
            data = {'id': card.pk, **{key: getattr(card, key) for key in card_fields},
                    'localized': {lang: {key: translated_card_field(card, lang, key) for key in localized_fields} for lang in LANGUAGES}}
            rows.append(('card', card.pk, data, '\n'.join(normalize_search_text(v) for v in card_search_values(card))))
            relations.append(('card', card.pk, 'character', card.character_id))
        for pack in packs:
            rows.append(('pack', pack.pk, {'id': pack.pk, 'code': pack.code, 'released': pack.released.isoformat() if pack.released else None,
                        'localized': {lang: {'name': translated_pack_field(pack, lang, 'name')} for lang in LANGUAGES}}, ''))
        for item in CollectionCard.objects.order_by('id'):
            data = {key: getattr(item, key) for key in ('id', 'card_id', 'character_id', 'pack_id', 'item_type', 'rare', 'code', 'name', 'image', 'img_sm')}
            rows.append(('collection', item.pk, data, normalize_search_text(item.name + item.code)))
            for field, kind in [('card_id', 'card'), ('character_id', 'character'), ('pack_id', 'pack')]:
                if data[field]:
                    relations.append(('collection', item.pk, kind, data[field]))
        for qna in QNA.objects.prefetch_related('cards').order_by('id'):
            data = {'id': qna.pk, 'title': qna.title, 'question': qna.question, 'answer': qna.answer,
                    'faq': qna.faq, 'tags': qna.tags, 'card_ids': sorted(c.pk for c in qna.cards.all())}
            rows.append(('qna', qna.pk, data, normalize_search_text(' '.join([qna.title, qna.question, qna.answer, qna.tags]))))
            relations.extend(('qna', qna.pk, 'card', pk) for pk in data['card_ids'])
        limits = SiteSettings.objects.filter(name='갯수예외처리카드').values_list('setting', flat=True).first() or {}
        rules = {'max_deck_sizes': {str(c.pk): get_max_deck_size(c.pk) for c in characters},
                 'min_deck_size': 5, 'max_hand': 5, 'max_ultimate': 1, 'copy_limits': limits,
                 'ui': {lang: javascript_i18n(lang) for lang in LANGUAGES}}
        rows.append(('rules', 1, rules, ''))
    keys = {(kind, pk) for kind, pk, _data, _search in rows}
    for a, b, c, d in relations:
        if (a, b) not in keys or (c, d) not in keys:
            raise ValueError('Catalog contains a dangling reference.')
    if not cards or not characters:
        raise ValueError('Refusing to publish an empty card catalog.')
    return rows, relations


def image_asset(url, root):
    if not url or not settings.MOBILE_CATALOG_FETCH_IMAGES:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {'http', 'https'} or parsed.hostname not in settings.MOBILE_IMAGE_ALLOWED_HOSTS:
        return None
    images = root / 'images'
    images.mkdir(parents=True, exist_ok=True)
    cache = root / 'image_sources'
    cache.mkdir(exist_ok=True)
    cache_file = cache / (hashlib.sha256(url.encode()).hexdigest() + '.json')
    cached = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    media_root = Path(settings.MEDIA_ROOT).resolve()
    local = (media_root / unquote(parsed.path).lstrip('/')).resolve()
    content = None
    signature = None
    if local.is_relative_to(media_root) and local.is_file():
        stat = local.stat()
        signature = f'{stat.st_mtime_ns}:{stat.st_size}'
        if cached.get('signature') == signature and (images / cached.get('filename', '')).is_file():
            return cached['filename']
        content = local.read_bytes()
    else:
        headers = {}
        if cached.get('etag'):
            headers['If-None-Match'] = cached['etag']
        elif cached.get('last_modified'):
            headers['If-Modified-Since'] = cached['last_modified']
        with requests.get(url, headers=headers, timeout=(5, 15), stream=True, allow_redirects=False) as response:
            if response.status_code == 304 and (images / cached.get('filename', '')).is_file():
                return cached['filename']
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError('Image redirects are not permitted.')
            if not response.headers.get('Content-Type', '').lower().startswith('image/'):
                raise ValueError('An image URL returned non-image content.')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 20 * 1024 * 1024:
                    raise ValueError('Image exceeds 20 MB.')
                chunks.append(chunk)
            content = b''.join(chunks)
            cached['etag'] = response.headers.get('ETag')
            cached['last_modified'] = response.headers.get('Last-Modified')
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
        suffix = '.webp'
    filename = hashlib.sha256(content).hexdigest() + suffix
    target = images / filename
    if not target.exists():
        tmp = target.with_suffix('.tmp')
        tmp.write_bytes(content)
        os.replace(tmp, target)
    cached.update(filename=filename, signature=signature)
    cache_file.write_text(json.dumps(cached), encoding='utf-8')
    return filename


def publish_catalog():
    root = Path(settings.MOBILE_CATALOG_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    rows, relations = read_snapshot()
    resolved = {}
    for _kind, _pk, data, _search in rows:
        for key in ('img', 'img_mid', 'img_sm', 'image'):
            url = data.get(key)
            if not url:
                continue
            if url not in resolved:
                # Do not silently publish an unchanged URL with stale image bytes.
                resolved[url] = image_asset(url, root)
            if resolved[url]:
                data[key] = '/api/mobile/v1/catalog/images/' + resolved[url]
    source_hash = digest([rows, relations])
    current = CatalogRelease.objects.filter(active=True).first()
    if current and current.source_hash == source_hash:
        return current, False
    version = timezone.now().strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:12]
    filename = version + '.sqlite'
    temporary = root / (filename + '.tmp')
    try:
        with closing(sqlite3.connect(temporary)) as db:
            db.executescript('''
                PRAGMA foreign_keys=ON;
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE entries (kind TEXT NOT NULL, id INTEGER NOT NULL, data TEXT NOT NULL, search TEXT NOT NULL,
                                      PRIMARY KEY (kind,id));
                CREATE TABLE relations (source_kind TEXT, source_id INTEGER, target_kind TEXT, target_id INTEGER,
                    FOREIGN KEY(source_kind,source_id) REFERENCES entries(kind,id),
                    FOREIGN KEY(target_kind,target_id) REFERENCES entries(kind,id));
                CREATE INDEX entries_kind ON entries(kind);
                CREATE INDEX relation_target ON relations(target_kind,target_id);
            ''')
            db.executemany('INSERT INTO metadata VALUES (?,?)', [('schema_version', '1'), ('release_version', version)])
            db.executemany('INSERT INTO entries VALUES (?,?,?,?)', [(k, i, json.dumps(d, ensure_ascii=False, separators=(',', ':')), s) for k, i, d, s in rows])
            db.executemany('INSERT INTO relations VALUES (?,?,?,?)', relations)
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('Invalid SQLite catalog.')
            db.commit()
        content = temporary.read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()
        os.replace(temporary, root / filename)
        with transaction.atomic():
            CatalogRelease.objects.filter(active=True).update(active=False)
            release = CatalogRelease.objects.create(version=version, source_hash=source_hash, sha256=sha256,
                                                    size_bytes=len(content), filename=filename, active=True)
        logger.info('mobile_catalog_published version=%s size=%s', version, len(content))
        return release, True
    finally:
        temporary.unlink(missing_ok=True)


def client_version(value):
    if not re.fullmatch(r'\d+\.\d+\.\d+', value or ''):
        raise ValueError('Invalid client version.')
    return tuple(map(int, value.split('.')))
