"""부쿠키 「프로스트 베일」 계산기 패시브: 서리 토글과 핀프와 같은 보호막 조작."""
from importlib import import_module

from django.apps import apps
from django.test import TestCase

from battlelog.services import create_standalone_session, initial_passive_state_for_character, perform_session_action
from battlelog.shields import SHIELD_KEY, shield_amount, supports_shield
from card.models import Card, Character
from deck.traits import setup_character
from mobile_api.passives import native_passive

migration = import_module('card.migrations.0033_bukuki_trait_passive_ui')


class BukukiPassiveTests(TestCase):
    def setUp(self):
        self.bukuki = Character.objects.create(name='부쿠키', datas={'hand': {'5000': 6}}, description='', group='', img='')
        self.other = Character.objects.create(name='루트', datas={'hand': {'5000': 6}}, description='', group='', img='')
        self.trait = Card.objects.create(name='프로스트 베일', code=migration.BUKUKI_TRAIT_CODE, character=self.bukuki, type='특성')
        migration.apply(apps, None)
        self.trait.refresh_from_db()
        self.character = setup_character(self.bukuki, self.trait)

    def test_frost_toggle_and_shield_are_configured(self):
        self.assertTrue(supports_shield(self.character))
        controls = native_passive(self.character)['controls']
        self.assertEqual([(c['type'], c['key']) for c in controls], [('toggle', 'frost')])
        self.assertEqual(controls[0]['labels'], {'ko': '서리', 'en': 'Frost', 'ja': '霜'})
        self.assertEqual(initial_passive_state_for_character(self.character)[SHIELD_KEY]['value'], 0)

    def test_migration_keeps_manual_values_and_is_idempotent(self):
        manual = {'supports_shield': False, 'initial_hp': 5000}
        Card.objects.filter(pk=self.trait.pk).update(trait_config=manual)
        migration.apply(apps, None)
        migration.apply(apps, None)
        self.trait.refresh_from_db()
        self.assertFalse(self.trait.trait_config['supports_shield'])
        self.assertEqual(self.trait.trait_config['initial_hp'], 5000)
        self.assertEqual(self.trait.trait_config['battle_passive_ui'], migration.BUKUKI_PASSIVE_UI)

    def test_revert_removes_only_added_values(self):
        Card.objects.filter(pk=self.trait.pk).update(trait_config={**self.trait.trait_config, 'initial_hp': 5000})
        migration.revert(apps, None)
        self.trait.refresh_from_db()
        self.assertEqual(self.trait.trait_config, {'initial_hp': 5000})

    def test_session_frost_toggle_and_shield_absorb_damage(self):
        other_trait = Card.objects.create(name='차지', code='TST-PS-001', character=self.other, type='특성')
        session = create_standalone_session('A', 'B', self.bukuki, self.other, trait_ids=[self.trait.id, other_trait.id])
        self.assertEqual(shield_amount(session.player1_passive_state), 0)

        def act(action, **kwargs):
            return perform_session_action(session, {'action': action, 'target': 'p1', **kwargs}, control_token=session.control_token)

        session = act('passive', key='frost', value=True)
        self.assertIs(session.player1_passive_state['frost']['value'], True)
        session = act('shield', amount=300)
        session = act('hp', amount=-500)
        self.assertEqual(session.player1_hp, 4800)
        self.assertEqual(shield_amount(session.player1_passive_state), 0)
        session = act('shield', amount=200)
        session = act('shield_reset')
        self.assertEqual(shield_amount(session.player1_passive_state), 0)
