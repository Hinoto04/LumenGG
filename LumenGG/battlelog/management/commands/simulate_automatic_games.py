from django.core.management.base import BaseCommand, CommandError

from battlelog.automatic_services import _pin_release_card_data, ensure_automatic_decks
from battlelog.game.catalog import active_ruleset_release
from battlelog.game.simulation import run_random_game
from battlelog.simulator_services import _initial_state
from deck.models import Deck


class Command(BaseCommand):
    help = 'Run deterministic headless automatic games to detect deadlocks and loops.'

    def add_arguments(self, parser):
        parser.add_argument('player1_deck', type=int)
        parser.add_argument('player2_deck', type=int)
        parser.add_argument('--games', type=int, default=10)
        parser.add_argument('--max-commands', type=int, default=2000)

    def handle(self, *args, **options):
        release = active_ruleset_release()
        if not release:
            raise CommandError('활성 규칙 릴리스가 없습니다.')
        decks = list(Deck.objects.select_related('character').filter(
            id__in=[options['player1_deck'], options['player2_deck']], deleted=False,
        ))
        by_id = {deck.id: deck for deck in decks}
        try:
            p1 = by_id[options['player1_deck']]
            p2 = by_id[options['player2_deck']]
        except KeyError:
            raise CommandError('덱을 찾을 수 없습니다.') from None
        ensure_automatic_decks(p1, p2, ruleset=release.snapshot)
        failed = []
        for index in range(max(1, options['games'])):
            state = _initial_state('Headless P1', 'Headless P2', p1, p2)
            state['priority_player'] = 'p1' if index % 2 == 0 else 'p2'
            state = _pin_release_card_data(state, release.snapshot)
            result = run_random_game(
                state, {**release.snapshot, 'version': release.version},
                seed=f'headless-{index}', max_commands=options['max_commands'],
            )
            self.stdout.write(f'{index + 1}: {result.reason} · commands={result.commands} · winner={result.winner or "-"}')
            if not result.completed:
                failed.append((index + 1, result))
        if failed:
            raise CommandError(f'{len(failed)}개 대전에서 교착 또는 진행 한도 초과가 발생했습니다.')
        self.stdout.write(self.style.SUCCESS(f'{options["games"]}개 자동 대전 완료'))
