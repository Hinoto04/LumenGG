import logging
import time
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, transaction
from mobile_api.catalog import publish_catalog
from mobile_api.models import CatalogRelease


class Command(BaseCommand):
    help = 'Publish validated mobile catalogs; --watch polls every 60 seconds.'

    def add_arguments(self, parser):
        parser.add_argument('--watch', action='store_true')
        parser.add_argument('--activate', help='Reactivate a previously published immutable version.')

    def handle(self, *args, **options):
        if options['activate']:
            if options['watch']:
                raise CommandError('--activate cannot be combined with --watch.')
            release = CatalogRelease.objects.filter(version=options['activate']).first()
            if not release or not (Path(settings.MOBILE_CATALOG_ROOT) / release.filename).is_file():
                raise CommandError('Release or its database file does not exist.')
            with transaction.atomic():
                CatalogRelease.objects.filter(active=True).update(active=False)
                release.active = True
                release.save(update_fields=['active'])
            self.stdout.write('Activated ' + release.version + '; stop the watcher until the source is corrected.')
            return
        # A shared lock directory prevents concurrent publishers on this volume.
        root = Path(settings.MOBILE_CATALOG_ROOT)
        root.mkdir(parents=True, exist_ok=True)
        import filelock
        with filelock.FileLock(str(root / '.publisher.lock'), timeout=0):
            while True:
                started = time.monotonic()
                close_old_connections()
                try:
                    release, changed = publish_catalog()
                    self.stdout.write(('Published ' if changed else 'Unchanged ') + release.version)
                except Exception as exc:
                    if not options['watch']:
                        raise CommandError(str(exc)) from exc
                    logging.getLogger(__name__).exception('mobile_catalog_publication_failed')
                if not options['watch']:
                    break
                time.sleep(max(1, 60 - (time.monotonic() - started)))
