from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from battlelog.game.drafts import build_effect_draft
from battlelog.game.catalog import effect_source_digest
from card.models import Card


class Command(BaseCommand):
    help = 'Populate conservative, non-publishable effect-editor drafts from card text.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--card-code',
            action='append',
            dest='card_codes',
            default=[],
            metavar='CODE',
            help='Limit seeding to an exact card code. Repeat for multiple cards.',
        )
        parser.add_argument(
            '--overwrite-unreviewed',
            action='store_true',
            help='Replace existing unreviewed definitions; reviewed definitions are never overwritten.',
        )

    def handle(self, *args, **options):
        requested_codes = list(dict.fromkeys(
            code.strip() for code in options['card_codes'] if code.strip()
        ))
        cards_query = Card.objects.prefetch_related('qna').order_by('id')
        if requested_codes:
            cards_query = cards_query.filter(code__in=requested_codes)
        cards = list(cards_query)
        found_codes = {card.code for card in cards}
        missing_codes = [code for code in requested_codes if code not in found_codes]
        if missing_codes:
            raise CommandError(
                'Unknown card code(s): ' + ', '.join(missing_codes)
            )
        changed = []
        skipped_reviewed = skipped_existing = 0
        ability_count = 0
        compiled_count = 0
        now = timezone.now()
        for card in cards:
            current = card.effect_definition or {}
            if current.get('reviewed') is True:
                skipped_reviewed += 1
                continue
            has_content = bool(current.get('abilities') or current.get('draft'))
            if has_content and not options['overwrite_unreviewed']:
                skipped_existing += 1
                continue
            qnas = list(card.qna.all())
            definition = build_effect_draft(
                card.code,
                card.text,
                qna_ids=[item.id for item in qnas],
                detail_text=card.detail_text,
            )
            definition['source_digest'] = effect_source_digest(card, qnas)
            card.effect_definition = definition
            card.effect_revision = int(card.effect_revision or 1) + 1
            card.effect_updated_at = now
            changed.append(card)
            ability_count += len(definition.get('abilities') or [])
            compiled_count += sum(
                1 for ability in definition.get('abilities') or []
                if ability.get('draft_compiled')
            )

        if not options['dry_run'] and changed:
            with transaction.atomic():
                Card.objects.bulk_update(
                    changed,
                    ['effect_definition', 'effect_revision', 'effect_updated_at'],
                    batch_size=100,
                )
        verb = 'would seed' if options['dry_run'] else 'seeded'
        self.stdout.write(self.style.SUCCESS(
            f'{verb}: cards={len(changed)}, abilities={ability_count}, compiled={compiled_count}, '
            f'skipped_reviewed={skipped_reviewed}, skipped_existing={skipped_existing}'
        ))
