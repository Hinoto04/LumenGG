"""대전 클라이언트 다국어: 엔진 문구 번역(play_i18n)과 ?lang= 언어 지정."""
import json
import re
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from card.models import Card, CardTranslation, Character, CharacterTranslation
from common.language import LANGUAGE_SESSION_KEY

from . import play_i18n
from .play_i18n import (
    localize_engine_text,
    localize_engine_text_fields,
    localize_event_payload,
    localize_prompt,
)


class EngineTextTests(TestCase):
    def setUp(self):
        play_i18n._NAME_CACHE.update(at=0.0, rows={})
        self.character = Character.objects.create(name='루트', description='', group='', datas={}, img='')
        CharacterTranslation.objects.create(character=self.character, language='en', name='Route')
        self.card = Card.objects.create(name='하이 잽', code='TST-AT-001', type='공격', character=self.character)
        CardTranslation.objects.create(card=self.card, language='en', name='High Jab')
        CardTranslation.objects.create(card=self.card, language='ja', name='ハイ・ジャブ')
        self.passive = Card.objects.create(name='「차지」', code='TST-PS1', type='특성', character=self.character)
        CardTranslation.objects.create(card=self.passive, language='en', name='「Charge」')

    def tearDown(self):
        play_i18n._NAME_CACHE.update(at=0.0, rows={})

    def test_fixed_engine_labels_use_exact_table_not_substring_terms(self):
        self.assertEqual(localize_engine_text('발동하지 않음', 'en'), "Don't activate")
        self.assertEqual(localize_engine_text('상대 시작 패 확인 완료', 'ja'), '相手の初期手札の確認完了')
        self.assertEqual(localize_engine_text('Ready', 'en'), 'Ready')

    def test_card_names_parts_and_speed_suffix(self):
        names = {'하이 잽': 'High Jab'}
        self.assertEqual(localize_engine_text('레디 · 하이 잽', 'en', names), 'Ready · High Jab')
        self.assertEqual(localize_engine_text('하이 잽(5속도)', 'en', names), 'High Jab (speed 5)')
        self.assertEqual(localize_engine_text('하이 잽(5속도)', 'ja', {'하이 잽': 'ハイ・ジャブ'}), 'ハイ・ジャブ(速度5)')

    def test_untranslatable_prompt_falls_back_to_generic_prompt_with_card_name(self):
        prompt = localize_prompt(
            '시험용 효과 문구', 'en', {},
            kind='optional_effect', source={'card_code': 'TST-PS1'},
        )
        self.assertEqual(prompt, "Activate 「Charge」's effect?")
        self.assertEqual(localize_prompt('무엇인가 고른다', 'ja', {}), '選択してください')

    def test_session_payload_actions_decision_and_players(self):
        payload = {
            'state': {'players': {
                'p1': {
                    'name': '플레이어1(루트)',
                    'character': {'id': self.character.id, 'name': '루트'},
                    'zones': {'hand': [{'card_id': self.card.id, 'name': '하이 잽'}]},
                },
            }},
            'pending_decision': {
                'prompt': '시험용 효과 문구', 'kind': 'optional_effect',
                'source': {'card_code': 'TST-PS1'},
                'options': [{'id': 'activate', 'label': '발동'}, {'id': 'decline', 'label': '발동하지 않음'}],
            },
            'legal_actions': [
                {'type': 'ready_card', 'label': '레디 · 하이 잽', 'payload': {'label': '레디 · 하이 잽'}},
                {'type': 'submit_decision', 'label': '시험용 효과 문구',
                 'options': [{'id': 'decline', 'label': '발동하지 않음'}]},
            ],
        }
        localize_engine_text_fields(payload, 'en')
        actions = payload['legal_actions']
        self.assertEqual(actions[0]['label'], 'Ready · High Jab')
        self.assertEqual(actions[0]['payload'], {'label': '레디 · 하이 잽'})  # 엔진에 되돌려 보내는 값은 그대로
        self.assertEqual(actions[1]['label'], "Activate 「Charge」's effect?")
        self.assertEqual(actions[1]['options'][0]['label'], "Don't activate")
        self.assertEqual(actions[1]['options'][0]['id'], 'decline')
        self.assertEqual(payload['pending_decision']['options'][0]['label'], 'Activate')
        player = payload['state']['players']['p1']
        self.assertEqual(player['character']['name'], 'Route')
        self.assertEqual(player['name'], 'Player 1 (Route)')

    def test_korean_payload_is_untouched(self):
        payload = {'legal_actions': [{'type': 'ready_card', 'label': '레디 · 하이 잽'}]}
        localize_engine_text_fields(payload, 'ko')
        self.assertEqual(payload['legal_actions'][0]['label'], '레디 · 하이 잽')

    def test_event_card_names_effect_label_and_decision_choices(self):
        discarded = localize_event_payload('card_discarded', {'card_id': self.card.id, 'card_label': '하이 잽'}, 'en')
        self.assertEqual(discarded['card_label'], 'High Jab')
        effect = localize_event_payload(
            'effect_resolved', {'card_id': self.card.id, 'card_label': '하이 잽', 'effect_label': '시험용 효과 설명'}, 'ja',
        )
        self.assertEqual(effect['card_label'], 'ハイ・ジャブ')
        self.assertEqual(effect['effect_label'], '効果発動')
        resolved = localize_event_payload('decision_resolved', {
            'prompt': '비용을 지불하지 않음', 'selected_options': [{'id': 'decline', 'label': '발동하지 않음'}],
        }, 'en')
        self.assertEqual(resolved['prompt'], "Don't pay the cost")
        self.assertEqual(resolved['selected_options'][0]['label'], "Don't activate")


class EffectTextTableTests(TestCase):
    """카드 DSL의 능력 라벨·결정 문구는 번역표(play_effect_text.json)로 문장째 옮긴다."""

    TABLE = {
        '루멘 존에 1장만 배치할 수 있다.': ['Only 1 can be placed in the Lumen Zone.', 'ルーメンゾーンに1枚のみ配置できる。'],
        '브레이크할  기술을 선택하세요.': ['Choose a Technique to break.', 'ブレイクする技を選んでください。'],
    }

    def setUp(self):
        self.saved = dict(play_i18n._EFFECT_TEXT)
        play_i18n._EFFECT_TEXT.update(
            source={play_i18n._effect_key(ko): values for ko, values in self.TABLE.items()}, at=0.0, tables={},
        )

    def tearDown(self):
        play_i18n._EFFECT_TEXT.clear()
        play_i18n._EFFECT_TEXT.update(self.saved, tables={}, at=0.0)

    def test_labels_and_prompts_use_whole_sentence_translations(self):
        self.assertEqual(
            localize_engine_text('루멘 존에 1장만 배치할 수 있다.', 'en'), 'Only 1 can be placed in the Lumen Zone.',
        )
        # 공백 차이(정의의 끝 공백·두 칸 띄움)는 무시한다.
        self.assertEqual(localize_prompt('브레이크할 기술을 선택하세요. ', 'ja', {}), 'ブレイクする技を選んでください。')
        payload = {'pending_decision': {
            'prompt': '브레이크할 기술을 선택하세요.',
            'options': [{'id': 'a', 'label': '루멘 존에 1장만 배치할 수 있다.'}],
        }}
        localize_engine_text_fields(payload, 'en')
        self.assertEqual(payload['pending_decision']['prompt'], 'Choose a Technique to break.')
        self.assertEqual(payload['pending_decision']['options'][0]['label'], 'Only 1 can be placed in the Lumen Zone.')
        effect = localize_event_payload('effect_resolved', {'effect_label': '루멘 존에 1장만 배치할 수 있다.'}, 'ja')
        self.assertEqual(effect['effect_label'], 'ルーメンゾーンに1枚のみ配置できる。')

    def test_sentence_without_translation_is_not_mixed_word_by_word(self):
        def by_terms(text, language):
            return text.replace('루멘', 'Lumen').replace('기술', 'Technique')

        with mock.patch.object(play_i18n, 'translate_text_by_parts', side_effect=by_terms):
            self.assertEqual(localize_engine_text('루멘 존의 기술을 고른다', 'en'), '루멘 존의 기술을 고른다')
            self.assertEqual(localize_engine_text('루멘 · 기술', 'en'), 'Lumen · Technique')

    def test_unavailable_options_label_and_reason(self):
        payload = {'pending_decision': {
            'prompt': '브레이크할 기술을 선택하세요.',
            'options': [],
            'unavailable_options': [
                {'id': 'a', 'label': '루멘 존에 1장만 배치할 수 있다.', 'reason': '조건에 맞는 카드가 부족합니다(1/2).'},
                {'id': 'b', 'label': '발동', 'reason': '「하이 잽」, 「로우 킥」 효과로 브레이크할 수 없습니다.'},
                {'id': 'c', 'label': '발동', 'reason': '효과로 버릴 수 없는 카드뿐입니다.'},
                {'id': 'd', 'label': '발동', 'reason': '조건에 맞는 카드가 없습니다.'},
            ],
        }}
        with mock.patch.object(play_i18n, '_card_names', return_value={'하이 잽': 'High Jab'}):
            localize_engine_text_fields(payload, 'en')
        options = payload['pending_decision']['unavailable_options']
        self.assertEqual(options[0]['label'], 'Only 1 can be placed in the Lumen Zone.')
        self.assertEqual(options[0]['reason'], 'Not enough cards meet the condition (1/2).')
        self.assertEqual(options[1]['reason'], "Can't be broken because of 「High Jab」, 「로우 킥」.")
        self.assertEqual(options[2]['reason'], 'Every candidate is protected from being discarded by an effect.')
        self.assertEqual(options[3]['reason'], 'No card meets the condition.')
        self.assertEqual(
            play_i18n.localize_unavailable_reason('효과로 브레이크할 수 없는 카드뿐입니다.', 'ja'),
            '効果でブレイクできないカードしかありません。',
        )


class EffectTextFileTests(SimpleTestCase):
    """배포되는 번역표 파일 자체의 형식."""

    def test_every_row_has_english_and_japanese_without_korean(self):
        rows = json.loads(play_i18n.EFFECT_TEXT_PATH.read_text(encoding='utf-8'))
        self.assertGreater(len(rows), 1000)
        token = re.compile(r'\[\[[^\]]+\]\]')
        for ko, values in rows.items():
            with self.subTest(ko=ko):
                self.assertEqual(len(values), 2)
                for text in values:
                    self.assertTrue(text.strip())
                    self.assertNotRegex(token.sub('', text), '[가-힣]')
                    self.assertEqual(sorted(token.findall(text)), sorted(token.findall(ko)))


class PlayLanguageQueryTests(TestCase):
    def test_lang_query_sets_session_language_and_page_lang(self):
        response = self.client.get(reverse('battlelog:play'), {'lang': 'ja'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session[LANGUAGE_SESSION_KEY], 'ja')
        self.assertContains(response, 'lang="ja"')

    def test_unknown_lang_is_ignored(self):
        self.client.get(reverse('battlelog:play'), {'lang': 'xx'})
        self.assertNotIn(LANGUAGE_SESSION_KEY, self.client.session)
