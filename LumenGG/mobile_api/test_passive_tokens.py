from django.test import TestCase

from card.models import Card, Character
from mobile_api.passives import native_passive


class CalculatorPassiveTokenTests(TestCase):
    """계산기 카운터: 이름이 맞는 토큰 카드 그림을 붙이고, 요한 예지는 5개까지만 보여 준다."""

    def character(self, name, controls):
        return Character.objects.create(
            name=name, description='', group='', img='',
            datas={'hand': {'5000': 6}, 'battle_passive_ui': {'options': {'controls': controls}}},
        )

    def token(self, character, code, name):
        return Card.objects.create(
            character=character, code=code, name=name, type='토큰',
            img=f'https://images.example.com/{code}.webp', img_sm='', img_mid='',
        )

    def controls(self, character, language='ko'):
        return {control['key']: control for control in native_passive(character, language)['controls']}

    def test_counter_gets_matching_token_card_in_every_language(self):
        delphy = self.character('델피', [
            {'type': 'toggle', 'key': 'down_stance', 'label': '다운 스탠스'},
            {'type': 'counter', 'key': 'garage_token', 'label': '개러지 토큰', 'max': 3},
        ])
        garage = self.token(delphy, 'CB04-TK-001', '「개러지」')
        for language in ('ko', 'en', 'ja'):
            with self.subTest(language=language):
                controls = self.controls(delphy, language)
                self.assertEqual(controls['garage_token']['token'], {'id': garage.id, 'code': 'CB04-TK-001', 'img': garage.img})
                self.assertNotIn('token', controls['down_stance'])

    def test_tokens_match_by_name_and_other_characters_tokens_are_ignored(self):
        tao = self.character('타오', [
            {'type': 'counter', 'key': 'yang_counter', 'label': '양', 'max': 4},
            {'type': 'counter', 'key': 'yin_counter', 'label': '음', 'max': 4},
        ])
        self.token(tao, 'UNC-AT-058', '「음」 토큰')
        self.token(tao, 'UNC-AT-059', '「양」 토큰')
        rin = self.character('린', [{'type': 'counter', 'key': 'ember_token', 'label': '불씨 토큰'}])
        controls = self.controls(tao)
        self.assertEqual(controls['yang_counter']['token']['code'], 'UNC-AT-059')
        self.assertEqual(controls['yin_counter']['token']['code'], 'UNC-AT-058')
        self.assertNotIn('token', self.controls(rin)['ember_token'])

    def test_yohan_foresight_shows_at_most_five(self):
        yohan = self.character('요한', [{'type': 'counter', 'key': 'foresight_counter', 'label': '예지 카운터', 'max': 10}])
        self.token(yohan, 'PMP-CS-009', '「예지」')
        foresight = self.controls(yohan)['foresight_counter']
        self.assertEqual(foresight['max'], 5)
        self.assertEqual(foresight['token']['code'], 'PMP-CS-009')
