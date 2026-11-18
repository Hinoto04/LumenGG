"""Export one AI-vs-AI start state for the Pyodide prototype (play/pyodide-lab.html).

Reads the isolated dev data (.temp/play-dev/play.sqlite, made by
scripts/serve_play_dev.py) from a temporary copy, so neither the configured
(possibly production) database nor the running dev server's file is touched.

    .venv/Scripts/python.exe scripts/export_client_ai_sample.py [--p1 1] [--p2 5]

Writes .temp/client-ai/sample.json:
    {"initial_state", "ruleset", "weights", "profile", "meta"}
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--p1', type=int, default=1, help='P1 덱 id (개발 데이터)')
parser.add_argument('--p2', type=int, default=5, help='P2 덱 id (개발 데이터)')
parser.add_argument('--source', default=str(root / '.temp/play-dev/play.sqlite'))
parser.add_argument('--out', default=str(root / '.temp/client-ai/sample.json'))
args = parser.parse_args()

source = Path(args.source)
if not source.exists():
    sys.exit(f'{source}가 없습니다. 먼저 scripts/serve-play-dev.ps1로 격리 개발 데이터를 만드세요.')
workdir = Path(tempfile.mkdtemp(prefix='lumen-client-ai-'))
database = workdir / 'play.sqlite'
shutil.copyfile(source, database)
for suffix in ('-wal', '-shm'):
    extra = Path(str(source) + suffix)
    if extra.exists():
        shutil.copyfile(extra, Path(str(database) + suffix))

os.environ['DJANGO_SETTINGS_MODULE'] = 'LumenGG.test_settings'
os.environ['LUMENGG_TEST_SQLITE_PATH'] = str(database)
sys.path.insert(0, str(root / 'LumenGG'))
import django  # noqa: E402

django.setup()
from django.db import connection  # noqa: E402

if connection.vendor != 'sqlite' or Path(connection.settings_dict['NAME']).resolve() != database.resolve():
    sys.exit(f'임시 SQLite 사본이 아닌 DB에 연결되어 중단합니다: {connection.settings_dict["NAME"]}')

from battlelog.automatic_services import _pin_release_card_data, ensure_automatic_decks  # noqa: E402
from battlelog.game.ai import DEFAULT_POLICY_WEIGHTS  # noqa: E402
from battlelog.game.catalog import active_ruleset_release  # noqa: E402
from battlelog.models import SimulatorAIPolicy  # noqa: E402
from battlelog.simulator_services import _initial_state  # noqa: E402
from deck.models import Deck  # noqa: E402

release = active_ruleset_release()
if not release:
    sys.exit('활성 규칙 릴리스가 없습니다.')
decks = {deck.id: deck for deck in Deck.objects.select_related('character').filter(id__in=[args.p1, args.p2])}
p1, p2 = decks[args.p1], decks[args.p2]
ensure_automatic_decks(p1, p2, ruleset=release.snapshot)
state = _initial_state('AI P1', 'AI P2', p1, p2)
state['priority_player'] = 'p1'
state = _pin_release_card_data(state, release.snapshot)

policy = SimulatorAIPolicy.objects.filter(is_active=True).order_by('-id').first() if hasattr(SimulatorAIPolicy, 'is_active') else SimulatorAIPolicy.objects.order_by('-id').first()
weights = (policy.weights if policy else None) or DEFAULT_POLICY_WEIGHTS
profile = None
try:
    from battlelog.models import SimulatorAIDeck
    ai_deck = SimulatorAIDeck.objects.filter(deck=p2).first()
    if ai_deck is not None:
        profile = ai_deck.payload()  # 세션이 document['ai_deck']에 고정하는 값과 같다.
except Exception as exc:  # 개발 DB에 AI 덱 표가 아직 없을 수 있다.
    print(f'AI 덱 프로필 없음: {type(exc).__name__}: {exc}')

out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
payload = {
    'initial_state': state,
    'ruleset': {**release.snapshot, 'version': release.version},
    'weights': weights,
    'profile': profile,
    'meta': {
        'release': release.version,
        'p1': {'deck': p1.id, 'name': p1.name, 'character': p1.character.name},
        'p2': {'deck': p2.id, 'name': p2.name, 'character': p2.character.name},
        'policy': getattr(policy, 'version', None),
    },
}
out.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':'), default=str), encoding='utf-8')
print(f'{out} ({out.stat().st_size:,} bytes) · {release.version} · {p1.name} vs {p2.name}')
connection.close()
shutil.rmtree(workdir, ignore_errors=True)
