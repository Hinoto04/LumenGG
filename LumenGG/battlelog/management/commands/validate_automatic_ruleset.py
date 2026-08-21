from django.core.management.base import BaseCommand, CommandError

from battlelog.game.catalog import validate_catalog
from battlelog.management.console import console_safe_json


class Command(BaseCommand):
    help = 'Validate all card effect definitions for automatic simulator publication.'

    def handle(self, *args, **options):
        report = validate_catalog(require_coverage=True)
        self.stdout.write(console_safe_json(report.as_dict(), self.stdout))
        if not report.is_valid:
            raise CommandError(f'자동 규칙 검증 실패: {len(report.errors)}개 오류')
