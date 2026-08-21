from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from battlelog.automatic_services import _pin_release_card_data, ensure_automatic_decks
from battlelog.game.ai import DEFAULT_POLICY_WEIGHTS
from battlelog.game.catalog import active_ruleset_release
from battlelog.game.training import train_self_play
from battlelog.models import SimulatorAIPolicy
from battlelog.simulator_services import _initial_state
from deck.models import Deck


class Command(BaseCommand):
    help = 'Train and version a deterministic simulator AI with AI-vs-AI self-play.'

    def add_arguments(self, parser):
        parser.add_argument('player1_deck', type=int)
        parser.add_argument('player2_deck', type=int)
        parser.add_argument('--policy-version', required=True)
        parser.add_argument('--generations', type=int, default=8)
        parser.add_argument('--candidates', type=int, default=4)
        parser.add_argument('--games-per-candidate', type=int, default=8)
        parser.add_argument('--evaluation-games', type=int, default=40)
        parser.add_argument('--seed', default='lumen-ai-training')
        parser.add_argument(
            '--training-pair', action='append', default=[], metavar='P1:P2',
            help='Additional deck pair. Repeat to train across multiple matchups.',
        )
        parser.add_argument('--activate', action='store_true')

    def handle(self, *args, **options):
        policy_version = str(options['policy_version'] or '').strip()
        if not policy_version:
            raise CommandError('정책 버전이 필요합니다.')
        if SimulatorAIPolicy.objects.filter(version=policy_version).exists():
            raise CommandError(f'이미 존재하는 정책 버전입니다: {policy_version}')
        release = active_ruleset_release()
        if not release:
            raise CommandError('활성 규칙 릴리스가 없습니다.')
        deck_pairs = [(options['player1_deck'], options['player2_deck'])]
        for raw_pair in options['training_pair']:
            try:
                player1_id, player2_id = (
                    int(value.strip()) for value in str(raw_pair).split(':', 1)
                )
            except (TypeError, ValueError):
                raise CommandError(
                    f'훈련 덱 조합 형식이 잘못되었습니다: {raw_pair} (예: 12:34)'
                ) from None
            deck_pairs.append((player1_id, player2_id))
        deck_pairs = list(dict.fromkeys(deck_pairs))
        deck_ids = {deck_id for pair in deck_pairs for deck_id in pair}
        decks = {
            deck.id: deck
            for deck in Deck.objects.select_related('character').filter(
                id__in=deck_ids,
                deleted=False,
            )
        }
        if set(decks) != deck_ids:
            raise CommandError('훈련 덱을 찾을 수 없습니다.') from None
        training_pairs = [(decks[p1], decks[p2]) for p1, p2 in deck_pairs]
        for player1_deck, player2_deck in training_pairs:
            ensure_automatic_decks(
                player1_deck, player2_deck, ruleset=release.snapshot,
            )
        active_policy = SimulatorAIPolicy.objects.filter(is_active=True).order_by(
            '-activated_at', '-created_at', '-id',
        ).first()
        baseline_weights = (
            active_policy.weights if active_policy else DEFAULT_POLICY_WEIGHTS
        )
        baseline_version = active_policy.version if active_policy else 'built-in-default'
        states = [
            _pin_release_card_data(
                _initial_state('Training P1', 'Training P2', player1_deck, player2_deck),
                release.snapshot,
            )
            for player1_deck, player2_deck in training_pairs
        ]
        ruleset = {**release.snapshot, 'version': release.version}
        result = train_self_play(
            states,
            ruleset,
            initial_weights=baseline_weights,
            generations=options['generations'],
            candidates_per_generation=options['candidates'],
            games_per_candidate=options['games_per_candidate'],
            evaluation_games=options['evaluation_games'],
            seed=options['seed'],
            progress=lambda metrics, games: self.stdout.write(
                f'generation {metrics["generation"]}: '
                f'score={metrics["score"]:.3f}, '
                f'incomplete={metrics["incomplete"]}, games={games}'
            ),
        )
        if options['activate'] and result.metrics.get('selected') != 'evolved':
            raise CommandError('기준 정책보다 나은 후보가 없어 활성화하지 않았습니다.')
        with transaction.atomic():
            if options['activate']:
                SimulatorAIPolicy.objects.filter(is_active=True).update(is_active=False)
            policy = SimulatorAIPolicy.objects.create(
                name='Lumen AI',
                version=policy_version,
                weights=result.weights,
                metrics={
                    **result.metrics,
                    'ruleset_version': release.version,
                    'training_decks': list(deck_pairs[0]),
                    'training_deck_pairs': [list(pair) for pair in deck_pairs],
                    'baseline_policy_version': baseline_version,
                },
                training_games=result.games,
                is_active=options['activate'],
                activated_at=timezone.now() if options['activate'] else None,
            )
        evaluation = result.metrics['evaluation']
        self.stdout.write(self.style.SUCCESS(
            f'{policy.version}: {result.games} games, '
            f'eval {evaluation["wins"]}W/{evaluation["losses"]}L/'
            f'{evaluation["draws"]}D, incomplete={evaluation["incomplete"]}'
        ))
