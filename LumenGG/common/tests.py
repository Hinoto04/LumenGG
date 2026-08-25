from io import StringIO

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from card.models import Card, CardTranslation, Character, CharacterTranslation
from card.search import card_matches_search
from common.language import LANGUAGE_COOKIE_NAME, game_term, javascript_translations, translated_card_field, translated_character_field, ui_text
from common.localization import card_translation_key, render_localized_markup
from common.management.commands.convert_localized_references import Command as ConvertLocalizedReferencesCommand
from common.localization_batches.batch_20260817 import SEMANTIC_REFERENCES, TRANSLATIONS
from common.models import (
    Rule,
    Rulebook,
    RulebookTranslation,
    RuleTranslation,
    RuleVisualGuide,
    RuleVisualGuideTranslation,
    TermTranslation,
    TranslationSource,
    TranslationValue,
)
from common.rule_references import link_rule_references
from common.rule_reference_semantics import semanticize_rulebooks
from common.rulebooks import get_rulebook, ordered_rule_tree, public_rulebook_summaries


class LanguageSettingTests(TestCase):
    def test_set_language_stores_session_and_cookie(self):
        response = self.client.post(
            reverse('common:setLanguage'),
            {'language': 'en', 'next': '/'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session['lumengg_language'], 'en')
        self.assertEqual(response.cookies[LANGUAGE_COOKIE_NAME].value, 'en')


class TranslationLookupTests(TestCase):
    def test_card_translation_falls_back_to_korean_when_missing(self):
        character = Character.objects.create(
            name='니아',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        card = Card.objects.create(
            name='라이! 촙!',
            code='ST1-005',
            character=character,
            img='https://example.com/card.webp',
        )

        self.assertEqual(translated_card_field(card, 'en', 'name'), '라이! 촙!')

    def test_card_translation_uses_selected_language(self):
        character = Character.objects.create(
            name='니아',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        card = Card.objects.create(
            name='라이! 촙!',
            code='ST1-005',
            character=character,
            img='https://example.com/card.webp',
        )
        CardTranslation.objects.create(
            card=card,
            language='en',
            name='Rai! Chop!',
        )

        self.assertEqual(translated_card_field(card, 'en', 'name'), 'Rai! Chop!')

    def test_game_term_translates_builtin_judgment_terms(self):
        self.assertEqual(game_term('방어', 'en'), 'Guard')
        self.assertEqual(game_term('상단·중단 상쇄', 'en'), 'High/Mid Clash')
        self.assertEqual(game_term('하단 회피/그랩', 'ja'), '下段 回避/投げ')
        self.assertEqual(game_term('개러지 토큰', 'en'), 'Garage Token')
        self.assertEqual(game_term('개러지 토큰', 'ja'), 'ガレージトークン')

    def test_yohan_passive_short_labels_are_translated(self):
        self.assertEqual(ui_text('홀', 'en'), 'Odd')
        self.assertEqual(ui_text('짝', 'en'), 'Even')
        self.assertEqual(ui_text('공', 'ja'), '攻')
        self.assertEqual(ui_text('수', 'ja'), '防')
        self.assertEqual(javascript_translations('en')['선언'], 'Declare')
        self.assertEqual(javascript_translations('ja')['예지'], '予知')

    def test_game_term_uses_custom_term_translation(self):
        TermTranslation.objects.update_or_create(
            source='테스트 용어',
            language='en',
            defaults={
                'text': 'Afterimage',
                'category': 'body',
            },
        )

        self.assertEqual(game_term('테스트 용어', 'en'), 'Afterimage')

    def test_card_reference_token_renders_current_translated_name(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        referenced = Card.objects.create(
            name='참조 카드',
            code='TKN-REF',
            character=character,
            img='https://example.com/ref.webp',
        )
        reference_translation = CardTranslation.objects.create(
            card=referenced,
            language='en',
            name='Reference Card',
        )
        source = Card.objects.create(
            name='토큰 테스트',
            code='TKN-SRC',
            character=character,
            text='Use [[card:TKN-REF]].',
            img='https://example.com/source.webp',
        )

        self.assertEqual(translated_card_field(source, 'en', 'text'), 'Use [Reference Card].')
        self.assertEqual(translated_card_field(source, 'ko', 'text'), 'Use [참조 카드].')

        reference_translation.name = 'Renamed Card'
        reference_translation.save()

        self.assertEqual(translated_card_field(source, 'en', 'text'), 'Use [Renamed Card].')

    def test_character_reference_token_renders_current_translated_name(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='[[character:nya]] 소개',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        CharacterTranslation.objects.create(
            character=character,
            language='en',
            name='NYA',
            description='About [[character:nya]]',
        )

        self.assertEqual(translated_character_field(character, 'en', 'description'), 'About [NYA]')

    def test_character_technique_condition_conversion_wraps_angle_outside_square_name(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        CharacterTranslation.objects.create(
            character=character,
            language='ja',
            name='ニア',
        )
        rin = Character.objects.create(
            name='린',
            localization_key='rin',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/rin.webp',
        )
        command = ConvertLocalizedReferencesCommand()
        command.cards = []
        command.card_lookup = {}
        command.characters = [character, rin]
        targets = command.build_targets_for_language('ko')

        converted = command.replace_targets(
            '모든 [니아] 공격 기술과 9속도 이하 니아 기술 및 버린 기술',
            targets,
            'TKN-SRC',
        )

        self.assertEqual(
            converted,
            '모든 <[[character:nya]] 공격> 기술과 <9속도 이하 [[character:nya]]> 기술 및 버린 기술',
        )
        self.assertEqual(
            render_localized_markup(converted, 'ko'),
            '모든 <[니아] 공격> 기술과 <9속도 이하 [니아]> 기술 및 버린 기술',
        )

        ja_targets = command.build_targets_for_language('ja')
        self.assertEqual(
            command.replace_targets('速度9以下のニア技', ja_targets, 'TKN-SRC'),
            '<速度9以下の [[character:nya]]> 技',
        )

    def test_semantic_conversion_distinguishes_yin_yang_states_and_tokens(self):
        command = ConvertLocalizedReferencesCommand()
        command.cards = []
        command.card_lookup = {}
        command.characters = []
        targets = command.build_targets_for_language('ko')

        converted = command.replace_targets(
            '「음」: 상태 / 「음」카운터 / 【양】카운터 / [드럼]',
            targets,
            'TKN-SRC',
        )

        self.assertEqual(
            converted,
            '[[state:yin]]: 상태 / [[token:yin]]카운터 / [[token:yang]]카운터 / [[token:drum]]',
        )
        self.assertEqual(
            render_localized_markup(converted, 'ko'),
            '「음」: 상태 / 【음】카운터 / 【양】카운터 / 【드럼】',
        )

    def test_named_keywords_and_character_states_use_semantic_tokens(self):
        command = ConvertLocalizedReferencesCommand()
        command.cards = []
        command.card_lookup = {}
        command.characters = []
        targets = command.build_targets_for_language('ko')

        converted = command.replace_targets(
            '"라이!"와 "레피!" / 「오버 리밋」 / 「제로 슈트」 / '
            '「예고」 / 라이!명이 / [[state-card:ST1-PS1]] / [[state-card:ST4-PS1]]',
            targets,
            'TKN-SRC',
        )

        self.assertEqual(
            converted,
            '[[keyword:rai]]와 [[keyword:lefi]] / [[state:over_limit]] / '
            '[[state:zero_suit]] / [[state:advance_notice]] / [[keyword:rai]]명이 / '
            '[[state:over_limit]] / [[state:advance_notice]]',
        )

        command.ensure_keyword_sources()
        command.ensure_semantic_sources()
        self.assertEqual(
            render_localized_markup(converted, 'en'),
            '"Rai!"와 "Lefi!" / 「Over Limit」 / 「Zero Suit」 / '
            '「Advance Notice」 / "Rai!"명이 / 「Over Limit」 / 「Advance Notice」',
        )

    def test_semantic_reference_tokens_render_with_standard_marks(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        state_card = Card.objects.create(
            name='「오버 리밋」',
            code='TKN-STATE',
            type='특성',
            character=character,
            img='https://example.com/state.webp',
        )
        token_card = Card.objects.create(
            name='【불씨】',
            code='TKN-COUNTER',
            type='토큰',
            character=character,
            img='https://example.com/token.webp',
        )
        source = Card.objects.create(
            name='표기 테스트',
            code='TKN-MARKUP',
            character=character,
            text=(
                '[[state-card:TKN-STATE]] and [[token-card:TKN-COUNTER]] '
                'and [[keyword:rakshasa]] and [[state:harmony]] and [[token:hidden_bond]]'
            ),
            img='https://example.com/source.webp',
        )
        keyword, _created = TranslationSource.objects.update_or_create(
            key='keyword.rakshasa',
            defaults={
                'category': 'keyword',
                'source_text': '나찰',
                'field_name': 'name',
            },
        )
        TranslationValue.objects.update_or_create(
            source=keyword,
            language='en',
            defaults={'text': 'Rakshasa'},
        )
        harmony, _created = TranslationSource.objects.update_or_create(
            key='term.state.harmony',
            defaults={
                'category': 'state',
                'source_text': '조화',
                'field_name': 'state',
            },
        )
        TranslationValue.objects.update_or_create(
            source=harmony,
            language='en',
            defaults={'text': 'Harmony'},
        )
        hidden_bond, _created = TranslationSource.objects.update_or_create(
            key='term.token.hidden_bond',
            defaults={
                'category': 'token',
                'source_text': '은연',
                'field_name': 'token',
            },
        )
        TranslationValue.objects.update_or_create(
            source=hidden_bond,
            language='en',
            defaults={'text': 'Hidden Bond'},
        )
        CardTranslation.objects.create(
            card=state_card,
            language='en',
            name='Over Limit',
        )
        CardTranslation.objects.create(
            card=token_card,
            language='en',
            name='Ember',
        )

        self.assertEqual(
            translated_card_field(source, 'ko', 'text'),
            '「오버 리밋」 and 【불씨】 and "나찰" and 「조화」 and 【은연】',
        )
        self.assertEqual(
            translated_card_field(source, 'en', 'text'),
            '「Over Limit」 and 【Ember】 and "Rakshasa" and 「Harmony」 and 【Hidden Bond】',
        )

    def test_search_uses_translation_catalog_values(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        card = Card.objects.create(
            name='검색 원본',
            code='TKN-SEARCH',
            character=character,
            img='https://example.com/card.webp',
        )
        source = TranslationSource.objects.get(key=card_translation_key(card, 'name'))
        TranslationValue.objects.create(
            source=source,
            language='en',
            text='Catalog Search Name',
        )

        self.assertTrue(card_matches_search(card, 'catalog search'))

    def test_fill_missing_localization_generates_hidden_keywords_from_translated_name(self):
        character = Character.objects.create(
            name='니아',
            localization_key='nya',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        card = Card.objects.create(
            name='퀵 알레',
            code='TKN-HIDDEN',
            character=character,
            hiddenKeyword='퀵알레/퀵알래/',
            img='https://example.com/card.webp',
        )
        CardTranslation.objects.create(
            card=card,
            language='en',
            name='Quick Allez',
            hiddenKeyword='퀵알레/',
        )
        CardTranslation.objects.create(
            card=card,
            language='ja',
            name='クイック・アレ',
            hiddenKeyword='퀵알레/',
        )

        call_command('fill_missing_localization', verbosity=0)

        en_hidden = translated_card_field(card, 'en', 'hiddenKeyword')
        ja_hidden = translated_card_field(card, 'ja', 'hiddenKeyword')

        self.assertIn('QuickAllez/', en_hidden)
        self.assertIn('quickallez/', en_hidden)
        self.assertNotIn('퀵알레', en_hidden)
        self.assertIn('クイックアレ/', ja_hidden)
        self.assertNotIn('퀵알레', ja_hidden)
        self.assertTrue(card_matches_search(card, 'quickallez'))
        self.assertTrue(card_matches_search(card, 'クイックアレ'))


class ReviewedSemanticReferenceTests(TestCase):
    def setUp(self):
        for reference in SEMANTIC_REFERENCES.values():
            source, _created = TranslationSource.objects.update_or_create(
                key=f'term.{reference["kind"]}.{reference["slug"]}',
                defaults={
                    'category': reference['kind'],
                    'source_text': reference['ko'],
                    'field_name': reference['kind'],
                    'is_active': True,
                },
            )
            for language in ('en', 'ja'):
                TranslationValue.objects.update_or_create(
                    source=source,
                    language=language,
                    defaults={
                        'text': reference[language],
                        'status': TranslationValue.STATUS_TRANSLATED,
                    },
                )

    def test_reviewed_semantic_references_render_with_kind_marks(self):
        for reference in SEMANTIC_REFERENCES.values():
            token = f'[[{reference["kind"]}:{reference["slug"]}]]'
            marks = ('「', '」') if reference['kind'] == 'state' else ('【', '】')
            for language in ('ko', 'en', 'ja'):
                with self.subTest(token=token, language=language):
                    self.assertEqual(
                        render_localized_markup(token, language),
                        f'{marks[0]}{reference[language]}{marks[1]}',
                    )

    def test_converter_uses_semantic_tokens_for_mapped_cards(self):
        command = ConvertLocalizedReferencesCommand()
        for code, reference in SEMANTIC_REFERENCES.items():
            card = Card(code=code, name=reference['ko'], type='토큰')
            with self.subTest(code=code):
                self.assertEqual(
                    command.card_token(card),
                    f'[[{reference["kind"]}:{reference["slug"]}]]',
                )

        ordinary = Card(code='TEST-001', name='일반 카드', type='공격')
        self.assertEqual(command.card_token(ordinary), '[[card:TEST-001]]')

    def test_converter_normalizes_dotted_legacy_semantic_token(self):
        command = ConvertLocalizedReferencesCommand()
        command.card_lookup = {}
        self.assertEqual(
            command.normalize_existing_tokens('Use [[term.token:yin]].'),
            'Use [[token:yin]].',
        )

    def test_review_batch_contains_no_hangul_in_foreign_text(self):
        for source_key, translations in TRANSLATIONS.items():
            for language, text in translations.items():
                with self.subTest(source_key=source_key, language=language):
                    self.assertNotRegex(text, r'[가-힣]')


class RulebookLocalizationTests(TestCase):
    def test_rulebook_loader_uses_static_locale_document(self):
        english = get_rulebook('guide', 'en')
        japanese = get_rulebook('guide', 'ja')

        self.assertEqual(english['title'], 'Lumen Condenser Learn to Play')
        self.assertEqual(japanese['title'], 'ルーメンコンデンサー はじめてのプレイガイド')
        self.assertEqual(english['translation_status'], 'machine-draft')
        self.assertIsNotNone(japanese['translation_notice'])

    def test_rulebook_anchor_contract_is_shared_between_languages(self):
        for slug in ('guide', 'comprehensive', 'tournament'):
            korean_anchors = [item['anchor'] for item in get_rulebook(slug, 'ko')['toc']]
            for language in ('en', 'ja'):
                with self.subTest(slug=slug, language=language):
                    localized_anchors = [item['anchor'] for item in get_rulebook(slug, language)['toc']]
                    self.assertEqual(localized_anchors, korean_anchors)

    def test_rulebook_index_summaries_follow_selected_language(self):
        summaries = public_rulebook_summaries('ja')

        self.assertEqual(summaries[0]['short_title'], 'はじめてのプレイガイド')
        self.assertTrue(all(item['language'] == 'ja' for item in summaries))

    def test_translation_notice_identifies_machine_generated_draft(self):
        notice = get_rulebook('guide', 'en')['translation_notice']

        self.assertIn('machine-generated reference draft', notice['text'])


class RuleHierarchyTests(TestCase):
    def setUp(self):
        self.book = Rulebook.objects.create(
            slug='test-rules',
            url_name='rules:detail',
            kicker='TEST RULES',
            searchable=True,
        )
        RulebookTranslation.objects.create(
            rulebook=self.book,
            language='ko',
            title='테스트 규칙서',
            short_title='테스트 규칙',
        )

    def make_rule(self, reference, title, *, parent=None, content='', priority=0):
        rule = Rule.objects.create(
            rulebook=self.book,
            parent=parent,
            reference_name=reference,
            priority=priority,
        )
        RuleTranslation.objects.create(
            rule=rule,
            language='ko',
            title=title,
            content=content,
        )
        return rule

    def test_nested_rule_numbers_follow_priority_within_each_parent(self):
        later_root = self.make_rule('later-root', '뒤쪽 상위 규칙', priority=20)
        first_root = self.make_rule('first-root', '앞쪽 상위 규칙', priority=10)
        later_child = self.make_rule(
            'later-child',
            '뒤쪽 하위 규칙',
            parent=first_root,
            priority=20,
        )
        first_child = self.make_rule(
            'first-child',
            '앞쪽 하위 규칙',
            parent=first_root,
            priority=10,
        )
        grandchild = self.make_rule('target-rule', '하위 규칙', parent=first_child)

        rows = ordered_rule_tree(self.book.rules.all())

        self.assertEqual(
            [(row['rule'].reference_name, row['number']) for row in rows],
            [
                ('first-root', '1'),
                ('first-child', '1.1'),
                ('target-rule', '1.1.1'),
                ('later-child', '1.2'),
                ('later-root', '2'),
            ],
        )
        self.assertEqual(grandchild.full_number, '1.1.1')

    def test_database_rulebook_renders_hierarchy_and_reference_links(self):
        root = self.make_rule(
            'root-rule',
            '상위 규칙',
            content='<p>[[target-rule]]을 확인합니다.</p>',
        )
        child = self.make_rule('target-rule', '하위 규칙', parent=root)

        rendered = get_rulebook(self.book.slug, 'ko')

        self.assertEqual(rendered['source'], 'database')
        self.assertEqual([item['title'] for item in rendered['toc']], ['1 상위 규칙', '1.1 하위 규칙'])
        self.assertIn('href="#target-rule"', str(rendered['html']))
        self.assertIn('1.1 하위 규칙', str(rendered['html']))

    def test_hidden_rules_keep_public_numbers_consistent_with_management_order(self):
        hidden = self.make_rule('hidden-rule', '비공개 규칙', priority=10)
        hidden.is_public = False
        hidden.save(update_fields=['is_public'])
        self.make_rule('public-rule', '공개 규칙', priority=20)

        rendered = get_rulebook(self.book.slug, 'ko')

        self.assertEqual([item['title'] for item in rendered['toc']], ['2 공개 규칙'])
        self.assertNotIn('비공개 규칙', str(rendered['html']))

    def test_rule_cannot_use_its_descendant_as_parent(self):
        root = self.make_rule('root-rule', '상위 규칙')
        child = self.make_rule('child-rule', '하위 규칙', parent=root)
        root.parent = child

        with self.assertRaises(ValidationError):
            root.full_clean()

    def test_reference_linker_does_not_rewrite_existing_links_or_code(self):
        targets = {'target-rule': {'label': '1 대상', 'number': '1', 'href': '#target-rule'}}
        html = link_rule_references(
            '<p>[[target-rule]] <a href="#">[[target-rule]]</a> <code>[[target-rule]]</code></p>',
            targets,
        )

        self.assertEqual(html.count('class="v2-rule-reference"'), 1)
        self.assertIn('<code>[[target-rule]]</code>', html)

    def test_numeric_reference_label_uses_current_automatic_number(self):
        html = link_rule_references(
            '<p>[[target-rule|9.9]]</p>',
            {'target-rule': {'label': '1.2 대상', 'number': '1.2', 'href': '#target-rule'}},
        )

        self.assertIn('>1.2</a>', html)
        self.assertNotIn('9.9', html)

    def test_rule_visual_guides_render_tabs_and_trusted_code(self):
        rule = self.make_rule('visual-rule', '비주얼 규칙')
        later = RuleVisualGuide.objects.create(
            rule=rule,
            priority=20,
            css='#later-visual { color: red; }',
            javascript='window.ruleVisualScript = true;',
        )
        first = RuleVisualGuide.objects.create(rule=rule, priority=10)
        hidden = RuleVisualGuide.objects.create(rule=rule, priority=30, is_public=False)
        RuleVisualGuideTranslation.objects.create(
            guide=later,
            language='ko',
            title='두 번째 가이드',
            content='<div id="later-visual">두 번째</div><script>window.inlineVisual = true;</script>',
        )
        RuleVisualGuideTranslation.objects.create(
            guide=first,
            language='ko',
            title='첫 번째 가이드',
            content='<button id="first-visual">첫 번째</button>',
        )
        RuleVisualGuideTranslation.objects.create(
            guide=hidden,
            language='ko',
            title='숨긴 가이드',
            content='<div>숨김</div>',
        )

        rendered = get_rulebook(self.book.slug, 'ko')
        html = str(rendered['html'])

        self.assertTrue(rendered['has_inline_visuals'])
        self.assertLess(html.index('첫 번째 가이드'), html.index('두 번째 가이드'))
        self.assertIn('data-rule-inline-visual-tab', html)
        self.assertIn('<style data-rule-visual-style=', html)
        self.assertIn('#later-visual { color: red; }', html)
        self.assertIn('window.ruleVisualScript = true;', html)
        self.assertIn('<script>window.inlineVisual = true;</script>', html)
        self.assertNotIn('숨긴 가이드', html)

    def test_semantic_reference_conversion_rewrites_number_and_named_references(self):
        root = self.make_rule('old-root', '상위 규칙')
        target = self.make_rule('old-target', '대상 규칙', parent=root)
        RuleTranslation.objects.create(rule=target, language='en', title='Target Rule')
        source = self.make_rule(
            'old-source',
            '참조 규칙',
            content=(
                '<p>1.1 및 [[old-target]]을 확인합니다. '
                '<a href="#old-target">링크 대상</a> <code>1.1</code></p>'
            ),
        )
        RuleTranslation.objects.create(rule=source, language='en', title='Reference Rule')

        semanticize_rulebooks([self.book])

        target.refresh_from_db()
        source_content = source.translations.get(language='ko').content
        self.assertEqual(target.reference_name, 'test-rules-target-rule')
        self.assertIn('old-target', target.reference_aliases)
        self.assertIn('[[test-rules-target-rule|1.1]]', source_content)
        self.assertIn('[[test-rules-target-rule]]', source_content)
        self.assertIn('[[test-rules-target-rule|링크 대상]]', source_content)
        self.assertIn('<code>1.1</code>', source_content)


class RulebookImportTests(TestCase):
    def test_import_command_creates_editable_database_rules(self):
        output = StringIO()

        call_command('import_rulebooks', '--slug', 'tournament', stdout=output)

        book = Rulebook.objects.get(slug='tournament')
        self.assertGreater(book.rules.count(), 10)
        self.assertTrue(book.rules.filter(translations__language='en').exists())
        self.assertTrue(book.visual_guides.filter(rule__isnull=True).exists())
        self.assertEqual(get_rulebook('tournament', 'ko')['source'], 'database')
        self.assertIn('규칙', output.getvalue())

    def test_import_command_preserves_numbered_rule_hierarchy(self):
        call_command('import_rulebooks', '--slug', 'comprehensive', stdout=StringIO())

        clause = next(
            rule
            for rule in Rule.objects.filter(rulebook__slug='comprehensive').select_related('parent')
            if 'rule-0-3-1' in rule.reference_aliases
        )

        self.assertRegex(clause.full_number, r'^\d+(?:\.\d+)+$')
        self.assertIsNotNone(clause.parent_id)
        self.assertFalse(clause.show_in_toc)
        self.assertTrue(clause.reference_name.startswith('rule-processing-unit'))
        self.assertIn('rule-0-3-1', clause.reference_aliases)

    def test_default_import_moves_every_rulebook_and_visual_guide_to_database(self):
        call_command('import_rulebooks', stdout=StringIO())

        for slug in ('guide', 'comprehensive', 'tournament'):
            with self.subTest(slug=slug):
                book = Rulebook.objects.get(slug=slug)
                rendered = get_rulebook(slug, 'ko')
                self.assertTrue(book.rules.exists())
                self.assertTrue(book.visual_guides.filter(rule__isnull=True).exists())
                self.assertIn('.v2-rulebook-visual', book.visual_css)
                self.assertIn('activatePanel', book.visual_javascript)
                self.assertEqual(rendered['source'], 'database')
                self.assertTrue(rendered['has_page_visuals'])
                self.assertIn('data-rulebook-visual', str(rendered['page_visual_html']))

        guide = Rulebook.objects.get(slug='guide')
        self.assertEqual(guide.visual_guides.filter(rule__isnull=True).count(), 3)
        guide_html = str(get_rulebook('guide', 'ko')['page_visual_html'])
        self.assertIn('v2-rulebook-board', guide_html)
        self.assertIn('v2-rulebook-card-anatomy', guide_html)
        self.assertIn('v2-rulebook-phase-track', guide_html)
        self.assertIn('data-rulebook-visual-common-style', guide_html)
        self.assertIn('data-rulebook-visual-common-script', guide_html)


class RuleEditorViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('rule-admin', 'rules@example.com', 'password')
        self.client.force_login(self.user)
        self.book = Rulebook.objects.get(slug='guide')

    def test_editor_creates_rule_with_wysiwyg_translation(self):
        response = self.client.post(reverse('rules:ruleCreate'), {
            'rulebook': self.book.pk,
            'parent': '',
            'reference_name': 'new-rule',
            'priority': 10,
            'show_in_toc': 'on',
            'is_public': 'on',
            'translation-ko-title': '새 규칙',
            'translation-ko-content': '<p><strong>편집 본문</strong></p>',
            'translation-en-title': '',
            'translation-en-content': '',
            'translation-ja-title': '',
            'translation-ja-content': '',
        })

        self.assertEqual(response.status_code, 302)
        rule = Rule.objects.get(reference_name='new-rule')
        self.assertEqual(rule.full_number, '1')
        self.assertIn('<strong>편집 본문</strong>', rule.translations.get(language='ko').content)

    def test_manage_pages_drill_down_one_rule_level_at_a_time(self):
        root = Rule.objects.create(
            rulebook=self.book,
            reference_name='root-rule',
        )
        child = Rule.objects.create(
            rulebook=self.book,
            parent=root,
            reference_name='child-rule',
        )
        grandchild = Rule.objects.create(
            rulebook=self.book,
            parent=child,
            reference_name='grandchild-rule',
        )
        RuleTranslation.objects.create(rule=root, language='ko', title='상위 규칙')
        RuleTranslation.objects.create(rule=child, language='ko', title='하위 규칙')
        RuleTranslation.objects.create(rule=grandchild, language='ko', title='손자 규칙')

        overview = self.client.get(reverse('rules:manage'))
        book_page = self.client.get(reverse('rules:manageBook', args=[self.book.pk]))
        root_page = self.client.get(reverse('rules:manageRule', args=[root.pk]))
        child_page = self.client.get(reverse('rules:manageRule', args=[child.pk]))

        self.assertContains(overview, str(self.book))
        self.assertNotContains(overview, '[[root-rule]]')
        self.assertContains(book_page, '[[root-rule]]')
        self.assertNotContains(book_page, '[[child-rule]]')
        self.assertContains(root_page, '[[child-rule]]')
        self.assertNotContains(root_page, '[[grandchild-rule]]')
        self.assertContains(child_page, '[[grandchild-rule]]')
        self.assertContains(child_page, '1.1.1')

    def test_move_rule_reorders_only_its_siblings_and_renumbers_them(self):
        root = Rule.objects.create(rulebook=self.book, reference_name='root-rule')
        first = Rule.objects.create(
            rulebook=self.book,
            parent=root,
            reference_name='first-rule',
            priority=10,
        )
        second = Rule.objects.create(
            rulebook=self.book,
            parent=root,
            reference_name='second-rule',
            priority=20,
        )
        third = Rule.objects.create(
            rulebook=self.book,
            parent=root,
            reference_name='third-rule',
            priority=30,
        )

        response = self.client.post(reverse('rules:ruleMove', args=[third.pk, 'up']))

        self.assertRedirects(
            response,
            f'{reverse("rules:manageRule", args=[root.pk])}#rule-{third.pk}',
            fetch_redirect_response=False,
        )
        siblings = list(root.children.order_by('priority', 'id'))
        self.assertEqual([rule.pk for rule in siblings], [first.pk, third.pk, second.pk])
        self.assertEqual([rule.priority for rule in siblings], [10, 20, 30])
        third.refresh_from_db()
        self.assertEqual(third.full_number, '1.2')

    def test_visual_guide_editor_saves_wysiwyg_css_and_javascript(self):
        rule = Rule.objects.create(rulebook=self.book, reference_name='visual-rule')
        RuleTranslation.objects.create(rule=rule, language='ko', title='비주얼 규칙')

        response = self.client.post(reverse('rules:visualCreate', args=[rule.pk]), {
            'priority': 10,
            'style_key': 'custom-board',
            'is_public': 'on',
            'css': '.visual-test { color: red; }',
            'javascript': 'window.visualEditorTest = true;',
            'visual-ko-title': '보드 가이드',
            'visual-ko-content': '<div class="visual-test"><strong>보드</strong></div>',
            'visual-en-title': '',
            'visual-en-content': '',
            'visual-ja-title': '',
            'visual-ja-content': '',
        })

        guide = RuleVisualGuide.objects.get(rule=rule)
        self.assertRedirects(
            response,
            f'{reverse("rules:manageRule", args=[rule.pk])}#visual-{guide.pk}',
            fetch_redirect_response=False,
        )
        self.assertEqual(guide.css, '.visual-test { color: red; }')
        self.assertEqual(guide.javascript, 'window.visualEditorTest = true;')
        self.assertEqual(guide.rulebook, self.book)
        self.assertEqual(guide.style_key, 'custom-board')
        translation = guide.translations.get(language='ko')
        self.assertIn('<strong>보드</strong>', translation.content)

        manage_page = self.client.get(reverse('rules:manageRule', args=[rule.pk]))
        self.assertContains(manage_page, '보드 가이드')
        self.assertContains(manage_page, reverse('rules:visualEdit', args=[guide.pk]))

    def test_rulebook_visual_guide_editor_saves_page_level_guide(self):
        response = self.client.post(reverse('rules:bookVisualCreate', args=[self.book.pk]), {
            'priority': 10,
            'style_key': 'field',
            'is_public': 'on',
            'css': '',
            'javascript': 'window.pageVisual = true;',
            'visual-ko-title': '상단 가이드',
            'visual-ko-content': '<div class="page-visual">가이드</div>',
            'visual-en-title': '',
            'visual-en-content': '',
            'visual-ja-title': '',
            'visual-ja-content': '',
        })

        guide = RuleVisualGuide.objects.get(rulebook=self.book, rule__isnull=True)
        self.assertRedirects(
            response,
            f'{reverse("rules:manageBook", args=[self.book.pk])}#visual-{guide.pk}',
            fetch_redirect_response=False,
        )
        self.assertEqual(guide.style_key, 'field')
        self.assertEqual(guide.translations.get(language='ko').title, '상단 가이드')
        manage_page = self.client.get(reverse('rules:manageBook', args=[self.book.pk]))
        self.assertContains(manage_page, '상단 가이드')

    def test_rulebook_visual_assets_editor_updates_shared_css_and_javascript(self):
        response = self.client.post(
            reverse('rules:bookVisualAssets', args=[self.book.pk]),
            {
                'visual_css': '.shared-visual { color: red; }',
                'visual_javascript': 'window.sharedVisual = true;',
            },
        )

        self.assertRedirects(
            response,
            reverse('rules:manageBook', args=[self.book.pk]),
            fetch_redirect_response=False,
        )
        self.book.refresh_from_db()
        self.assertEqual(self.book.visual_css, '.shared-visual { color: red; }')
        self.assertEqual(self.book.visual_javascript, 'window.sharedVisual = true;')

        edit_page = self.client.get(reverse('rules:bookVisualAssets', args=[self.book.pk]))
        self.assertContains(edit_page, '.shared-visual { color: red; }')
