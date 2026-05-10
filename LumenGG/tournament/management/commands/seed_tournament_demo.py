import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from deck.models import Deck
from tournament.models import Tournament, TournamentDeckSubmission, TournamentParticipant, TournamentRound
from tournament.services import create_round


class Command(BaseCommand):
    help = '기존 유저와 지정 덱 ID로 대회 진행 테스트용 대회를 생성합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--deck-ids',
            default='1002,1003,1004',
            help='참가자에게 랜덤 배정할 덱 ID 목록입니다. 기본값: 1002,1003,1004',
        )
        parser.add_argument(
            '--players',
            type=int,
            default=6,
            help='랜덤으로 참가시킬 유저 수입니다. 기본값: 6',
        )
        parser.add_argument(
            '--deck-count',
            type=int,
            default=1,
            help='대회에서 요구하는 제출 덱 수입니다. 기본값: 1',
        )
        parser.add_argument(
            '--swiss-rounds',
            type=int,
            default=3,
            help='스위스 + 토너먼트 대회에서 진행할 스위스 라운드 수입니다. 기본값: 3',
        )
        parser.add_argument(
            '--top-cut',
            type=int,
            default=4,
            help='스위스 + 토너먼트 대회에서 토너먼트에 진출할 인원 수입니다. 기본값: 4',
        )
        parser.add_argument(
            '--elimination-mode',
            choices=[Tournament.ELIMINATION_SINGLE, Tournament.ELIMINATION_DOUBLE],
            default=Tournament.ELIMINATION_SINGLE,
            help='토너먼트 단계 방식입니다. 기본값: single',
        )
        parser.add_argument(
            '--name',
            default='',
            help='생성할 대회명입니다. 비워두면 자동 생성합니다.',
        )
        parser.add_argument(
            '--organizer',
            default='',
            help='운영자 username 또는 user id입니다. 비워두면 staff/superuser 중 우선 선택합니다.',
        )
        parser.add_argument(
            '--seed',
            type=int,
            default=None,
            help='랜덤 결과를 고정할 seed 값입니다.',
        )
        parser.add_argument(
            '--start-round',
            action='store_true',
            help='생성 직후 스위스 1라운드를 바로 시작합니다.',
        )
        parser.add_argument(
            '--include-organizer',
            action='store_true',
            help='운영자도 랜덤 참가자 후보에 포함합니다.',
        )

    def handle(self, *args, **options):
        deck_ids = self.parse_deck_ids(options['deck_ids'])
        player_count = options['players']
        deck_count = options['deck_count']

        if player_count < 1:
            raise CommandError('--players는 1 이상이어야 합니다.')
        if deck_count < 0:
            raise CommandError('--deck-count는 0 이상이어야 합니다.')
        if deck_count > len(deck_ids):
            raise CommandError('--deck-count는 --deck-ids에 지정한 덱 수보다 클 수 없습니다.')
        if options['swiss_rounds'] < 0:
            raise CommandError('--swiss-rounds는 0 이상이어야 합니다.')
        if options['top_cut'] < 2:
            raise CommandError('--top-cut은 2 이상이어야 합니다.')

        rng = random.Random(options['seed'])
        decks = self.get_decks(deck_ids)
        organizer = self.get_organizer(options['organizer'])
        players = self.pick_players(organizer, player_count, options['include_organizer'], rng)

        name = options['name'] or timezone.now().strftime('테스트 대회 %Y-%m-%d %H:%M')

        with transaction.atomic():
            tournament = Tournament.objects.create(
                name=name,
                organizer=organizer,
                description='management command로 생성된 대회 진행 테스트용 데이터입니다.',
                venue='테스트 환경',
                event_date=timezone.now(),
                format=Tournament.FORMAT_HYBRID,
                elimination_mode=options['elimination_mode'],
                status=Tournament.STATUS_REGISTRATION,
                decklist_required_count=deck_count,
                round_duration_minutes=50,
                swiss_round_count=options['swiss_rounds'],
                top_cut_count=options['top_cut'],
                max_players=len(players),
            )

            assignments = []
            for seed_no, user in enumerate(players, start=1):
                assigned_decks = rng.sample(decks, deck_count) if deck_count else []
                participant = TournamentParticipant.objects.create(
                    tournament=tournament,
                    user=user,
                    display_name=user.username,
                    deck=assigned_decks[0] if assigned_decks else None,
                    seed=seed_no,
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

            round_obj = None
            if options['start_round']:
                if len(players) < 2:
                    raise CommandError('--start-round를 쓰려면 참가자가 2명 이상 필요합니다.')
                round_obj = create_round(tournament, TournamentRound.STAGE_SWISS, tournament.round_duration_minutes)

        self.stdout.write(self.style.SUCCESS(f'대회 생성 완료: #{tournament.id} {tournament.name}'))
        self.stdout.write(
            f'운영자: {organizer.username} / 참가자: {len(players)}명 / 제출 덱 수: {deck_count} / '
            f'스위스 {options["swiss_rounds"]}R / TOP {options["top_cut"]} / {options["elimination_mode"]}'
        )
        self.stdout.write(f'URL: {reverse("tournament:detailV2", kwargs={"id": tournament.id})}')
        if round_obj:
            self.stdout.write(self.style.SUCCESS(f'스위스 {round_obj.number}라운드 시작됨'))

        self.stdout.write('')
        self.stdout.write('참가자 / 제출 덱')
        for participant, assigned_decks in assignments:
            deck_text = ', '.join(f'#{deck.id} {deck.name}' for deck in assigned_decks) or '제출 없음'
            self.stdout.write(f'- {participant.name}: {deck_text}')

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

    def get_organizer(self, raw_value):
        if raw_value:
            query = {'id': int(raw_value)} if raw_value.isdigit() else {'username': raw_value}
            try:
                return User.objects.get(**query)
            except User.DoesNotExist as exc:
                raise CommandError(f'운영자 유저를 찾을 수 없습니다: {raw_value}') from exc

        organizer = User.objects.filter(is_active=True, is_staff=True).order_by('id').first()
        if organizer:
            return organizer
        organizer = User.objects.filter(is_active=True, is_superuser=True).order_by('id').first()
        if organizer:
            return organizer
        organizer = User.objects.filter(is_active=True).order_by('id').first()
        if organizer:
            return organizer
        raise CommandError('활성화된 유저가 없습니다.')

    def pick_players(self, organizer, player_count, include_organizer, rng):
        users = list(User.objects.filter(is_active=True).order_by('id'))
        if not include_organizer:
            users = [user for user in users if user.id != organizer.id]

        if not users:
            if include_organizer:
                raise CommandError('참가자로 사용할 활성화된 유저가 없습니다.')
            users = [organizer]

        if len(users) < player_count:
            self.stdout.write(
                self.style.WARNING(
                    f'요청한 참가자 수는 {player_count}명이지만 후보 유저가 {len(users)}명이라 가능한 만큼만 사용합니다.'
                )
            )
            player_count = len(users)

        return rng.sample(users, player_count)
