"""Presentation metadata for the single calculator layout (web and app share the themes)."""
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.templatetags.static import static

# 예전 UI 선택 파라미터. 계산기 화면이 하나로 합쳐져 링크에서만 걷어낸다.
LEGACY_UI_PARAMETERS = ('ui', 'choose_ui')


def calculator_url(url):
    """Drop retired UI selectors while keeping tokens, other parameters and the fragment."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in LEGACY_UI_PARAMETERS]
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
