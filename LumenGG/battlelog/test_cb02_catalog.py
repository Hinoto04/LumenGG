import copy

from django.test import SimpleTestCase

from battlelog.game.drafts import build_effect_draft
from battlelog.game.review import review_automatic_definition
from battlelog.game.schema import validate_effect_definition
from common.localization_batches.batch_cb02_20261023 import CARDS


class CB02CatalogEffectTests(SimpleTestCase):
    def test_every_cb02_card_compiles_and_passes_deterministic_review(self):
        self.assertEqual(len(CARDS), 29)
        for row in CARDS:
            card = row['snapshot']
            with self.subTest(code=card['code']):
                definition = build_effect_draft(
                    card['code'], card['text'], detail_text=card['detail_text'],
                    qna_ids=row['qna_ids'],
                )
                self.assertTrue(definition['abilities'])
                self.assertTrue(all(a.get('draft_compiled') for a in definition['abilities']))
                result = review_automatic_definition(
                    definition, card_has_text=True, card_snapshot=card,
                )
                self.assertTrue(result.passed, result.as_dict())
                self.assertEqual(
                    {a.ability_id for a in result.abilities},
                    {a['id'] for a in definition['abilities']},
                )
                for ability in result.abilities:
                    self.assertGreaterEqual(len(ability.scenarios), 3)
                    self.assertTrue(all(s['passed'] for s in ability.scenarios))
                definition['review_evidence'] = result.as_dict()
                definition['reviewed'] = True
                definition['draft'] = False
                for ability in definition['abilities']:
                    ability['draft'] = False
                self.assertEqual(validate_effect_definition(
                    definition, require_coverage=True, card_has_text=True,
                ), [])

    def test_compiler_does_not_silently_drop_a_cb02_ability(self):
        for row in CARDS:
            card = row['snapshot']
            definition = build_effect_draft(
                card['code'], card['text'], detail_text=card['detail_text'], qna_ids=row['qna_ids'],
            )
            for index, ability in enumerate(definition['abilities']):
                with self.subTest(code=card['code'], ability=ability['id']):
                    mutated = copy.deepcopy(definition)
                    mutated['abilities'][index]['effects'] = []
                    result = review_automatic_definition(
                        mutated, card_has_text=True, card_snapshot=card,
                    )
                    self.assertFalse(result.passed, result.as_dict())
