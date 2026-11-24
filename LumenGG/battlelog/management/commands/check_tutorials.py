"""튜토리얼 각본이 규칙 릴리스에서 그대로 진행되는지 확인한다(읽기 전용).

    manage.py check_tutorials                         # 공개된 자동 규칙 릴리스, 모든 단원
    manage.py check_tutorials --release 2026.11.1     # 발행 전 릴리스 확인
    manage.py check_tutorials --setup candidate.json  # 카드 배정 후보 확인 {lesson_id: setup}

카드·캐릭터·릴리스를 읽기만 하고 세션이나 데이터를 만들지 않는다. 실패하면 종료 코드 1.
"""

import json
from contextlib import nullcontext
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.test.utils import override_settings

from battlelog.automatic_services import automatic_mode_release
from battlelog.models import RulesetRelease
from battlelog.tutorial import LESSONS, TutorialUnavailable
from battlelog.tutorial.runtime import simulate_lesson


class Command(BaseCommand):
    help = '튜토리얼 각본을 규칙 릴리스로 끝까지 진행해 본다(읽기 전용).'

    def add_arguments(self, parser):
        parser.add_argument('--lesson', action='append', help='확인할 단원 id(여러 번 가능). 기본: 전체')
        parser.add_argument('--release', help='RulesetRelease 버전. 기본: 공개된 자동 규칙 릴리스')
        parser.add_argument('--setup', help='카드 배정 JSON 파일 {lesson_id: {characters, cards}}')

    def handle(self, *args, **options):
        if options.get('release'):
            release = RulesetRelease.objects.filter(version=options['release']).first()
            if release is None:
                raise CommandError(f'릴리스를 찾을 수 없습니다: {options["release"]}')
        else:
            release = automatic_mode_release()
            if release is None:
                raise CommandError('검증된 자동 규칙 릴리스가 없습니다.')
        overrides = {}
        if options.get('setup'):
            overrides = json.loads(Path(options['setup']).read_text(encoding='utf-8'))
        lesson_ids = options.get('lesson') or list(LESSONS)
        failed = False
        with override_settings(LUMEN_TUTORIAL_SETUP=overrides) if overrides else nullcontext():
            for lesson_id in lesson_ids:
                try:
                    result = simulate_lesson(lesson_id, release)
                except TutorialUnavailable as exc:
                    self.stdout.write(self.style.WARNING(f'{lesson_id}: 건너뜀 — {exc}'))
                    continue
                line = (
                    f'{lesson_id} [{release.version}]: {result["status"]} '
                    f'단계 {", ".join(result["steps"]) or "없음"} / 판정 {result["results"]}'
                )
                if result['status'] == 'completed':
                    self.stdout.write(self.style.SUCCESS(line))
                else:
                    failed = True
                    self.stdout.write(self.style.ERROR(f'{line}\n  사유: {result["reason"]}'))
        if failed:
            raise SystemExit(1)

