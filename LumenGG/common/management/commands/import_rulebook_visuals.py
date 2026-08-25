from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.models import Rulebook
from common.rulebook_visual_import import import_rulebook_visuals
from common.rulebooks import _rulebook_configs


class Command(BaseCommand):
    help = '기존 룰북 비주얼 JSON을 편집 가능한 DB 비주얼 가이드로 가져옵니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--slug',
            action='append',
            dest='slugs',
            help='가져올 룰북 slug입니다. 여러 번 사용할 수 있습니다.',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help='기존 룰북 상단 비주얼 가이드를 JSON 원본으로 교체합니다.',
        )
        parser.add_argument('--dry-run', action='store_true', help='DB에 저장하지 않고 결과만 확인합니다.')

    def handle(self, *args, **options):
        configs = _rulebook_configs()
        requested = set(options['slugs'] or [])
        if requested:
            unknown = requested - {item['slug'] for item in configs}
            if unknown:
                raise CommandError(f'알 수 없는 룰북 slug: {", ".join(sorted(unknown))}')
            configs = [item for item in configs if item['slug'] in requested]

        total = 0
        with transaction.atomic():
            for config in configs:
                try:
                    book = Rulebook.objects.get(slug=config['slug'])
                except Rulebook.DoesNotExist as error:
                    raise CommandError(
                        f'{config["slug"]} 룰북이 없습니다. import_rulebooks를 먼저 실행하세요.'
                    ) from error
                if not book.rules.exists():
                    raise CommandError(
                        f'{book.slug} 룰북에 규칙이 없습니다. import_rulebooks를 먼저 실행하세요.'
                    )
                try:
                    guides = import_rulebook_visuals(
                        book,
                        config,
                        replace=options['replace'],
                    )
                except ValueError as error:
                    raise CommandError(str(error)) from error
                total += len(guides)
                self.stdout.write(f'{book.slug}: 비주얼 가이드 {len(guides)}개')
            if options['dry_run']:
                transaction.set_rollback(True)

        suffix = ' (dry-run, 저장하지 않음)' if options['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(f'비주얼 가이드 {total}개 처리{suffix}'))
