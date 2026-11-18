"""AI 수치표(ai_outcome_table.json)를 자기대전으로 측정한다.

DB는 읽기만 한다. 결과는 JSON 파일로만 쓴다.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from battlelog.automatic_services import _cached_ruleset, _pin_release_card_data, ensure_automatic_decks
from battlelog.game.ai_outcomes import TABLE_PATH, OutcomeRecorder
from battlelog.game.catalog import active_ruleset_release
from battlelog.game.simulation import run_policy_game
from battlelog.models import SimulatorAIDeck
from battlelog.simulator_services import _initial_state
from deck.models import Deck


class Command(BaseCommand):
    help = '덱끼리 자기대전을 돌려 카드별·판정 결과별 평균 자원 이득(AI 수치표)을 만든다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--deck', type=int, action='append', default=[],
            help='측정할 덱 ID. 여러 번 쓴다. 없으면 활성 AI 덱 전부.',
        )
        parser.add_argument('--games', type=int, default=2, help='덱 조합(선후 포함)마다 판 수.')
        parser.add_argument('--out', default=str(TABLE_PATH))
        parser.add_argument('--seed', default='outcome-table')
        parser.add_argument('--dry-run', action='store_true', help='파일을 쓰지 않고 요약만 출력한다.')

    def handle(self, *args, **options):
        release = active_ruleset_release()
        if not release:
            raise CommandError('활성 규칙 릴리스가 없습니다.')
        deck_ids = list(dict.fromkeys(options['deck'])) or list(
            SimulatorAIDeck.objects.filter(is_active=True).values_list('deck_id', flat=True)
        )
        if len(deck_ids) < 2:
            raise CommandError('덱이 두 개 이상 필요합니다.')
        decks = {
            deck.id: deck
            for deck in Deck.objects.select_related('character').filter(id__in=deck_ids, deleted=False)
        }
        missing = set(deck_ids) - set(decks)
        if missing:
            raise CommandError(f'덱을 찾을 수 없습니다: {sorted(missing)}')
        ruleset = _cached_ruleset(release.id)
        valid = []
        for deck_id in deck_ids:
            try:
                ensure_automatic_decks(decks[deck_id], decks[deck_id], ruleset=release.snapshot)
            except ValueError as exc:
                self.stderr.write(f'덱 {deck_id} 제외: {exc}')
                continue
            valid.append(decks[deck_id])
        if len(valid) < 2:
            raise CommandError('자동 모드에 쓸 수 있는 덱이 두 개 이상 필요합니다.')

        recorder = OutcomeRecorder(ruleset)
        played = errors = 0
        for first in valid:
            for second in valid:
                if first.id == second.id:
                    continue
                for game in range(options['games']):
                    state = _pin_release_card_data(
                        _initial_state('Outcome P1', 'Outcome P2', first, second), release.snapshot,
                    )
                    game_recorder = OutcomeRecorder(ruleset)
                    result = run_policy_game(
                        state, ruleset, seed=f'{options["seed"]}:{first.id}:{second.id}:{game}',
                        on_step=game_recorder.step,
                    )
                    played += 1
                    if not result.completed:
                        errors += 1
                        self.stderr.write(f'{first.id} vs {second.id} #{game}: {result.reason} {result.error[:120]}')
                        continue
                    recorder.merge(game_recorder)
                self.stdout.write(f'{first.id} vs {second.id}: 누적 배틀 {recorder.battles}')

        payload = recorder.table_payload(
            release=release.id, release_version=getattr(release, 'version', None),
            decks=[deck.id for deck in valid], games=played - errors,
        )
        drifting = sum(
            1 for entry in payload['cards'].values()
            if entry['judged'] >= 3 and entry['drift'] / entry['judged'] > 0.2
        )
        self.stdout.write(
            f'게임 {played}판(실패 {errors}), 배틀 {recorder.battles}회, 카드 {len(payload["cards"])}종, '
            f'판정이 자주 바뀌는 카드 {drifting}종'
        )
        if options['dry_run']:
            return
        Path(options['out']).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8',
        )
        self.stdout.write(f'저장: {options["out"]}')
