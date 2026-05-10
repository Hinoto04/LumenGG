import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max
from django.urls import reverse

from deck.models import Deck
from tournament.models import Tournament, TournamentDeckSubmission, TournamentParticipant


class Command(BaseCommand):
    help = '이미 생성된 대회에 기존 유저를 랜덤 참가자로 추가합니다.'

    def add_arguments(self, parser):
        parser.add_argument('tournament_id', type=int, help='참가자를 추가할 대회 ID입니다.')
        parser.add_argument(
            '--players',
            type=int,
            required=True,
            help='랜덤으로 추가할 참가자 수입니다.',
        )
        parser.add_argument(
            '--deck-ids',
            default='1002,1003,1004',
            help='참가자에게 랜덤 배정할 덱 ID 목록입니다. 기본값: 1002,1003,1004',
        )
        parser.add_argument(
            '--deck-count',
            type=int,
            default=None,
            help='참가자당 제출 덱 수입니다. 비워두면 대회의 요구 덱 리스트 수를 사용합니다.',
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=None,
            help='랜덤 결과를 고정할 seed 값입니다.',
        )
        parser.add_argument(
            '--include-organizer',
            action='store_true',
            help='운영자도 랜덤 참가자 후보에 포함합니다.',
        )
        parser.add_argument(
            '--ignore-max-players',
            action='store_true',
            help='대회의 최대 참가자 수 제한을 무시하고 추가합니다.',
        )

    def handle(self, *args, **options):
        tournament = self.get_tournament(options['tournament_id'])
        player_count = options['players']
        deck_count = tournament.decklist_required_count if options['deck_count'] is None else options['deck_count']

        if player_count < 1:
            raise CommandError('--players는 1 이상이어야 합니다.')
        if deck_count < 0:
            raise CommandError('--deck-count는 0 이상이어야 합니다.')

        decks = []
        if deck_count:
            deck_ids = self.parse_deck_ids(options['deck_ids'])
            if deck_count > len(deck_ids):
                raise CommandError('--deck-count는 --deck-ids에 지정한 덱 수보다 클 수 없습니다.')
            decks = self.get_decks(deck_ids)

        if not options['ignore_max_players'] and tournament.max_players:
            active_count = tournament.participants.filter(dropped=False).count()
            remaining_slots = max(tournament.max_players - active_count, 0)
            if remaining_slots <= 0:
                raise CommandError('대회의 최대 참가자 수가 이미 가득 찼습니다.')
            if player_count > remaining_slots:
                self.stdout.write(
                    self.style.WARNING(
                        f'요청한 참가자 수는 {player_count}명이지만 남은 참가 가능 인원이 {remaining_slots}명이라 가능한 만큼만 추가합니다.'
                    )
                )
                player_count = remaining_slots

        rng = random.Random(options['seed'])
        players = self.pick_players(tournament, player_count, options['include_organizer'], rng)

        if not players:
            raise CommandError('추가할 수 있는 참가자 후보가 없습니다.')

        next_seed = (tournament.participants.aggregate(max_seed=Max('seed'))['max_seed'] or 0) + 1
        assignments = []

        with transaction.atomic():
            for offset, user in enumerate(players):
                assigned_decks = rng.sample(decks, deck_count) if deck_count else []
                participant = TournamentParticipant.objects.create(
                    tournament=tournament,
                    user=user,
                    display_name=user.username,
                    deck=assigned_decks[0] if assigned_decks else None,
                    seed=next_seed + offset,
                )
                TournamentDeckSubmission.objects.bulk_create([
                    TournamentDeckSubmission(
                        participant=participant,
                        deck=deck,
                        slot=slot,
                    )
                    for slot, deck in enumerate(assigned_decks, start=1)
                ])
                assignments.append((participant, assigned_decks))

        self.stdout.write(self.style.SUCCESS(f'참가자 추가 완료: #{tournament.id} {tournament.name}'))
        self.stdout.write(f'추가 참가자: {len(assignments)}명 / 제출 덱 수: {deck_count}')
        self.stdout.write(f'URL: {reverse("tournament:detailV2", kwargs={"id": tournament.id})}')

        self.stdout.write('')
        self.stdout.write('추가된 참가자 / 제출 덱')
        for participant, assigned_decks in assignments:
            deck_text = ', '.join(f'#{deck.id} {deck.name}' for deck in assigned_decks) or '제출 없음'
            self.stdout.write(f'- {participant.name}: {deck_text}')

    def get_tournament(self, tournament_id):
        try:
            return Tournament.objects.select_related('organizer').get(id=tournament_id)
        except Tournament.DoesNotExist as exc:
            raise CommandError(f'대회를 찾을 수 없습니다: {tournament_id}') from exc

    def parse_deck_ids(self, raw_value):
        try:
            deck_ids = [int(value.strip()) for value in raw_value.split(',') if value.strip()]
        except ValueError as exc:
            raise CommandError('--deck-ids는 쉼표로 구분된 숫자여야 합니다.') from exc
        if not deck_ids:
            raise CommandError('--deck-ids가 비어 있습니다.')
        return deck_ids

    def get_decks(self, deck_ids):
        decks_by_id = Deck.objects.filter(id__in=deck_ids, deleted=False).select_related('author', 'character').in_bulk()
        missing_ids = [deck_id for deck_id in deck_ids if deck_id not in decks_by_id]
        if missing_ids:
            raise CommandError(f'존재하지 않거나 삭제된 덱 ID가 있습니다: {missing_ids}')
        return [decks_by_id[deck_id] for deck_id in deck_ids]

    def pick_players(self, tournament, player_count, include_organizer, rng):
        existing_user_ids = set(tournament.participants.values_list('user_id', flat=True))
        users = list(User.objects.filter(is_active=True).exclude(id__in=existing_user_ids).order_by('id'))
        if not include_organizer:
            users = [user for user in users if user.id != tournament.organizer_id]

        if len(users) < player_count:
            self.stdout.write(
                self.style.WARNING(
                    f'요청한 참가자 수는 {player_count}명이지만 후보 유저가 {len(users)}명이라 가능한 만큼만 사용합니다.'
                )
            )
            player_count = len(users)

        return rng.sample(users, player_count)
