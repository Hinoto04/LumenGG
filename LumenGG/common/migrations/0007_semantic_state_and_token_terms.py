import re

from django.db import migrations, models


LANGUAGES = ('en', 'ja')
MARK_PAIRS = (
    ('[', ']'),
    ('【', '】'),
    ('「', '」'),
    ('"', '"'),
    ('“', '”'),
    ('`', '`'),
)
SEMANTIC_SOURCES = (
    ('state', 'harmony', '조화', ('term.tag.harmony', 'term.general.harmony')),
    ('state', 'saintess', '성녀', ('term.tag.saintess',)),
    ('state', 'disaster_one', '디제스터 원', ('term.tag.disaster_one',)),
    ('state', 'dark_night', '암야', ('term.tag.dark_night_2', 'term.general.dark_night')),
    ('state', 'blue_flame', '청염', ('term.tag.blue_flame_2',)),
    ('state', 'yin', '음', ('term.tag.yin', 'term.general.yin')),
    ('state', 'yang', '양', ('term.tag.yang', 'term.general.yang')),
    ('token', 'hidden_bond', '은연', ('term.tag.hidden_bond',)),
    ('token', 'howling', '하울링', ('term.tag.howling', 'term.general.howling')),
    ('token', 'calling_card', '예고장', ('term.tag.calling_card_2', 'term.tag.calling_card')),
    ('token', 'parts', '파츠', ('term.general.parts', 'term.tag.parts')),
    ('token', 'vocal', '보컬', ('term.tag.vocal',)),
    ('token', 'drum', '드럼', ('term.tag.drum',)),
    ('token', 'guitar', '기타', ('term.tag.guitar',)),
    ('token', 'bass', '베이스', ('term.tag.bass',)),
    ('token', 'yin', '음', ('term.tag.yin', 'term.general.yin')),
    ('token', 'yang', '양', ('term.tag.yang', 'term.general.yang')),
)
ALWAYS_TOKEN_SLUGS = (
    'hidden_bond',
    'howling',
    'calling_card',
    'parts',
    'vocal',
    'drum',
    'guitar',
    'bass',
)
STATE_SLUGS = ('harmony', 'saintess', 'disaster_one', 'dark_night', 'blue_flame')
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


def seed_semantic_sources(apps, schema_editor):
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationValue = apps.get_model('common', 'TranslationValue')

    for kind, slug, source_text, seed_keys in SEMANTIC_SOURCES:
        seed = first_source(TranslationSource, seed_keys)
        source, _created = TranslationSource.objects.update_or_create(
            key=f'term.{kind}.{slug}',
            defaults={
                'category': kind,
                'source_text': strip_marks(source_text),
                'field_name': kind,
                'note': f'Semantic {kind} reference; rendered with standard marks.',
                'is_active': True,
            },
        )
        seed_values = {}
        if seed is not None:
            seed_values = {
                value.language: value
                for value in TranslationValue.objects.filter(source_id=seed.id)
            }
        for language in LANGUAGES:
            seed_value = seed_values.get(language)
            text = strip_marks(seed_value.text) if seed_value is not None else ''
            status = seed_value.status if seed_value is not None else 'missing'
            if kind == 'state' and slug == 'disaster_one' and language == 'ja':
                status = 'needs_review'
            TranslationValue.objects.update_or_create(
                source_id=source.id,
                language=language,
                defaults={
                    'text': text,
                    'data': {},
                    'status': status,
                },
            )


def aliases_by_language(apps):
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationValue = apps.get_model('common', 'TranslationValue')
    aliases = {'ko': {}, 'en': {}, 'ja': {}}
    for kind, slug, _source_text, _seed_keys in SEMANTIC_SOURCES:
        source = TranslationSource.objects.filter(key=f'term.{kind}.{slug}').first()
        if source is None:
            continue
        aliases['ko'][(kind, slug)] = strip_marks(source.source_text)
        for value in TranslationValue.objects.filter(source_id=source.id):
            aliases[value.language][(kind, slug)] = strip_marks(value.text)
    return aliases


def protect_tokens(text):
    placeholders = {}

    def replace(match):
        placeholder = f'@@LUMEN_SEMANTIC_TOKEN_{len(placeholders)}@@'
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


def replace_bare(text, alias, token):
    if re.fullmatch(r'[A-Za-z0-9 _-]+', alias):
        return re.sub(r'(?<![A-Za-z0-9_])' + re.escape(alias) + r'(?![A-Za-z0-9_])', token, text)
    return text.replace(alias, token)


def replace_semantic_text(text, language, aliases):
    if not text:
        return text
    text = str(text)

    legacy_tokens = {
        '[[term:tag.harmony]]': '[[state:harmony]]',
        '[[term:tag.saintess]]': '[[state:saintess]]',
        '[[term:tag.disaster_one]]': '[[state:disaster_one]]',
        '[[term:tag.dark_night_2]]': '[[state:dark_night]]',
        '[[term:tag.blue_flame_2]]': '[[state:blue_flame]]',
        '[[term:tag.hidden_bond]]': '[[token:hidden_bond]]',
        '[[term:tag.howling]]': '[[token:howling]]',
        '[[term:tag.calling_card_2]]': '[[token:calling_card]]',
        '[[term:general.parts]]': '[[token:parts]]',
        '[[term:tag.vocal]]': '[[token:vocal]]',
        '[[term:tag.drum]]': '[[token:drum]]',
        '[[term:tag.guitar]]': '[[token:guitar]]',
        '[[term:tag.bass]]': '[[token:bass]]',
    }
    for old, new in legacy_tokens.items():
        text = text.replace(old, new)

    protected, placeholders = protect_tokens(text)

    for slug in ALWAYS_TOKEN_SLUGS:
        alias = aliases.get(language, {}).get(('token', slug), '')
        if not alias:
            continue
        token = f'[[token:{slug}]]'
        protected = replace_marked(protected, alias, token)
        protected = replace_bare(protected, alias, token)

    counter_words = {
        'ko': r'카운터',
        'en': r'Counters?',
        'ja': r'カウンター',
    }
    for slug in ('yin', 'yang'):
        token_alias = aliases.get(language, {}).get(('token', slug), '')
        state_alias = aliases.get(language, {}).get(('state', slug), '')
        if token_alias:
            token = f'[[token:{slug}]]'
            escaped = re.escape(token_alias)
            for open_mark, close_mark in MARK_PAIRS:
                protected = re.sub(
                    re.escape(open_mark)
                    + r'\s*'
                    + escaped
                    + r'\s*'
                    + re.escape(close_mark)
                    + r'(?=\s*'
                    + counter_words[language]
                    + r')',
                    token,
                    protected,
                    flags=re.IGNORECASE,
                )
            protected = replace_marked(protected, token_alias, token, (('【', '】'), ('[', ']')))
        if state_alias:
            protected = replace_marked(
                protected,
                state_alias,
                f'[[state:{slug}]]',
                (('「', '」'),),
            )

    for slug in STATE_SLUGS:
        alias = aliases.get(language, {}).get(('state', slug), '')
        if not alias:
            continue
        protected = replace_marked(
            protected,
            alias,
            f'[[state:{slug}]]',
            (('「', '」'), ('[', ']')),
        )

    return restore_tokens(protected, placeholders)


def convert_card_texts(apps, schema_editor):
    Card = apps.get_model('card', 'Card')
    CardTranslation = apps.get_model('card', 'CardTranslation')
    aliases = aliases_by_language(apps)

    for card in Card.objects.order_by('id'):
        changed = []
        for field_name in ('text', 'detail_text'):
            old = getattr(card, field_name, '') or ''
            new = replace_semantic_text(old, 'ko', aliases)
            if new != old:
                setattr(card, field_name, new)
                changed.append(field_name)
        if changed:
            card.save(update_fields=changed)

    for translation in CardTranslation.objects.order_by('id'):
        changed = []
        for field_name in ('text', 'detail_text'):
            old = getattr(translation, field_name, '') or ''
            new = replace_semantic_text(old, translation.language, aliases)
            if new != old:
                setattr(translation, field_name, new)
                changed.append(field_name)
        if changed:
            translation.save(update_fields=changed)


def forwards(apps, schema_editor):
    seed_semantic_sources(apps, schema_editor)
    convert_card_texts(apps, schema_editor)


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0006_alter_translationsource_category'),
    ]

    operations = [
        migrations.AlterField(
            model_name='translationsource',
            name='category',
            field=models.CharField(
                choices=[
                    ('card', 'Card'),
                    ('character', 'Character'),
                    ('general', 'General'),
                    ('card_type', 'Card type'),
                    ('position', 'Position'),
                    ('body', 'Body'),
                    ('special', 'Special'),
                    ('result', 'Result'),
                    ('tag', 'Tag'),
                    ('ui', 'UI'),
                    ('pack', 'Pack'),
                    ('keyword', 'Keyword'),
                    ('state', 'State'),
                    ('token', 'Token / counter'),
                ],
                default='general',
                max_length=32,
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
