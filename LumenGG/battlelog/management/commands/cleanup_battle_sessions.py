from django.core.management.base import BaseCommand

from battlelog.services import cleanup_expired_sessions


class Command(BaseCommand):
    help = '만료된 독립 계산기 세션과 보관 기간이 지난 대회 계산기 세션을 삭제합니다.'

    def handle(self, *args, **options):
        deleted_count = cleanup_expired_sessions()
        self.stdout.write(self.style.SUCCESS(f'{deleted_count}개의 계산기 관련 객체를 삭제했습니다.'))
