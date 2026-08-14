import hashlib
import re
import unicodedata
from copy import deepcopy
from functools import lru_cache

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.utils import OperationalError, ProgrammingError


DEFAULT_LANGUAGE = 'ko'
SUPPORTED_TRANSLATION_LANGUAGES = ('en', 'ja')
SUPPORTED_LANGUAGE_CODES = (DEFAULT_LANGUAGE, *SUPPORTED_TRANSLATION_LANGUAGES)

CARD_TRANSLATED_FIELDS = (
    'name',
    'ruby',
    'text',
    'detail_text',
    'keyword',
    'hiddenKeyword',
    'search',
)
CHARACTER_TRANSLATED_FIELDS = (
    'name',
    'description',
    'group',
    'datas',
)
MARKUP_FIELDS = {'text', 'detail_text', 'description', 'group'}
TOKEN_RE = re.compile(
    r'\[\[(card|state-card|token-card|counter-card|character|keyword|state|token|term):([^\]\r\n]+)\]\]'
)
MARK_PAIRS = {
    '[': ']',
    '【': '】',
    '「': '」',
    '"': '"',
    '“': '”',
}


def normalize_language_code(language):
    if not language:
        return DEFAULT_LANGUAGE
    code = str(language).lower().replace('_', '-').split('-', 1)[0]
    if code in SUPPORTED_LANGUAGE_CODES:
        return code
    return DEFAULT_LANGUAGE


def clear_localization_cache():
    _translation_texts.cache_clear()
    _translation_data.cache_clear()
    _source_texts.cache_clear()
    _source_data.cache_clear()
    _source_translation_rows.cache_clear()
    _source_category_index.cache_clear()


def _slug(value, fallback='item'):
    value = str(value or '').strip()
    normalized = unicodedata.normalize('NFKD', value)
    ascii_value = normalized.encode('ascii', 'ignore').decode('ascii').lower()
    ascii_value = re.sub(r'[^a-z0-9]+', '_', ascii_value).strip('_')
    if ascii_value:
        return ascii_value[:80]
    digest = hashlib.sha1(value.encode('utf-8')).hexdigest()[:10]
    return f'{fallback}_{digest}'


def unique_slug(value, used, fallback='item'):
    base = _slug(value, fallback=fallback)
    candidate = base
    index = 2
    while candidate in used:
        candidate = f'{base}_{index}'
        index += 1
    used.add(candidate)
    return candidate


def card_translation_key(card_or_code, field_name):
    code = getattr(card_or_code, 'code', card_or_code)
    if not code:
        return ''
    return f'card.{str(code).strip()}.{field_name}'


def character_translation_key(character_or_key, field_name):
    key = getattr(character_or_key, 'localization_key', character_or_key)
    if not key:
        return ''
    return f'character.{str(key).strip()}.{field_name}'


def term_translation_key(category, slug):
    category = str(category or 'general').strip() or 'general'
    slug = str(slug or '').strip()
    if not slug:
        return ''
    return f'term.{category}.{slug}'


def ui_translation_key(slug):
    slug = str(slug or '').strip()
    if not slug:
        return ''
    return f'ui.{slug}'


def _translation_models():
    from common.models import TranslationSource, TranslationValue

    return TranslationSource, TranslationValue


@lru_cache(maxsize=16)
def _translation_texts(language):
    language = normalize_language_code(language)
    if language == DEFAULT_LANGUAGE:
        return {}
    try:
        _TranslationSource, TranslationValue = _translation_models()
        rows = (
            TranslationValue.objects
            .filter(language=language, source__is_active=True)
            .exclude(text='')
            .values_list('source__key', 'text')
        )
        return dict(rows)
    except (OperationalError, ProgrammingError):
        return {}


@lru_cache(maxsize=16)
def _translation_data(language):
    language = normalize_language_code(language)
    if language == DEFAULT_LANGUAGE:
        return {}
    try:
        _TranslationSource, TranslationValue = _translation_models()
        rows = (
            TranslationValue.objects
            .filter(language=language, source__is_active=True)
            .exclude(data={})
            .values_list('source__key', 'data')
        )
        return dict(rows)
    except (OperationalError, ProgrammingError):
        return {}


@lru_cache(maxsize=1)
def _source_texts():
    try:
        TranslationSource, _TranslationValue = _translation_models()
        return dict(
            TranslationSource.objects
            .filter(is_active=True)
            .values_list('key', 'source_text')
        )
    except (OperationalError, ProgrammingError):
        return {}


@lru_cache(maxsize=1)
def _source_data():
    try:
        TranslationSource, _TranslationValue = _translation_models()
        return dict(
            TranslationSource.objects
            .filter(is_active=True)
            .exclude(source_data={})
            .values_list('key', 'source_data')
        )
    except (OperationalError, ProgrammingError):
        return {}


@lru_cache(maxsize=16)
def _source_translation_rows(language):
    language = normalize_language_code(language)
    if language == DEFAULT_LANGUAGE:
        return ()
    try:
        _TranslationSource, TranslationValue = _translation_models()
        return tuple(
            TranslationValue.objects
            .filter(language=language, source__is_active=True)
            .exclude(text='')
            .exclude(source__source_text='')
            .values_list('source__category', 'source__field_name', 'source__source_text', 'text')
        )
    except (OperationalError, ProgrammingError):
        return ()


@lru_cache(maxsize=16)
def _source_category_index(language):
    index = {}
    for category, _field_name, source_text, translated in _source_translation_rows(language):
        index[(category, source_text)] = translated
        index.setdefault((None, source_text), translated)
    return index


def source_translations_for_language(language, categories=None, field_names=None):
    language = normalize_language_code(language)
    if language == DEFAULT_LANGUAGE:
        return {}
    allowed = set(categories or [])
    allowed_fields = set(field_names or [])
    mapping = {}
    for category, field_name, source_text, translated in _source_translation_rows(language):
        if not categories or category in allowed:
            if allowed_fields and field_name not in allowed_fields:
                continue
            mapping[source_text] = translated
    return mapping


def translation_source_exists(key):
    if not key:
        return False
    return key in _source_texts() or key in _source_data()


def translate_key(key, language, fallback=None):
    language = normalize_language_code(language)
    if not key:
        return fallback or ''
    if language != DEFAULT_LANGUAGE:
        translated = _translation_texts(language).get(key)
        if translated not in (None, ''):
            return translated
    if fallback is not None:
        return fallback
    source = _source_texts().get(key)
    if source is not None:
        return source
    return key


def translate_data_key(key, language, fallback=None):
    language = normalize_language_code(language)
    if not key:
        return deepcopy(fallback) if fallback is not None else {}
    if language != DEFAULT_LANGUAGE:
        translated = _translation_data(language).get(key)
        if translated not in (None, {}):
            return deepcopy(translated)
    if fallback is not None:
        return deepcopy(fallback)
    source = _source_data().get(key)
    if source is not None:
        return deepcopy(source)
    return {}


def translate_source(text, language, category=None):
    language = normalize_language_code(language)
    if language == DEFAULT_LANGUAGE or text is None:
        return None
    return _source_category_index(language).get((category, str(text)))


def translate_text_by_parts(text, language, categories=None, field_names=None):
    if text is None:
        return ''
    language = normalize_language_code(language)
    if language == DEFAULT_LANGUAGE:
        return str(text)

    text = str(text)
    if text in ('', '-', 'X'):
        return text

    translations = source_translations_for_language(language, categories=categories, field_names=field_names)
    if text in translations:
        return translations[text]

    translated = text
    for source in sorted(translations.keys(), key=len, reverse=True):
        translated = translated.replace(source, translations[source])
    return translated


def render_localized_markup(text, language):
    if text is None:
        return ''
    text = str(text)
    if '[[' not in text:
        return text

    def replace(match):
        kind = match.group(1)
        payload = match.group(2).strip()
        if kind in ('card', 'state-card', 'token-card', 'counter-card'):
            name = _localized_card_name(payload, language, match.group(0))
            if name == match.group(0):
                return name
            if kind == 'state-card':
                return wrap_mark(name, '「')
            if kind in ('token-card', 'counter-card'):
                return wrap_mark(name, '【')
            return wrap_mark(name, '[')
        if kind == 'character':
            key = character_translation_key(payload, 'name')
            if translation_source_exists(key):
                return wrap_mark(translate_key(key, language), '[')
            name = _fallback_character_name(payload, language, match.group(0))
            return name if name == match.group(0) else wrap_mark(name, '[')
        if kind == 'keyword':
            key = f'keyword.{payload}'
            if translation_source_exists(key):
                return wrap_mark(translate_key(key, language), '"')
            return match.group(0)
        if kind in ('state', 'token'):
            key = term_translation_key(kind, payload)
            if translation_source_exists(key):
                open_mark = '「' if kind == 'state' else '【'
                return wrap_mark(translate_key(key, language), open_mark)
            return match.group(0)
        if kind == 'term':
            parts = payload.split('.', 1)
            if len(parts) != 2:
                return match.group(0)
            key = term_translation_key(parts[0], parts[1])
            if translation_source_exists(key):
                return translate_key(key, language)
            return match.group(0)
        return match.group(0)

    return TOKEN_RE.sub(replace, text)


def strip_outer_marks(value):
    text = str(value or '').strip()
    changed = True
    while changed and len(text) >= 2:
        changed = False
        for open_mark, close_mark in MARK_PAIRS.items():
            if text.startswith(open_mark) and text.endswith(close_mark):
                text = text[len(open_mark):-len(close_mark)].strip()
                changed = True
                break
    return text


def wrap_mark(value, open_mark):
    text = strip_outer_marks(value)
    close_mark = MARK_PAIRS.get(open_mark, open_mark)
    return f'{open_mark}{text}{close_mark}'


def _localized_card_name(code, language, missing):
    key = card_translation_key(code, 'name')
    if translation_source_exists(key):
        return translate_key(key, language)
    return _fallback_card_name(code, language, missing)


def _fallback_card_name(code, language, missing):
    try:
        Card = apps.get_model('card', 'Card')
        card = Card.objects.filter(code=code).first()
    except (OperationalError, ProgrammingError, LookupError):
        return missing
    if not card:
        return missing
    return translate_card_field(card, language, 'name')


def _fallback_character_name(localization_key, language, missing):
    try:
        Character = apps.get_model('card', 'Character')
        character = Character.objects.filter(localization_key=localization_key).first()
    except (OperationalError, ProgrammingError, LookupError):
        return missing
    if not character:
        return missing
    return translate_character_field(character, language, 'name')


def translate_card_field(card, language, field_name):
    fallback = getattr(card, field_name, '') if card is not None else ''
    key = card_translation_key(card, field_name)
    value = translate_key(key, language, fallback=fallback) if key else fallback
    if field_name in MARKUP_FIELDS:
        value = render_localized_markup(value, language)
    return value


def translate_character_field(character, language, field_name):
    fallback = getattr(character, field_name, '') if character is not None else ''
    key = character_translation_key(character, field_name)
    value = translate_key(key, language, fallback=fallback) if key else fallback
    if field_name in MARKUP_FIELDS:
        value = render_localized_markup(value, language)
    return value


def translate_character_datas(character, language):
    if character is None:
        return {}
    base_datas = deepcopy(character.datas or {})
    key = character_translation_key(character, 'datas')
    if not key:
        return base_datas
    translated = translate_data_key(key, language, fallback=base_datas)
    if not isinstance(translated, dict):
        return base_datas
    merged = deepcopy(base_datas)
    merged.update(deepcopy(translated))
    return merged


def _content_type_for(obj):
    if obj is None:
        return None
    return ContentType.objects.get_for_model(obj, for_concrete_model=False)


def _upsert_source(key, category, source_text='', source_data=None, obj=None, field_name='', note=''):
    if not key:
        return None
    TranslationSource, _TranslationValue = _translation_models()
    defaults = {
        'category': category,
        'source_text': source_text or '',
        'source_data': source_data or {},
        'field_name': field_name or '',
        'note': note or '',
        'is_active': True,
    }
    content_type = _content_type_for(obj)
    if content_type is not None:
        defaults['content_type'] = content_type
        defaults['object_id'] = obj.pk
    source, _created = TranslationSource.objects.update_or_create(
        key=key,
        defaults=defaults,
    )
    return source


def _upsert_value(source, language, text='', data=None, overwrite_empty=True):
    if source is None:
        return None
    language = normalize_language_code(language)
    if language == DEFAULT_LANGUAGE:
        return None
    _TranslationSource, TranslationValue = _translation_models()
    data = data or {}
    if not overwrite_empty and not text and not data:
        value = TranslationValue.objects.filter(source=source, language=language).first()
        if value is not None:
            return value
    status = TranslationValue.STATUS_TRANSLATED if (text or data) else TranslationValue.STATUS_MISSING
    value, _created = TranslationValue.objects.update_or_create(
        source=source,
        language=language,
        defaults={
            'text': text or '',
            'data': data,
            'status': status,
        },
    )
    return value


def sync_card_source(card):
    try:
        for field_name in CARD_TRANSLATED_FIELDS:
            key = card_translation_key(card, field_name)
            if not key:
                continue
            _upsert_source(
                key,
                'card',
                source_text=getattr(card, field_name, '') or '',
                obj=card,
                field_name=field_name,
            )
        clear_localization_cache()
    except (OperationalError, ProgrammingError):
        return


def sync_card_translation(translation):
    try:
        sync_card_source(translation.card)
        for field_name in CARD_TRANSLATED_FIELDS:
            key = card_translation_key(translation.card, field_name)
            source = _upsert_source(
                key,
                'card',
                source_text=getattr(translation.card, field_name, '') or '',
                obj=translation.card,
                field_name=field_name,
            )
            _upsert_value(
                source,
                translation.language,
                text=getattr(translation, field_name, '') or '',
                overwrite_empty=False,
            )
        clear_localization_cache()
    except (OperationalError, ProgrammingError):
        return


def sync_character_source(character):
    try:
        for field_name in CHARACTER_TRANSLATED_FIELDS:
            key = character_translation_key(character, field_name)
            if not key:
                continue
            source_text = '' if field_name == 'datas' else getattr(character, field_name, '') or ''
            source_data = getattr(character, 'datas', {}) or {} if field_name == 'datas' else {}
            _upsert_source(
                key,
                'character',
                source_text=source_text,
                source_data=source_data,
                obj=character,
                field_name=field_name,
            )
        clear_localization_cache()
    except (OperationalError, ProgrammingError):
        return


def sync_character_translation(translation):
    try:
        sync_character_source(translation.character)
        for field_name in CHARACTER_TRANSLATED_FIELDS:
            key = character_translation_key(translation.character, field_name)
            source = _upsert_source(
                key,
                'character',
                source_text='' if field_name == 'datas' else getattr(translation.character, field_name, '') or '',
                source_data=getattr(translation.character, 'datas', {}) or {} if field_name == 'datas' else {},
                obj=translation.character,
                field_name=field_name,
            )
            if field_name == 'datas':
                _upsert_value(source, translation.language, data=translation.datas or {}, overwrite_empty=False)
            else:
                _upsert_value(
                    source,
                    translation.language,
                    text=getattr(translation, field_name, '') or '',
                    overwrite_empty=False,
                )
        clear_localization_cache()
    except (OperationalError, ProgrammingError):
        return


def sync_term_translation(term_translation):
    try:
        TranslationSource, _TranslationValue = _translation_models()
        source = (
            TranslationSource.objects
            .filter(category=term_translation.category, source_text=term_translation.source)
            .first()
        )
        if source is None:
            base_slug = _slug(term_translation.text or term_translation.source, fallback='term')
            key = term_translation_key(term_translation.category, base_slug)
            existing_keys = set(
                TranslationSource.objects
                .filter(key__startswith=f'term.{term_translation.category}.')
                .values_list('key', flat=True)
            )
            index = 2
            while key in existing_keys:
                key = term_translation_key(term_translation.category, f'{base_slug}_{index}')
                index += 1
            source = _upsert_source(
                key,
                term_translation.category,
                source_text=term_translation.source,
                field_name=term_translation.category,
                note=term_translation.note,
            )
        _upsert_value(source, term_translation.language, text=term_translation.text)
        clear_localization_cache()
    except (OperationalError, ProgrammingError):
        return
