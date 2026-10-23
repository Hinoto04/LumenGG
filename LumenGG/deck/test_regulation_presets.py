import copy
from io import StringIO
from itertools import combinations

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from card.models import Card, Character
from .models import Regulation, RegulationVersion
from .presets import load_preset, publish_preset, rules_for_preset
from .regulations import DEFAULT_RULES
from .validation import card_snapshot, validate


class December2026RegulationTests(TestCase):
    def setUp(self):
        self.preset = load_preset('2026-12')
        self.character = Character.objects.create(name='Test', datas={})
        references = self.preset['banned_cards'] + [c for group in self.preset['choose_one_groups'] for c in group['cards']]
        self.cards = {}
        for reference in references:
            if reference['code'] not in self.cards:
                self.cards[reference['code']] = Card.objects.create(
                    code=reference['code'], name=reference['name'], character=self.character, type='공격',
                )
        self.trait = Card.objects.create(code='TEST-PS-001', name='Test trait', character=self.character, type='특성')
        self.rules = rules_for_preset(self.preset)

    def issues(self, codes, reserve=()):
        rows = lambda entries: [{'card_id': self.cards[c].pk, 'count': 1, 'hand': 0, 'side': 0} for c in entries]
        snapshot = {
            'character_id': self.character.pk,
            'character': {'id': self.character.pk, 'name': self.character.name, 'datas': {}},
            'trait_card_id': self.trait.pk,
            'cards': rows(codes),
            'reserve_cards': [{'card_id': self.cards[c].pk, 'count': 1} for c in reserve],
            'catalog': {str(c.pk): card_snapshot(c) for c in [*self.cards.values(), self.trait]},
            'regulation_rules': {**self.rules, 'reserve_limit': len(reserve)},
        }
        return [i for i in validate(snapshot)['issues'] if i['code'] in ('banned_card', 'restricted_combination')]

    def test_every_choose_one_pair_is_restricted_and_every_single_is_permitted(self):
        self.assertEqual(len(self.preset['choose_one_groups']), 12)
        self.assertEqual(len(self.rules['combinations']), 29)
        self.assertEqual(len(self.cards), 31)
        for group in self.preset['choose_one_groups']:
            codes = [c['code'] for c in group['cards']]
            for code in codes:
                with self.subTest(group=group['label'], single=code):
                    self.assertEqual(self.issues([code]), [])
            for pair in combinations(codes, 2):
                with self.subTest(group=group['label'], pair=pair):
                    issues = self.issues(pair)
                    self.assertTrue(issues)
                    self.assertTrue(all(i['code'] == 'restricted_combination' for i in issues))

    def test_ban_and_registered_scope_apply_across_main_and_reserve(self):
        self.assertEqual([i['code'] for i in self.issues(['LMI-AT-027'])], ['banned_card'])
        self.assertEqual([i['code'] for i in self.issues([], ['LMI-AT-027'])], ['banned_card'])
        self.assertEqual([i['code'] for i in self.issues(['AWL-AT-013'], ['ST1-007'])], ['restricted_combination'])

    def test_publishing_is_common_idempotent_and_does_not_apply_errata(self):
        Card.objects.create(code='CB03-AT-007', name='네메시스', character=self.character,
            effect_definition={'abilities': [], 'original': True})
        before = list(Card.objects.order_by('pk').values())
        version, created = publish_preset('2026-12')
        self.assertTrue(created)
        self.assertEqual(version.regulation.name, '26.12 금제')
        self.assertIsNone(version.regulation.owner_id)
        self.assertEqual(version.effective_date.isoformat(), '2026-12-01')
        self.assertEqual(version.rules['reserve_limit'], 0)
        self.assertFalse(version.rules['reserve_public'])
        self.assertEqual({r['scope'] for r in version.rules['bans'] + version.rules['combinations']}, {'registered'})
        repeated, created = publish_preset('2026-12')
        self.assertFalse(created)
        self.assertEqual(repeated.pk, version.pk)
        self.assertEqual(before, list(Card.objects.order_by('pk').values()))

    def test_missing_card_or_mismatched_name_never_publishes_partial_policy(self):
        preset = copy.deepcopy(self.preset)
        preset['banned_cards'][0]['name'] = 'Not this card'
        with self.assertRaises(ValidationError):
            rules_for_preset(preset)
        self.cards['LMI-AT-027'].delete()
        with self.assertRaises(ValidationError):
            publish_preset('2026-12')
        self.assertFalse(Regulation.objects.filter(name='26.12 금제').exists())

    def test_existing_different_version_is_never_overwritten(self):
        regulation = Regulation.objects.create(name='26.12 금제')
        original = RegulationVersion.objects.create(regulation=regulation, version='1', rules=DEFAULT_RULES)
        with self.assertRaises(ValidationError):
            publish_preset('2026-12')
        original.refresh_from_db()
        self.assertEqual(original.rules, DEFAULT_RULES)

    def test_command_dry_run_has_no_writes(self):
        output = StringIO()
        call_command('publish_regulation', '2026-12', dry_run=True, stdout=output)
        self.assertIn('택1 12묶음 / 제한 조합 29개', output.getvalue())
        self.assertFalse(Regulation.objects.filter(name='26.12 금제').exists())
