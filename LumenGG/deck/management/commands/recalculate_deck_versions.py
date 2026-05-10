from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Prefetch

from deck.models import CardInDeck, Deck
from deck.utils import get_deck_version_from_card_ids


class Command(BaseCommand):
    help = '기존 덱의 버전을 현재 자동 계산 규칙으로 재지정합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--deck-ids',
            default='',
            help='특정 덱 ID만 처리합니다. 쉼표로 여러 개를 지정할 수 있습니다. 예: 1,2,3',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='DB를 수정하지 않고 변경될 내용만 확인합니다.',
        )
        parser.add_argument(
            '--exclude-deleted',
            action='store_true',
            help='삭제 표시된 덱은 처리하지 않습니다.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='처리할 최대 덱 수입니다. 0이면 제한하지 않습니다.',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=200,
            help='bulk update를 한 번에 수행할 덱 수입니다. 기본값: 200',
        )
        parser.add_argument(
            '--show-unchanged',
            action='store_true',
            help='버전이 바뀌지 않는 덱도 출력합니다.',
        )

    def handle(self, *args, **options):
        deck_ids = self.parse_deck_ids(options['deck_ids'])
        limit = options['limit']
        batch_size = options['batch_size']

        if limit < 0:
            raise CommandError('--limit은 0 이상이어야 합니다.')
        if batch_size < 1:
            raise CommandError('--batch-size는 1 이상이어야 합니다.')

        decks = Deck.objects.all().order_by('id')
        if options['exclude_deleted']:
            decks = decks.filter(deleted=False)
        if deck_ids:
            decks = decks.filter(id__in=deck_ids)
            found_ids = set(decks.values_list('id', flat=True))
            missing_ids = sorted(set(deck_ids) - found_ids)
            if missing_ids:
                raise CommandError(f'처리할 수 없는 덱 ID가 있습니다: {missing_ids}')

        if limit:
            decks = decks[:limit]

        decks = decks.prefetch_related(
            Prefetch(
                'cids',
                queryset=CardInDeck.objects.only('deck_id', 'card_id').order_by(),
                to_attr='version_source_cards',
            )
        )

        processed = 0
        changed = 0
        unchanged = 0
        pending_updates = []

        for deck in decks.iterator(chunk_size=batch_size):
            processed += 1
            card_ids = [entry.card_id for entry in deck.version_source_cards]
            next_version = get_deck_version_from_card_ids(card_ids)
            current_version = deck.version or ''

            if current_version == next_version:
                unchanged += 1
                if options['show_unchanged']:
                    self.stdout.write(f'= #{deck.id} {deck.name}: {current_version}')
                continue

            changed += 1
            self.stdout.write(
                f'{"DRY " if options["dry_run"] else ""}# {deck.id} {deck.name}: '
                f'{current_version or "N/A"} -> {next_version}'
            )

            if not options['dry_run']:
                deck.version = next_version
                pending_updates.append(deck)
                if len(pending_updates) >= batch_size:
                    self.bulk_update_versions(pending_updates)
                    pending_updates = []

        if pending_updates:
            self.bulk_update_versions(pending_updates)

        mode = '미리보기' if options['dry_run'] else '완료'
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'덱 버전 재계산 {mode}: 처리 {processed}개 / 변경 {changed}개 / 유지 {unchanged}개'
            )
        )

    def parse_deck_ids(self, raw_value):
        if not raw_value:
            return []
        try:
            deck_ids = [
                int(value.strip())
                for value in raw_value.split(',')
                if value.strip()
            ]
        except ValueError as exc:
            raise CommandError('--deck-ids는 쉼표로 구분된 숫자여야 합니다.') from exc
        return list(dict.fromkeys(deck_ids))

    def bulk_update_versions(self, decks):
        with transaction.atomic():
            Deck.objects.bulk_update(decks, ['version'])
