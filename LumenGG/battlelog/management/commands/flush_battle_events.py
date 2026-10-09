from django.core.management.base import BaseCommand
import time
from django.db import close_old_connections

from battlelog.event_buffer import flush_pending_battle_events, flush_session_events


class Command(BaseCommand):
    help = 'Redis에 임시 저장된 계산기 로그를 DB BattleEvent로 일괄 저장합니다.'

    def add_arguments(self, parser):
        parser.add_argument('--watch', action='store_true', help='Flush continuously every ten seconds.')
        parser.add_argument('--session-id', type=int, help='특정 계산기 세션의 로그만 저장합니다.')
        parser.add_argument('--limit', type=int, help='처리할 세션 수를 제한합니다.')

    def handle(self, *args, **options):
        if options.get('watch'):
            while True:
                close_old_connections()
                count = flush_pending_battle_events(options.get('limit'))
                self.stdout.write(f'Flushed {count} calculator events')
                time.sleep(10)
        session_id = options.get('session_id')
        if session_id:
            flushed_count = flush_session_events(session_id)
        else:
            flushed_count = flush_pending_battle_events(options.get('limit'))
        self.stdout.write(self.style.SUCCESS(f'{flushed_count}개의 계산기 로그를 DB에 저장했습니다.'))
