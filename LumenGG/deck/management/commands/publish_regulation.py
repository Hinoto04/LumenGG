from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from deck.presets import PRESET_ROOT, load_preset, publish_preset, rules_for_preset


class Command(BaseCommand):
    help = 'Publish a reviewed common regulation preset without changing card effects or existing decks.'

    def add_arguments(self, parser):
        parser.add_argument('preset', choices=sorted(p.stem for p in PRESET_ROOT.glob('*.json')))
        parser.add_argument('--dry-run', action='store_true', help='Resolve every card and validate without publishing.')

    def handle(self, *args, **options):
        try:
            preset = load_preset(options['preset'])
            rules = rules_for_preset(preset)
            if options['dry_run']:
                self.stdout.write(f"검증 완료: {preset['name']} / 금지 {len(rules['bans'])}장 / 택1 {len(preset['choose_one_groups'])}묶음 / 제한 조합 {len(rules['combinations'])}개")
                return
            version, created = publish_preset(options['preset'])
        except (ValidationError, ValueError, KeyError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"{'생성 완료' if created else '기존 규칙 확인'}: {version} (id={version.pk}) / 금지 {len(version.rules['bans'])}장 / 제한 조합 {len(version.rules['combinations'])}개"))
