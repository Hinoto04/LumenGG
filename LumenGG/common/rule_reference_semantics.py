import re
from html import unescape
from html.parser import HTMLParser

from django.db import transaction
from django.utils.html import strip_tags
from django.utils.text import slugify

from .models import Rule, RuleTranslation


BOOK_REFERENCE_PREFIXES = {
    'comprehensive': 'rule',
    'tournament': 'floor',
}
REFERENCE_TOKEN_RE = re.compile(r'\[\[([^\[\]]+?)\]\]')
NUMBER_REFERENCE_RE = re.compile(
    r'(?<![\d.vV])(\d+(?:\.\d+){1,3})(?![\d.]|-web)'
)
HREF_FRAGMENT_RE = re.compile(r'(?P<prefix>href\s*=\s*["\'][^"\']*#)(?P<reference>[^"\']+)')
RULE_ANCHOR_LINK_RE = re.compile(
    r'<a\b[^>]*\bhref=(?P<quote>["\'])(?P<href>[^"\']*#(?P<reference>[^"\']+))(?P=quote)[^>]*>'
    r'(?P<label>.*?)</a>',
    re.I | re.S,
)
SKIP_TEXT_TAGS = {'a', 'code', 'pre', 'script', 'style'}


def semanticize_rulebooks(rulebooks, *, source_numbers=None):
    """Assign readable references and turn plain rule-number mentions into tokens."""
    rulebooks = list(rulebooks)
    if not rulebooks:
        return {'renamed': 0, 'rewritten': 0}

    book_ids = [book.pk for book in rulebooks]
    rules = list(
        Rule.objects
        .filter(rulebook_id__in=book_ids)
        .select_related('rulebook', 'parent')
        .prefetch_related('translations')
        .order_by('rulebook__sort_order', 'priority', 'id')
    )
    reserved = set(
        Rule.objects
        .exclude(rulebook_id__in=book_ids)
        .values_list('reference_name', flat=True)
    )
    for aliases in (
        Rule.objects
        .exclude(rulebook_id__in=book_ids)
        .values_list('reference_aliases', flat=True)
    ):
        reserved.update(aliases or [])

    final_references = {}
    used = set(reserved)
    for rule in rules:
        candidate = semantic_reference_for_rule(rule)
        final_reference = _unique_reference(candidate, rule.full_number, used)
        final_references[rule.pk] = final_reference
        used.add(final_reference)

    renamed = 0
    old_to_new = {}
    for rule in rules:
        final_reference = final_references[rule.pk]
        for old_reference in [rule.reference_name, *(rule.reference_aliases or [])]:
            if old_reference:
                old_to_new[old_reference] = final_reference
        if rule.reference_name != final_reference:
            renamed += 1

    changed_rules = [rule for rule in rules if rule.reference_name != final_references[rule.pk]]
    with transaction.atomic():
        for rule in changed_rules:
            rule.reference_name = f'temporary-rule-reference-{rule.pk}'
        if changed_rules:
            Rule.objects.bulk_update(changed_rules, ['reference_name'])

        for rule in rules:
            final_reference = final_references[rule.pk]
            aliases = []
            for alias in [rule.reference_name, *old_to_new.keys(), *(rule.reference_aliases or [])]:
                if old_to_new.get(alias) == final_reference and alias != final_reference and alias not in aliases:
                    aliases.append(alias)
            rule.reference_name = final_reference
            rule.reference_aliases = aliases
            rule.reference_targets = [
                old_to_new.get(reference, reference)
                for reference in (rule.reference_targets or [])
            ]
        Rule.objects.bulk_update(
            rules,
            ['reference_name', 'reference_aliases', 'reference_targets'],
        )

        current_reference_by_alias = _all_reference_aliases()
        number_maps = _number_maps(rules)
        for book_id, source_rule_ids in (source_numbers or {}).items():
            book_number_map = number_maps.setdefault(book_id, {})
            for number, rule_id in source_rule_ids.items():
                reference_name = final_references.get(rule_id)
                if number and reference_name:
                    book_number_map[number] = reference_name
        translations = list(
            RuleTranslation.objects
            .filter(rule__rulebook_id__in=book_ids)
            .select_related('rule__rulebook')
        )
        changed_translations = []
        for translation in translations:
            rewritten = rewrite_rule_content(
                translation.content,
                aliases=current_reference_by_alias,
                number_targets=number_maps.get(translation.rule.rulebook_id, {}),
            )
            if rewritten != translation.content:
                translation.content = rewritten
                changed_translations.append(translation)
        if changed_translations:
            RuleTranslation.objects.bulk_update(changed_translations, ['content'])

    return {
        'renamed': renamed,
        'rewritten': len(changed_translations),
        'references': _all_reference_aliases(),
    }


def semantic_reference_for_rule(rule):
    explicit_reference = (rule.reference_name or '').strip()
    prefix = BOOK_REFERENCE_PREFIXES.get(rule.rulebook.slug, slugify(rule.rulebook.slug) or 'rule')
    if (
        re.fullmatch(rf'{re.escape(prefix)}-[a-z][a-z0-9-]*', explicit_reference)
        and not explicit_reference.startswith(f'{prefix}-section-')
    ):
        return explicit_reference[:120].rstrip('-')

    translations = list(rule.translations.all())
    english = next((item for item in translations if item.language == 'en' and item.title), None)
    korean = next((item for item in translations if item.language == 'ko' and item.title), None)
    title = (english.title if english else '') or (korean.title if korean else '') or rule.reference_name
    semantic_name = slugify(title) or slugify(title, allow_unicode=True)
    semantic_name = semantic_name.strip('-')[:88].rstrip('-')
    if not semantic_name:
        semantic_name = f'section-{rule.full_number.replace(".", "-") or rule.pk}'
    return f'{prefix}-{semantic_name}'[:120].rstrip('-')


def rewrite_rule_content(html, *, aliases, number_targets):
    html = RULE_ANCHOR_LINK_RE.sub(
        lambda match: _rule_link_token(match, aliases),
        str(html or ''),
    )
    parser = _ReferenceContentRewriter(aliases, number_targets)
    parser.feed(html)
    parser.close()
    return ''.join(parser.output)


def _rule_link_token(match, aliases):
    reference = match.group('reference')
    current_reference = aliases.get(reference)
    if not current_reference:
        return match.group(0)
    label = unescape(strip_tags(match.group('label'))).strip() or current_reference
    label = label.replace('|', '·').replace(']]', '')
    return f'[[{current_reference}|{label}]]'


def _all_reference_aliases():
    references = {}
    for reference_name, aliases in Rule.objects.values_list('reference_name', 'reference_aliases'):
        references[reference_name] = reference_name
        for alias in aliases or []:
            references[alias] = reference_name
    return references


def _number_maps(rules):
    maps = {}
    for rule in rules:
        number = rule.full_number
        if number:
            maps.setdefault(rule.rulebook_id, {})[number] = rule.reference_name
    return maps


def _unique_reference(candidate, number, used):
    if candidate not in used:
        return candidate
    number_suffix = number.replace('.', '-') if number else 'section'
    numbered_candidate = f'{candidate[:110].rstrip("-")}-{number_suffix}'
    if numbered_candidate not in used:
        return numbered_candidate
    index = 2
    while True:
        suffix = f'-{index}'
        indexed_candidate = f'{candidate[:120 - len(suffix)].rstrip("-")}{suffix}'
        if indexed_candidate not in used:
            return indexed_candidate
        index += 1


class _ReferenceContentRewriter(HTMLParser):
    def __init__(self, aliases, number_targets):
        super().__init__(convert_charrefs=False)
        self.aliases = aliases
        self.number_targets = number_targets
        self.output = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        raw = self.get_starttag_text()
        self.output.append(HREF_FRAGMENT_RE.sub(self._rewrite_href, raw))
        if tag.lower() in SKIP_TEXT_TAGS:
            self.skip_depth += 1

    def handle_startendtag(self, tag, attrs):
        self.output.append(HREF_FRAGMENT_RE.sub(self._rewrite_href, self.get_starttag_text()))

    def handle_endtag(self, tag):
        self.output.append(f'</{tag}>')
        if tag.lower() in SKIP_TEXT_TAGS and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            self.output.append(data)
            return
        token_updated = REFERENCE_TOKEN_RE.sub(self._rewrite_token, data)
        parts = REFERENCE_TOKEN_RE.split(token_updated)
        rebuilt = []
        for index, part in enumerate(parts):
            if index % 2:
                rebuilt.append(f'[[{part}]]')
            else:
                rebuilt.append(NUMBER_REFERENCE_RE.sub(self._rewrite_number, part))
        self.output.append(''.join(rebuilt))

    def handle_entityref(self, name):
        self.output.append(f'&{name};')

    def handle_charref(self, name):
        self.output.append(f'&#{name};')

    def handle_comment(self, data):
        self.output.append(f'<!--{data}-->')

    def handle_decl(self, decl):
        self.output.append(f'<!{decl}>')

    def _rewrite_href(self, match):
        reference = match.group('reference')
        return f'{match.group("prefix")}{self.aliases.get(reference, reference)}'

    def _rewrite_token(self, match):
        raw = match.group(1).strip()
        reference, separator, label = raw.partition('|')
        current_reference = self.aliases.get(reference.strip(), reference.strip())
        return f'[[{current_reference}{"|" + label if separator else ""}]]'

    def _rewrite_number(self, match):
        number = match.group(1)
        reference = self.number_targets.get(number)
        return f'[[{reference}|{number}]]' if reference else number
