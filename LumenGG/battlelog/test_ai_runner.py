"""사람 수를 먼저 보내고 AI가 나중에 생각하는 구동(ai_runner)과 레디 타이머."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from . import automatic_services
from . import test_automatic_engine as engine_tests
from .ai_runner import _lock_key, _worker, kick_ai
from .game.engine import AutomaticGameEngine, StaleState, acknowledge_clock
from .models import LumenSimulatorSession
from .play_start import start_session
from .test_automatic_engine import attack, base_state, ruleset


class AIRunnerTests(TestCase):
    setUp = engine_tests.SimulatorAIHTTPTests.setUp

    def new_ai_session(self):
        session = start_session(
            self.user, player1_deck_id=self.decks[0].id, player2_deck_id=self.decks[1].id,
            mode='automatic', opponent='ai',
        )
        return LumenSimulatorSession.objects.get(pk=session.pk)

    def human_pass(self, session):
        observation = automatic_services.automatic_observation(session, 'p1')
        # 사람이 할 수 있는 진행 행동 하나(시작 패 확인·페이즈 종료·레디 등)를 한다.
        action = next(
            a for a in observation['legal_actions']
            if a['type'] not in {'pause_clock', 'concede', 'request_rewind', 'resume_clock'}
        )
        return automatic_services.perform_automatic_command(session, {
            'command_id': 'human-pass', 'expected_version': session.version,
            'action_id': action['action_id'], 'selections': {},
            'seat': 'p1', 'seat_token': session.player1_token,
        })

    def test_stale_ai_command_is_chosen_again_instead_of_manual_fallback(self):
        session = self.human_pass(self.new_ai_session())
        original = automatic_services.perform_automatic_command
        calls = {'count': 0}

        def flaky(*args, **kwargs):
            calls['count'] += 1
            if calls['count'] == 1:
                raise StaleState('사람 명령이 먼저 들어왔다')
            return original(*args, **kwargs)

        with patch('battlelog.automatic_services.perform_automatic_command', side_effect=flaky):
            advanced = automatic_services.advance_ai_session(session)

        self.assertEqual(advanced.mode, LumenSimulatorSession.MODE_AUTOMATIC)
        self.assertGreaterEqual(calls['count'], 2)
        self.assertGreater(advanced.version, session.version)

    def test_synchronous_kick_broadcasts_every_ai_command(self):
        session = self.human_pass(self.new_ai_session())

        with patch('battlelog.ai_runner.broadcast_simulator_session') as broadcast:
            kicked = kick_ai(session)

        self.assertEqual(kicked.mode, LumenSimulatorSession.MODE_AUTOMATIC)
        self.assertGreater(broadcast.call_count, 0)
        self.assertEqual(broadcast.call_count, kicked.version - session.version)

    def test_worker_runs_the_loop_and_releases_the_lock(self):
        from django.core.cache import cache

        session = self.new_ai_session()
        with patch('battlelog.ai_runner.broadcast_simulator_session'), \
                patch('battlelog.ai_runner.close_old_connections'):
            from . import ai_runner
            ai_runner._running.add(session.id)
            _worker(session.id)

        self.assertNotIn(session.id, ai_runner._running)
        self.assertIsNone(cache.get(_lock_key(session.id)))

    def test_human_seat_only_games_are_not_kicked(self):
        session = self.new_ai_session()
        session.player2_controller = LumenSimulatorSession.CONTROLLER_HUMAN
        session.save(update_fields=['player2_controller'])

        with patch('battlelog.ai_runner.advance_ai_session') as advance:
            kick_ai(session)

        advance.assert_not_called()


class ReadyClockTests(SimpleTestCase):
    def test_ready_clock_counts_from_the_opponents_ready(self):
        state = base_state([attack('mine', 'p1')], [attack('theirs', 'p2')])
        rules = ruleset(attack('mine', 'p1'), attack('theirs', 'p2'))
        start = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
        engine = AutomaticGameEngine.initialize(state, rules, now=start, seed='clock', settings={'ready_timeout_seconds': 10})
        for side in ('p1', 'p2'):
            action = next(a for a in engine.legal_actions(side) if a['type'] == 'pass_phase')
            engine.submit_action(side, action['action_id'], {}, command_id=f'pass-{side}')

        # AI(p2)가 4초 고민한 뒤 레디한다.
        engine.now = start + timedelta(seconds=4)
        ready = next(a for a in engine.legal_actions('p2') if a['type'] == 'ready_card')
        engine.submit_action('p2', ready['action_id'], {}, command_id='ai-ready')
        clock = engine.engine_state['clock']

        self.assertEqual(clock['owner'], 'p1')
        # 사람 화면에 표시된 순간(1초 뒤)부터 10초.
        shown = start + timedelta(seconds=5)
        self.assertTrue(acknowledge_clock(engine.engine_state, 'p1', clock['id'], shown))
        self.assertEqual(engine.engine_state['clock']['deadline'], (shown + timedelta(seconds=10)).isoformat())
