import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.models import Rule, Rulebook
from common.rule_reference_semantics import semanticize_rulebooks
from common.rulebooks import CONTENT_DIR, _rulebook_configs


class Command(BaseCommand):
    help = '규칙 참조명을 의미형 이름으로 바꾸고 본문과 비주얼 href를 갱신합니다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--slug',
            action='append',
            dest='slugs',
            help='변환할 DB 룰북 slug입니다. 여러 번 사용할 수 있습니다.',
        )
        parser.add_argument('--dry-run', action='store_true', help='DB와 JSON 파일을 변경하지 않습니다.')

    def handle(self, *args, **options):
        configs = [item for item in _rulebook_configs() if item.get('storage') == 'database']
        requested = set(options['slugs'] or [])
        if requested:
            unknown = requested - {item['slug'] for item in configs}
            if unknown:
                raise CommandError(f'DB 룰북이 아닌 slug: {", ".join(sorted(unknown))}')
            configs = [item for item in configs if item['slug'] in requested]

        books_by_slug = {
            book.slug: book
            for book in Rulebook.objects.filter(slug__in=[item['slug'] for item in configs])
        }
        missing = [item['slug'] for item in configs if item['slug'] not in books_by_slug]
        if missing:
            raise CommandError(f'룰북 DB 레코드가 없습니다: {", ".join(missing)}')
        books = [books_by_slug[item['slug']] for item in configs]

        with transaction.atomic():
            result = semanticize_rulebooks(books)
            if options['dry_run']:
                transaction.set_rollback(True)

        visual_updates = 0
        if not options['dry_run']:
            for config in configs:
                visual_file = config.get('visual_file')
                if visual_file:
                    heading_targets = _heading_targets(books_by_slug[config['slug']])
                    visual_updates += _update_visual_hrefs(
                        CONTENT_DIR / visual_file,
                        result['references'],
                        heading_targets,
                    )

        suffix = ' (dry-run)' if options['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(
            f'참조명 {result["renamed"]}개, 본문 {result["rewritten"]}개, '
            f'비주얼 href {visual_updates}개 갱신{suffix}'
        ))


def _heading_targets(book):
    targets = {}
    rules = (
        Rule.objects
        .filter(rulebook=book)
        .select_related('parent')
        .prefetch_related('translations')
    )
    for rule in rules:
        korean = next(
            (item for item in rule.translations.all() if item.language == 'ko'),
            None,
        )
        if not korean or not korean.title:
            continue
        targets[korean.title] = rule.reference_name
        if rule.full_number:
            targets[f'{rule.full_number} {korean.title}'] = rule.reference_name
    return targets


def _update_visual_hrefs(path, references, heading_targets):
    path = Path(path)
    if not path.exists():
        return 0
    payload = json.loads(path.read_text(encoding='utf-8'))
    update_count = 0

    def update(value, key=''):
        nonlocal update_count
        if isinstance(value, list):
            return [update(item) for item in value]
        if isinstance(value, dict):
            updated = {item_key: update(item, item_key) for item_key, item in value.items()}
            heading_reference = heading_targets.get(value.get('heading', ''))
            if heading_reference and 'fallback' in updated:
                semantic_fallback = f'#{heading_reference}'
                if updated['fallback'] != semantic_fallback:
                    updated['fallback'] = semantic_fallback
                    update_count += 1
            return updated
        if key not in {'href', 'fallback'} or not isinstance(value, str) or '#' not in value:
            return value
        prefix, reference = value.rsplit('#', 1)
        current_reference = references.get(reference)
        if not current_reference or current_reference == reference:
            return value
        update_count += 1
        return f'{prefix}#{current_reference}'

    updated_payload = update(payload)
    if update_count:
        path.write_text(
            json.dumps(updated_payload, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
    return update_count
