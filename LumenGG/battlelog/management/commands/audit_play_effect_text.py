"""대전 클라이언트 효과 문구 번역표(play_effect_text.json)에 빠진 문구를 찾는다(읽기 전용).

카드 자동 효과 정의와 활성 규칙 릴리스에 적힌 능력 라벨·결정 문구·선택지 중
한국어가 들어 있는데 번역표에 없는 것을 카드 코드와 함께 보여 준다.
새 카드의 자동 효과를 추가했다면 이 목록을 번역해 번역표에 더한다.
"""
import json
import re

from django.core.management.base import BaseCommand, CommandError

from battlelog.game.catalog import active_ruleset_release
from battlelog.play_i18n import _effect_key, effect_text_source
from card.models import Card

HANGUL = re.compile('[가-힣]')
TEXT_KEYS = ('label', 'prompt')
# 검수 시나리오·초안 원문은 화면에 나오지 않는다.
SKIPPED_KEYS = ('review', 'scenarios', 'draft_text')


def effect_strings(definition):
    """정의 안의 화면 표시 문구(label·prompt) 중 한국어가 들어 있는 것."""
    found = []

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in SKIPPED_KEYS:
                    continue
                if key in TEXT_KEYS and isinstance(item, str) and HANGUL.search(item):
                    found.append(item.strip())
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(definition or {})
    return found


class Command(BaseCommand):
    help = '대전 클라이언트 효과 문구 번역표에 빠진 카드 문구를 찾는다.'

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true', help='빠진 문구를 JSON으로 출력한다.')
        parser.add_argument('--fail', action='store_true', help='빠진 문구가 있으면 실패로 끝낸다.')

    def handle(self, *args, **options):
        missing = {}
        known = effect_text_source()

        def check(code, definition):
            for text in effect_strings(definition):
                if _effect_key(text) not in known:
                    missing.setdefault(text, set()).add(code)

        for card in Card.objects.exclude(effect_definition=None).only('code', 'effect_definition'):
            check(card.code, card.effect_definition)
        release = active_ruleset_release()
        if release:
            for code, card in ((release.snapshot or {}).get('cards') or {}).items():
                check(code, (card or {}).get('effect_definition'))

        rows = [{'ko': text, 'codes': sorted(codes)} for text, codes in sorted(missing.items())]
        if options['json']:
            self.stdout.write(json.dumps(rows, ensure_ascii=False, indent=1))
        else:
            for row in rows:
                self.stdout.write(f"{', '.join(row['codes'])}: {row['ko']}")
            self.stdout.write(f'번역표 {len(known)}개 · 빠진 문구 {len(rows)}개')
        if rows and options['fail']:
            raise CommandError(f'번역표에 빠진 문구가 {len(rows)}개 있습니다.')
