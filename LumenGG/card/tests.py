import json
from datetime import date

from django.contrib.auth.models import Permission, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Card, CardTranslation, Character
from .search import card_matches_search, card_matches_search_exact
from common.language import LANGUAGE_SESSION_KEY
from collection.models import CollectionCard, Pack
from qna.models import QNA, QNARelation


class EffectSandboxPhaseSuggestionTests(SimpleTestCase):
    def test_nested_phase_is_condition_suggests_lumen(self):
        from .views.views import _effect_sandbox_suggested_phase

        ability = {
            'condition': {
                'op': 'all',
                'conditions': [
                    {'op': 'phase_is', 'phase': 'lumen'},
                    {'op': 'zone_count', 'zone': 'hand', 'max': 4},
                ],
            },
        }

        self.assertEqual(_effect_sandbox_suggested_phase(ability), 'lumen')

    def test_ambiguous_phase_branches_do_not_change_form_phase(self):
        from .views.views import _effect_sandbox_suggested_phase

        ability = {
            'condition': {
                'op': 'any',
                'conditions': [
                    {'op': 'phase_is', 'phase': 'lumen'},
                    {'op': 'phase_is', 'phase': 'recovery'},
                ],
            },
        }

        self.assertEqual(_effect_sandbox_suggested_phase(ability), '')

    def test_source_from_zone_condition_suggests_list(self):
        from .views.views import _effect_sandbox_suggested_source_zone

        ability = {
            'condition': {
                'op': 'equals',
                'left': 'context.source_from_zone',
                'right': 'list',
            },
        }

        self.assertEqual(
            _effect_sandbox_suggested_source_zone(ability), 'list',
        )

    def test_structured_equals_operands_do_not_break_zone_inference(self):
        from .views.views import _effect_sandbox_suggested_source_zone

        ability = {
            'condition': {
                'op': 'equals',
                'left': {'path': 'context.event_controller'},
                'right': {'controller': True},
            },
        }

        self.assertEqual(_effect_sandbox_suggested_source_zone(ability), '')


class CardUpdateLocalizationTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(
            name='니아',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        self.card = Card.objects.create(
            name='원본 카드',
            ruby='원본 루비',
            type='공격',
            frame=5,
            damage=300,
            pos='상단',
            body='손',
            special='',
            code='TST-001',
            hit='2',
            guard='-2',
            counter='콤보',
            g_top='방어',
            g_mid='',
            g_bot='',
            character=self.character,
            text='원본 효과',
            detail_text='원본 보충 설명',
            keyword='원본 태그',
            hiddenKeyword='원본 숨김',
            search='원본 검색',
        )
        self.user = User.objects.create_user('card-admin', password='password')
        self.user.user_permissions.add(Permission.objects.get(
            codename='change_card',
            content_type__app_label='card',
        ))
        self.user.user_permissions.add(Permission.objects.get(
            codename='tag_update',
            content_type__app_label='card',
        ))
        self.client.force_login(self.user)

    def test_update_page_uses_current_language_translation(self):
        session = self.client.session
        session[LANGUAGE_SESSION_KEY] = 'en'
        session.save()

        response = self.client.get(reverse('card:update', args=[self.card.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_translation_update'])
        self.assertEqual(response.context['form'].fields['name'].widget.attrs['placeholder'], '원본 카드')

    def test_update_writes_translation_without_changing_source_card(self):
        session = self.client.session
        session[LANGUAGE_SESSION_KEY] = 'en'
        session.save()

        response = self.client.post(reverse('card:update', args=[self.card.id]), {
            'name': 'Translated Card',
            'ruby': 'Translated Ruby',
            'text': 'Translated effect',
            'detail_text': 'Translated note',
            'keyword': 'translated tag',
            'hiddenKeyword': 'translated hidden',
            'search': 'translated search',
        })

        self.assertEqual(response.status_code, 302)
        self.card.refresh_from_db()
        self.assertEqual(self.card.name, '원본 카드')
        self.assertEqual(self.card.text, '원본 효과')

        translation = CardTranslation.objects.get(card=self.card, language='en')
        self.assertEqual(translation.name, 'Translated Card')
        self.assertEqual(translation.text, 'Translated effect')
        self.assertEqual(translation.keyword, 'translated tag')

    def test_detail_tag_form_uses_current_language_translation(self):
        CardTranslation.objects.create(
            card=self.card,
            language='en',
            name='Translated Card',
            keyword='translated tag',
            hiddenKeyword='translated hidden',
            search='translated search',
        )
        session = self.client.session
        session[LANGUAGE_SESSION_KEY] = 'en'
        session.save()

        response = self.client.get(reverse('card:detail', args=[self.card.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['tag_edit']['values']['keyword'], 'translated tag')
        self.assertEqual(response.context['tag_edit']['values']['hidden'], 'translated hidden')
        self.assertEqual(response.context['tag_edit']['values']['search'], 'translated search')
        self.assertEqual(response.context['tag_edit']['placeholders']['keyword'], '원본 태그')

    def test_tag_update_writes_current_language_translation(self):
        session = self.client.session
        session[LANGUAGE_SESSION_KEY] = 'en'
        session.save()

        response = self.client.post(reverse('card:editCardTag', args=[self.card.id]), {
            'keyword': 'english tag/',
            'hidden': 'english hidden',
            'search': 'english search/',
        })

        self.assertEqual(response.status_code, 302)
        self.card.refresh_from_db()
        self.assertEqual(self.card.keyword, '원본 태그')
        self.assertEqual(self.card.hiddenKeyword, '원본 숨김')
        self.assertEqual(self.card.search, '원본 검색')

        translation = CardTranslation.objects.get(card=self.card, language='en')
        self.assertEqual(translation.keyword, 'english tag/')
        self.assertEqual(translation.hiddenKeyword, 'english hidden')
        self.assertEqual(translation.search, 'english search/')


class CardPrintingDetailTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(
            name='니아', description='', group='루멘콘덴서', datas={},
            img='https://example.com/nia.webp',
        )
        self.card = Card.objects.create(
            name='판본 테스트', code='TST-001', character=self.character,
            img='https://example.com/printing-n.webp',
        )
        starter = Pack.objects.create(name='테스트 스타터', code='TST', released=date(2025, 1, 1))
        promo = Pack.objects.create(name='프로모 팩', code='PRM', released=date(2025, 2, 1))
        CollectionCard.objects.create(
            card=self.card, pack=starter, code='TST-001', rare='N',
            image='https://example.com/printing-n.webp',
        )
        CollectionCard.objects.create(
            card=self.card, pack=starter, code='TST-001', rare='SR',
            image='https://example.com/printing-sr.webp',
        )
        CollectionCard.objects.create(
            card=self.card, pack=promo, code='PRM-001', rare='SP',
            image='https://example.com/printing-sp.webp',
        )

    def test_detail_exposes_printing_modal_and_clickable_release_rows(self):
        response = self.client.get(reverse('card:detail', args=[self.card.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['card_editions']), 3)
        self.assertEqual(len(response.context['release_groups']), 2)
        self.assertEqual(
            response.context['release_groups'][0]['image'],
            'https://example.com/printing-n.webp',
        )
        self.assertContains(response, 'data-card-edition-open')
        self.assertContains(response, 'data-card-edition-option', count=3)
        self.assertContains(response, 'data-card-release-option', count=2)
        self.assertContains(response, 'data-code="TST-001"')
        self.assertContains(response, '테스트 스타터')
        self.assertContains(response, '프로모 팩')
        self.assertContains(response, 'v2/card-detail.js')


class CardEffectReviewTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(
            name='CMYK', localization_key='cmyk-test',
            description='', group='루멘콘덴서', datas={},
            img='https://example.com/cmyk.webp',
        )
        self.card = Card.objects.create(
            name='검수 카드', code='REV-AT-001', character=self.character,
            type='공격', frame=5, damage=400, pos='상단',
            text='①사용 시, 1FP를 얻는다.', detail_text='테스트 보충 설명',
            img='https://example.com/review.webp',
            effect_definition={
                'schema_version': 1,
                'reviewed': False,
                'draft': True,
                'source_refs': {
                    'rulebook_pages': [48], 'qna_ids': [], 'card_text': True,
                },
                'abilities': [{
                    'id': 'rev-at-001-n1', 'label': '사용 시 1FP 획득',
                    'draft_text': '사용 시, 1FP를 얻는다.',
                    'kind': 'effect', 'mode': 'mandatory',
                    'trigger': {'event': 'use'}, 'timing': 'use',
                    'visibility': 'public', 'draft': True,
                    'draft_compiled': True,
                    'source_refs': {
                        'rulebook_pages': [48], 'qna_ids': [], 'card_text': True,
                    },
                    'effects': [{
                        'op': 'change_fp', 'player': {'controller': True},
                        'amount': 1,
                    }],
                }],
            },
        )
        self.qna = QNA.objects.create(
            title='검수 재정', question='언제 처리하나요?',
            answer='사용 시 처리합니다.',
        )
        QNARelation.objects.create(card=self.card, qna=self.qna)
        self.reviewer = User.objects.create_user('effect-reviewer', password='password')
        self.reviewer.user_permissions.add(Permission.objects.get(
            codename='change_card', content_type__app_label='card',
        ))

    def reviewed_definition(self):
        definition = dict(self.card.effect_definition)
        definition['reviewed'] = True
        definition['draft'] = False
        definition['source_refs'] = {
            **definition['source_refs'], 'qna_ids': [self.qna.pk],
        }
        definition['abilities'] = [dict(definition['abilities'][0])]
        definition['abilities'][0]['draft'] = False
        definition['abilities'][0]['source_refs'] = {
            **definition['abilities'][0]['source_refs'], 'qna_ids': [self.qna.pk],
        }
        return definition

    def sandbox_config(self, **overrides):
        config = {
            'event': 'use', 'controller': 'p1', 'phase': 'battle',
            'source_zone': 'battle', 'fixture_mode': 'choices',
            'players': {
                'p1': {'hp': 4000, 'fp': 5, 'passive_state': {}},
                'p2': {'hp': 4000, 'fp': 5, 'passive_state': {}},
            },
            'cards': [], 'context': {}, 'engine': {},
        }
        config.update(overrides)
        return config

    def forced_choice_definition(self, operation='move_card', *, minimum=1, maximum=1):
        terminal = {'op': operation, 'selection_key': 'chosen'}
        if operation == 'move_card':
            terminal['to_zone'] = 'hand'
        return {
            'schema_version': 1, 'reviewed': False, 'draft': True,
            'source_refs': {
                'rulebook_pages': [48], 'qna_ids': [], 'card_text': True,
            },
            'abilities': [{
                'id': 'forced-list-choice',
                'label': f'리스트에서 {minimum}~{maximum}장 선택',
                'draft_text': f'리스트에서 기술 {minimum}~{maximum}장을 선택해 처리한다.',
                'kind': 'effect', 'mode': 'mandatory',
                'trigger': {'event': 'use'}, 'timing': 'use',
                'visibility': 'public', 'draft': True,
                'draft_compiled': True,
                'source_refs': {
                    'rulebook_pages': [48], 'qna_ids': [], 'card_text': True,
                },
                'effects': [{
                    'op': 'request_choice', 'player': {'controller': True},
                    'prompt': f'리스트에서 반드시 {minimum}~{maximum}장을 선택하세요.',
                    'selector': {
                        'kind': 'card', 'player': {'controller': True},
                        'zones': ['list'], 'min': minimum, 'max': maximum,
                        **({'as_operation': 'break_card'} if operation == 'break_card' else {}),
                    },
                    'selection_key': 'chosen', 'default': [],
                    'then': [terminal],
                }],
            }],
        }

    def test_card_detail_links_effect_review_only_for_change_permission(self):
        response = self.client.get(reverse('card:detail', args=[self.card.pk]))
        self.assertNotContains(response, reverse('card:effectReview', args=[self.card.pk]))

        self.client.force_login(self.reviewer)
        response = self.client.get(reverse('card:detail', args=[self.card.pk]))
        self.assertContains(response, reverse('card:effectReview', args=[self.card.pk]))

    def test_effect_review_requires_change_card_permission(self):
        response = self.client.get(reverse('card:effectReview', args=[self.card.pk]))
        self.assertEqual(response.status_code, 403)

        ordinary = User.objects.create_user('ordinary', password='password')
        self.client.force_login(ordinary)
        response = self.client.get(reverse('card:effectReview', args=[self.card.pk]))
        self.assertEqual(response.status_code, 403)

    def test_effect_dsl_help_pages_require_change_card_permission(self):
        for name in ('effectDslGuide', 'effectDslReference'):
            with self.subTest(name=name):
                response = self.client.get(reverse(f'card:{name}'))
                self.assertEqual(response.status_code, 403)

    def test_effect_dsl_guide_is_beginner_oriented_and_linked_from_editor(self):
        self.client.force_login(self.reviewer)

        guide = self.client.get(reverse('card:effectDslGuide'))
        review = self.client.get(reverse('card:effectReview', args=[self.card.pk]))

        self.assertEqual(guide.status_code, 200)
        self.assertContains(guide, '자동 효과 DSL 작성 가이드')
        self.assertContains(guide, '효과 설정 화면에서 입력하는 순서')
        self.assertContains(guide, '정상 상황')
        self.assertContains(guide, '경계 상황')
        self.assertContains(guide, '불발 상황')
        self.assertContains(review, reverse('card:effectDslGuide'), count=3)
        self.assertContains(review, reverse('card:effectDslReference'), count=3)

    def test_effect_dsl_reference_covers_every_engine_identifier(self):
        from battlelog.game.spec import CONDITION_OPS, EFFECT_OPS, TRIGGERS, VALUE_OPS

        self.client.force_login(self.reviewer)
        response = self.client.get(reverse('card:effectDslReference'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['dsl']['undocumented_effect_ops'])
        self.assertFalse(response.context['dsl']['unknown_documented_effect_ops'])
        self.assertFalse(response.context['dsl']['undocumented_triggers'])
        self.assertFalse(response.context['dsl']['undocumented_conditions'])
        self.assertFalse(response.context['dsl']['undocumented_values'])
        for operation in EFFECT_OPS:
            self.assertContains(response, f'data-dsl-effect-op="{operation}"')
        for operation in CONDITION_OPS:
            self.assertContains(response, f'data-dsl-condition-op="{operation}"')
        for operation in VALUE_OPS:
            self.assertContains(response, f'data-dsl-value-op="{operation}"')
        for trigger in TRIGGERS:
            self.assertContains(response, f'data-dsl-trigger="{trigger}"')

    def test_effect_review_shows_source_qna_interpretation_and_editor(self):
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse('card:effectReview', args=[self.card.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.card.text)
        self.assertContains(response, self.card.detail_text)
        self.assertContains(response, self.qna.title)
        self.assertContains(response, 'FP 변경')
        self.assertContains(response, 'data-effect-editor')
        self.assertContains(response, '카드 고유 콤보 규칙')
        self.assertContains(response, '격리형 효과 테스트')
        self.assertContains(response, '실제 배틀 판정 (권장)')
        self.assertContains(response, '실제 콤보 기술 해석')
        self.assertContains(response, '실제 캐치 기술 해석')
        self.assertContains(response, '실제 게임·턴·페이즈 진행')
        self.assertContains(response, '내 배틀 카드 재현값 JSON')
        self.assertContains(response, '상대 배틀 카드 재현값 JSON')
        self.assertContains(response, '함께 제시할 후속 카드 코드')
        self.assertContains(response, '후속 카드 콤보 속도')
        self.assertContains(
            response,
            '입력한 배틀 재현값을 그대로 사용 (타이밍 자동 합성 안 함)',
        )
        self.assertContains(response, 'p1 · 여러 후보 중 선택')
        self.assertContains(response, '필수 후보 없음 · 후속 처리 중단')
        self.assertContains(
            response,
            'id="effect-sandbox-p1-fp" type="number" min="-999"',
        )
        self.assertContains(
            response,
            'id="effect-sandbox-p2-fp" type="number" min="-999"',
        )
        self.assertContains(
            response, reverse('card:effectSandboxStart', args=[self.card.pk]),
        )

    def test_effect_review_offers_common_scenarios_without_card_abilities(self):
        self.card.effect_definition = {
            'schema_version': 1, 'reviewed': False, 'draft': True,
            'source_refs': {
                'rulebook_pages': [], 'qna_ids': [], 'card_text': True,
            },
            'abilities': [],
        }
        self.card.save(update_fields=['effect_definition'])
        self.client.force_login(self.reviewer)

        response = self.client.get(reverse('card:effectReview', args=[self.card.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '공통 테스트 · 리스트에서 기술 1장 획득')
        self.assertContains(response, '공통 테스트 · 리스트에서 기술 2장 획득')
        self.assertContains(response, '공통 테스트 · 리스트의 기술 1장 브레이크')
        self.assertContains(response, '공통 테스트 · 패의 기술 1장 버리기')
        self.assertContains(
            response,
            '공통 테스트 · 사이드 덱에서 루멘으로 기술 1장 이동',
        )
        self.assertContains(
            response, '공통 테스트 · 상대가 자신의 패 1장 버리기',
        )
        self.assertContains(response, 'id="effect-sandbox-form"')

    def test_effect_sandbox_requires_change_card_permission(self):
        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_effect_sandbox_executes_unsaved_definition_without_persisting(self):
        definition = json.loads(json.dumps(self.card.effect_definition))
        definition['abilities'][0]['effects'][0]['amount'] = 3
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'rev-at-001-n1',
                'effect_definition': definition,
                'config': self.sandbox_config(fixture_mode='minimal'),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['players']['p1']['fp'], 8)
        self.card.refresh_from_db()
        self.assertEqual(
            self.card.effect_definition['abilities'][0]['effects'][0]['amount'], 1,
        )

    def test_effect_sandbox_reaches_use_through_real_battle_pipeline(self):
        definition = json.loads(json.dumps(self.card.effect_definition))
        definition['abilities'][0]['effects'][0]['amount'] = 3
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'rev-at-001-n1',
                'effect_definition': definition,
                'config': self.sandbox_config(
                    execution_mode='battle_pipeline', fixture_mode='minimal',
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertEqual(result['execution_mode'], 'battle_pipeline')
        self.assertEqual(result['execution_mode_label'], '실제 배틀 진행')
        self.assertIn('battle_reveal', result['pipeline_reached_events'])
        self.assertIn('use', result['pipeline_reached_events'])
        self.assertTrue(result['resolved'])
        self.assertTrue(any(
            event['type'] == 'effect_resolved'
            and event['payload'].get('ability_id') == 'rev-at-001-n1'
            for event in result['events']
        ))

    def test_empty_active_zones_keeps_source_trigger_active(self):
        definition = json.loads(json.dumps(self.card.effect_definition))
        definition['abilities'][0]['active_zones'] = []
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'rev-at-001-n1',
                'effect_definition': definition,
                'config': self.sandbox_config(
                    execution_mode='battle_pipeline', fixture_mode='minimal',
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['result']['resolved'])

    def test_effect_sandbox_pipeline_rejects_wrong_trigger_comparison(self):
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'rev-at-001-n1',
                'effect_definition': self.card.effect_definition,
                'config': self.sandbox_config(
                    event='after_use', execution_mode='battle_pipeline',
                    fixture_mode='minimal',
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn(
            '실제 진행 경로 모드에서는',
            response.json()['error'],
        )

    def test_effect_sandbox_reaches_counter_printed_combo_through_pipeline(self):
        self.card.hit = '+1'
        self.card.counter = '콤보'
        self.card.save(update_fields=['hit', 'counter'])
        definition = json.loads(json.dumps(self.card.effect_definition))
        ability = definition['abilities'][0]
        ability.update({
            'id': 'rev-at-001-combo',
            'label': '카운터 콤보 타이밍 테스트',
            'draft_text': '카운터 판정이 콤보면 1FP를 얻는다.',
            'trigger': {'event': 'combo'}, 'timing': 'combo',
            'condition': {
                'op': 'equals', 'left': 'context.combo_judgment',
                'right': True,
            },
        })
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': ability['id'],
                'effect_definition': definition,
                'config': self.sandbox_config(
                    event='combo', execution_mode='battle_pipeline',
                    fixture_mode='minimal',
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertTrue(result['resolved'])
        self.assertIn('counter', result['pipeline_reached_events'])
        self.assertIn('opponent_counter', result['pipeline_reached_events'])
        self.assertIn('combo', result['pipeline_reached_events'])

    def test_effect_sandbox_reaches_special_clash_with_battle_override(self):
        self.card.frame = 9
        self.card.pos = '중단'
        self.card.special = '하단 공격 기술에 상쇄'
        self.card.save(update_fields=['frame', 'pos', 'special'])
        definition = json.loads(json.dumps(self.card.effect_definition))
        ability = definition['abilities'][0]
        ability.update({
            'id': 'rev-at-001-special-clash',
            'label': '상대 콤보 판정 상쇄 테스트',
            'draft_text': '상대의 히트 판정이 콤보라면 1FP를 얻는다.',
            'trigger': {'event': 'clash'}, 'timing': 'clash',
            'condition': {
                'op': 'equals', 'left': 'context.opponent_card.hit',
                'right': '콤보',
            },
        })
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': ability['id'],
                'effect_definition': definition,
                'config': self.sandbox_config(
                    event='clash', execution_mode='battle_pipeline',
                    fixture_mode='minimal',
                    battle_overrides={
                        'opponent': {
                            'type': '공격', 'frame': 8, 'pos': '하단',
                            'hit': '콤보',
                        },
                    },
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertTrue(result['resolved'])
        self.assertIn('clash', result['pipeline_reached_events'])
        self.assertTrue(any(
            event['type'] == 'effect_resolved'
            and event['payload'].get('ability_id') == ability['id']
            for event in result['events']
        ))

    def test_effect_sandbox_can_preserve_exact_attack_clash_matchup(self):
        self.card.frame = 7
        self.card.pos = '상단'
        self.card.body = '손'
        self.card.save(update_fields=['frame', 'pos', 'body'])
        definition = json.loads(json.dumps(self.card.effect_definition))
        definition['defense_rules'] = [{
            'judgment': 'clash', 'position': '상단', 'grant': True,
            'where': {'body': '손'},
        }]
        ability = definition['abilities'][0]
        ability.update({
            'id': 'rev-at-001-exact-clash',
            'label': '손 판정만 상쇄',
            'draft_text': '상쇄 시 1FP를 얻는다.',
            'trigger': {'event': 'clash'}, 'timing': 'clash',
        })
        self.client.force_login(self.reviewer)

        def run(opponent_body):
            return self.client.post(
                reverse('card:effectSandboxStart', args=[self.card.pk]),
                data=json.dumps({
                    'ability_id': ability['id'],
                    'effect_definition': definition,
                    'config': self.sandbox_config(
                        event='clash', execution_mode='battle_pipeline',
                        fixture_mode='minimal',
                        preserve_battle_overrides=True,
                        battle_overrides={'opponent': {
                            'type': '공격', 'frame': 6, 'damage': 400,
                            'pos': '상단', 'body': opponent_body,
                            'special': None, 'hit': '1', 'guard': '1',
                            'counter': '1', 'g_top': None, 'g_mid': None,
                            'g_bot': None,
                        }},
                        players={
                            'p1': {'hp': 4000, 'fp': 0,
                                   'passive_state': {}},
                            'p2': {'hp': 4000, 'fp': 0,
                                   'passive_state': {}},
                        },
                    ),
                }),
                content_type='application/json',
            )

        matching = run('손')
        non_matching = run('발')

        self.assertEqual(matching.status_code, 200, matching.content)
        self.assertEqual(non_matching.status_code, 200, non_matching.content)
        matching_result = matching.json()['result']
        non_matching_result = non_matching.json()['result']
        self.assertTrue(matching_result['resolved'])
        self.assertIn('clash', matching_result['pipeline_reached_events'])
        self.assertEqual(
            next(
                event['payload']['result']
                for event in matching_result['events']
                if event['type'] == 'battle_judged'
            ),
            {'p1': 'clash', 'p2': 'clash'},
        )
        self.assertFalse(non_matching_result['resolved'])
        self.assertNotIn(
            'clash', non_matching_result['pipeline_reached_events'],
        )
        self.assertEqual(
            next(
                event['payload']['result']
                for event in non_matching_result['events']
                if event['type'] == 'battle_judged'
            ),
            {'p1': 'countered', 'p2': 'counter'},
        )

    def test_effect_sandbox_reaches_grab_negated_through_real_choice(self):
        self.card.special = '그랩'
        self.card.save(update_fields=['special'])
        hand_grab = Card.objects.create(
            name='무효용 그랩', code='REV-AT-GRAB',
            character=self.character, type='공격', frame=8,
            damage=300, pos='상단', special='그랩', hit='1',
            text='', effect_definition={
                'schema_version': 1, 'reviewed': True, 'no_effect': True,
                'source_refs': {
                    'rulebook_pages': [], 'qna_ids': [],
                    'card_text': False,
                },
                'abilities': [],
            },
        )
        definition = json.loads(json.dumps(self.card.effect_definition))
        ability = definition['abilities'][0]
        ability.update({
            'id': 'rev-at-001-grab-negated',
            'label': '그랩 무효 시 사이드 덱으로 이동',
            'draft_text': '그랩 무효 시 이 기술을 사이드 덱으로 보낸다.',
            'trigger': {'event': 'grab_negated'},
            'timing': 'result',
            'effects': [{'op': 'move_card', 'to_zone': 'side'}],
        })
        self.client.force_login(self.reviewer)
        started = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': ability['id'],
                'effect_definition': definition,
                'config': self.sandbox_config(
                    event='grab_negated',
                    execution_mode='battle_pipeline',
                    fixture_mode='minimal',
                    cards=[{
                        'card_id': hand_grab.pk, 'owner': 'p2',
                        'zone': 'hand', 'face_up': False,
                    }],
                    players={
                        'p1': {'hp': 4000, 'fp': 0,
                               'passive_state': {}},
                        'p2': {'hp': 4000, 'fp': 0,
                               'passive_state': {}},
                    },
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(started.status_code, 200, started.content)
        started_body = started.json()
        decision = started_body['result']['pending_decision']
        self.assertEqual(decision['kind'], 'grab_negation')
        continued = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({
                'token': started_body['token'],
                'selected': [decision['options'][0]['id']],
            }),
            content_type='application/json',
        )

        self.assertEqual(continued.status_code, 200, continued.content)
        result = continued.json()['result']
        self.assertTrue(result['resolved'])
        self.assertIn('grab_negated', result['pipeline_reached_events'])
        self.assertIn(
            self.card.code,
            [card['code'] for card in result['players']['p1']['zones']['side']],
        )
        self.assertIn(
            hand_grab.code,
            [card['code'] for card in result['players']['p2']['zones']['break']],
        )

    def test_effect_sandbox_can_continue_effect_granted_catch_action(self):
        catch_card = Card.objects.create(
            name='캐치 후보', code='REV-AT-002', character=self.character,
            type='공격', frame=7, damage=300, pos='중단', hit='+0',
            text='', effect_definition={
                'schema_version': 1, 'reviewed': True, 'no_effect': True,
                'source_refs': {
                    'rulebook_pages': [], 'qna_ids': [], 'card_text': False,
                },
                'abilities': [],
            },
        )
        definition = json.loads(json.dumps(self.card.effect_definition))
        ability = definition['abilities'][0]
        ability.update({
            'id': 'rev-at-001-grant-catch',
            'label': '히트 시 리스트에서 캐치',
            'draft_text': '히트 시 리스트의 8속도 이하 기술로 캐치할 수 있다.',
            'trigger': {'event': 'hit'}, 'timing': 'hit_counter',
            'effects': [{
                'op': 'grant_catch', 'player': {'controller': True},
                'allow_zones': ['list'], 'max_speed': 8,
            }],
        })
        self.client.force_login(self.reviewer)
        start = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': ability['id'],
                'effect_definition': definition,
                'config': self.sandbox_config(
                    event='hit', execution_mode='battle_pipeline',
                    fixture_mode='minimal',
                    cards=[{
                        'card_id': catch_card.pk, 'owner': 'p1',
                        'zone': 'list', 'face_up': True,
                    }],
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(start.status_code, 200, start.content)
        start_body = start.json()
        self.assertEqual(start_body['result']['status'], 'waiting_action')
        catch_action = next(
            action for action in start_body['result']['available_actions']
            if action['type'] == 'play_catch_card'
        )
        continued = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({
                'token': start_body['token'], 'selected': [],
                'action_id': catch_action['action_id'],
                'owner': catch_action['owner'],
            }),
            content_type='application/json',
        )

        self.assertEqual(continued.status_code, 200, continued.content)
        result = continued.json()['result']
        self.assertTrue(any(
            event['type'] == 'card_moved'
            and event['payload'].get('reason') == 'catch'
            and event['payload'].get('card_instance_id')
            for event in result['events']
        ))

    def test_effect_sandbox_can_include_passive_support_effects_in_pipeline(self):
        passive = Card.objects.create(
            name='테스트 특성', code='REV-PS-001',
            character=self.character, type='특성',
            text='자신 콤보 기술 사용 후, 2FP를 얻는다.',
            effect_definition={
                'schema_version': 1, 'reviewed': True,
                'source_refs': {
                    'rulebook_pages': [48], 'qna_ids': [], 'card_text': True,
                },
                'abilities': [{
                    'id': 'rev-ps-001-use',
                    'label': '콤보 기술 사용 후 2FP 획득',
                    'draft_text': '자신 콤보 기술 사용 후, 2FP를 얻는다.',
                    'kind': 'effect', 'mode': 'mandatory',
                    'trigger': {'event': 'after_use'}, 'timing': 'after_use',
                    'active_zones': ['passive'], 'visibility': 'public',
                    'source_refs': {
                        'rulebook_pages': [48], 'qna_ids': [],
                        'card_text': True,
                    },
                    'effects': [{
                        'op': 'change_fp', 'player': {'controller': True},
                        'amount': 2,
                    }],
                }, {
                    'id': 'rev-ps-001-combo-range',
                    'label': '콤보 속도 +2까지 허용',
                    'draft_text': '콤보를 직전 속도보다 2 느리게 이을 수 있다.',
                    'kind': 'function', 'mode': 'continuous',
                    'timing': 'function', 'active_zones': ['passive'],
                    'visibility': 'public',
                    'source_refs': {
                        'rulebook_pages': [48], 'qna_ids': [],
                        'card_text': True,
                    },
                    'effects': [{
                        'op': 'modify_combo',
                        'player': {'controller': True},
                        'max_speed_delta': 2, 'duration': 'continuous',
                    }],
                }],
            },
        )
        definition = json.loads(json.dumps(self.card.effect_definition))
        definition['combo_rules'] = [{'speed_options': [6]}]
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'rev-at-001-n1',
                'effect_definition': definition,
                'config': self.sandbox_config(
                    execution_mode='combo_pipeline', source_zone='hand',
                    combo_previous_speed=4, combo_speed=6,
                    fixture_mode='minimal',
                    include_support_effects=True,
                    cards=[{
                        'card_id': passive.pk, 'owner': 'p1',
                        'zone': 'passive', 'face_up': True,
                    }],
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        resolved_ids = {
            event['payload'].get('ability_id')
            for event in response.json()['result']['events']
            if event['type'] == 'effect_resolved'
        }
        self.assertIn('rev-at-001-n1', resolved_ids)
        self.assertIn('rev-ps-001-use', resolved_ids)

    def test_effect_sandbox_applies_character_import_deck_rules_to_battle(self):
        trait = Card.objects.create(
            name='키메라 특성', code='REV-PS-CHIMERA',
            character=self.character, type='특성', text='타 캐릭터 공격 효과 무효',
            effect_definition={
                'schema_version': 1, 'reviewed': True,
                'source_refs': {
                    'rulebook_pages': [48], 'qna_ids': [], 'card_text': True,
                },
                'abilities': [{
                    'id': 'rev-ps-chimera-function', 'kind': 'function',
                    'mode': 'continuous', 'timing': 'function',
                    'visibility': 'public', 'active_zones': ['passive'],
                    'source_refs': {
                        'rulebook_pages': [48], 'qna_ids': [],
                        'card_text': True,
                    },
                    'effects': [{'op': 'static_rule', 'rules': ['deck_rules']}],
                }],
                'deck_rules': {
                    'other_character_cards': {
                        'allowed_types': ['공격'], 'exclude_ultimate': True,
                        'exclude_character_ids': [],
                        'treat_as_own_character': True,
                        'negate_effects': True, 'break_after_use': True,
                    },
                },
            },
        )
        foreign_character = Character.objects.create(
            name='외부 캐릭터', localization_key='foreign-review',
            description='', group='루멘콘덴서', datas={},
            img='https://example.com/foreign.webp',
        )
        imported = Card.objects.create(
            name='수입 기술', code='REV-FOREIGN-AT-001',
            character=foreign_character, type='공격', frame=5,
            damage=300, pos='상단', text='①사용 시, HP 200을 지불한다.',
            effect_definition={
                'schema_version': 1, 'reviewed': True,
                'source_refs': {
                    'rulebook_pages': [48], 'qna_ids': [], 'card_text': True,
                },
                'abilities': [{
                    'id': 'rev-foreign-use-cost', 'kind': 'effect',
                    'mode': 'mandatory', 'timing': 'use',
                    'trigger': {'event': 'use'}, 'active_zones': ['battle'],
                    'visibility': 'public',
                    'source_refs': {
                        'rulebook_pages': [48], 'qna_ids': [],
                        'card_text': True,
                    },
                    'effects': [{
                        'op': 'pay_hp', 'player': {'controller': True},
                        'amount': 200,
                    }],
                }],
            },
        )
        opposing = Card.objects.create(
            name='상대 기술', code='REV-OPPOSING-AT-001',
            character=foreign_character, type='공격', frame=12,
            damage=300, pos='하단', text='',
            effect_definition={
                'schema_version': 1, 'reviewed': True, 'no_effect': True,
                'source_refs': {
                    'rulebook_pages': [], 'qna_ids': [], 'card_text': False,
                },
                'abilities': [],
            },
        )
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[trait.pk]),
            data=json.dumps({
                'ability_id': 'rev-ps-chimera-function',
                'effect_definition': trait.effect_definition,
                'config': self.sandbox_config(
                    event='after_use', execution_mode='battle_pipeline',
                    source_zone='passive', fixture_mode='none',
                    include_source_effects=True,
                    include_support_effects=True,
                    cards=[{
                        'card_id': imported.pk, 'owner': 'p1',
                        'zone': 'battle', 'face_up': True,
                    }, {
                        'card_id': opposing.pk, 'owner': 'p2',
                        'zone': 'battle', 'face_up': True,
                    }],
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertEqual(result['players']['p1']['hp'], 4000)
        self.assertIn(
            imported.code,
            [card['code'] for card in result['players']['p1']['zones']['break']],
        )
        self.assertFalse(any(
            event['type'] == 'effect_resolved'
            and event['payload'].get('ability_id') == 'rev-foreign-use-cost'
            for event in result['events']
        ))

    def test_effect_sandbox_can_include_other_source_card_abilities(self):
        definition = json.loads(json.dumps(self.card.effect_definition))
        definition['abilities'][0].update({
            'id': 'rev-at-001-deploy', 'label': '사용 시 루멘으로 이동',
            'draft_text': '사용 시 이 카드를 루멘 존으로 이동한다.',
            'effects': [{'op': 'move_card', 'to_zone': 'lumen'}],
        })
        definition['abilities'].append({
            'id': 'rev-at-001-arrived', 'label': '루멘 배치 후 FP 획득',
            'draft_text': '이 카드가 루멘 존으로 이동하면 2FP를 얻는다.',
            'kind': 'effect', 'mode': 'mandatory', 'timing': 'function',
            'visibility': 'public', 'active_zones': ['lumen'],
            'trigger': {'event': 'card_moved'},
            'condition': {
                'op': 'all', 'conditions': [{
                    'op': 'equals',
                    'left': {'path': 'context.event_card_instance_id'},
                    'right': {'path': 'context.source_card_instance_id'},
                }, {
                    'op': 'equals', 'left': 'context.to_zone', 'right': 'lumen',
                }],
            },
            'source_refs': {
                'rulebook_pages': [48], 'qna_ids': [], 'card_text': True,
            },
            'effects': [{
                'op': 'change_fp', 'player': {'controller': True}, 'amount': 2,
            }],
        })
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'rev-at-001-deploy',
                'effect_definition': definition,
                'config': self.sandbox_config(
                    execution_mode='battle_pipeline', fixture_mode='minimal',
                    include_source_effects=True,
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        resolved_ids = {
            event['payload'].get('ability_id')
            for event in response.json()['result']['events']
            if event['type'] == 'effect_resolved'
        }
        self.assertIn('rev-at-001-deploy', resolved_ids)
        self.assertIn('rev-at-001-arrived', resolved_ids)

    def test_effect_sandbox_uses_source_character_hand_table(self):
        self.character.datas = {'hand': {'5000': 5}}
        self.character.save(update_fields=['datas'])
        hand_cards = [
            Card.objects.create(
                name=f'패 제한 후보 {index}', code=f'REV-HAND-{index:03d}',
                character=self.character, type='공격', frame=5 + index,
                damage=300, pos='중단', text='',
                effect_definition={
                    'schema_version': 1, 'reviewed': True,
                    'no_effect': True,
                    'source_refs': {
                        'rulebook_pages': [], 'qna_ids': [],
                        'card_text': False,
                    },
                    'abilities': [],
                },
            )
            for index in range(2)
        ]
        definition = json.loads(json.dumps(self.card.effect_definition))
        ability = definition['abilities'][0]
        ability.update({
            'id': 'rev-at-001-hand-limit-recovery',
            'label': '리커버리 최대 패에서 사이드 덱으로 이동',
            'draft_text': (
                '리커버리 페이즈 시 자신의 패가 최대 제한과 같을 경우 '
                '이 카드를 사이드 덱으로 보낸다.'
            ),
            'trigger': {'event': 'phase_start'}, 'timing': 'function',
            'active_zones': ['lumen'],
            'condition': {
                'op': 'all',
                'conditions': [{
                    'op': 'phase_is', 'phase': 'recovery',
                }, {
                    'op': 'equals',
                    'left': {
                        'op': 'zone_count',
                        'player': {'controller': True}, 'zone': 'hand',
                    },
                    'right': {'path': 'context.controller_hand_limit'},
                }],
            },
            'effects': [{'op': 'move_card', 'to_zone': 'side'}],
        })
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': ability['id'],
                'effect_definition': definition,
                'config': self.sandbox_config(
                    event='phase_start', execution_mode='phase_pipeline',
                    source_zone='lumen', phase='recovery',
                    fixture_mode='choices',
                    cards=[{
                        'card_id': card.pk, 'owner': 'p1',
                        'zone': 'hand', 'face_up': False,
                    } for card in hand_cards],
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertTrue(result['resolved'])
        self.assertIn(
            self.card.code,
            [card['code'] for card in result['players']['p1']['zones']['side']],
        )

    def test_effect_sandbox_character_key_selector_sees_support_card(self):
        candidate = Card.objects.create(
            name='같은 캐릭터 후보', code='REV-AT-003',
            character=self.character, type='공격', frame=6, damage=300,
            pos='중단', text='', effect_definition={
                'schema_version': 1, 'reviewed': True, 'no_effect': True,
                'source_refs': {
                    'rulebook_pages': [], 'qna_ids': [], 'card_text': False,
                },
                'abilities': [],
            },
        )
        definition = self.forced_choice_definition()
        selector = definition['abilities'][0]['effects'][0]['selector']
        selector['zones'] = ['side']
        selector['where'] = {
            'is_technique': True,
            'character_key': self.character.localization_key,
        }
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'forced-list-choice',
                'effect_definition': definition,
                'config': self.sandbox_config(
                    fixture_mode='minimal', cards=[{
                        'card_id': candidate.pk, 'owner': 'p1',
                        'zone': 'side', 'face_up': False,
                    }],
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        decision = response.json()['result']['pending_decision']
        self.assertEqual(len(decision['options']), 1)
        self.assertIn('같은 캐릭터 후보', decision['options'][0]['label'])

    def test_effect_sandbox_runs_selected_card_through_real_catch_pipeline(self):
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'rev-at-001-n1',
                'effect_definition': self.card.effect_definition,
                'config': self.sandbox_config(
                    execution_mode='catch_pipeline', source_zone='hand',
                    fixture_mode='minimal', catch_speed=5,
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertEqual(result['execution_mode'], 'catch_pipeline')
        self.assertEqual(result['execution_mode_label'], '실제 캐치 기술 해석')
        self.assertTrue(result['resolved'])
        reached = result['pipeline_reached_events']
        self.assertTrue(all(event in reached for event in (
            'use', 'catch', 'hit', 'after_use',
        )))
        self.assertLess(reached.index('use'), reached.index('catch'))
        self.assertLess(reached.index('catch'), reached.index('hit'))
        self.assertLess(reached.index('hit'), reached.index('after_use'))

    def test_effect_sandbox_reaches_phase_start_through_state_machine(self):
        definition = json.loads(json.dumps(self.card.effect_definition))
        ability = definition['abilities'][0]
        ability.update({
            'id': 'rev-at-001-ready-start',
            'label': '레디 페이즈 시작 시 FP 획득',
            'draft_text': '레디 페이즈 시작 시 1FP를 얻는다.',
            'trigger': {'event': 'phase_start'}, 'timing': 'function',
            'active_zones': ['passive'],
            'condition': {
                'op': 'equals', 'left': 'context.phase', 'right': 'ready',
            },
        })
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': ability['id'], 'effect_definition': definition,
                'config': self.sandbox_config(
                    event='phase_start', execution_mode='phase_pipeline',
                    source_zone='passive', phase='ready', fixture_mode='minimal',
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertTrue(result['resolved'])
        self.assertIn('phase_end', result['pipeline_reached_events'])
        self.assertIn('phase_start', result['pipeline_reached_events'])
        self.assertEqual(result['players']['p1']['fp'], 6)

    def test_effect_sandbox_skips_printed_combo_after_catch_without_pair(self):
        self.card.hit = '콤보'
        self.card.save(update_fields=['hit'])
        self.client.force_login(self.reviewer)
        start = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'rev-at-001-n1',
                'effect_definition': self.card.effect_definition,
                'config': self.sandbox_config(
                    execution_mode='catch_pipeline', source_zone='hand',
                    fixture_mode='minimal', catch_speed=5,
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(start.status_code, 200, start.content)
        result = start.json()['result']
        self.assertNotIn(
            'end_combo',
            {action['type'] for action in result['available_actions']},
        )
        skipped = next(
            event for event in result['events']
            if event['type'] == 'combo_skipped'
        )
        self.assertEqual(
            skipped['payload']['reason'], 'normal_combo_requires_two_cards',
        )
        self.assertFalse(any(
            event['type'] == 'combo_started' for event in result['events']
        ))

    def test_effect_sandbox_runs_continuous_card_catch_rule(self):
        definition = json.loads(json.dumps(self.card.effect_definition))
        definition['abilities'] = [{
            'id': 'rev-at-001-catch-rule', 'label': '카운터로 3속도 캐치',
            'draft_text': '캐치 시 카운터 1개를 소모해 3속도로 사용할 수 있다.',
            'kind': 'effect', 'mode': 'continuous', 'timing': 'catch',
            'visibility': 'public',
            'source_refs': {
                'rulebook_pages': [47], 'qna_ids': [], 'card_text': True,
            },
            'effects': [{'op': 'static_rule', 'rules': ['catch_rules']}],
        }]
        definition['catch_rules'] = [{
            'optional_fixed_speed': 3,
            'counter_cost': {'counter': 'test_counter', 'amount': 1},
            'numbered_effect': True,
        }]
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'rev-at-001-catch-rule',
                'effect_definition': definition,
                'config': self.sandbox_config(
                    event='catch', execution_mode='catch_pipeline',
                    source_zone='hand', fixture_mode='minimal', catch_speed=3,
                    players={
                        'p1': {
                            'hp': 4000, 'fp': 0,
                            'passive_state': {'test_counter': {'count': 1}},
                        },
                        'p2': {'hp': 4000, 'fp': 0, 'passive_state': {}},
                    },
                ),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertEqual(
            result['players']['p1']['passive_state']['test_counter']['count'], 0,
        )
        self.assertTrue(any(
            event['type'] == 'catch_counter_cost_paid'
            and event['payload'].get('fixed_speed') == 3
            for event in result['events']
        ))

    def test_effect_sandbox_waits_for_mandatory_card_choice_before_move(self):
        definition = self.forced_choice_definition()
        self.client.force_login(self.reviewer)
        start = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'forced-list-choice',
                'effect_definition': definition,
                'config': self.sandbox_config(),
            }),
            content_type='application/json',
        )

        self.assertEqual(start.status_code, 200, start.content)
        start_data = start.json()
        result = start_data['result']
        self.assertEqual(result['status'], 'waiting')
        decision = result['pending_decision']
        self.assertEqual(decision['kind'], 'effect_choice')
        self.assertEqual(decision['minimum'], 1)
        self.assertEqual(decision['maximum'], 1)
        chosen = next(
            option['id'] for option in decision['options']
            if 'ATTACK' in option['id'].upper()
        )
        self.assertTrue(any(
            card['instance_id'] == chosen
            for card in result['players']['p1']['zones']['list']
        ))
        self.assertFalse(any(
            event['type'] == 'card_moved'
            and event['payload'].get('card_instance_id') == chosen
            for event in result['events']
        ))

        decided = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({'token': start_data['token'], 'selected': [chosen]}),
            content_type='application/json',
        )

        self.assertEqual(decided.status_code, 200, decided.content)
        decided_result = decided.json()['result']
        self.assertEqual(decided_result['status'], 'completed')
        self.assertTrue(any(
            card['instance_id'] == chosen
            for card in decided_result['players']['p1']['zones']['hand']
        ))
        movement = next(
            event for event in decided_result['events']
            if event['type'] == 'card_moved'
            and event['payload'].get('card_instance_id') == chosen
        )
        self.assertEqual(movement['payload']['from_zone'], 'list')
        self.assertEqual(movement['payload']['to_zone'], 'hand')

    def test_common_acquire_scenario_works_with_empty_card_definition(self):
        self.client.force_login(self.reviewer)
        empty_definition = {
            'schema_version': 1, 'reviewed': False, 'draft': True,
            'source_refs': {
                'rulebook_pages': [], 'qna_ids': [], 'card_text': True,
            },
            'abilities': [],
        }
        start_response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'sandbox-prototype:acquire-one',
                'effect_definition': empty_definition,
                'config': self.sandbox_config(),
            }),
            content_type='application/json',
        )

        self.assertEqual(start_response.status_code, 200, start_response.content)
        start = start_response.json()
        decision = start['result']['pending_decision']
        self.assertEqual(decision['owner'], 'p1')
        self.assertEqual((decision['minimum'], decision['maximum']), (1, 1))
        chosen = next(
            option['id'] for option in decision['options']
            if 'ATTACK' in option['id'].upper()
        )
        self.assertTrue(any(
            card['instance_id'] == chosen
            for card in start['result']['players']['p1']['zones']['list']
        ))

        decided = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({'token': start['token'], 'selected': [chosen]}),
            content_type='application/json',
        )

        self.assertEqual(decided.status_code, 200, decided.content)
        result = decided.json()['result']
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(any(
            card['instance_id'] == chosen
            for card in result['players']['p1']['zones']['hand']
        ))

    def test_common_acquire_special_technique_follows_core_break_rule(self):
        self.client.force_login(self.reviewer)
        start_response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'sandbox-prototype:acquire-one',
                'effect_definition': self.card.effect_definition,
                'config': self.sandbox_config(),
            }),
            content_type='application/json',
        )

        self.assertEqual(start_response.status_code, 200, start_response.content)
        start = start_response.json()
        special_id = next(
            option['id'] for option in start['result']['pending_decision']['options']
            if 'SPECIAL' in option['id'].upper()
        )
        decided = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({'token': start['token'], 'selected': [special_id]}),
            content_type='application/json',
        )

        self.assertEqual(decided.status_code, 200, decided.content)
        result = decided.json()['result']
        self.assertTrue(any(
            card['instance_id'] == special_id
            for card in result['players']['p1']['zones']['break']
        ))
        self.assertFalse(any(
            card['instance_id'] == special_id
            for card in result['players']['p1']['zones']['hand']
        ))
        movement = next(
            event for event in result['events']
            if event['type'] == 'card_moved'
            and event['payload'].get('card_instance_id') == special_id
        )
        self.assertEqual(movement['payload']['from_zone'], 'list')
        self.assertEqual(movement['payload']['to_zone'], 'break')

    def test_common_multi_acquire_requires_and_moves_two_selected_cards(self):
        self.client.force_login(self.reviewer)
        start_response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'sandbox-prototype:acquire-two',
                'effect_definition': self.card.effect_definition,
                'config': self.sandbox_config(),
            }),
            content_type='application/json',
        )

        self.assertEqual(start_response.status_code, 200, start_response.content)
        start = start_response.json()
        decision = start['result']['pending_decision']
        self.assertEqual((decision['minimum'], decision['maximum']), (2, 2))
        selected = [option['id'] for option in decision['options'][:2]]
        decided = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({'token': start['token'], 'selected': selected}),
            content_type='application/json',
        )

        self.assertEqual(decided.status_code, 200, decided.content)
        result = decided.json()['result']
        hand_ids = {
            card['instance_id'] for card in result['players']['p1']['zones']['hand']
        }
        self.assertTrue(set(selected).issubset(hand_ids))
        moved_ids = {
            event['payload'].get('card_instance_id')
            for event in result['events']
            if event['type'] == 'card_moved'
            and event['payload'].get('from_zone') == 'list'
            and event['payload'].get('to_zone') == 'hand'
        }
        self.assertTrue(set(selected).issubset(moved_ids))

    def test_common_break_scenario_continues_into_real_replenishment_choice(self):
        self.client.force_login(self.reviewer)
        start = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'sandbox-prototype:break-one',
                'effect_definition': self.card.effect_definition,
                'config': self.sandbox_config(),
            }),
            content_type='application/json',
        ).json()
        broken_id = next(
            option['id'] for option in start['result']['pending_decision']['options']
            if 'ATTACK' in option['id'].upper()
        )

        broken_response = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({'token': start['token'], 'selected': [broken_id]}),
            content_type='application/json',
        )
        self.assertEqual(broken_response.status_code, 200, broken_response.content)
        broken = broken_response.json()
        replenish = broken['result']['pending_decision']
        self.assertEqual(replenish['kind'], 'break_replenish')
        replacement_id = next(
            option['id'] for option in replenish['options']
            if option['id'] != 'decline'
        )

        replenished_response = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({
                'token': broken['token'], 'selected': [replacement_id],
            }),
            content_type='application/json',
        )

        self.assertEqual(
            replenished_response.status_code, 200, replenished_response.content,
        )
        result = replenished_response.json()['result']
        self.assertTrue(any(
            card['instance_id'] == broken_id
            for card in result['players']['p1']['zones']['break']
        ))
        self.assertTrue(any(
            card['instance_id'] == replacement_id
            for card in result['players']['p1']['zones']['list']
        ))
        self.assertTrue(any(
            event['type'] == 'card_moved'
            and event['payload'].get('card_instance_id') == replacement_id
            and event['payload'].get('from_zone') == 'side'
            and event['payload'].get('to_zone') == 'list'
            for event in result['events']
        ))

    def test_common_discard_scenario_waits_then_moves_selected_hand_card(self):
        self.client.force_login(self.reviewer)
        start = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'sandbox-prototype:discard-one',
                'effect_definition': self.card.effect_definition,
                'config': self.sandbox_config(),
            }),
            content_type='application/json',
        ).json()
        decision = start['result']['pending_decision']
        self.assertEqual(decision['owner'], 'p1')
        self.assertEqual((decision['minimum'], decision['maximum']), (1, 1))
        chosen = next(
            option['id'] for option in decision['options']
            if 'ATTACK' in option['id'].upper()
        )

        response = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({'token': start['token'], 'selected': [chosen]}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertTrue(any(
            card['instance_id'] == chosen
            for card in result['players']['p1']['zones']['list']
        ))
        self.assertTrue(any(
            event['type'] == 'card_discarded'
            and event['payload'].get('card_instance_id') == chosen
            for event in result['events']
        ))
        self.assertEqual(result['audit']['decisions'][0]['status'], 'resolved')
        self.assertEqual(result['audit']['movements'][0]['from_zone'], 'hand')
        self.assertEqual(result['audit']['movements'][0]['to_zone'], 'list')

    def test_common_move_scenario_shows_side_to_lumen_transition(self):
        self.client.force_login(self.reviewer)
        start = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'sandbox-prototype:move-side-lumen-one',
                'effect_definition': self.card.effect_definition,
                'config': self.sandbox_config(),
            }),
            content_type='application/json',
        ).json()
        decision = start['result']['pending_decision']
        chosen = next(
            option['id'] for option in decision['options']
            if 'ATTACK' in option['id'].upper()
        )

        response = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({'token': start['token'], 'selected': [chosen]}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertTrue(any(
            card['instance_id'] == chosen
            for card in result['players']['p1']['zones']['lumen']
        ))
        movement = next(
            item for item in result['audit']['movements']
            if item['card_instance_id'] == chosen
        )
        self.assertEqual((movement['from_zone'], movement['to_zone']), ('side', 'lumen'))

    def test_common_scenario_can_keep_reviewed_card_effects_active(self):
        self.client.force_login(self.reviewer)
        config = self.sandbox_config(include_source_effects=True)
        start_response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'sandbox-prototype:move-side-lumen-one',
                'effect_definition': self.card.effect_definition,
                'config': config,
            }),
            content_type='application/json',
        )
        self.assertEqual(start_response.status_code, 200, start_response.content)
        start = start_response.json()
        ordering = start['result']['pending_decision']
        prototype_first = next(
            option['id'] for option in ordering['options']
            if str(option.get('label') or '').startswith('공통 테스트')
        )
        ordered_response = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({
                'token': start['token'], 'selected': [prototype_first],
            }),
            content_type='application/json',
        )
        self.assertEqual(
            ordered_response.status_code, 200, ordered_response.content,
        )
        ordered = ordered_response.json()
        decision = ordered['result']['pending_decision']
        chosen = next(
            option['id'] for option in decision['options']
            if 'ATTACK' in option['id'].upper()
        )

        response = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({
                'token': ordered['token'], 'selected': [chosen],
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertEqual(result['players']['p1']['fp'], 6)
        self.assertTrue(any(
            event['type'] == 'effect_resolved'
            and event['payload'].get('ability_id') == 'rev-at-001-n1'
            for event in result['events']
        ))
        self.assertTrue(any(
            card['instance_id'] == chosen
            for card in result['players']['p1']['zones']['lumen']
        ))

    def test_common_opponent_discard_makes_opponent_choose_own_card(self):
        self.client.force_login(self.reviewer)
        start = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'sandbox-prototype:opponent-discard-one',
                'effect_definition': self.card.effect_definition,
                'config': self.sandbox_config(controller='p1'),
            }),
            content_type='application/json',
        ).json()
        decision = start['result']['pending_decision']
        self.assertEqual(decision['owner'], 'p2')
        self.assertTrue(all(option['owner'] == 'p2' for option in decision['options']))
        chosen = next(
            option['id'] for option in decision['options']
            if 'ATTACK' in option['id'].upper()
        )

        response = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({'token': start['token'], 'selected': [chosen]}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertTrue(any(
            card['instance_id'] == chosen
            for card in result['players']['p2']['zones']['list']
        ))
        self.assertEqual(result['audit']['decisions'][0]['owner'], 'p2')
        self.assertEqual(result['audit']['decisions'][0]['selected'][0]['id'], chosen)

    def test_effect_sandbox_rejects_empty_answer_for_mandatory_choice(self):
        self.client.force_login(self.reviewer)
        start = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'forced-list-choice',
                'effect_definition': self.forced_choice_definition(),
                'config': self.sandbox_config(),
            }),
            content_type='application/json',
        ).json()

        response = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({'token': start['token'], 'selected': []}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('선택 수', response.json()['error'])

    def test_effect_sandbox_moves_multiple_cards_chosen_by_player_two(self):
        self.client.force_login(self.reviewer)
        start_response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'forced-list-choice',
                'effect_definition': self.forced_choice_definition(
                    minimum=2, maximum=3,
                ),
                'config': self.sandbox_config(controller='p2'),
            }),
            content_type='application/json',
        )

        self.assertEqual(start_response.status_code, 200, start_response.content)
        start = start_response.json()
        decision = start['result']['pending_decision']
        self.assertEqual(decision['owner'], 'p2')
        self.assertEqual((decision['minimum'], decision['maximum']), (2, 3))
        chosen = [option['id'] for option in decision['options'][:2]]

        decided = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({'token': start['token'], 'selected': chosen}),
            content_type='application/json',
        )

        self.assertEqual(decided.status_code, 200, decided.content)
        result = decided.json()['result']
        self.assertEqual(result['status'], 'completed')
        hand_ids = {
            card['instance_id'] for card in result['players']['p2']['zones']['hand']
        }
        self.assertTrue(set(chosen).issubset(hand_ids))
        moved_ids = {
            event['payload'].get('card_instance_id')
            for event in result['events']
            if event['type'] == 'card_moved'
            and event['payload'].get('from_zone') == 'list'
            and event['payload'].get('to_zone') == 'hand'
        }
        self.assertTrue(set(chosen).issubset(moved_ids))

    def test_effect_sandbox_reports_insufficient_mandatory_candidates(self):
        self.client.force_login(self.reviewer)
        definition = self.forced_choice_definition()
        definition['abilities'][0]['effects'].append({
            'op': 'change_fp', 'player': {'controller': True}, 'amount': 3,
        })
        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'forced-list-choice',
                'effect_definition': definition,
                'config': self.sandbox_config(fixture_mode='minimal'),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['pending_decision'])
        self.assertEqual(result['players']['p1']['fp'], 5)
        self.assertTrue(any(
            event['type'] == 'effect_choice_skipped'
            for event in result['events']
        ))
        skipped_index = next(
            index for index, event in enumerate(result['events'])
            if event['type'] == 'effect_choice_skipped'
        )
        self.assertEqual(result['events'][skipped_index + 1:], [])

    def test_effect_sandbox_skips_empty_optional_choice_and_continues(self):
        self.client.force_login(self.reviewer)
        definition = self.forced_choice_definition(minimum=0, maximum=1)
        choice = definition['abilities'][0]['effects'][0]
        choice['optional'] = True
        choice['selector']['where'] = {'code': 'NO-SUCH-CANDIDATE'}
        definition['abilities'][0]['effects'].append({
            'op': 'change_fp', 'player': {'controller': True}, 'amount': 2,
        })

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'forced-list-choice',
                'effect_definition': definition,
                'config': self.sandbox_config(fixture_mode='minimal'),
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['result']
        self.assertEqual(result['status'], 'completed')
        self.assertIsNone(result['pending_decision'])
        self.assertEqual(result['players']['p1']['fp'], 7)
        self.assertFalse(any(
            event['type'] in {'decision_requested', 'effect_choice_skipped'}
            for event in result['events']
        ))

    def test_effect_sandbox_offers_exactly_one_real_candidate(self):
        candidate = Card.objects.create(
            name='유일한 후보', code='REV-AT-CHOICE', character=self.character,
            type='공격', frame=4, damage=300, pos='하단', text='',
        )
        self.client.force_login(self.reviewer)
        config = self.sandbox_config(fixture_mode='minimal')
        config['cards'] = [{
            'card_id': candidate.pk, 'owner': 'p1', 'zone': 'list',
            'face_up': True,
        }]

        response = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'forced-list-choice',
                'effect_definition': self.forced_choice_definition(),
                'config': config,
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        options = response.json()['result']['pending_decision']['options']
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]['label'], '유일한 후보')

    def test_effect_sandbox_wrong_trigger_is_reproducible_and_does_not_apply(self):
        self.client.force_login(self.reviewer)
        body = {
            'ability_id': 'rev-at-001-n1',
            'effect_definition': self.card.effect_definition,
            'config': self.sandbox_config(event='after_use', fixture_mode='minimal'),
        }

        first = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps(body), content_type='application/json',
        )
        second = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps(body), content_type='application/json',
        )

        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        first_result = first.json()['result']
        self.assertEqual(first_result['status'], 'not_triggered')
        self.assertEqual(first_result['players']['p1']['fp'], 5)
        self.assertEqual(first_result, second.json()['result'])

    def test_effect_sandbox_break_choice_uses_real_break_and_followup_flow(self):
        self.client.force_login(self.reviewer)
        start = self.client.post(
            reverse('card:effectSandboxStart', args=[self.card.pk]),
            data=json.dumps({
                'ability_id': 'forced-list-choice',
                'effect_definition': self.forced_choice_definition('break_card'),
                'config': self.sandbox_config(),
            }),
            content_type='application/json',
        ).json()
        chosen = next(
            option['id'] for option in start['result']['pending_decision']['options']
            if 'ATTACK' in option['id'].upper()
        )

        decided = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({'token': start['token'], 'selected': [chosen]}),
            content_type='application/json',
        )

        self.assertEqual(decided.status_code, 200, decided.content)
        result = decided.json()['result']
        self.assertTrue(any(
            card['instance_id'] == chosen
            for card in result['players']['p1']['zones']['break']
        ))
        self.assertTrue(any(
            event['type'] == 'card_broken'
            and event['payload'].get('card_instance_id') == chosen
            for event in result['events']
        ))
        self.assertEqual(result['pending_decision']['kind'], 'break_replenish')

    def test_effect_sandbox_rejects_tampered_state_token(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse('card:effectSandboxDecision', args=[self.card.pk]),
            data=json.dumps({'token': 'tampered', 'selected': ['anything']}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('서명', response.json()['error'])

    def test_effect_review_save_approves_current_sources_and_increments_revision(self):
        self.client.force_login(self.reviewer)
        definition = self.reviewed_definition()
        # 검수 완료 저장은 편집기에서 남은 초안 플래그도 정규화해야 한다.
        definition['draft'] = True
        definition['abilities'][0]['draft'] = True
        response = self.client.post(
            reverse('card:effectReview', args=[self.card.pk]),
            {'effect_definition': json.dumps(definition, ensure_ascii=False)},
        )

        self.assertRedirects(
            response, reverse('card:effectReview', args=[self.card.pk]),
        )
        self.card.refresh_from_db()
        self.assertTrue(self.card.effect_definition['reviewed'])
        self.assertFalse(self.card.effect_definition['draft'])
        self.assertFalse(self.card.effect_definition['abilities'][0]['draft'])
        self.assertTrue(self.card.effect_definition.get('source_digest'))
        self.assertEqual(self.card.effect_revision, 2)

        response = self.client.get(reverse('card:effectReview', args=[self.card.pk]))
        self.assertEqual(response.context['review']['status'], 'ok')

    def test_effect_review_rejects_invalid_definition(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse('card:effectReview', args=[self.card.pk]),
            {'effect_definition': json.dumps({
                'schema_version': 1, 'reviewed': True,
            }, ensure_ascii=False)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'effect_definition',
            '$.abilities: 능력 목록이 필요합니다.',
        )
        self.card.refresh_from_db()
        self.assertFalse(self.card.effect_definition['reviewed'])

    def test_effect_review_rejects_non_object_definition_without_server_error(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse('card:effectReview', args=[self.card.pk]),
            {'effect_definition': '["invalid"]'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'effect_definition',
            '$: 효과 정의는 객체여야 합니다.',
        )

    def test_effect_review_can_save_and_continue_to_next_unreviewed_card(self):
        next_card = Card.objects.create(
            name='다음 검수 카드', code='REV-AT-002',
            character=self.character, text='',
        )
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse('card:effectReview', args=[self.card.pk]),
            {
                'effect_definition': json.dumps(self.reviewed_definition(), ensure_ascii=False),
                '_saveandnextunreviewed': '1',
            },
        )

        self.assertRedirects(
            response, reverse('card:effectReview', args=[next_card.pk]),
        )

    def test_admin_card_change_links_general_effect_review(self):
        admin_user = User.objects.create_superuser(
            'effect-admin', 'effect-admin@example.com', 'password',
        )
        self.client.force_login(admin_user)
        response = self.client.get(reverse('admin:card_card_change', args=[self.card.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse('card:effectReview', args=[self.card.pk]),
        )
        self.assertContains(response, reverse('card:effectDslGuide'))
        self.assertContains(response, reverse('card:effectDslReference'))


class CardSearchNormalizationTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(
            name='세츠메이',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/setsumei.webp',
        )
        self.card = Card.objects.create(
            name='세츠메이 킥',
            code='ST1-018',
            character=self.character,
            img='https://example.com/card.webp',
            keyword='콤보 시동기/',
        )
        CardTranslation.objects.create(
            card=self.card,
            language='en',
            name='Setsumei Kick',
            keyword='Combo Starter',
        )

    def test_search_ignores_case_spaces_and_punctuation(self):
        self.assertTrue(card_matches_search(self.card, 'setsumeikick'))
        self.assertTrue(card_matches_search(self.card, 'SETSUMEI-KICK'))
        self.assertTrue(card_matches_search(self.card, 'setsumei   kick!!!'))

    def test_exact_search_uses_normalized_card_names(self):
        self.assertTrue(card_matches_search_exact(self.card, 'setsumei-kick'))
        self.assertFalse(card_matches_search_exact(self.card, 'setsumei'))
