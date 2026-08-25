import json
import re
from collections import defaultdict
from html import escape
from pathlib import Path
from urllib.parse import quote

import markdown
from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError
from django.urls import NoReverseMatch, reverse
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from .language import normalize_language, ui_text
from .models import Rule, Rulebook
from .rule_references import link_rule_references

try:
    import bleach
except ImportError:  # pragma: no cover - trusted local content fallback
    bleach = None


CONTENT_DIR = Path(settings.BASE_DIR) / 'content' / 'rulebook'
CATALOG_PATH = CONTENT_DIR / 'catalog.json'
RULEBOOK_LANGUAGES = {'ko', 'en', 'ja'}

ALLOWED_TAGS = {
    'a', 'abbr', 'b', 'blockquote', 'br', 'code', 'dd', 'del', 'div', 'dl',
    'dt', 'em', 'figcaption', 'figure', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 'span', 'strong', 'sub', 'sup',
    'table', 'tbody', 'td', 'th', 'thead', 'tr', 'u', 'ul',
}
ALLOWED_ATTRIBUTES = {
    '*': ['class', 'id', 'title'],
    'a': ['href', 'id', 'name', 'rel', 'target', 'title'],
    'img': ['alt', 'height', 'loading', 'src', 'title', 'width'],
    'td': ['align', 'colspan', 'rowspan'],
    'th': ['align', 'colspan', 'rowspan', 'scope'],
}


def public_rulebook_summaries(language='ko'):
    language = _rulebook_language(language)
    summaries = []
    known_slugs = set()

    for config in _rulebook_configs():
        known_slugs.add(config['slug'])
        summaries.append(rulebook_summary(config['slug'], language))

    try:
        extra_books = (
            Rulebook.objects
            .filter(is_public=True, rules__is_public=True)
            .exclude(slug__in=known_slugs)
            .prefetch_related('translations')
            .distinct()
            .order_by('sort_order', 'id')
        )
        summaries.extend(_database_rulebook_summary(book, language) for book in extra_books)
    except (OperationalError, ProgrammingError):
        pass

    return summaries


def rulebook_summary(slug, language='ko'):
    language = _rulebook_language(language)
    database_summary = _database_rulebook_summary_by_slug(slug, language)
    if database_summary is not None:
        return database_summary

    config = _rulebook_config(slug)
    metadata, _body = _load_markdown(config['filename'], language)
    return {
        **config,
        'title': metadata.get('title') or config['filename'],
        'short_title': metadata.get('short_title') or metadata.get('title') or config['filename'],
        'summary': ui_text(config.get('summary', ''), language),
        'version': metadata.get('version', ''),
        'status': metadata.get('status', ''),
        'updated': metadata.get('updated') or metadata.get('web_edited') or metadata.get('source_updated') or '',
        'language': language,
        'translation_status': metadata.get('translation_status', ''),
        'href': _rulebook_href(config['slug'], config.get('url_name')),
        'source': 'markdown',
    }


def get_rulebook(slug, language='ko'):
    language = _rulebook_language(language)
    database_rulebook = _get_database_rulebook(slug, language)
    if database_rulebook is not None:
        return database_rulebook

    config = _rulebook_config(slug)
    metadata, body = _load_markdown(config['filename'], language)
    body = _prepare_public_body(slug, body)
    body = _rewrite_local_links(body)
    body, toc = _add_heading_anchors(body)
    search_items = _build_search_items(
        body,
        slug=slug,
        anchor_prefix=config.get('anchor_prefix', 'rule-'),
    ) if config.get('searchable') else []
    body = _format_callouts(body)
    body = _badge_review_markers(body)

    return {
        **rulebook_summary(slug, language),
        'metadata': metadata,
        'toc': toc,
        'html': _render_markdown(body),
        'search_items': search_items,
        'visuals': _translate_visuals(_load_visuals(config, toc=toc), language),
        'translation_notice': _translation_notices().get(language),
    }


def ordered_rule_tree(rules):
    """Return rules in priority tree order with automatic decimal numbers."""
    rules = list(rules)
    rule_ids = {rule.pk for rule in rules}
    children = defaultdict(list)
    for rule in rules:
        parent_id = rule.parent_id if rule.parent_id in rule_ids else None
        children[parent_id].append(rule)
    for child_rules in children.values():
        child_rules.sort(key=lambda item: (item.priority, item.pk))

    rows = []
    visited = set()

    def visit(rule, depth, number_parts):
        if rule.pk in visited:
            return
        visited.add(rule.pk)
        rows.append({'rule': rule, 'depth': depth, 'number': '.'.join(number_parts)})
        for index, child in enumerate(children.get(rule.pk, []), start=1):
            visit(child, depth + 1, [*number_parts, str(index)])

    root_number = 0
    for root_number, root in enumerate(children.get(None, []), start=1):
        visit(root, 0, [str(root_number)])
    for rule in rules:
        if rule.pk not in visited:
            root_number += 1
            visit(rule, 0, [str(root_number)])
    return rows


def _get_database_rulebook(slug, language):
    try:
        book = (
            Rulebook.objects
            .filter(slug=slug, is_public=True, rules__is_public=True)
            .prefetch_related('translations', 'visual_guides__translations')
            .distinct()
            .get()
        )
        rules = list(
            Rule.objects
            .filter(rulebook=book)
            .select_related('parent', 'rulebook')
            .prefetch_related('translations', 'visual_guides__translations')
        )
    except (Rulebook.DoesNotExist, OperationalError, ProgrammingError):
        return None

    rows = ordered_rule_tree(rules)
    references = _reference_targets(language, current_book=book)
    toc = []
    html_parts = []
    search_items = []
    heading_targets = {}
    has_inline_visuals = False

    for row in rows:
        rule = row['rule']
        if not rule.is_public:
            continue
        translation = _rule_translation(rule, language)
        title = translation['title'] or rule.reference_name
        number = row['number']
        display_title = f'{number} {title}'.strip()
        anchor = rule.reference_name
        level = min(row['depth'] + 1, 4)
        heading_level = min(row['depth'] + 2, 6)
        if rule.show_in_toc:
            toc.append({'level': level, 'title': display_title, 'anchor': anchor})

        korean_translation = _rule_translation(rule, 'ko')
        korean_display_title = f'{number} {korean_translation["title"]}'.strip()
        for heading in {title, display_title, korean_translation['title'], korean_display_title}:
            if heading:
                heading_targets[heading] = f'#{quote(anchor, safe="")}'

        content = _sanitize_html(translation['content'])
        content = link_rule_references(content, references)
        visual_html = _render_rule_visual_guides(rule, language, references)
        has_inline_visuals = has_inline_visuals or bool(visual_html)
        number_html = f'<span class="v2-rule-number">{escape(number)}</span> ' if number else ''
        alias_html = ''.join(
            f'<span class="v2-rule-anchor-alias" id="{escape(alias, quote=True)}"></span>'
            for alias in rule.reference_aliases
            if alias and alias != anchor
        )
        html_parts.append(
            alias_html +
            f'<section class="v2-rule-section" id="{escape(anchor, quote=True)}" '
            f'data-rule-reference="{escape(anchor, quote=True)}">'
            f'<h{heading_level}>{number_html}{escape(title)}</h{heading_level}>'
            f'{visual_html}{content}</section>'
        )

        if book.searchable:
            search_items.append({
                'anchor': anchor,
                'number': display_title,
                'text': _compact_text(strip_tags(content))[:360],
                'url': f'{_rulebook_href(book.slug, book.url_name)}#{quote(anchor, safe="")}',
            })

    summary = _database_rulebook_summary(book, language)
    page_visual_html = _render_rulebook_visual_guides(book, language, references)
    return {
        **summary,
        'metadata': {},
        'toc': toc,
        'html': mark_safe(''.join(html_parts)),
        'search_items': search_items,
        'has_inline_visuals': has_inline_visuals,
        'page_visual_html': page_visual_html,
        'has_page_visuals': bool(page_visual_html),
        'visuals': [],
        'translation_notice': _translation_notices().get(language),
    }


def _database_rulebook_summary_by_slug(slug, language):
    try:
        book = (
            Rulebook.objects
            .filter(slug=slug, is_public=True, rules__is_public=True)
            .prefetch_related('translations')
            .distinct()
            .get()
        )
    except (Rulebook.DoesNotExist, OperationalError, ProgrammingError):
        return None
    return _database_rulebook_summary(book, language)


def _database_rulebook_summary(book, language):
    translation = _book_translation(book, language)
    return {
        'slug': book.slug,
        'url_name': book.url_name,
        'kicker': book.kicker,
        'summary': translation['summary'],
        'searchable': book.searchable,
        'anchor_prefix': book.anchor_prefix,
        'visual_file': book.visual_file,
        'title': translation['title'] or book.slug,
        'short_title': translation['short_title'] or translation['title'] or book.slug,
        'version': book.version,
        'status': '',
        'updated': book.updated_on.isoformat() if book.updated_on else '',
        'language': language,
        'translation_status': '',
        'href': _rulebook_href(book.slug, book.url_name),
        'source': 'database',
    }


def _book_translation(book, language):
    translations = list(book.translations.all())
    selected = _select_translation(translations, language)
    korean = next((item for item in translations if item.language == 'ko'), None)
    return {
        'title': (selected.title if selected else '') or (korean.title if korean else ''),
        'short_title': (selected.short_title if selected else '') or (korean.short_title if korean else ''),
        'summary': (selected.summary if selected else '') or (korean.summary if korean else ''),
    }


def _rule_translation(rule, language):
    translations = list(rule.translations.all())
    selected = _select_translation(translations, language)
    korean = next((item for item in translations if item.language == 'ko'), None)
    return {
        'title': (selected.title if selected else '') or (korean.title if korean else ''),
        'content': (selected.content if selected else '') or (korean.content if korean else ''),
    }


def _rule_visual_translation(guide, language):
    translations = list(guide.translations.all())
    selected = _select_translation(translations, language)
    korean = next((item for item in translations if item.language == 'ko'), None)
    return {
        'title': (selected.title if selected else '') or (korean.title if korean else ''),
        'content': (selected.content if selected else '') or (korean.content if korean else ''),
    }


def _render_rule_visual_guides(rule, language, references):
    guides = [guide for guide in rule.visual_guides.all() if guide.is_public]
    if not guides:
        return ''

    guide_data = []
    for guide in guides:
        translation = _rule_visual_translation(guide, language)
        title = translation['title'] or f'Visual {guide.pk}'
        content = link_rule_references(translation['content'], references)
        guide_data.append({
            'guide': guide,
            'title': title,
            'content': content,
            'key': f'rule-visual-{guide.pk}',
        })

    if len(guide_data) > 1:
        tabs = ''.join(
            f'<button type="button" role="tab" '
            f'class="{"is-active" if index == 0 else ""}" '
            f'aria-selected="{"true" if index == 0 else "false"}" '
            f'data-rule-inline-visual-tab="{item["key"]}">'
            f'{escape(item["title"])}</button>'
            for index, item in enumerate(guide_data)
        )
        heading = f'<div class="v2-rule-inline-visual-tabs" role="tablist">{tabs}</div>'
    else:
        heading = f'<strong class="v2-rule-inline-visual-title">{escape(guide_data[0]["title"])}</strong>'

    panels = []
    for index, item in enumerate(guide_data):
        guide = item['guide']
        hidden = ' hidden' if index else ''
        style = f'<style data-rule-visual-style="{guide.pk}">{guide.css}</style>' if guide.css else ''
        script = (
            f'<script data-rule-visual-script="{guide.pk}">{guide.javascript}</script>'
            if guide.javascript else ''
        )
        panels.append(
            f'<div class="v2-rule-inline-visual-panel{_visual_style_class(guide)}" role="tabpanel" '
            f'data-rule-inline-visual-panel="{item["key"]}"{hidden}>'
            f'<div class="v2-rule-inline-visual-content">{item["content"]}</div>'
            f'{style}{script}</div>'
        )

    return (
        '<div class="v2-rule-inline-visual" data-rule-inline-visual>'
        '<div class="v2-rule-inline-visual-head">'
        '<span>VISUAL GUIDE</span>'
        f'{heading}</div>{"".join(panels)}</div>'
    )


def _render_rulebook_visual_guides(book, language, references):
    guides = [
        guide
        for guide in book.visual_guides.all()
        if guide.rule_id is None and guide.is_public
    ]
    if not guides:
        return ''

    guide_data = []
    for guide in guides:
        translation = _rule_visual_translation(guide, language)
        guide_data.append({
            'guide': guide,
            'title': translation['title'] or f'Visual {guide.pk}',
            'content': link_rule_references(translation['content'], references),
            'key': f'rulebook-visual-{guide.pk}',
        })

    tabs = ''.join(
        f'<button type="button" role="tab" '
        f'class="{"is-active" if index == 0 else ""}" '
        f'aria-selected="{"true" if index == 0 else "false"}" '
        f'data-rulebook-visual-tab="{item["key"]}">'
        f'{escape(item["title"])}</button>'
        for index, item in enumerate(guide_data)
    )
    panels = []
    for index, item in enumerate(guide_data):
        guide = item['guide']
        hidden = ' hidden' if index else ''
        style = f'<style data-rule-visual-style="{guide.pk}">{guide.css}</style>' if guide.css else ''
        script = (
            f'<script data-rule-visual-script="{guide.pk}">{guide.javascript}</script>'
            if guide.javascript else ''
        )
        panels.append(
            f'<article class="v2-rulebook-visual-panel{_visual_style_class(guide)}" '
            f'data-rulebook-visual-panel="{item["key"]}"{hidden}>'
            f'{item["content"]}{style}{script}</article>'
        )

    title = escape(ui_text('핵심 구조', language))
    description = escape(ui_text(
        '그림에서 궁금한 영역을 누르면 설명을 확인하고 관련 본문으로 이동할 수 있습니다.',
        language,
    ))
    common_style = (
        f'<style data-rulebook-visual-common-style="{book.pk}">{book.visual_css}</style>'
        if book.visual_css else ''
    )
    common_script = (
        f'<script data-rulebook-visual-common-script="{book.pk}">{book.visual_javascript}</script>'
        if book.visual_javascript else ''
    )
    return mark_safe(
        '<section class="v2-panel v2-rulebook-visual" data-rulebook-visual>'
        '<div class="v2-rulebook-visual-head"><div>'
        '<div class="v2-kicker">VISUAL GUIDE</div>'
        f'<h2>{title}</h2><p>{description}</p></div>'
        f'<div class="v2-rulebook-visual-tabs" role="tablist">{tabs}</div></div>'
        f'{"".join(panels)}{common_style}{common_script}</section>'
    )


def _visual_style_class(guide):
    style_key = re.sub(r'[^a-zA-Z0-9_-]', '', guide.style_key or '')
    return f' is-{style_key}' if style_key else ''


def _select_translation(translations, language):
    return (
        next((item for item in translations if item.language == language), None)
        or next((item for item in translations if item.language == 'ko'), None)
        or (translations[0] if translations else None)
    )


def _reference_targets(language, current_book):
    try:
        books = list(
            Rulebook.objects
            .filter(is_public=True, rules__is_public=True)
            .prefetch_related('translations')
            .distinct()
        )
        rules = list(
            Rule.objects
            .filter(rulebook__is_public=True)
            .select_related('rulebook', 'parent')
            .prefetch_related('translations')
        )
    except (OperationalError, ProgrammingError):
        return {}

    targets = {}
    rules_by_book = defaultdict(list)
    for rule in rules:
        rules_by_book[rule.rulebook_id].append(rule)

    books_by_id = {book.pk: book for book in books}
    for book_id, book_rules in rules_by_book.items():
        book = books_by_id.get(book_id)
        if book is None:
            continue
        base_href = '' if book.pk == current_book.pk else _rulebook_href(book.slug, book.url_name)
        for row in ordered_rule_tree(book_rules):
            rule = row['rule']
            if not rule.is_public:
                continue
            title = _rule_translation(rule, language)['title'] or rule.reference_name
            targets[rule.reference_name] = {
                'label': f'{row["number"]} {title}'.strip(),
                'number': row['number'],
                'href': f'{base_href}#{quote(rule.reference_name, safe="")}',
            }
            for alias in rule.reference_aliases:
                if alias:
                    targets[alias] = targets[rule.reference_name]
    return targets


def _rulebook_href(slug, url_name=''):
    if url_name:
        try:
            return reverse(url_name)
        except NoReverseMatch:
            pass
    try:
        return reverse('rules:detail', kwargs={'slug': slug})
    except NoReverseMatch:
        return f'/rules/{slug}/'


def _catalog():
    return json.loads(CATALOG_PATH.read_text(encoding='utf-8'))


def _rulebook_configs():
    return sorted(
        _catalog().get('rulebooks', []),
        key=lambda item: (item.get('order', 0), item['slug']),
    )


def _rulebook_config(slug):
    for config in _rulebook_configs():
        if config['slug'] == slug:
            return config
    raise KeyError(slug)


def _translation_notices():
    return _catalog().get('translation_notices', {})


def _rulebook_language(language):
    language = normalize_language(language)
    return language if language in RULEBOOK_LANGUAGES else 'ko'


def _load_markdown(filename, language='ko'):
    language = _rulebook_language(language)
    path = CONTENT_DIR / filename if language == 'ko' else CONTENT_DIR / language / filename
    text = path.read_text(encoding='utf-8')
    return _split_frontmatter(text)


def _split_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return {}, text

    end_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == '---'),
        None,
    )
    if end_index is None:
        return {}, text

    metadata = {}
    for line in lines[1:end_index]:
        if ':' not in line or line.startswith(' '):
            continue
        key, value = line.split(':', 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, '\n'.join(lines[end_index + 1:])


def _prepare_public_body(slug, body):
    body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
    if slug == 'guide':
        body = re.sub(r'\n# 웹 시각화 설계표\n.*?(?=\n# 관련 문서|\Z)', '\n', body, flags=re.S)
    if slug == 'tournament':
        body = body.replace('[원본 PDF 보기](./source/루멘콘덴서%20플로어룰20260530개정.pdf) · ', '')
        body = re.sub(r'\n- \[12\. 웹 편집 및 교차 문서 확인 사항\]\(#floor-editorial-notes\)', '', body)
        body = re.sub(
            r'\n<a id="floor-editorial-notes"></a>\n# 12\. 웹 편집 및 교차 문서 확인 사항\n.*?(?=\n---\n\n# 개정 이력|\Z)',
            '\n',
            body,
            flags=re.S,
        )
    return body.strip()


def _rewrite_local_links(body):
    replacements = {
        './lumen-comprehensive-rules.md': '/rules/comprehensive/',
        'lumen-comprehensive-rules.md': '/rules/comprehensive/',
        './lumen-beginner-guide.md': '/rules/guide/',
        'lumen-beginner-guide.md': '/rules/guide/',
        './lumen-tournament-floor-rules.md': '/rules/tournament/',
        'lumen-tournament-floor-rules.md': '/rules/tournament/',
        './VISUAL_ASSET_INDEX.md': '/rules/',
        'VISUAL_ASSET_INDEX.md': '/rules/',
    }
    for source, target in replacements.items():
        body = body.replace(f']({source}#', f']({target}#')
        body = body.replace(f']({source})', f']({target})')
    return body


def _add_heading_anchors(body):
    toc = []
    output = []
    pending_anchor = ''
    section_index = 0
    anchor_pattern = re.compile(r'^\s*<a\s+id="([^"]+)"></a>\s*$')
    heading_pattern = re.compile(r'^(#{1,4})\s+(.+?)\s*$')

    for line in body.splitlines():
        anchor_match = anchor_pattern.match(line)
        if anchor_match:
            pending_anchor = anchor_match.group(1)
            output.append(line)
            continue
        heading_match = heading_pattern.match(line)
        if heading_match:
            section_index += 1
            level = len(heading_match.group(1))
            title = _strip_inline_markup(heading_match.group(2))
            anchor = pending_anchor or f'section-{section_index}'
            if not pending_anchor:
                output.append(f'<a id="{anchor}"></a>')
            toc.append({'level': level, 'title': title, 'anchor': anchor})
            pending_anchor = ''
        output.append(line)
        if pending_anchor and line.strip():
            pending_anchor = ''
    return '\n'.join(output), toc


def _anchor_for_title(toc, title, fallback='#'):
    for item in toc:
        if item['title'] == title:
            return f'#{item["anchor"]}'
    number_match = re.match(r'^(\d+(?:\.\d+)*)\.?\s+', title)
    if number_match:
        pattern = re.compile(rf'^{re.escape(number_match.group(1))}(?:\.|\s)')
        for item in toc:
            if pattern.match(item['title']):
                return f'#{item["anchor"]}'
    return fallback


def _load_visuals(config, *, toc, heading_targets=None):
    visual_file = config.get('visual_file', '')
    if not visual_file:
        return []
    path = CONTENT_DIR / visual_file
    if not path.exists():
        return []
    visuals = json.loads(path.read_text(encoding='utf-8')).get('visuals', [])
    heading_targets = heading_targets or {}

    def resolve(value):
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, dict):
            if 'heading' in value and set(value).intersection({'heading', 'fallback'}):
                heading = value['heading']
                return heading_targets.get(heading) or _anchor_for_title(toc, heading, value.get('fallback', '#'))
            return {key: resolve(item) for key, item in value.items()}
        return value

    return resolve(visuals)


def _translate_visuals(visuals, language):
    if language == 'ko':
        return visuals
    path = CONTENT_DIR / 'visuals' / f'translations.{language}.json'
    catalog = {}
    if path.exists():
        catalog = json.loads(path.read_text(encoding='utf-8')).get('translations', {})
    translatable_keys = {'title', 'summary', 'label', 'text', 'hint'}

    def translated_text(value):
        translated = catalog.get(value)
        if translated is not None or not re.search(r'[가-힣]', value):
            return translated if translated is not None else value
        return ui_text(value, language)

    def translate(value):
        if isinstance(value, list):
            return [translate(item) for item in value]
        if isinstance(value, dict):
            return {
                key: translated_text(item) if key in translatable_keys and isinstance(item, str) else translate(item)
                for key, item in value.items()
            }
        return value

    return translate(visuals)


def _badge_review_markers(body):
    return re.sub(
        r'`\[(확인 필요|세부 확인 필요|검토 초안|편집 정의|편집 명문화|표기 방식 확인 필요)\]`|\[(확인 필요|세부 확인 필요|검토 초안|편집 정의|편집 명문화|표기 방식 확인 필요)\]',
        lambda match: f'<span class="v2-rulebook-badge">{match.group(1) or match.group(2)}</span>',
        body,
    )


def _format_callouts(body):
    return re.sub(
        r'^> \[!(NOTE|IMPORTANT|WARNING|CAUTION)\]\s*$',
        lambda match: f'> <span class="v2-rulebook-badge">{match.group(1)}</span>',
        body,
        flags=re.M,
    )


def _sanitize_html(html):
    if bleach is None:
        return str(html or '')
    return bleach.clean(
        str(html or ''),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=['http', 'https', 'mailto'],
        strip=True,
    )


def _render_markdown(body):
    html = markdown.markdown(
        body,
        extensions=['extra', 'sane_lists', 'fenced_code', 'tables'],
        output_format='html5',
    )
    return mark_safe(_sanitize_html(html))


def _build_search_items(body, *, slug, anchor_prefix='rule-'):
    items = []
    url_path = f'/rules/{slug}/'
    if anchor_prefix == 'rule-':
        pattern = re.compile(
            r'<a id="(rule-[^"]+)"></a>\s*\n\*\*([^*]+)\*\*\s*(.*?)(?=\n<a id="rule-|\n<a id="chapter-|\n# |\n## |\Z)',
            re.S,
        )
        for match in pattern.finditer(body):
            anchor = match.group(1)
            items.append({
                'anchor': anchor,
                'number': _strip_inline_markup(match.group(2)),
                'text': _compact_text(match.group(3)),
                'url': f'{url_path}#{anchor}',
            })
        return items

    escaped_prefix = re.escape(anchor_prefix)
    pattern = re.compile(
        r'<a id="(' + escaped_prefix + r'[^"]+)"></a>\s*\n(#{1,4})\s+(.+?)\s*\n(.*?)(?=\n<a id="' + escaped_prefix + r'|\n<a id="section-|\n# |\n## |\n### |\n#### |\Z)',
        re.S,
    )
    for match in pattern.finditer(body):
        text = _compact_text(match.group(4))[:260]
        if text:
            items.append({
                'anchor': match.group(1),
                'number': _strip_inline_markup(match.group(3)),
                'text': text,
                'url': f'{url_path}#{match.group(1)}',
            })
    return items


def _strip_inline_markup(value):
    value = re.sub(r'<[^>]+>', '', value)
    value = re.sub(r'[`*_~\[\]]', '', value)
    return value.strip()


def _compact_text(value):
    value = re.sub(r'<[^>]+>', ' ', value)
    value = re.sub(r'[`*_>#|]', ' ', value)
    value = re.sub(r'\[[^\]]+\]\([^)]+\)', lambda match: match.group(0).split('](', 1)[0][1:], value)
    return re.sub(r'\s+', ' ', value).strip()
