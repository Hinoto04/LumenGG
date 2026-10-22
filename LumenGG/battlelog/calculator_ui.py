"""Presentation metadata only; both calculator skins use the same session."""
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.templatetags.static import static


def calculator_ui(value):
    return 'character' if value == 'character' else 'classic'


def calculator_url(url, ui):
    """Keep tokens and other query parameters intact; classic URLs stay canonical."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in ('ui', 'choose_ui')]
    if calculator_ui(ui) == 'character':
        query.append(('ui', 'character'))
    return urlunsplit(parts._replace(query=urlencode(query)))


@lru_cache(maxsize=1)
def calculator_themes():
    path = Path(settings.BASE_DIR) / 'content' / 'calculator-ui.json'
    return {item['name']: item for item in json.loads(path.read_text(encoding='utf-8'))}


def character_calculator_ui(character):
    item = calculator_themes().get(character.name)
    if not item:
        return None
    key = item['theme_key']
    return {
        'theme_key': key,
        'accent': item['accent'],
        'secondary': item['secondary'],
        'motif': item['motif'],
        'passive_variant': key,
        'background': static(f'v2/calculator-character/{key}/background.webp'),
        'emblem': static(f'v2/calculator-character/{key}/emblem.png'),
    }
