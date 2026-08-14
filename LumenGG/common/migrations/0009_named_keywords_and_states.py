import re

from django.db import migrations


LANGUAGES = ('en', 'ja')
MARK_PAIRS = (
    ('[', ']'),
    ('【', '】'),
    ('「', '」'),
    ('"', '"'),
    ('“', '”'),
    ('`', '`'),
)
NAMED_SOURCES = (
    (
        'keyword',
        'rai',
        '라이!',
        {'en': 'Rai!', 'ja': 'ライ！'},
        ('term.tag.rai',),
    ),
    (
        'keyword',
        'lefi',
        '레피!',
        {'en': 'Lefi!', 'ja': 'レピ！'},
        ('term.tag.lefi',),
    ),
    (
        'state',
        'over_limit',
        '오버 리밋',
        {'en': 'Over Limit', 'ja': 'オーバーリミット'},
        ('term.tag.over_limit', 'term.general.over_limit'),
    ),
    (
        'state',
        'zero_suit',
        '제로 슈트',
        {'en': 'Zero Suit', 'ja': 'ゼロスーツ'},
        ('term.tag.zero_suit_2', 'term.tag.zero_suit'),
    ),
    (
        'state',
        'advance_notice',
        '예고',
        {'en': 'Advance Notice', 'ja': '予告'},
        ('term.tag.advance_notice', 'term.general.notice'),
    ),
)
CHARACTER_FALLBACKS = {
    'nya': {'ko': '니아', 'en': 'NYA', 'ja': 'ニア'},
    'pinp': {'ko': '핀프', 'en': 'PINP', 'ja': 'ピンプ'},
    'kiss': {'ko': '키스', 'en': 'KISS', 'ja': 'キス'},
}
STATE_CARD_TOKENS = {
    '[[state-card:ST1-PS1]]': '[[state:over_limit]]',
    '[[state-card:ST4-PS1]]': '[[state:advance_notice]]',
}
TECHNIQUE_TERMS = ('기술', 'Technique', 'Techniques', 'technique', 'techniques', '技')
CONDITION_TRAITS = (
    '공격',
    '수비',
    '손',
    '발',
    '상단',
    '중단',
    '하단',
    'Attack',
    'Defense',
    'Hand',
    'Foot',
    'High',
    'Mid',
    'Middle',
    'Low',
    'Dodge',
    'Guard',
    'Clash',
    '攻撃',
    '防御',
    '手',
    '足',
    '上段',
    '中段',
    '下段',
)
TOKEN_PATTERN = re.compile(r'\[\[[^\]\r\n]+\]\]')


def strip_marks(value):
    text = str(value or '').strip()
    changed = True
    while changed and len(text) >= 2:
        changed = False
        for open_mark, close_mark in MARK_PAIRS:
            if text.startswith(open_mark) and text.endswith(close_mark):
                text = text[len(open_mark):-len(close_mark)].strip()
                changed = True
                break
    return text


def first_source(TranslationSource, keys):
    for key in keys:
        source = TranslationSource.objects.filter(key=key).first()
        if source is not None:
            return source
    return None


def seed_named_sources(apps):
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationValue = apps.get_model('common', 'TranslationValue')

    for kind, slug, source_text, fallbacks, seed_keys in NAMED_SOURCES:
        seed = first_source(TranslationSource, seed_keys)
        source, _created = TranslationSource.objects.update_or_create(
            key=f'{"keyword" if kind == "keyword" else "term.state"}.{slug}',
            defaults={
                'category': kind,
                'source_text': source_text,
                'field_name': 'name' if kind == 'keyword' else 'state',
                'note': f'Semantic {kind} reference; rendered with standard marks.',
                'is_active': True,
            },
        )
        seed_values = {}
        if seed is not None:
            seed_values = {
                value.language: value.text
                for value in TranslationValue.objects.filter(source_id=seed.id)
            }
        for language in LANGUAGES:
            text = strip_marks(seed_values.get(language, '')) or fallbacks[language]
            if kind == 'keyword' and not text.endswith(('!', '！')):
                text += '！' if language == 'ja' else '!'
            TranslationValue.objects.update_or_create(
                source_id=source.id,
                language=language,
                defaults={
                    'text': text,
                    'data': {},
                    'status': 'translated',
                },
            )


def source_aliases(apps):
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationValue = apps.get_model('common', 'TranslationValue')
    aliases = {'ko': {}, 'en': {}, 'ja': {}}
    for kind, slug, _source_text, _fallbacks, _seed_keys in NAMED_SOURCES:
        key = f'{"keyword" if kind == "keyword" else "term.state"}.{slug}'
        source = TranslationSource.objects.filter(key=key).first()
        if source is None:
            continue
        aliases['ko'][(kind, slug)] = strip_marks(source.source_text)
        for value in TranslationValue.objects.filter(source_id=source.id):
            aliases.setdefault(value.language, {})[(kind, slug)] = strip_marks(value.text)
    return aliases


def character_aliases(apps):
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationValue = apps.get_model('common', 'TranslationValue')
    aliases = {
        language: {key: values[language] for key, values in CHARACTER_FALLBACKS.items()}
        for language in ('ko', 'en', 'ja')
    }
    for key in CHARACTER_FALLBACKS:
        source = TranslationSource.objects.filter(key=f'character.{key}.name').first()
        if source is None:
            continue
        aliases['ko'][key] = strip_marks(source.source_text)
        for value in TranslationValue.objects.filter(source_id=source.id):
            if value.language in aliases and value.text:
                aliases[value.language][key] = strip_marks(value.text)
    return aliases


def protect_tokens(text):
    placeholders = {}

    def replace(match):
        placeholder = f'@@LUMEN_NAMED_TOKEN_{len(placeholders)}@@'
        placeholders[placeholder] = match.group(0)
        return placeholder

    return TOKEN_PATTERN.sub(replace, text), placeholders


def restore_tokens(text, placeholders):
    for placeholder, token in placeholders.items():
        text = text.replace(placeholder, token)
    return text


def replace_marked(text, alias, token, marks=MARK_PAIRS):
    escaped = re.escape(alias)
    for open_mark, close_mark in marks:
        text = re.sub(
            re.escape(open_mark) + r'\s*' + escaped + r'\s*' + re.escape(close_mark),
            token,
            text,
        )
    return text


def replace_keyword(text, alias, token, language):
    text = replace_marked(text, alias, token)
    context_suffixes = {
        'ko': r'(?=\s*명)',
        'en': r'(?=\s+(?:in\s+(?:the\s+)?name|name))',
        'ja': r'(?=\s*(?:の?名))',
    }
    return re.sub(
        r'(?<![\w\[\[:])' + re.escape(alias) + context_suffixes[language],
        token,
        text,
        flags=re.IGNORECASE if language == 'en' else 0,
    )


def inside_angle_condition(text, index):
    last_open = max(text.rfind('<', 0, index), text.rfind('〈', 0, index))
    last_close = max(text.rfind('>', 0, index), text.rfind('〉', 0, index))
    return last_open > last_close


def character_condition_replacement(full_text, match, token):
    if inside_angle_condition(full_text, match.start()):
        return match.group(0)
    prefix = re.sub(r'\s+', ' ', (match.group('prefix') or '').strip())
    traits = re.sub(r'\s+', ' ', (match.group('traits') or '').strip())
    condition = ' '.join(part for part in (prefix, token, traits) if part)
    return f'<{condition}> {match.group("term")}'


def replace_character(text, alias, token):
    escaped_alias = re.escape(alias)
    technique_terms = '|'.join(re.escape(term) for term in TECHNIQUE_TERMS)
    traits = '|'.join(re.escape(trait) for trait in CONDITION_TRAITS)
    speed_prefix = (
        r'(?:(?:\d+\s*(?:~|-)\s*\d+|\d+)\s*속도(?:\s*(?:이하|이상))?'
        r'|Speed\s*\d+(?:\s*(?:or\s*(?:lower|higher)|or\s*less|or\s*more|and\s*(?:below|above)))?'
        r'|速度\s*\d+\s*(?:以下|以上)?\s*の?)'
    )
    prefix = rf'(?P<prefix>(?:{speed_prefix}\s*)?)'
    trait_group = rf'(?P<traits>(?:\s*(?:{traits})){{0,4}})'
    term = rf'(?P<term>{technique_terms})'
    marked_pattern = re.compile(
        prefix + r'\[\s*' + escaped_alias + r'\s*\]' + trait_group + r'\s*' + term
    )
    prefixed_bare_pattern = re.compile(
        rf'(?P<prefix>{speed_prefix}\s*)'
        + escaped_alias
        + trait_group
        + r'\s*'
        + term
    )
    bare_pattern = re.compile(
        r'(?P<prefix>)(?<![\w\[\[:])'
        + escaped_alias
        + trait_group
        + r'\s*'
        + term
    )
    text = marked_pattern.sub(lambda match: character_condition_replacement(text, match, token), text)
    text = prefixed_bare_pattern.sub(
        lambda match: character_condition_replacement(text, match, token),
        text,
    )
    text = bare_pattern.sub(lambda match: character_condition_replacement(text, match, token), text)
    return re.sub(r'\[\s*' + escaped_alias + r'\s*\]', token, text)


def replace_named_text(text, language, aliases, characters):
    if not text:
        return text
    text = str(text)
    for old, new in STATE_CARD_TOKENS.items():
        text = text.replace(old, new)

    protected, placeholders = protect_tokens(text)
    for slug in ('rai', 'lefi'):
        alias = aliases.get(language, {}).get(('keyword', slug), '')
        if alias:
            protected = replace_keyword(protected, alias, f'[[keyword:{slug}]]', language)
    for slug in ('over_limit', 'zero_suit', 'advance_notice'):
        alias = aliases.get(language, {}).get(('state', slug), '')
        if alias:
            protected = replace_marked(
                protected,
                alias,
                f'[[state:{slug}]]',
                (('「', '」'), ('[', ']')),
            )
    for key, alias in characters.get(language, {}).items():
        if alias:
            protected = replace_character(protected, alias, f'[[character:{key}]]')
    return restore_tokens(protected, placeholders)


def update_fields(obj, language, aliases, characters):
    changed = []
    for field_name in ('text', 'detail_text'):
        old = getattr(obj, field_name, '') or ''
        new = replace_named_text(old, language, aliases, characters)
        if new != old:
            setattr(obj, field_name, new)
            changed.append(field_name)
    if changed:
        obj.save(update_fields=changed)


def convert_card_texts(apps):
    Card = apps.get_model('card', 'Card')
    CardTranslation = apps.get_model('card', 'CardTranslation')
    aliases = source_aliases(apps)
    characters = character_aliases(apps)

    for card in Card.objects.order_by('id'):
        update_fields(card, 'ko', aliases, characters)
    for translation in CardTranslation.objects.order_by('id'):
        update_fields(translation, translation.language, aliases, characters)


def convert_catalog_texts(apps):
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationValue = apps.get_model('common', 'TranslationValue')
    aliases = source_aliases(apps)
    characters = character_aliases(apps)

    sources = TranslationSource.objects.filter(
        category='card',
        field_name__in=('text', 'detail_text'),
    ).order_by('id')
    for source in sources:
        old = source.source_text or ''
        new = replace_named_text(old, 'ko', aliases, characters)
        if new != old:
            source.source_text = new
            source.save(update_fields=['source_text'])
        for value in TranslationValue.objects.filter(source_id=source.id).order_by('id'):
            old = value.text or ''
            new = replace_named_text(old, value.language, aliases, characters)
            if new != old:
                value.text = new
                value.save(update_fields=['text', 'updated_at'])


def forwards(apps, schema_editor):
    seed_named_sources(apps)
    convert_card_texts(apps)
    convert_catalog_texts(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0008_convert_catalog_semantic_tokens'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
