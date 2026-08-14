import re

from django.core.management.base import BaseCommand
from card.models import Card, CardTranslation, Character
from common.localization import (
    SUPPORTED_TRANSLATION_LANGUAGES,
    TOKEN_RE,
    clear_localization_cache,
    strip_outer_marks,
)
from common.models import TranslationSource, TranslationValue


FIELDS = ('text', 'detail_text')
LANGUAGES = SUPPORTED_TRANSLATION_LANGUAGES

BRACKET_PAIRS = (
    ('[', ']'),
    ('【', '】'),
    ('「', '」'),
    ('"', '"'),
    ('“', '”'),
    ('`', '`'),
)
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
STATE_CARD_CODES = {'CB03-PS-001', 'LMI-AT-056', 'LMI-AT-057', 'LMI-AT-058'}
SEMANTIC_STATE_CARDS = {
    'ST1-PS1': 'over_limit',
    'ST4-PS1': 'advance_notice',
}
KEYWORD_ALIASES = {
    'rai': {
        'ko': ('라이!',),
        'en': ('Rai!',),
        'ja': ('ライ！',),
    },
    'lefi': {
        'ko': ('레피!',),
        'en': ('Lefi!',),
        'ja': ('レピ！',),
    },
    'rakshasa': {
        'ko': ('나찰',),
        'en': ('Rakshasa',),
        'ja': ('羅刹',),
    },
}
SEMANTIC_ALIASES = {
    'state': {
        'over_limit': {'ko': ('오버 리밋',), 'en': ('Over Limit',), 'ja': ('オーバーリミット',)},
        'zero_suit': {'ko': ('제로 슈트',), 'en': ('Zero Suit',), 'ja': ('ゼロスーツ',)},
        'advance_notice': {'ko': ('예고',), 'en': ('Advance Notice',), 'ja': ('予告',)},
        'harmony': {'ko': ('조화',), 'en': ('Harmony',), 'ja': ('調和',)},
        'saintess': {'ko': ('성녀',), 'en': ('Saintess',), 'ja': ('聖女',)},
        'disaster_one': {'ko': ('디제스터 원',), 'en': ('Disaster One',), 'ja': ('ディザスターワン', 'ディザスター・ワン')},
        'dark_night': {'ko': ('암야',), 'en': ('Dark Night',), 'ja': ('闇夜',)},
        'blue_flame': {'ko': ('청염',), 'en': ('Blue Flame',), 'ja': ('青炎',)},
        'yin': {'ko': ('음',), 'en': ('Yin',), 'ja': ('陰',)},
        'yang': {'ko': ('양',), 'en': ('Yang',), 'ja': ('陽',)},
    },
    'token': {
        'hidden_bond': {'ko': ('은연',), 'en': ('Hidden Bond',), 'ja': ('隠縁',)},
        'howling': {'ko': ('하울링',), 'en': ('Howling',), 'ja': ('ハウリング',)},
        'calling_card': {'ko': ('예고장',), 'en': ('Calling Card',), 'ja': ('予告状',)},
        'parts': {'ko': ('파츠',), 'en': ('Parts',), 'ja': ('パーツ',)},
        'vocal': {'ko': ('보컬',), 'en': ('Vocal',), 'ja': ('ボーカル',)},
        'drum': {'ko': ('드럼',), 'en': ('Drum',), 'ja': ('ドラム',)},
        'guitar': {'ko': ('기타',), 'en': ('Guitar',), 'ja': ('ギター',)},
        'bass': {'ko': ('베이스',), 'en': ('Bass',), 'ja': ('ベース',)},
        'yin': {'ko': ('음',), 'en': ('Yin',), 'ja': ('陰',)},
        'yang': {'ko': ('양',), 'en': ('Yang',), 'ja': ('陽',)},
    },
}
LEGACY_SEMANTIC_TOKENS = {
    'general.over_limit': ('state', 'over_limit'),
    'tag.over_limit': ('state', 'over_limit'),
    'tag.zero_suit': ('state', 'zero_suit'),
    'tag.zero_suit_2': ('state', 'zero_suit'),
    'tag.advance_notice': ('state', 'advance_notice'),
    'tag.harmony': ('state', 'harmony'),
    'tag.saintess': ('state', 'saintess'),
    'tag.disaster_one': ('state', 'disaster_one'),
    'tag.dark_night_2': ('state', 'dark_night'),
    'tag.blue_flame_2': ('state', 'blue_flame'),
    'tag.hidden_bond': ('token', 'hidden_bond'),
    'tag.howling': ('token', 'howling'),
    'tag.calling_card_2': ('token', 'calling_card'),
    'general.parts': ('token', 'parts'),
    'tag.vocal': ('token', 'vocal'),
    'tag.drum': ('token', 'drum'),
    'tag.guitar': ('token', 'guitar'),
    'tag.bass': ('token', 'bass'),
}


class Command(BaseCommand):
    help = 'Convert clear card names, states, tokens, and keyword references to localization tokens.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write replacements. Without this, only prints a dry-run report.')
        parser.add_argument('--samples', type=int, default=50)

    def handle(self, *args, **options):
        apply_changes = options['apply']
        sample_limit = options['samples']
        total = 0
        samples = []
        by_token = {}

        if apply_changes:
            self.ensure_keyword_sources()
            self.ensure_semantic_sources()

        self.cards = list(Card.objects.exclude(name='').exclude(code='').prefetch_related('translations').order_by('id'))
        self.card_lookup = {card.code: card for card in self.cards}
        self.characters = list(
            Character.objects
            .exclude(name='')
            .exclude(localization_key='')
            .prefetch_related('translations')
            .order_by('id')
        )
        self.targets_by_language = {
            'ko': self.build_targets_for_language('ko'),
            **{
                language: self.build_targets_for_language(language)
                for language in LANGUAGES
            },
        }
        for card in Card.objects.order_by('id'):
            changed = self.convert_object_text(card, self.targets_by_language['ko'])
            if changed:
                total += len(changed)
                samples.extend((f'{card.code}.{field}', old, new) for field, old, new in changed)
                self.count_tokens(changed, by_token)
                if apply_changes:
                    card.save(update_fields=[field for field, _old, _new in changed])

        for language in LANGUAGES:
            targets = self.targets_by_language[language]
            for translation in CardTranslation.objects.filter(language=language).select_related('card').order_by('card_id'):
                changed = self.convert_object_text(translation, targets)
                if changed:
                    total += len(changed)
                    samples.extend(
                        (f'{translation.card.code}/{language}.{field}', old, new)
                        for field, old, new in changed
                    )
                    self.count_tokens(changed, by_token)
                    if apply_changes:
                        translation.save(update_fields=[field for field, _old, _new in changed])

        clear_localization_cache()
        label = 'Applied' if apply_changes else 'Dry-run'
        self.stdout.write(f'{label}: {total} field replacements')
        self.stdout.write('Token counts:')
        for token, count in sorted(by_token.items(), key=lambda item: (-item[1], item[0]))[:sample_limit]:
            self.stdout.write(f'  {token}: {count}')
        self.stdout.write('Samples:')
        for owner, old, new in samples[:sample_limit]:
            self.stdout.write(f'  {owner}: {self.preview(old)} -> {self.preview(new)}')
        if not apply_changes:
            self.stdout.write('Run again with --apply to write these replacements.')

    def convert_object_text(self, obj, targets):
        changed = []
        owner = getattr(getattr(obj, 'card', obj), 'code', str(obj.pk))
        for field in FIELDS:
            old = getattr(obj, field, '') or ''
            if not old:
                continue
            new = self.replace_targets(old, targets, owner)
            if new != old:
                setattr(obj, field, new)
                changed.append((field, old, new))
        return changed

    def replace_targets(self, text, targets, owner):
        normalized = self.normalize_existing_tokens(text)
        protected, placeholders = self.protect_existing_tokens(normalized)
        replaced = protected
        for target in targets:
            if target['owner'] == owner:
                continue
            replaced = self.replace_target(replaced, target)
        return self.restore_existing_tokens(replaced, placeholders)

    def normalize_existing_tokens(self, text):
        def replace(match):
            kind = match.group(1)
            payload = match.group(2).strip()
            if kind in ('card', 'state-card', 'token-card', 'counter-card'):
                if kind == 'state-card' and payload in SEMANTIC_STATE_CARDS:
                    return f'[[state:{SEMANTIC_STATE_CARDS[payload]}]]'
                card = self.card_lookup.get(payload)
                if card:
                    return self.card_token(card)
            if kind == 'term' and payload in LEGACY_SEMANTIC_TOKENS:
                semantic_kind, slug = LEGACY_SEMANTIC_TOKENS[payload]
                return f'[[{semantic_kind}:{slug}]]'
            return match.group(0)

        return TOKEN_RE.sub(replace, text)

    def replace_target(self, text, target):
        result = text
        if target.get('kind') == 'character':
            result = self.replace_character_technique_condition(result, target)
        for pattern in target.get('counter_marked_patterns', {}).values():
            result = pattern.sub(target['token'], result)
        for open_mark, close_mark in BRACKET_PAIRS:
            result = self.replace_marked(result, target, open_mark, close_mark)
        if target.get('name_context_pattern'):
            result = target['name_context_pattern'].sub(target['token'], result)
        result = self.replace_bare(result, target)
        return result

    def replace_character_technique_condition(self, text, target):
        marked_pattern = target.get('character_marked_technique_pattern')
        prefixed_bare_pattern = target.get('character_prefixed_bare_technique_pattern')
        bare_pattern = target.get('character_bare_technique_pattern')
        if marked_pattern:
            text = marked_pattern.sub(lambda match: self.character_condition_replacement(text, match, target), text)
        if prefixed_bare_pattern:
            text = prefixed_bare_pattern.sub(
                lambda match: self.character_condition_replacement(text, match, target),
                text,
            )
        if bare_pattern:
            text = bare_pattern.sub(lambda match: self.character_condition_replacement(text, match, target), text)
        return text

    def character_condition_replacement(self, full_text, match, target):
        if self.inside_angle_condition(full_text, match.start()):
            return match.group(0)
        prefix = re.sub(r'\s+', ' ', (match.group('prefix') or '').strip())
        traits = re.sub(r'\s+', ' ', (match.group('traits') or '').strip())
        condition_parts = [part for part in (prefix, target['token'], traits) if part]
        return f'<{" ".join(condition_parts)}> {match.group("term")}'

    def inside_angle_condition(self, text, index):
        last_open = max(text.rfind('<', 0, index), text.rfind('〈', 0, index))
        last_close = max(text.rfind('>', 0, index), text.rfind('〉', 0, index))
        return last_open > last_close

    def replace_marked(self, text, target, open_mark, close_mark):
        if target.get('open_marks') and open_mark not in target['open_marks']:
            return text
        pattern = target['marked_patterns'][(open_mark, close_mark)]
        return pattern.sub(target['token'], text)

    def replace_bare(self, text, target):
        if not target.get('bare_safe'):
            return text
        return target['bare_pattern'].sub(target['token'], text)

    def protect_existing_tokens(self, text):
        placeholders = {}

        def replace(match):
            key = f'@@LUMEN_TOKEN_{len(placeholders)}@@'
            placeholders[key] = match.group(0)
            return key

        return TOKEN_RE.sub(replace, text), placeholders

    def restore_existing_tokens(self, text, placeholders):
        for key, token in placeholders.items():
            text = text.replace(key, token)
        return text

    def build_targets_for_language(self, language):
        targets = []
        for card in self.cards:
            if card.code in SEMANTIC_STATE_CARDS:
                continue
            name = self.card_name_for_language(card, language)
            for candidate in self.name_candidates(name):
                targets.append({
                    'name': candidate,
                    'token': self.card_token(card),
                    'owner': card.code,
                    'kind': 'card',
                })
            if language == 'ko':
                for candidate in self.name_candidates(card.name):
                    targets.append({
                        'name': candidate,
                        'token': self.card_token(card),
                        'owner': card.code,
                        'kind': 'card',
                    })
        for character in self.characters:
            name = self.character_name_for_language(character, language)
            for candidate in self.name_candidates(name, include_short=True):
                targets.append({
                    'name': candidate,
                    'token': f'[[character:{character.localization_key}]]',
                    'owner': f'character:{character.localization_key}',
                    'kind': 'character',
                })
            if language == 'ko':
                for candidate in self.name_candidates(character.name, include_short=True):
                    targets.append({
                        'name': candidate,
                        'token': f'[[character:{character.localization_key}]]',
                        'owner': f'character:{character.localization_key}',
                        'kind': 'character',
                    })
        for slug, aliases in KEYWORD_ALIASES.items():
            for alias in aliases.get(language, ()):
                targets.append({
                    'name': alias,
                    'token': f'[[keyword:{slug}]]',
                    'owner': f'keyword:{slug}',
                    'kind': 'keyword',
                    'name_context_language': language,
                })
        # Token counters are processed before states so legacy forms such as
        # 「음」카운터 are normalized as token references, not states.
        for semantic_kind in ('token', 'state'):
            entries = SEMANTIC_ALIASES[semantic_kind]
            for slug, aliases in entries.items():
                for alias in aliases.get(language, ()):
                    target = {
                        'name': alias,
                        'token': f'[[{semantic_kind}:{slug}]]',
                        'owner': f'{semantic_kind}:{slug}',
                        'kind': semantic_kind,
                        'allow_bare': semantic_kind == 'token' and slug not in ('yin', 'yang'),
                    }
                    if semantic_kind == 'state':
                        target['open_marks'] = ('「',)
                    elif slug in ('yin', 'yang'):
                        target['open_marks'] = ('【', '[')
                        target['context_counter'] = True
                    targets.append(target)
        return self.safe_targets(targets)

    def card_name_for_language(self, card, language):
        if language == 'ko':
            return card.name
        for translation in card.translations.all():
            if translation.language == language and translation.name:
                return translation.name
        return ''

    def character_name_for_language(self, character, language):
        if language == 'ko':
            return character.name
        for translation in character.translations.all():
            if translation.language == language and translation.name:
                return translation.name
        return ''

    def name_candidates(self, name, include_short=False):
        name = str(name or '').strip()
        if not name:
            return []
        stripped = strip_outer_marks(name)
        candidates = set()
        if len(name) >= 3:
            candidates.add(name)
        if len(stripped) >= (1 if include_short else 2):
            candidates.add(stripped)
        compact = re.sub(r'\s+', '', stripped)
        if len(compact) >= 3:
            candidates.add(compact)
        return sorted(candidates, key=len, reverse=True)

    def card_token(self, card):
        if self.is_state_card(card):
            return f'[[state-card:{card.code}]]'
        if self.is_token_card(card):
            return f'[[token-card:{card.code}]]'
        return f'[[card:{card.code}]]'

    def is_state_card(self, card):
        return card.code in STATE_CARD_CODES or (
            card.type == '특성'
            and str(card.name or '').strip().startswith('「')
        )

    def is_token_card(self, card):
        return card.type == '토큰' or str(card.name or '').strip().startswith('【')

    def safe_targets(self, targets):
        unique = {}
        for target in targets:
            key = (target['name'], target['token'], target['owner'])
            unique[key] = target
        targets = list(unique.values())
        names = [target['name'] for target in targets]
        unsafe = {name for name in names for other in names if name != other and name in other}
        safe = []
        for target in targets:
            target['bare_safe'] = (
                target.get('allow_bare', True)
                and len(target['name']) >= 3
                and target['name'] not in unsafe
            )
            safe.append(self.compile_target(target))
        return sorted(safe, key=lambda target: len(target['name']), reverse=True)

    def compile_target(self, target):
        name = re.escape(target['name'])
        target['marked_patterns'] = {
            (open_mark, close_mark): re.compile(
                re.escape(open_mark) + r'\s*' + name + r'\s*' + re.escape(close_mark)
            )
            for open_mark, close_mark in BRACKET_PAIRS
        }
        if any(
            target['name'].startswith(open_mark) and target['name'].endswith(close_mark)
            for open_mark, close_mark in BRACKET_PAIRS
        ):
            target['bare_pattern'] = re.compile(name)
        else:
            target['bare_pattern'] = re.compile(r'(?<![\w\[\[:])' + name + r'(?![\w\]\]])')
        if target.get('kind') == 'character':
            self.compile_character_technique_patterns(target, name)
        if target.get('name_context_language'):
            language = target['name_context_language']
            suffix = {
                'ko': r'(?=\s*명)',
                'en': r'(?=\s+(?:in\s+(?:the\s+)?name|name))',
                'ja': r'(?=\s*(?:の?名))',
            }[language]
            target['name_context_pattern'] = re.compile(
                r'(?<![\w\[\[:])' + name + suffix,
                re.IGNORECASE if language == 'en' else 0,
            )
        if target.get('context_counter'):
            counter_term = r'(?:카운터|Counters?|カウンター)'
            target['counter_marked_patterns'] = {
                (open_mark, close_mark): re.compile(
                    re.escape(open_mark)
                    + r'\s*'
                    + name
                    + r'\s*'
                    + re.escape(close_mark)
                    + r'(?=\s*'
                    + counter_term
                    + r')',
                    re.IGNORECASE,
                )
                for open_mark, close_mark in BRACKET_PAIRS
            }
        return target

    def compile_character_technique_patterns(self, target, escaped_name):
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
        target['character_marked_technique_pattern'] = re.compile(
            prefix + r'\[\s*' + escaped_name + r'\s*\]' + trait_group + r'\s*' + term
        )
        target['character_prefixed_bare_technique_pattern'] = re.compile(
            rf'(?P<prefix>{speed_prefix}\s*)'
            + escaped_name
            + trait_group
            + r'\s*'
            + term
        )
        target['character_bare_technique_pattern'] = re.compile(
            r'(?P<prefix>)(?<![\w\[\[:])'
            + escaped_name
            + trait_group
            + r'\s*'
            + term
        )

    def ensure_keyword_sources(self):
        for slug, aliases in KEYWORD_ALIASES.items():
            key = f'keyword.{slug}'
            defaults = {
                'category': 'keyword',
                'source_text': aliases['ko'][0],
                'field_name': 'name',
                'is_active': True,
            }
            source = TranslationSource.objects.filter(key=key).first()
            if source is None:
                source = TranslationSource.objects.create(key=key, **defaults)
            else:
                changed = []
                for field_name, value in defaults.items():
                    if getattr(source, field_name) != value:
                        setattr(source, field_name, value)
                        changed.append(field_name)
                if changed:
                    source.save(update_fields=changed)
            for language in LANGUAGES:
                text = aliases.get(language, ('',))[0]
                if not text:
                    continue
                value_defaults = {
                    'text': text,
                    'data': {},
                    'status': TranslationValue.STATUS_TRANSLATED,
                }
                value = TranslationValue.objects.filter(source=source, language=language).first()
                if value is None:
                    TranslationValue.objects.create(
                        source=source,
                        language=language,
                        **value_defaults,
                    )
                    continue
                changed = []
                for field_name, field_value in value_defaults.items():
                    if getattr(value, field_name) != field_value:
                        setattr(value, field_name, field_value)
                        changed.append(field_name)
                if changed:
                    value.save(update_fields=changed)

    def ensure_semantic_sources(self):
        for semantic_kind, entries in SEMANTIC_ALIASES.items():
            for slug, aliases in entries.items():
                key = f'term.{semantic_kind}.{slug}'
                defaults = {
                    'category': semantic_kind,
                    'source_text': aliases['ko'][0],
                    'field_name': semantic_kind,
                    'is_active': True,
                }
                source, _created = TranslationSource.objects.update_or_create(key=key, defaults=defaults)
                for language in LANGUAGES:
                    text = aliases.get(language, ('',))[0]
                    if not text:
                        continue
                    TranslationValue.objects.update_or_create(
                        source=source,
                        language=language,
                        defaults={
                            'text': text,
                            'data': {},
                            'status': TranslationValue.STATUS_TRANSLATED,
                        },
                    )

    def count_tokens(self, changed, counter):
        for _field, _old, new in changed:
            for token in re.findall(r'\[\[[^\]]+\]\]', new):
                counter[token] = counter.get(token, 0) + 1

    def preview(self, text):
        return str(text).replace('\r', '').replace('\n', ' | ')[:120]
