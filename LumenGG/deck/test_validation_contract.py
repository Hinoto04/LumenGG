import json
from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase
from .validation import validate


class SharedValidationContractTests(SimpleTestCase):
    def test_shared_web_app_server_cases(self):
        cases = json.loads((Path(settings.BASE_DIR) / 'content/deck-validation-cases.json').read_text(encoding='utf-8'))
        for case in cases:
            with self.subTest(name=case['name']):
                result = validate(case['snapshot'], stage=case['stage'], active=case['active'])
                self.assertEqual(result['is_valid'], case['valid'], result)
                self.assertEqual(sorted(set(i['code'] for i in result['issues'])), sorted(case['codes']))
