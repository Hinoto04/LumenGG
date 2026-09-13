from io import StringIO
from importlib import import_module

from django.apps import apps as django_apps
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
from common.rule_contracts import unresolved_rule_references
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

    def test_clause_rule_displays_number_without_repeating_generated_title(self):
        root = self.make_rule('root-rule', '객체')
        clause = self.make_rule(
            'clause-rule',
            '플레이어는 게임 객체다.',
            parent=root,
            content='<p>플레이어는 게임 객체다.</p>',
        )
        clause.show_in_toc = False
        clause.save(update_fields=['show_in_toc'])

        rendered = get_rulebook(self.book.slug, 'ko')
        html = str(rendered['html'])

        self.assertIn('class="v2-rule-clause-number"', html)
        self.assertIn('<span class="v2-rule-number">1.1</span>', html)
        self.assertEqual(html.count('플레이어는 게임 객체다.'), 2)
        self.assertIn('aria-label="플레이어는 게임 객체다."', html)
        self.assertNotIn('<h3><span class="v2-rule-number">1.1</span>', html)

    def test_rule_contract_displays_key_parent_scope_and_dependencies(self):
        root = self.make_rule('root-rule', '객체 규칙')
        target = self.make_rule('target-rule', '처리 단위', parent=root)
        source = self.make_rule('source-rule', '상태 확인', parent=root)
        source.reference_targets = [target.reference_name]
        source.save(update_fields=['reference_targets'])

        html = str(get_rulebook(self.book.slug, 'ko')['html'])

        self.assertEqual(html.count('class="v2-rule-contract"'), 3)
        self.assertIn('<code>source-rule</code>', html)
        self.assertIn('상위 규칙</b><a href="#root-rule">1 객체 규칙</a>', html)
        self.assertIn('data-rule-contract-target="target-rule"', html)
        self.assertIn(
            'data-rule-contract-target="target-rule"><code>target-rule</code>'
            '<span>1.1 처리 단위</span></a>',
            html,
        )

    def test_unresolved_rule_reference_is_reported_with_source_key(self):
        source = self.make_rule('source-rule', '잘못된 참조')
        source.reference_targets = ['rule-does-not-exist']
        source.save(update_fields=['reference_targets'])

        self.assertEqual(
            unresolved_rule_references(self.book),
            [{
                'source': 'source-rule',
                'target': 'rule-does-not-exist',
                'title': '잘못된 참조',
            }],
        )

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

    def test_imported_comprehensive_rules_include_detailed_game_areas(self):
        call_command('import_rulebooks', '--slug', 'comprehensive', stdout=StringIO())

        book = Rulebook.objects.get(slug='comprehensive')
        rules = list(book.rules.prefetch_related('translations'))

        def with_alias(alias):
            return next(
                rule
                for rule in rules
                if alias == rule.reference_name or alias in (rule.reference_aliases or [])
            )

        list_rule = with_alias('rule-2-1-1')
        zone_children = list(
            book.rules.filter(parent_id=list_rule.parent_id).order_by('priority', 'pk')
        )
        self.assertEqual(len(zone_children), 11)
        self.assertEqual(zone_children[0].pk, with_alias('rule-game-area-common-rules').pk)
        self.assertEqual(zone_children[3].pk, with_alias('rule-1-2-1').pk)
        self.assertEqual(zone_children[4].pk, list_rule.pk)

        list_content = list_rule.translations.get(language='ko').content
        break_rule = with_alias('rule-10-2-1')
        self.assertIn('리스트의 최대 매수는 14장', list_content)
        self.assertIn(f'[[{break_rule.reference_name}|브레이크]]', list_content)
        self.assertEqual(list_rule.translations.count(), 3)
        self.assertEqual(book.version, '0.6-web')

    def test_imported_comprehensive_rules_define_only_players_and_cards_as_objects(self):
        call_command('import_rulebooks', '--slug', 'comprehensive', stdout=StringIO())

        book = Rulebook.objects.get(slug='comprehensive')
        rules = list(book.rules.prefetch_related('translations'))

        def with_alias(alias):
            return next(
                rule
                for rule in rules
                if alias == rule.reference_name or alias in (rule.reference_aliases or [])
            )

        object_root = with_alias('chapter-1')
        object_sections = list(
            book.rules
            .filter(parent=object_root)
            .prefetch_related('translations')
            .order_by('priority', 'pk')
        )
        self.assertEqual(
            [section.translations.get(language='ko').title for section in object_sections],
            ['플레이어', '카드'],
        )

        player_info = with_alias('rule-3-2-2')
        card_info = with_alias('rule-card-common-information')
        self.assertEqual(player_info.parent_id, object_sections[0].pk)
        self.assertEqual(card_info.parent_id, object_sections[1].pk)
        self.assertIn(
            '<td>현재 체력</td>',
            player_info.translations.get(language='ko').content,
        )
        self.assertIn(
            '<td>소유자</td>',
            card_info.translations.get(language='ko').content,
        )

        deck_clause = with_alias('rule-3-1-1')
        deck_construction_clause = with_alias('rule-3-5-1')
        self.assertEqual(deck_clause.parent_id, deck_construction_clause.parent_id)
        self.assertNotEqual(deck_clause.parent_id, object_root.pk)

    def test_imported_comprehensive_rules_have_strict_reference_contracts(self):
        call_command('import_rulebooks', '--slug', 'comprehensive', stdout=StringIO())

        book = Rulebook.objects.get(slug='comprehensive')
        contract = Rule.objects.get(reference_name='rule-rule-contracts')
        contract_children = list(contract.children.order_by('priority', 'pk'))

        self.assertEqual(book.version, '0.6-web')
        self.assertEqual(len(contract_children), 5)
        self.assertEqual(
            [rule.reference_name for rule in contract_children],
            [
                'rule-contract-unit',
                'rule-reference-key',
                'rule-scope-inheritance',
                'rule-dependency-resolution',
                'rule-normative-clause-contract',
            ],
        )
        self.assertGreaterEqual(
            sum(len(rule.reference_targets) for rule in book.rules.all()),
            400,
        )
        self.assertEqual(unresolved_rule_references(book), [])

        rendered = get_rulebook('comprehensive', 'ko')
        public_rule_count = book.rules.filter(is_public=True).count()
        self.assertEqual(
            str(rendered['html']).count('class="v2-rule-contract"'),
            public_rule_count,
        )
        battle_sequence = next(
            rule
            for rule in book.rules.all()
            if 'rule-7-1-2' in (rule.reference_aliases or [])
        )
        self.assertGreaterEqual(len(battle_sequence.reference_targets), 7)

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


class ComprehensiveRulebookLayoutMigrationTests(TestCase):
    def setUp(self):
        self.book = Rulebook.objects.get(slug='comprehensive')
        self.book.rules.all().delete()
        self.roots = {}
        for index in range(13):
            root = self._rule(
                f'legacy-root-{index}',
                alias=f'chapter-{index}',
                priority=(index + 1) * 10,
                title=f'기존 {index}장',
                content=(
                    '<p>Combo intro</p>' if index == 8
                    else '<p>Catch intro</p>' if index == 9
                    else ''
                ),
            )
            self.roots[index] = root

        section_roots = {
            '0.1': 0, '0.2': 0, '0.3': 0,
            '1.1': 1, '1.2': 1, '1.3': 1,
            '2.1': 2, '2.2': 2,
            '3.1': 3, '3.2': 3, '3.3': 3, '3.4': 3, '3.5': 3,
            '4.1': 4,
            '10.1': 10, '10.2': 10, '10.3': 10,
            '11.1': 11, '11.2': 11,
            '12.1': 12, '12.2': 12,
        }
        self.sections = {}
        sibling_counts = {}
        for number, root_index in section_roots.items():
            sibling_counts[root_index] = sibling_counts.get(root_index, 0) + 1
            heading = self._rule(
                f'legacy-section-{number.replace(".", "-")}',
                parent=self.roots[root_index],
                priority=sibling_counts[root_index] * 10,
                title=f'기존 {number}',
            )
            self.sections[number] = heading
            self._rule(
                f'legacy-clause-{number.replace(".", "-")}',
                alias=f'rule-{number.replace(".", "-")}-1',
                parent=heading,
                priority=10,
                title=f'{number} 조항',
                show_in_toc=False,
            )

        for index in range(2, 10):
            self._rule(
                f'legacy-zone-clause-{index}',
                alias=f'rule-2-1-{index}',
                parent=self.sections['2.1'],
                priority=index * 10,
                title=f'기존 영역 {index}',
                show_in_toc=False,
            )

        for section_number, last_clause in {
            '3.2': 4,
            '3.3': 2,
            '3.4': 2,
            '11.1': 2,
            '11.2': 5,
        }.items():
            for index in range(2, last_clause + 1):
                self._rule(
                    f'legacy-clause-{section_number.replace(".", "-")}-{index}',
                    alias=f'rule-{section_number.replace(".", "-")}-{index}',
                    parent=self.sections[section_number],
                    priority=index * 10,
                    title=f'{section_number}.{index} 조항',
                    show_in_toc=False,
                )

        self.combo_table = self._rule(
            'legacy-combo-table',
            parent=self.roots[8],
            priority=5,
            title='콤보 보정표',
        )
        self.catch_table = self._rule(
            'legacy-catch-table',
            parent=self.roots[9],
            priority=5,
            title='캐치 종류',
        )
        self.visual = RuleVisualGuide.objects.create(
            rulebook=self.book,
            rule=self.roots[11],
            style_key='legacy-special',
            priority=10,
        )
        self.page_visual = RuleVisualGuide.objects.create(
            rulebook=self.book,
            rule=None,
            style_key='rules',
            priority=10,
        )
        RuleVisualGuideTranslation.objects.create(
            guide=self.page_visual,
            language='ko',
            title='판정 지도',
            content='<p>기존 판정 지도</p>',
        )

    def _rule(
        self,
        reference_name,
        *,
        alias='',
        parent=None,
        priority=10,
        title='',
        content='',
        show_in_toc=True,
    ):
        rule = Rule.objects.create(
            rulebook=self.book,
            parent=parent,
            reference_name=reference_name,
            reference_aliases=[alias] if alias else [],
            priority=priority,
            show_in_toc=show_in_toc,
        )
        RuleTranslation.objects.create(
            rule=rule,
            language='ko',
            title=title or reference_name,
            content=content,
        )
        return rule

    @staticmethod
    def _translation_title(rule, language='ko'):
        return rule.translations.get(language=language).title

    def _rule_with_alias(self, alias):
        return next(
            rule
            for rule in Rule.objects.filter(rulebook=self.book)
            if alias == rule.reference_name or alias in (rule.reference_aliases or [])
        )

    def test_migration_reorders_existing_rules_without_reimporting_clauses(self):
        migration = import_module('common.migrations.0017_reorder_comprehensive_rulebook')
        migration.reorder_comprehensive_rules(django_apps, None)

        self.book.refresh_from_db()
        self.assertEqual(self.book.version, '0.3-web')
        self.assertEqual(str(self.book.updated_on), '2026-09-01')

        expected_root_titles = [
            '규칙서를 읽기 전 알아야 할 내용',
            '게임 내 객체의 정의',
            '게임 내 영역의 정의',
            '게임 준비',
            '게임 진행',
            '게임 종료',
            '카드의 효과와 우선권',
            '배틀',
            '콤보와 캐치',
            '규칙에 의한 효과',
        ]
        chapter_roots = [self._rule_with_alias(f'chapter-{index}') for index in range(10)]
        self.assertEqual(
            [self._translation_title(rule) for rule in chapter_roots],
            expected_root_titles,
        )
        self.assertEqual(
            [rule.pk for rule in Rule.objects.filter(rulebook=self.book, parent=None).order_by('priority', 'pk')],
            [rule.pk for rule in chapter_roots],
        )

        object_children = list(
            chapter_roots[1].children.prefetch_related('translations').order_by('priority', 'pk')
        )
        self.assertEqual(
            [self._translation_title(rule) for rule in object_children],
            [
                '플레이어와 캐릭터 카드', '덱', '특성 카드',
                '공격·수비 기술', '특수 기술', '얼티밋 기술',
            ],
        )

        combo_children = list(
            chapter_roots[8].children.prefetch_related('translations').order_by('priority', 'pk')
        )
        self.assertEqual(
            [self._translation_title(rule) for rule in combo_children],
            ['콤보', '콤보 보정표', '캐치', '캐치 종류'],
        )
        self.assertEqual(
            combo_children[0].translations.get(language='ko').content,
            '<p>Combo intro</p>',
        )
        self.assertEqual(
            chapter_roots[8].translations.get(language='ko').content,
            '',
        )

        public_section = self.sections['2.2']
        public_section.refresh_from_db()
        public_clauses = list(public_section.children.order_by('priority', 'pk'))
        self.assertEqual(
            [rule.reference_name for rule in public_clauses],
            ['legacy-clause-1-2', 'legacy-clause-2-2'],
        )

        self.assertFalse(Rule.objects.filter(pk=self.roots[11].pk).exists())
        object_root = chapter_roots[1]
        object_root.refresh_from_db()
        self.assertIn('legacy-root-11', object_root.reference_aliases)
        self.visual.refresh_from_db()
        self.assertEqual(self.visual.rule_id, object_root.pk)

        judgment_map = self.page_visual.translations.get(language='ko')
        self.assertEqual(judgment_map.content.count('data-rulebook-hotspot'), 9)
        self.assertIn('게임 내 객체의 정의', judgment_map.content)
        self.assertIn('#rule-rule-based-effects', judgment_map.content)
        self.assertTrue(
            self.page_visual.translations.filter(language='en', title='Judgment Map').exists()
        )
        self.assertTrue(
            self.page_visual.translations.filter(language='ja', title='判定マップ').exists()
        )

        # A numbered-rule alias and its database row survive the structural migration.
        clause = self._rule_with_alias('rule-3-2-1')
        self.assertEqual(clause.reference_name, 'legacy-clause-3-2')
        self.assertEqual(self._translation_title(clause), '3.2 조항')

        migrated_state = list(
            Rule.objects.filter(rulebook=self.book)
            .order_by('pk')
            .values_list('pk', 'parent_id', 'priority', 'reference_aliases')
        )
        migration.reorder_comprehensive_rules(django_apps, None)
        self.assertEqual(
            list(
                Rule.objects.filter(rulebook=self.book)
                .order_by('pk')
                .values_list('pk', 'parent_id', 'priority', 'reference_aliases')
            ),
            migrated_state,
        )

    def test_zone_definition_migration_expands_and_reorders_existing_clauses(self):
        layout_migration = import_module(
            'common.migrations.0017_reorder_comprehensive_rulebook'
        )
        zone_migration = import_module(
            'common.migrations.0018_expand_game_area_definitions'
        )
        layout_migration.reorder_comprehensive_rules(django_apps, None)
        appendix_c = self._rule(
            'legacy-appendix-c',
            alias='appendix-c',
            priority=140,
            title='기존 편집 목록',
            content='<p>기존 공개 정보 확인 항목</p>',
        )
        appendix_t = self._rule(
            'legacy-appendix-t',
            alias='appendix-t',
            priority=150,
            title='기존 대회 규정',
        )
        revision = self._rule(
            'legacy-revision-history',
            priority=160,
            title='기존 개정 이력',
            content='<p>기존 이력</p>',
        )
        zone_migration.expand_game_area_definitions(django_apps, None)

        self.book.refresh_from_db()
        self.assertEqual(self.book.version, '0.4-web')
        self.assertEqual(str(self.book.updated_on), '2026-09-01')

        expected_aliases = [
            'rule-game-area-common-rules',
            'rule-2-1-4',
            'rule-2-1-5',
            'rule-1-2-1',
            'rule-2-1-1',
            'rule-2-1-2',
            'rule-2-1-6',
            'rule-2-1-7',
            'rule-2-1-9',
            'rule-2-1-3',
            'rule-2-1-8',
        ]
        expected_rules = [self._rule_with_alias(alias) for alias in expected_aliases]
        zone_children = list(self.sections['2.1'].children.order_by('priority', 'pk'))
        self.assertEqual(
            [rule.pk for rule in zone_children],
            [rule.pk for rule in expected_rules],
        )
        self.assertEqual(
            [self._translation_title(rule) for rule in zone_children],
            [
                '영역과 플레이어의 연결', '캐릭터 존', '특성 존', '패',
                '리스트', '사이드 덱', '배틀 존', '루멘 존',
                '얼티밋 존', '브레이크 존', 'FP 영역',
            ],
        )

        hand = self._rule_with_alias('rule-1-2-1')
        self.assertEqual(hand.parent_id, self.sections['2.1'].pk)
        self.assertIn(
            '[[rule-3-2-2|패 매수 상한]]',
            hand.translations.get(language='ko').content,
        )
        list_rule = self._rule_with_alias('rule-2-1-1')
        self.assertIn(
            '리스트의 최대 매수는 14장',
            list_rule.translations.get(language='ko').content,
        )
        self.assertIn(
            '[[rule-10-2-1|브레이크]]',
            list_rule.translations.get(language='ko').content,
        )
        self.assertEqual(list_rule.translations.count(), 3)

        public_children = list(self.sections['2.2'].children.order_by('priority', 'pk'))
        self.assertEqual(
            [rule.pk for rule in public_children],
            [self._rule_with_alias('rule-2-2-1').pk],
        )
        area_root = self._rule_with_alias('chapter-2')
        area_content = area_root.translations.get(language='ko').content
        self.assertIn('<th>용도·허용 카드</th>', area_content)
        self.assertIn('<td>FP 영역</td>', area_content)
        self.assertIn(
            '루멘 존 기본 공개 상태',
            appendix_c.translations.get(language='ko').content,
        )
        self.assertEqual(appendix_t.translations.get(language='ko').title, '기존 대회 규정')
        self.assertIn(
            'v0.4-web',
            revision.translations.get(language='ko').content,
        )

        migrated_state = list(
            Rule.objects.filter(rulebook=self.book)
            .order_by('pk')
            .values_list('pk', 'parent_id', 'priority', 'reference_aliases')
        )
        zone_migration.expand_game_area_definitions(django_apps, None)
        self.assertEqual(
            list(
                Rule.objects.filter(rulebook=self.book)
                .order_by('pk')
                .values_list('pk', 'parent_id', 'priority', 'reference_aliases')
            ),
            migrated_state,
        )
        self.assertEqual(
            sum(
                1
                for rule in Rule.objects.filter(rulebook=self.book)
                if rule.reference_name == 'rule-game-area-common-rules'
                or 'rule-game-area-common-rules' in (rule.reference_aliases or [])
            ),
            1,
        )

    def test_object_migration_restructures_player_and_card_sections(self):
        layout_migration = import_module(
            'common.migrations.0017_reorder_comprehensive_rulebook'
        )
        zone_migration = import_module(
            'common.migrations.0018_expand_game_area_definitions'
        )
        object_migration = import_module(
            'common.migrations.0019_restructure_game_objects'
        )
        layout_migration.reorder_comprehensive_rules(django_apps, None)
        appendix_t = self._rule(
            'legacy-appendix-t-for-objects',
            alias='appendix-t',
            priority=150,
            title='기존 대회 규정',
        )
        revision = self._rule(
            'legacy-revision-history-for-objects',
            priority=160,
            title='기존 개정 이력',
            content='<p>기존 이력</p>',
        )
        zone_migration.expand_game_area_definitions(django_apps, None)

        original_clause_ids = {
            alias: self._rule_with_alias(alias).pk
            for alias in [
                'rule-3-2-1', 'rule-3-2-2', 'rule-3-2-3', 'rule-3-2-4',
                'rule-3-3-1', 'rule-3-3-2', 'rule-3-4-1', 'rule-3-4-2',
                'rule-11-1-1', 'rule-11-1-2',
                'rule-11-2-1', 'rule-11-2-2', 'rule-11-2-3',
                'rule-11-2-4', 'rule-11-2-5', 'rule-3-1-1',
            ]
        }
        removed_section_ids = {
            self.sections[number].pk for number in ('3.3', '3.4', '11.1', '11.2')
        }

        object_migration.restructure_game_objects(django_apps, None)

        self.book.refresh_from_db()
        self.assertEqual(self.book.version, '0.5-web')
        self.assertEqual(str(self.book.updated_on), '2026-09-01')

        object_root = self._rule_with_alias('chapter-1')
        object_sections = list(
            object_root.children.prefetch_related('translations').order_by('priority', 'pk')
        )
        self.assertEqual(
            [self._translation_title(section) for section in object_sections],
            ['플레이어', '카드'],
        )
        player_section, card_section = object_sections
        self.assertEqual(
            [
                next(
                    alias
                    for alias in ('rule-3-2-1', 'rule-3-2-2', 'rule-3-2-3', 'rule-3-2-4')
                    if alias == rule.reference_name or alias in (rule.reference_aliases or [])
                )
                for rule in player_section.children.order_by('priority', 'pk')
            ],
            ['rule-3-2-1', 'rule-3-2-2', 'rule-3-2-3', 'rule-3-2-4'],
        )
        expected_card_aliases = [
            'rule-game-object-card',
            'rule-card-common-information',
            'rule-card-character-information',
            'rule-3-3-1', 'rule-3-3-2', 'rule-3-4-1', 'rule-3-4-2',
            'rule-11-1-1', 'rule-11-1-2',
            'rule-11-2-1', 'rule-11-2-2', 'rule-11-2-3',
            'rule-11-2-4', 'rule-11-2-5',
        ]
        self.assertEqual(
            [
                next(
                    alias
                    for alias in expected_card_aliases
                    if alias == rule.reference_name or alias in (rule.reference_aliases or [])
                )
                for rule in card_section.children.order_by('priority', 'pk')
            ],
            expected_card_aliases,
        )

        for alias, rule_id in original_clause_ids.items():
            self.assertEqual(self._rule_with_alias(alias).pk, rule_id)
        self.assertFalse(Rule.objects.filter(pk__in=removed_section_ids).exists())

        deck_clause = self._rule_with_alias('rule-3-1-1')
        setup_clause = self._rule_with_alias('rule-3-5-1')
        self.assertEqual(deck_clause.parent_id, setup_clause.parent_id)
        self.assertEqual(
            list(
                Rule.objects
                .filter(parent_id=setup_clause.parent_id)
                .order_by('priority', 'pk')
                .values_list('pk', flat=True)
            )[0],
            deck_clause.pk,
        )
        self.assertIn(
            '<td>현재 체력</td>',
            self._rule_with_alias('rule-3-2-2').translations.get(language='ko').content,
        )
        self.assertIn(
            '<td>소유자</td>',
            self._rule_with_alias('rule-card-common-information')
            .translations.get(language='ko').content,
        )
        self.assertEqual(
            self._rule_with_alias('rule-card-common-information').translations.count(),
            3,
        )
        revision.refresh_from_db()
        self.assertIn('v0.5-web', revision.translations.get(language='ko').content)
        self.assertTrue(Rule.objects.filter(pk=appendix_t.pk).exists())
        judgment_map = self.page_visual.translations.get(language='ko').content
        self.assertIn(
            '대상으로 지정할 수 있는 게임 객체인 플레이어와 카드',
            judgment_map,
        )
        self.assertIn('플레이어 · 카드', judgment_map)
        self.assertNotIn('플레이어 · 카드 · 덱', judgment_map)

        migrated_state = list(
            Rule.objects.filter(rulebook=self.book)
            .order_by('pk')
            .values_list('pk', 'parent_id', 'priority', 'reference_aliases')
        )
        object_migration.restructure_game_objects(django_apps, None)
        self.assertEqual(
            list(
                Rule.objects.filter(rulebook=self.book)
                .order_by('pk')
                .values_list('pk', 'parent_id', 'priority', 'reference_aliases')
            ),
            migrated_state,
        )
        self.assertEqual(
            sum(
                1
                for rule in Rule.objects.filter(rulebook=self.book)
                if rule.reference_name == 'rule-card-common-information'
                or 'rule-card-common-information' in (rule.reference_aliases or [])
            ),
            1,
        )

    def test_object_migration_backfills_missing_player_and_deck_rules(self):
        layout_migration = import_module(
            'common.migrations.0017_reorder_comprehensive_rulebook'
        )
        zone_migration = import_module(
            'common.migrations.0018_expand_game_area_definitions'
        )
        object_migration = import_module(
            'common.migrations.0019_restructure_game_objects'
        )
        layout_migration.reorder_comprehensive_rules(django_apps, None)
        zone_migration.expand_game_area_definitions(django_apps, None)

        deck_section_id = self.sections['3.1'].pk
        deck_section = Rule.objects.get(pk=deck_section_id)
        deck_section.reference_aliases = [
            *deck_section.reference_aliases,
            'rule-meaning-of-deck',
        ]
        deck_section.save(update_fields=['reference_aliases'])
        self.sections['3.2'].delete()
        self._rule_with_alias('rule-3-1-1').delete()

        object_migration.restructure_game_objects(django_apps, None)

        object_root = self._rule_with_alias('chapter-1')
        object_sections = list(
            object_root.children.prefetch_related('translations').order_by('priority', 'pk')
        )
        self.assertEqual(
            [self._translation_title(section) for section in object_sections],
            ['플레이어', '카드'],
        )
        self.assertEqual(object_sections[1].pk, deck_section_id)
        for alias in [
            'rule-3-2-1', 'rule-3-2-2', 'rule-3-2-3', 'rule-3-2-4',
            'rule-3-1-1',
        ]:
            self.assertIsNotNone(self._rule_with_alias(alias))
        self.assertEqual(
            self._rule_with_alias('rule-3-1-1').parent_id,
            self._rule_with_alias('rule-3-5-1').parent_id,
        )

        migrated_state = list(
            Rule.objects.filter(rulebook=self.book)
            .order_by('pk')
            .values_list('pk', 'parent_id', 'priority', 'reference_aliases')
        )
        object_migration.restructure_game_objects(django_apps, None)
        self.assertEqual(
            list(
                Rule.objects.filter(rulebook=self.book)
                .order_by('pk')
                .values_list('pk', 'parent_id', 'priority', 'reference_aliases')
            ),
            migrated_state,
        )

    def test_rule_contract_migration_adds_keys_and_resolved_dependencies(self):
        contract_migration = import_module(
            'common.migrations.0020_rule_contract_references'
        )
        self.book.rules.all().delete()
        call_command('import_rulebooks', '--slug', 'comprehensive', stdout=StringIO())
        self.book.refresh_from_db()
        tournament = Rulebook.objects.get(slug='tournament')
        external_target = Rule.objects.create(
            rulebook=tournament,
            reference_name='floor-test-external-contract-target',
            reference_aliases=[],
            reference_targets=[],
            priority=9990,
            show_in_toc=False,
        )
        history = self._rule_with_alias('rule-history')
        history_translation = history.translations.get(language='ko')
        history_translation.content += (
            '<p>[[floor-test-external-contract-target|외부 참조 테스트]]</p>'
        )
        history_translation.save(update_fields=['content'])
        contract = self._rule_with_alias('rule-rule-contracts')
        contract.delete()
        Rule.objects.filter(rulebook=self.book).update(reference_targets=[])
        self.book.version = '0.5-web'
        self.book.save(update_fields=['version'])

        contract_migration.add_rule_contract_references(django_apps, None)

        self.book.refresh_from_db()
        contract = self._rule_with_alias('rule-rule-contracts')
        contract_children = list(contract.children.order_by('priority', 'pk'))
        all_reference_names = set(
            Rule.objects.values_list('reference_name', flat=True)
        )

        self.assertEqual(self.book.version, '0.6-web')
        self.assertEqual(len(contract_children), 5)
        self.assertEqual(contract.translations.count(), 3)
        history.refresh_from_db()
        self.assertIn(external_target.reference_name, history.reference_targets)
        self.assertGreater(
            len(self._rule_with_alias('rule-3-2-2').reference_targets),
            0,
        )
        for rule in Rule.objects.filter(rulebook=self.book):
            self.assertTrue(set(rule.reference_targets).issubset(all_reference_names))

        migrated_state = list(
            Rule.objects.filter(rulebook=self.book)
            .order_by('pk')
            .values_list(
                'pk', 'parent_id', 'priority', 'reference_aliases', 'reference_targets'
            )
        )
        contract_migration.add_rule_contract_references(django_apps, None)
        self.assertEqual(
            list(
                Rule.objects.filter(rulebook=self.book)
                .order_by('pk')
                .values_list(
                    'pk', 'parent_id', 'priority', 'reference_aliases', 'reference_targets'
                )
            ),
            migrated_state,
        )


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
