"""무영 「밤까치」: 청염 패시브를 유지하면서 핀프와 같은 보호막을 사용한다."""
from importlib import import_module

from django.apps import apps
from django.test import TestCase

from battlelog.services import create_standalone_session, perform_session_action
from battlelog.shields import shield_amount, supports_shield
from card.models import Card, Character
from deck.traits import setup_character

migration = import_module('card.migrations.0034_muyeong_trait_shield')

BLUE_FLAME_UI = {'options': {'title': '청염', 'controls': [
    {'type': 'status', 'key': 'blue_flame', 'label': '청염', 'condition': {'type': 'hpAtMost', 'value': 2500}}]}}


class MuyeongShieldTests(TestCase):
    def setUp(self):
        self.muyeong = Character.objects.create(name='무영', datas={'hand': {'5000': 6}}, description='', group='', img='')
        self.other = Character.objects.create(name='루트', datas={'hand': {'5000': 6}}, description='', group='', img='')
        self.trait = Card.objects.create(
            name='밤까치', code=migration.MUYEONG_TRAIT_CODE, character=self.muyeong, type='특성',
            trait_config={'battle_passive_ui': BLUE_FLAME_UI, 'legacy_character_actions': True, 'supports_shield': False})
        self.other_trait = Card.objects.create(name='차지', code='TST-PS-001', character=self.other, type='특성')

    def test_migration_enables_shield_and_keeps_blue_flame(self):
        self.assertFalse(supports_shield(setup_character(self.muyeong, self.trait)))
        migration.apply(apps, None)
        migration.apply(apps, None)
        self.trait.refresh_from_db()
        self.assertTrue(supports_shield(setup_character(self.muyeong, self.trait)))
        self.assertEqual(self.trait.trait_config['battle_passive_ui'], BLUE_FLAME_UI)
        self.assertTrue(self.trait.trait_config['legacy_character_actions'])
        migration.revert(apps, None)
        self.trait.refresh_from_db()
        self.assertIs(self.trait.trait_config['supports_shield'], False)

    def test_session_shield_absorbs_damage(self):
        migration.apply(apps, None)
        session = create_standalone_session('A', 'B', self.muyeong, self.other, trait_ids=[self.trait.id, self.other_trait.id])

        def act(action, **kwargs):
            return perform_session_action(session, {'action': action, 'target': 'p1', **kwargs}, control_token=session.control_token)

        session = act('shield', amount=300)
        session = act('hp', amount=-500)
        self.assertEqual(session.player1_hp, 4800)
        self.assertEqual(shield_amount(session.player1_passive_state), 0)
        session = act('shield', amount=200)
        session = act('shield_reset')
        self.assertEqual(shield_amount(session.player1_passive_state), 0)
