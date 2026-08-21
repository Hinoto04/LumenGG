"""Portable management-command output helpers."""

import json


def console_safe_json(value, stdout, *, indent=2):
    """Keep JSON readable on Windows consoles that cannot encode every glyph."""
    rendered = json.dumps(value, ensure_ascii=False, indent=indent)
    raw_stream = getattr(stdout, '_out', stdout)
    encoding = getattr(raw_stream, 'encoding', None) or 'utf-8'
    try:
        rendered.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        try:
            rendered = rendered.encode(
                encoding, errors='backslashreplace',
            ).decode(encoding)
        except LookupError:
            rendered = json.dumps(value, ensure_ascii=True, indent=indent)
    return rendered
