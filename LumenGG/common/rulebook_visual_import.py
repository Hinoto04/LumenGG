import json
import re
from html import escape
from pathlib import Path

from django.conf import settings

from .language import ui_text
from .models import RuleVisualGuide, RuleVisualGuideTranslation
from .rulebooks import RULEBOOK_LANGUAGES, _load_visuals, _translate_visuals


CONTENT_DIR = Path(settings.BASE_DIR) / 'content' / 'rulebook'
BASE_CSS_PATH = Path(settings.BASE_DIR) / 'static' / 'v2' / 'base.css'
COMMON_JAVASCRIPT_PATH = CONTENT_DIR / 'visuals' / 'common.js'
STYLE_PROPERTIES = ('top', 'left', 'right', 'bottom', 'width', 'height')
VISUAL_CSS_MARKERS = (
    'v2-rulebook-visual',
    'v2-rulebook-board',
    'v2-rulebook-zone',
    'v2-rulebook-card',
    'v2-rulebook-anatomy',
    'v2-rulebook-example',
    'v2-rulebook-phase',
    'v2-rulebook-sample',
)


def import_rulebook_visuals(book, config, *, replace=False):
    existing = book.visual_guides.filter(rule__isnull=True)
    if existing.exists() and not replace:
        raise ValueError(
            f'{book.slug}에 이미 룰북 상단 비주얼 가이드가 있습니다. '
            '--replace를 사용해야 덮어쓸 수 있습니다.'
        )

    heading_targets = _heading_targets(book, config)
    visuals = _load_visuals(config, toc=[], heading_targets=heading_targets)
    if replace:
        existing.delete()

    created = []
    translated_visuals = {
        language: _translate_visuals(visuals, language)
        for language in sorted(RULEBOOK_LANGUAGES)
    }
    for index, visual in enumerate(visuals):
        guide = RuleVisualGuide.objects.create(
            rulebook=book,
            rule=None,
            style_key=_class_token(visual.get('kind', '')),
            priority=(index + 1) * 10,
            is_public=True,
        )
        for language in sorted(RULEBOOK_LANGUAGES):
            translated = translated_visuals[language][index]
            RuleVisualGuideTranslation.objects.create(
                guide=guide,
                language=language,
                title=translated.get('title') or visual.get('title') or f'Visual {index + 1}',
                content=render_visual_content(translated, language),
            )
        created.append(guide)

    book.visual_file = ''
    book.visual_css = extract_visual_css(BASE_CSS_PATH.read_text(encoding='utf-8'))
    book.visual_javascript = COMMON_JAVASCRIPT_PATH.read_text(encoding='utf-8')
    book.save(update_fields=['visual_file', 'visual_css', 'visual_javascript'])
    return created


def render_visual_content(visual, language='ko'):
    kind = visual.get('kind', '')
    if kind == 'field':
        stage = _render_field(visual)
    elif kind == 'cards':
        stage = _render_cards(visual)
    else:
        stage = _render_phase_track(visual)
    return f'{stage}{_render_info(visual, language)}'


def _render_field(visual):
    items = ''.join(
        '<button '
        f'class="v2-rulebook-zone is-{_class_token(item.get("key"))}" '
        f'{_hotspot_attributes(item)} type="button">'
        f'<span>{_text(item.get("label"))}</span>'
        f'{_optional_small(item.get("hint"))}</button>'
        for item in visual.get('items', [])
    )
    return (
        '<div class="v2-rulebook-visual-stage">'
        f'<div class="v2-rulebook-board">{items}</div></div>'
    )


def _render_cards(visual):
    type_buttons = []
    marker_sets = []
    for index, item in enumerate(visual.get('items', [])):
        key = _class_token(item.get('key'))
        type_buttons.append(
            '<button '
            f'class="v2-rulebook-card-type-button is-{key}" '
            f'data-rulebook-card-type="{_attr(key)}" '
            f'data-example-image="{_attr(item.get("example_image"))}" '
            f'{_hotspot_attributes(item)} type="button">'
            f'<span>{_text(item.get("label"))}</span></button>'
        )
        markers = ''.join(_render_marker(marker) for marker in item.get('markers', []))
        hidden = ' hidden' if index else ''
        marker_sets.append(
            f'<div class="v2-rulebook-card-marker-set" '
            f'data-rulebook-card-marker-set="{_attr(key)}"{hidden}>{markers}</div>'
        )

    image = ''
    if visual.get('example_image'):
        image = (
            '<img class="v2-rulebook-example-card-image" data-rulebook-card-example-image '
            f'src="{_attr(visual.get("example_image"))}" alt="{_attr(visual.get("title"))}">'
        )
    return (
        '<div class="v2-rulebook-visual-stage">'
        '<div class="v2-rulebook-card-anatomy">'
        f'<div class="v2-rulebook-card-type-list">{"".join(type_buttons)}</div>'
        '<div class="v2-rulebook-anatomy-stage"><div class="v2-rulebook-example-card">'
        f'{image}{"".join(marker_sets)}</div></div></div></div>'
    )


def _render_marker(marker):
    key = _class_token(marker.get('key'))
    shape = _class_token(marker.get('shape') or 'circle')
    label_side = _class_token(marker.get('label_side') or 'right')
    style_parts = []
    if marker.get('label_gap'):
        style_parts.append(f'--rulebook-label-gap: {marker["label_gap"]}')
    for property_name in STYLE_PROPERTIES:
        if marker.get(property_name):
            style_parts.append(f'{property_name}: {marker[property_name]}')
    style = f' style="{_attr("; ".join(style_parts))}"' if style_parts else ''
    return (
        f'<button class="v2-rulebook-card-marker is-{key} is-{shape} is-label-{label_side}" '
        f'{_hotspot_attributes(marker)} data-rulebook-card-marker type="button"{style}>'
        f'<span></span><strong>{_text(marker.get("label"))}</strong></button>'
    )


def _render_phase_track(visual):
    items = ''.join(
        '<button class="v2-rulebook-phase" '
        f'{_hotspot_attributes(item)} type="button">'
        f'<span>{index}</span><strong>{_text(item.get("label"))}</strong>'
        f'{_optional_em(item.get("hint"))}</button>'
        for index, item in enumerate(visual.get('items', []), start=1)
    )
    return (
        '<div class="v2-rulebook-visual-stage">'
        f'<div class="v2-rulebook-phase-track">{items}</div></div>'
    )


def _render_info(visual, language):
    title = visual.get('title', '')
    return (
        '<aside class="v2-rulebook-visual-info">'
        f'<span>{_text(title)}</span>'
        f'<strong data-rulebook-visual-title>{_text(title)}</strong>'
        '<small data-rulebook-visual-hint></small>'
        f'<p data-rulebook-visual-text>{_text(visual.get("summary"))}</p>'
        f'<a class="v2-button v2-button-primary" data-rulebook-visual-link '
        f'href="{_attr(visual.get("href") or "#")}">'
        f'{_text(ui_text("본문으로 이동", language))}</a></aside>'
    )


def _hotspot_attributes(item):
    return (
        'data-rulebook-hotspot '
        f'data-title="{_attr(item.get("title"))}" '
        f'data-text="{_attr(item.get("text"))}" '
        f'data-hint="{_attr(item.get("hint"))}" '
        f'data-href="{_attr(item.get("href") or "#")}"'
    )


def _heading_targets(book, config):
    visual_file = config.get('visual_file') or ''
    path = CONTENT_DIR / visual_file
    if not visual_file or not path.exists():
        return {}
    raw_visuals = json.loads(path.read_text(encoding='utf-8')).get('visuals', [])
    headings = set(_find_headings(raw_visuals))
    rules = list(book.rules.prefetch_related('translations').all())
    rules_by_title = {}
    for rule in rules:
        korean = next(
            (item for item in rule.translations.all() if item.language == 'ko'),
            None,
        )
        if korean and korean.title:
            rules_by_title.setdefault(_normalize_heading(korean.title), rule)

    targets = {}
    for heading in headings:
        rule = rules_by_title.get(_normalize_heading(heading))
        if rule:
            targets[heading] = f'#{rule.reference_name}'
    return targets


def _find_headings(value):
    if isinstance(value, list):
        for item in value:
            yield from _find_headings(item)
    elif isinstance(value, dict):
        if isinstance(value.get('heading'), str):
            yield value['heading']
        for item in value.values():
            yield from _find_headings(item)


def _normalize_heading(value):
    value = re.sub(r'^\d+(?:\.\d+)*\.?\s*', '', str(value or ''))
    return re.sub(r'\s+', ' ', value).strip().casefold()


def _class_token(value):
    return re.sub(r'[^a-zA-Z0-9_-]', '', str(value or ''))


def _attr(value):
    return escape(str(value or ''), quote=True)


def _text(value):
    return escape(str(value or ''))


def _optional_small(value):
    return f'<small>{_text(value)}</small>' if value else ''


def _optional_em(value):
    return f'<em>{_text(value)}</em>' if value else ''


def extract_visual_css(stylesheet):
    return _extract_matching_css(stylesheet).strip()


def _extract_matching_css(stylesheet):
    output = []
    cursor = 0
    length = len(stylesheet)
    while cursor < length:
        open_brace = stylesheet.find('{', cursor)
        if open_brace < 0:
            break
        semicolon = stylesheet.find(';', cursor, open_brace)
        if semicolon >= 0:
            cursor = semicolon + 1
            continue

        header = stylesheet[cursor:open_brace].strip()
        close_brace = _matching_brace(stylesheet, open_brace)
        if close_brace < 0:
            break
        body = stylesheet[open_brace + 1:close_brace]
        clean_header = re.sub(r'/\*.*?\*/', '', header, flags=re.S).strip()

        if clean_header.startswith(('@media', '@supports', '@layer')):
            nested = _extract_matching_css(body).strip()
            if nested:
                output.append(f'{clean_header} {{\n{nested}\n}}')
        elif any(marker in clean_header for marker in VISUAL_CSS_MARKERS):
            output.append(f'{clean_header} {{{body}}}')
        cursor = close_brace + 1
    return '\n\n'.join(output)


def _matching_brace(value, open_index):
    depth = 0
    quote = ''
    escaped = False
    for index in range(open_index, len(value)):
        character = value[index]
        if escaped:
            escaped = False
            continue
        if character == '\\':
            escaped = True
            continue
        if quote:
            if character == quote:
                quote = ''
            continue
        if character in {'"', "'"}:
            quote = character
        elif character == '{':
            depth += 1
        elif character == '}':
            depth -= 1
            if depth == 0:
                return index
    return -1
