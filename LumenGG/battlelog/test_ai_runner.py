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


class AIReadyThinkTests(TestCase):
    """AI는 레디 페이즈가 열리자마자 레디하지 않고 잠시 '생각'한다(LUMEN_AI_READY_DELAY)."""

    setUp = engine_tests.SimulatorAIHTTPTests.setUp
    new_ai_session = AIRunnerTests.new_ai_session
    human_pass = AIRunnerTests.human_pass

    def test_ai_waits_before_its_ready_but_not_before_other_actions(self):
        clock = {'now': 0.0}
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            clock['now'] += seconds

        session = self.new_ai_session()
        readied = False
        with patch('battlelog.automatic_services.time.monotonic', side_effect=lambda: clock['now']), \
                patch('battlelog.automatic_services.time.sleep', side_effect=fake_sleep), \
                patch('battlelog.automatic_services._ready_think_seconds', return_value=3.0):
            for _step in range(12):
                before = len((session.document or {}).get('events') or [])
                session = automatic_services.advance_ai_session(session, think=True)
                events = ((session.document or {}).get('events') or [])[before:]
                if any(e.get('type') == 'card_readied' and e.get('actor') == 'p2' for e in events):
                    readied = True
                    break
                session = self.human_pass(session)

        self.assertTrue(readied)
        self.assertEqual(len(sleeps), 1)
        self.assertAlmostEqual(sleeps[0], 3.0)

    def test_without_think_the_ai_never_sleeps(self):
        session = self.human_pass(self.new_ai_session())
        with patch('battlelog.automatic_services.time.sleep') as sleep:
            automatic_services.advance_ai_session(session)
        sleep.assert_not_called()


class AIReadyWaitTests(SimpleTestCase):
    NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def state(self, seconds_left=None, paused=False):
        clock = {} if seconds_left is None else {
            'deadline': (self.NOW + timedelta(seconds=seconds_left)).isoformat(), 'paused': paused,
        }
        return {'turn': 1, 'engine': {'clock': clock}}

    def test_wait_is_capped_at_half_the_ready_clock(self):
        wait = automatic_services.ai_ready_wait

        self.assertEqual(wait(self.state(), 'p2', 3.0, now=self.NOW), 3.0)
        self.assertEqual(wait(self.state(4), 'p2', 3.0, now=self.NOW), 2.0)
        self.assertEqual(wait(self.state(-1), 'p2', 3.0, now=self.NOW), 0.0)
        self.assertEqual(wait(self.state(4, paused=True), 'p2', 3.0, now=self.NOW), 3.0)
        self.assertEqual(wait(self.state(), 'p2', -1.0, now=self.NOW), 0.0)

    def test_think_time_is_stable_per_turn_and_can_be_turned_off(self):
        session = LumenSimulatorSession(id=5)
        think = automatic_services._ready_think_seconds

        with self.settings(LUMEN_AI_READY_DELAY=(2.0, 4.0)):
            first = think(session, {'turn': 1}, 'p2')
            self.assertEqual(first, think(session, {'turn': 1}, 'p2'))
            self.assertTrue(2.0 <= first <= 4.0)
        with self.settings(LUMEN_AI_READY_DELAY=(0, 0)):
            self.assertEqual(think(session, {'turn': 1}, 'p2'), 0.0)
