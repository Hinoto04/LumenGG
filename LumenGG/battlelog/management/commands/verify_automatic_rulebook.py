from django.core.management.base import BaseCommand

from battlelog.game.catalog import verify_rulebook_source


class Command(BaseCommand):
    help = 'Verify the pinned automatic simulator rulebook SHA-256.'

    def handle(self, *args, **options):
        result = verify_rulebook_source()
        self.stdout.write(self.style.SUCCESS(
            f'{result["sha256"]} · {result["pages"]} pages · {result["path"]}'
        ))
