from django.core.management.base import BaseCommand
from django.db.models import Count

from card.models import Card, Character
from common.localization import SUPPORTED_TRANSLATION_LANGUAGES, TOKEN_RE, character_translation_key, term_translation_key
from common.models import TranslationSource, TranslationValue


TEXT_FIELDS = ('text', 'detail_text', 'keyword', 'hiddenKeyword', 'search')


class Command(BaseCommand):
    help = 'Check translation catalog health.'

    def add_arguments(self, parser):
        parser.add_argument('--strict', action='store_true', help='Exit with an error when missing translations are found.')
        parser.add_argument('--samples', type=int, default=20, help='Maximum samples to print for each section.')

    def handle(self, *args, **options):
        strict = options['strict']
        sample_limit = options['samples']
        errors = 0

        errors += self.report_duplicate_card_codes(sample_limit)
        errors += self.report_duplicate_character_keys(sample_limit)
        missing_count = self.report_missing_translations(sample_limit)
        broken_count = self.report_broken_tokens(sample_limit)
        direct_count = self.report_direct_references(sample_limit)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Localization check complete: missing={missing_count}, broken_tokens={broken_count}, direct_refs={direct_count}, errors={errors}'
        ))
        if errors or broken_count or (strict and missing_count):
            raise SystemExit(1)

    def report_duplicate_card_codes(self, sample_limit):
        duplicates = (
            Card.objects.exclude(code='')
            .values('code')
            .annotate(total=Count('id'))
            .filter(total__gt=1)
            .order_by('code')
        )
        count = duplicates.count()
        if count:
            self.stdout.write(self.style.ERROR(f'Duplicate card codes: {count}'))
            for row in duplicates[:sample_limit]:
                self.stdout.write(f'  {row["code"]}: {row["total"]}')
        return count

    def report_duplicate_character_keys(self, sample_limit):
        duplicates = (
            Character.objects.exclude(localization_key='')
            .values('localization_key')
            .annotate(total=Count('id'))
            .filter(total__gt=1)
            .order_by('localization_key')
        )
        count = duplicates.count()
        if count:
            self.stdout.write(self.style.ERROR(f'Duplicate character keys: {count}'))
            for row in duplicates[:sample_limit]:
                self.stdout.write(f'  {row["localization_key"]}: {row["total"]}')
        return count

    def report_missing_translations(self, sample_limit):
        missing = []
        sources = TranslationSource.objects.filter(is_active=True).exclude(source_text='', source_data={})
        for source in sources.order_by('key'):
            for language in SUPPORTED_TRANSLATION_LANGUAGES:
                value = TranslationValue.objects.filter(source=source, language=language).first()
                if value is None or value.status == TranslationValue.STATUS_MISSING or (not value.text and not value.data):
                    missing.append((source.key, language))

        self.stdout.write(f'Missing translations: {len(missing)}')
        for key, language in missing[:sample_limit]:
            self.stdout.write(f'  {key} / {language}')
        return len(missing)

    def report_broken_tokens(self, sample_limit):
        broken = []
        card_codes = set(Card.objects.exclude(code='').values_list('code', flat=True))
        character_keys = set(Character.objects.exclude(localization_key='').values_list('localization_key', flat=True))
        source_keys = set(TranslationSource.objects.filter(is_active=True).values_list('key', flat=True))

        for owner, text in self.iter_catalog_texts():
            for match in TOKEN_RE.finditer(text):
                kind, payload = match.group(1), match.group(2).strip()
                if kind in ('card', 'state-card', 'token-card', 'counter-card') and payload not in card_codes:
                    broken.append((owner, match.group(0)))
                elif kind == 'character' and payload not in character_keys:
                    broken.append((owner, match.group(0)))
                elif kind == 'keyword':
                    key = f'keyword.{payload}'
                    if key not in source_keys:
                        broken.append((owner, match.group(0)))
                elif kind in ('state', 'token'):
                    key = term_translation_key(kind, payload)
                    if key not in source_keys:
                        broken.append((owner, match.group(0)))
                elif kind == 'term':
                    parts = payload.split('.', 1)
                    key = term_translation_key(parts[0], parts[1]) if len(parts) == 2 else ''
                    if key not in source_keys:
                        broken.append((owner, match.group(0)))

        self.stdout.write(f'Broken tokens: {len(broken)}')
        for owner, token in broken[:sample_limit]:
            self.stdout.write(f'  {owner}: {token}')
        return len(broken)

    def report_direct_references(self, sample_limit):
        card_names = [
            (card.code, card.name)
            for card in Card.objects.exclude(name='').exclude(code='').order_by('-name')
            if len(card.name) >= 2
        ]
        character_names = [
            (character.localization_key, character.name)
            for character in Character.objects.exclude(name='').order_by('-name')
            if len(character.name) >= 2
        ]
        direct = []
        for owner, text in self.iter_catalog_texts():
            if '[[' in text:
                continue
            for code, name in card_names:
                if name in text and code not in owner:
                    direct.append((owner, f'card:{code}', name))
                    break
            for key, name in character_names:
                if name in text and key not in owner:
                    direct.append((owner, f'character:{key}', name))
                    break

        self.stdout.write(f'Direct Korean name references: {len(direct)}')
        for owner, target, name in direct[:sample_limit]:
            self.stdout.write(f'  {owner}: {target} ({name})')
        return len(direct)

    def iter_catalog_texts(self):
        for source in TranslationSource.objects.filter(is_active=True).exclude(source_text='').order_by('key'):
            yield source.key, source.source_text
        for value in TranslationValue.objects.exclude(text='').select_related('source').order_by('source__key', 'language'):
            yield f'{value.source.key}/{value.language}', value.text
