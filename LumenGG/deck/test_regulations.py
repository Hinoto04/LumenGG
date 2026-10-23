import copy
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from card.models import Card, Character
from .models import Deck, CardInDeck, ReserveCardInDeck, Regulation, RegulationVersion
from .validation import snapshot_deck, baseline, validate
from .regulations import DEFAULT_RULES


class RegulationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('player')
        Character.objects.create(name='Neutral', datas={})
        self.character = Character.objects.create(name='Tester', datas={'hand': {'5000': 5}})
        self.trait = Card.objects.create(name='Original', code='T-PS-001', type='특성', character=self.character,
            effect_definition={'deck_rules': {'main_size': 20}})
        self.other = Card.objects.create(name='Alternative', code='T-PS-002', type='특성', character=self.character,
            effect_definition={'deck_rules': {'main_size': 24}})
        self.cards = [Card.objects.create(name=f'Technique {n}', code=f'T-AT-{n:03}', type='공격', character=self.character) for n in range(25)]
        self.deck = Deck.objects.create(name='Test', author=self.user, character=self.character, trait_card=self.trait, schema_version=2)
        CardInDeck.objects.bulk_create([CardInDeck(deck=self.deck, card=c, hand=int(i < 5), side=int(i >= 14)) for i, c in enumerate(self.cards[:20])])

    def snapshot(self, **rules):
        result = snapshot_deck(self.deck)
        result['regulation_rules'] = {**DEFAULT_RULES, **rules}
        return result

    def codes(self, result):
        return {i['code'] for i in result['issues']}

    def test_selected_trait_is_not_merged_with_alternative(self):
        self.assertTrue(validate(self.snapshot(), stage='setup')['is_valid'])

    def test_registered_and_active_scopes(self):
        reserve = self.cards[20]
        ReserveCardInDeck.objects.create(deck=self.deck, card=reserve)
        rule = {'card_ids': [self.cards[0].pk, reserve.pk], 'scope': 'registered'}
        snap = self.snapshot(reserve_limit=1, combinations=[rule])
        self.assertIn('restricted_combination', self.codes(validate(snap)))
        snap['regulation_rules']['combinations'][0]['scope'] = 'active'
        self.assertTrue(validate(snap)['is_valid'])

    def test_trait_size_change_and_type_limits(self):
        ReserveCardInDeck.objects.create(deck=self.deck, card=self.other)
        for c in self.cards[20:24]:
            ReserveCardInDeck.objects.create(deck=self.deck, card=c)
        snap = self.snapshot(reserve_limit=5, technique_swap_limit=4, trait_swap_limit=1)
        active = baseline(snap)
        active['trait_card_id'] = self.other.pk
        active['cards'].extend({'card_id': c.pk, 'count': 1, 'hand': 0, 'side': 1} for c in self.cards[20:24])
        result = validate(snap, stage='setup', active=active)
        self.assertTrue(result['is_valid'], result)
        self.assertEqual(result['swap_counts'], {'technique': 4, 'trait': 1, 'ultimate': 0})
        snap['regulation_rules']['trait_swap_limit'] = 0
        self.assertIn('trait_swap_limit', self.codes(validate(snap, stage='replacement', active=active)))

    def test_unregistered_card_and_draft_warning(self):
        snap = self.snapshot()
        active = baseline(snap)
        active['cards'][0]['card_id'] = self.cards[24].pk
        self.assertIn('unknown_card', self.codes(validate(snap, active=active)))
        snap['cards'] = snap['cards'][:3]
        self.assertTrue(validate(snap, stage='draft')['is_valid'])
        self.assertFalse(validate(snap)['is_valid'])

    def test_unrestricted_deck_skips_composition_and_reserve_limits(self):
        ReserveCardInDeck.objects.create(deck=self.deck, card=self.cards[20])
        snap = snapshot_deck(self.deck)
        snap['cards'] = snap['cards'][:3]
        self.assertIsNone(snap['regulation_rules'])
        self.assertTrue(validate(snap)['is_valid'])

    def test_immutable_policy_and_explicit_swap_limits(self):
        regulation = Regulation.objects.create(name='Local', owner=self.user)
        with self.assertRaises(ValidationError):
            RegulationVersion.objects.create(regulation=regulation, version='bad', rules={'reserve_limit': 5})
        version = RegulationVersion.objects.create(regulation=regulation, version='1', rules=DEFAULT_RULES)
        version.rules['reserve_limit'] = 5
        with self.assertRaises(ValidationError):
            version.save()
