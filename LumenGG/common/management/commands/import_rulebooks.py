import re
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.models import Rule, Rulebook, RulebookTranslation, RuleTranslation
from common.rule_reference_semantics import semanticize_rulebooks
from common.rulebook_visual_import import import_rulebook_visuals
from common.rulebooks import (
    RULEBOOK_LANGUAGES,
    _badge_review_markers,
    _format_callouts,
    _load_markdown,
    _prepare_public_body,
    _render_markdown,
    _rewrite_local_links,
    _rulebook_configs,
)


ANCHOR_RE = re.compile(r'^\s*<a\s+id="([^"]+)"></a>\s*$')
HEADING_RE = re.compile(r'^(#{1,4})\s+(.+?)\s*$')
NUMBERED_RULE_RE = re.compile(r'^\*\*([A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*)\.?\*\*\s*(.*)$')
NUMBERED_TITLE_RE = re.compile(r'^([A-Za-z0-9]+(?:\.[A-Za-z0-9]+)*)\.?\s+(.+)$')


class Command(BaseCommand):
    help = 'Markdown 룰북을 계층형 DB 규칙으로 가져옵니다.'

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
            help='이미 등록된 규칙을 삭제하고 Markdown 내용으로 다시 만듭니다.',
        )
        parser.add_argument('--dry-run', action='store_true', help='DB에 반영하지 않고 결과만 확인합니다.')

    def handle(self, *args, **options):
        configs = _rulebook_configs()
        requested = set(options['slugs'] or [])
        if requested:
            unknown = requested - {item['slug'] for item in configs}
            if unknown:
                raise CommandError(f'알 수 없는 룰북 slug: {", ".join(sorted(unknown))}')
            configs = [item for item in configs if item['slug'] in requested]
            html_slugs = [item['slug'] for item in configs if item.get('storage') == 'html']
            if html_slugs:
                raise CommandError(
                    f'{", ".join(html_slugs)}는 단일 HTML 룰북이므로 DB 이관 대상이 아닙니다.'
                )
        else:
            configs = [item for item in configs if item.get('storage', 'database') == 'database']

        totals = {'books': 0, 'rules': 0, 'translations': 0, 'visuals': 0}
        with transaction.atomic():
            for config in configs:
                result = self._import_book(config, replace=options['replace'])
                totals['books'] += 1
                totals['rules'] += result['rules']
                totals['translations'] += result['translations']
                totals['visuals'] += result['visuals']
                self.stdout.write(
                    f'{config["slug"]}: 규칙 {result["rules"]}개, '
                    f'번역 {result["translations"]}개, 비주얼 {result["visuals"]}개'
                )
            if options['dry_run']:
                transaction.set_rollback(True)

        suffix = ' (dry-run, 저장하지 않음)' if options['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(
            f'룰북 {totals["books"]}개, 규칙 {totals["rules"]}개, '
            f'번역 {totals["translations"]}개, 비주얼 {totals["visuals"]}개 처리{suffix}'
        ))

    def _import_book(self, config, *, replace):
        source_documents = {
            language: self._parse_source(config, language)
            for language in sorted(RULEBOOK_LANGUAGES)
        }
        korean = source_documents['ko']
        metadata = korean['metadata']
        book, _created = Rulebook.objects.update_or_create(
            slug=config['slug'],
            defaults={
                'url_name': config.get('url_name') or 'rules:detail',
                'kicker': config.get('kicker', ''),
                'version': metadata.get('version', ''),
                'updated_on': _parse_date(metadata.get('updated') or metadata.get('web_edited')),
                'visual_file': config.get('visual_file', ''),
                'searchable': config.get('searchable', False),
                'anchor_prefix': config.get('anchor_prefix', 'rule-'),
                'sort_order': config.get('order', 0),
                'is_public': True,
            },
        )

        if book.rules.exists():
            if not replace:
                raise CommandError(
                    f'{book.slug}에 이미 규칙이 있습니다. 기존 편집 내용을 덮어쓰려면 --replace를 사용하세요.'
                )
            book.rules.all().delete()

        for language, document in source_documents.items():
            language_metadata = document['metadata']
            RulebookTranslation.objects.update_or_create(
                rulebook=book,
                language=language,
                defaults={
                    'title': language_metadata.get('title') or metadata.get('title') or book.slug,
                    'short_title': (
                        language_metadata.get('short_title')
                        or language_metadata.get('title')
                        or metadata.get('short_title')
                        or book.slug
                    ),
                    'summary': config.get('summary', ''),
                },
            )

        translations_by_language = {
            language: _match_translated_entries(korean['entries'], document['entries'])
            for language, document in source_documents.items()
        }
        existing_references = set(
            Rule.objects.exclude(rulebook=book).values_list('reference_name', flat=True)
        )
        parent_stack = {}
        rules_by_number = {}
        sibling_priorities = {}
        created_rules = []
        translation_count = 0

        for index, entry in enumerate(korean['entries']):
            reference_name = _unique_reference(
                entry['reference_name'],
                config['slug'],
                existing_references,
            )
            parent = _find_parent(entry, parent_stack, rules_by_number)
            parent_key = parent.pk if parent else None
            priority = sibling_priorities.get(parent_key, 0) + 10
            sibling_priorities[parent_key] = priority
            rule = Rule.objects.create(
                rulebook=book,
                parent=parent,
                reference_name=reference_name,
                priority=priority,
                show_in_toc=entry['show_in_toc'],
                is_public=True,
            )
            created_rules.append(rule)
            existing_references.add(reference_name)
            parent_stack[entry['depth']] = rule
            for depth in [item for item in parent_stack if item > entry['depth']]:
                del parent_stack[depth]
            if entry['full_number']:
                rules_by_number[entry['full_number']] = rule

            for language in sorted(RULEBOOK_LANGUAGES):
                translated = translations_by_language[language][index]
                if translated is None:
                    continue
                RuleTranslation.objects.create(
                    rule=rule,
                    language=language,
                    title=translated['title'],
                    content=translated['html'],
                )
                translation_count += 1

        semanticize_rulebooks(
            [book],
            source_numbers={
                book.pk: {
                    number: rule.pk
                    for number, rule in rules_by_number.items()
                },
            },
        )
        visuals = import_rulebook_visuals(book, config, replace=True)
        return {
            'rules': len(created_rules),
            'translations': translation_count,
            'visuals': len(visuals),
        }

    def _parse_source(self, config, language):
        metadata, body = _load_markdown(config['filename'], language)
        body = _prepare_public_body(config['slug'], body)
        body = _rewrite_local_links(body)
        return {
            'metadata': metadata,
            'entries': _parse_entries(body, config['slug']),
        }


def _parse_entries(body, slug):
    entries = []
    current = None
    pending_anchor = ''
    generated_index = 0

    def flush():
        nonlocal current
        if current is None:
            return
        markdown_body = '\n'.join(current.pop('lines')).strip()
        markdown_body = _format_callouts(markdown_body)
        markdown_body = _badge_review_markers(markdown_body)
        current['html'] = str(_render_markdown(markdown_body))
        entries.append(current)
        current = None

    for line in body.splitlines():
        anchor_match = ANCHOR_RE.match(line)
        if anchor_match:
            if pending_anchor and current is not None:
                current['lines'].append(f'<a id="{pending_anchor}"></a>')
            pending_anchor = anchor_match.group(1)
            continue

        heading_match = HEADING_RE.match(line)
        rule_match = NUMBERED_RULE_RE.match(line)
        if heading_match or rule_match:
            flush()
            generated_index += 1
            if heading_match:
                raw_title = heading_match.group(2).strip()
                full_number, title = _split_numbered_title(raw_title)
                depth = len(heading_match.group(1)) - 1
                show_in_toc = True
                initial_lines = []
            else:
                full_number = rule_match.group(1)
                statement = rule_match.group(2).strip()
                title = _short_rule_title(statement)
                depth = max(len(full_number.split('.')) - 1, 0)
                show_in_toc = False
                initial_lines = [statement]
            current = {
                'source_anchor': pending_anchor,
                'reference_name': pending_anchor or f'{slug}-section-{generated_index}',
                'title': title,
                'full_number': full_number,
                'depth': depth,
                'show_in_toc': show_in_toc,
                'lines': initial_lines,
            }
            pending_anchor = ''
            continue

        if pending_anchor and line.strip():
            if current is not None:
                current['lines'].append(f'<a id="{pending_anchor}"></a>')
            pending_anchor = ''
        if current is not None:
            current['lines'].append(line)

    flush()
    return entries


def _split_numbered_title(value):
    match = NUMBERED_TITLE_RE.match(value)
    if not match:
        return '', value
    return match.group(1), match.group(2).strip()


def _short_rule_title(statement):
    text = re.sub(r'<[^>]+>|[`*_~\[\]]', '', statement)
    text = re.sub(r'\s+', ' ', text).strip()
    first_sentence = re.split(r'(?<=[.!?。])\s+', text, maxsplit=1)[0]
    return first_sentence if len(first_sentence) <= 90 else f'{first_sentence[:87].rstrip()}...'


def _match_translated_entries(korean_entries, translated_entries):
    translated_by_anchor = {
        item['source_anchor']: item
        for item in translated_entries
        if item['source_anchor']
    }
    matched = []
    for index, korean in enumerate(korean_entries):
        translated = translated_by_anchor.get(korean['source_anchor']) if korean['source_anchor'] else None
        if translated is None and index < len(translated_entries):
            translated = translated_entries[index]
        matched.append(translated)
    return matched


def _find_parent(entry, parent_stack, rules_by_number):
    if entry['full_number'] and '.' in entry['full_number']:
        numbered_parent = rules_by_number.get(entry['full_number'].rsplit('.', 1)[0])
        if numbered_parent is not None:
            return numbered_parent
    for depth in range(entry['depth'] - 1, -1, -1):
        if depth in parent_stack:
            return parent_stack[depth]
    return None


def _unique_reference(reference, slug, existing):
    candidate = reference
    if candidate not in existing:
        return candidate
    candidate = f'{slug}-{reference}'
    suffix = 2
    while candidate in existing:
        candidate = f'{slug}-{reference}-{suffix}'
        suffix += 1
    return candidate


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
