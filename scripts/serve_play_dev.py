"""Isolated game server for play/ development. Only writes under .temp/play-dev/.

The configured (possibly production) database is never opened here. Data comes
from a bundle exported read-only by ``manage.py export_play_bundle``; it is
loaded into a separate SQLite file with the test settings.

    .venv/Scripts/python.exe scripts/serve_play_dev.py [--reset] [--port 8874]

The game client is served at /battlelog/play/ (built bundle) or by Vite on
127.0.0.1:5175, which proxies /battlelog, /ws, /static and /play-dev here.
Dev-only endpoint: GET /play-dev/login/ logs in as the owner of the dev decks.
"""
import argparse
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
directory = root / '.temp/play-dev'
parser = argparse.ArgumentParser()
parser.add_argument('--bundle', default=str(directory / 'bundle.json'))
parser.add_argument('--port', type=int, default=8874)
parser.add_argument('--reset', action='store_true', help='SQLite 파일을 지우고 묶음을 다시 읽는다')
args = parser.parse_args()

bundle_path = Path(args.bundle)
if not bundle_path.exists():
    sys.exit(f'{bundle_path}가 없습니다. scripts/serve-play-dev.ps1로 실행하면 먼저 export_play_bundle이 묶음을 만듭니다.')

directory.mkdir(parents=True, exist_ok=True)
database = directory / 'play.sqlite'
if args.reset and database.exists():
    database.unlink()

os.environ['DJANGO_SETTINGS_MODULE'] = 'LumenGG.test_settings'
os.environ['LUMENGG_TEST_SQLITE_PATH'] = str(database)
sys.path.insert(0, str(root / 'LumenGG'))
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from django.core import serializers  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db import connection, transaction  # noqa: E402

# Daphne handles WebSocket commands and HTTP requests in parallel threads.
# Wait for SQLite locks instead of failing (which would push an automatic
# match into manual fallback), and let readers work during a write (WAL).
connection.settings_dict.setdefault('OPTIONS', {})['timeout'] = 30

# The guard that matters: refuse to run against anything but our SQLite file.
if connection.vendor != 'sqlite' or Path(connection.settings_dict['NAME']).resolve() != database.resolve():
    sys.exit(f'격리된 SQLite가 아닌 DB에 연결되어 중단합니다: {connection.settings_dict["NAME"]}')

with connection.cursor() as cursor:
    cursor.execute('PRAGMA journal_mode=WAL')
call_command('migrate', interactive=False, verbosity=0)
settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
# Vite(5175)가 프록시한 POST도 받는다. 운영에서는 같은 출처라 필요 없다.
settings.CSRF_TRUSTED_ORIGINS = ['http://127.0.0.1:5175', 'http://localhost:5175']

from django.contrib.auth.models import User  # noqa: E402
from django.contrib.auth import login  # noqa: E402
from django.http import HttpResponseRedirect  # noqa: E402
from django.urls import path  # noqa: E402

from battlelog.game.card_identity import is_passive_card  # noqa: E402
from battlelog.models import RulesetRelease, SimulatorAIPolicy  # noqa: E402
from card.models import Card  # noqa: E402
from common.models import SiteSettings  # noqa: E402
from deck.models import CardInDeck, Deck, Regulation, RegulationVersion, ReserveCardInDeck  # noqa: E402
from deck.regulations import DEFAULT_RULES  # noqa: E402

DEV_USER = 'play-dev'
# 교체 편집을 시험하는 레귤레이션. 실제 공개 덱에는 아직 교체 덱이 없어 개발 서버에서 만든다.
SWAP_RULES = {
    **DEFAULT_RULES, 'reserve_limit': 5,
    'technique_swap_limit': 2, 'trait_swap_limit': 1, 'ultimate_swap_limit': 1,
}


def _save_rows(rows):
    for item in serializers.deserialize('python', rows, ignorenonexistent=True):
        item.save()


def _swap_deck(user, source, released_codes, version):
    """Copy of a source deck with reserve cards of the same character and a swap regulation."""
    deck = Deck.objects.create(
        name=f'{source["name"]} (교체 시험)', author=user, character_id=source['character_id'],
        trait_card_id=source['trait_card_id'], regulation_version=version,
        visibility=Deck.VISIBILITY_PUBLIC, schema_version=2,
        description=f'source deck {source["source_id"]} + reserve',
    )
    CardInDeck.objects.bulk_create([
        CardInDeck(deck=deck, card_id=entry['card_id'], count=entry['count'], hand=entry['hand'], side=entry['side'])
        for entry in source['cards']
    ])
    used = {entry['card_id'] for entry in source['cards']} | {source['trait_card_id']}
    pool = [
        card for card in Card.objects.filter(character_id=source['character_id']).order_by('code')
        if card.pk not in used and card.code in released_codes
    ]
    picks = [card for card in pool if not card.ultimate and not is_passive_card(card)
             and any(kind in (card.type or '') for kind in ('공격', '수비', '특수'))][:3]
    picks += [card for card in pool if is_passive_card(card)][:1]
    picks += [card for card in pool if card.ultimate][:1]
    ReserveCardInDeck.objects.bulk_create([ReserveCardInDeck(deck=deck, card=card, count=1) for card in picks])


def load_bundle():
    bundle = json.loads(bundle_path.read_text(encoding='utf-8'))
    release_row = bundle['release']
    if RulesetRelease.objects.filter(version=release_row['fields']['version']).exists():
        return
    print('묶음을 SQLite로 읽는 중…', flush=True)
    with transaction.atomic():
        SiteSettings.objects.get_or_create(name='갯수예외처리카드', defaults={'setting': {}})
        _save_rows(bundle['characters'])
        _save_rows(bundle['character_translations'])
        _save_rows(bundle['cards'])
        _save_rows(bundle['card_translations'])
        RulesetRelease.objects.filter(is_active=True).update(is_active=False)
        SimulatorAIPolicy.objects.filter(is_active=True).update(is_active=False)
        release_row = {**release_row, 'pk': None, 'fields': {**release_row['fields'], 'is_active': True}}
        policy_row = {**bundle['policy'], 'pk': None, 'fields': {**bundle['policy']['fields'], 'is_active': True}}
        _save_rows([release_row, policy_row])
        released_codes = set((release_row['fields']['snapshot'].get('cards') or {}).keys())
        user, _ = User.objects.get_or_create(username=DEV_USER)
        regulation, _ = Regulation.objects.get_or_create(name='개발 교체 시험', owner=user)
        version, _ = RegulationVersion.objects.get_or_create(regulation=regulation, version='1', defaults={'rules': SWAP_RULES})
        for side in ('p1', 'p2'):
            for index, source in enumerate(bundle['decks'][side]):
                # 실제 사이트처럼 새 형식(특성 지정)이라 대전 전에 덱 준비 단계를 거친다.
                deck = Deck.objects.create(
                    name=source['name'], author=user, character_id=source['character_id'],
                    trait_card_id=source['trait_card_id'], visibility=Deck.VISIBILITY_PUBLIC,
                    schema_version=2, description=f'source deck {source["source_id"]}',
                )
                CardInDeck.objects.bulk_create([
                    CardInDeck(deck=deck, card_id=entry['card_id'], count=entry['count'],
                               hand=entry['hand'], side=entry['side'])
                    for entry in source['cards']
                ])
                if index == 0 and source['trait_card_id']:
                    _swap_deck(user, source, released_codes, version)


def dev_login(request):
    """Log in as the owner of the dev decks, so the lobby can list them as 'my decks'."""
    user = User.objects.get(username=DEV_USER)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return HttpResponseRedirect('/')


load_bundle()
from LumenGG.urls import urlpatterns  # noqa: E402

urlpatterns[:0] = [path('play-dev/login/', dev_login)]
print(f'Play dev server: http://127.0.0.1:{args.port}/battlelog/play/  (DB: {database})', flush=True)
call_command('runserver', f'127.0.0.1:{args.port}', use_reloader=False, insecure=True)
