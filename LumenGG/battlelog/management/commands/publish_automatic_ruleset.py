from django.core.management.base import BaseCommand, CommandError

from battlelog.game.catalog import RulesetPublicationError, publish_ruleset_release


class Command(BaseCommand):
    help = 'Publish and activate an immutable automatic simulator ruleset.'

    def add_arguments(self, parser):
        parser.add_argument('version')
        parser.add_argument('--no-activate', action='store_true')

    def handle(self, *args, **options):
        try:
            release, report = publish_ruleset_release(options['version'], activate=not options['no_activate'])
        except RulesetPublicationError as exc:
            raise CommandError(f'자동 규칙 검증 실패: {len(exc.report.errors)}개 오류') from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f'{release.version} published: {release.content_hash} ({report.card_count} cards, {report.ability_count} abilities)'
        ))
