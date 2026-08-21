import json

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from .models import Card, CardTranslation, Character
from .search import card_matches_search, card_matches_search_exact
from common.language import LANGUAGE_SESSION_KEY
from qna.models import QNA, QNARelation


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


class CardEffectReviewTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(
            name='CMYK', description='', group='루멘콘덴서', datas={},
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
        self.assertContains(response, 'p1 · 여러 후보 중 선택')
        self.assertContains(response, '필수 후보 없음 · 후속 처리 중단')
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
