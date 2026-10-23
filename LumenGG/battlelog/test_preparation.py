import copy
import uuid
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import PermissionDenied
from deck import test_regulations as fixtures
from deck.validation import baseline
from .preparation import create_preparation, apply_preparation, preparation_view, next_preparation
from .simulator_services import create_simulator_session, serialize_simulator_session
from .preparation_services import perform_simulator_preparation


class PreparationTests(TestCase):
    setUp = fixtures.RegulationTests.setUp
    snapshot = fixtures.RegulationTests.snapshot

    def body(self, preparation, action='ready', **kwargs):
        return {'request_id': str(uuid.uuid4()), 'expected_version': preparation['version'], 'preparation_action': action, **kwargs}

    def test_private_edits_and_simultaneous_confirmation_are_idempotent(self):
        preparation = create_preparation({'p1': self.snapshot(), 'p2': self.snapshot()})
        first = self.body(preparation)
        preparation, started = apply_preparation(preparation, 'p1', first)
        self.assertFalse(started)
        public = preparation_view(preparation, 'viewer')
        self.assertEqual(public['players']['p1'], {'ready': True})
        self.assertNotIn('registered', preparation_view(preparation, 'p2')['players']['p1'])
        same, started = apply_preparation(preparation, 'p1', first)
        self.assertIs(same, preparation)
        second = self.body(preparation)
        preparation, started = apply_preparation(preparation, 'p2', second)
        self.assertTrue(started)
        self.assertEqual(preparation['status'], 'playing')
        _, repeated_start = apply_preparation(preparation, 'p2', second)
        self.assertFalse(repeated_start)

    def test_cancel_and_baseline_restore(self):
        preparation = create_preparation({'p1': self.snapshot(), 'p2': self.snapshot()})
        preparation, _ = apply_preparation(preparation, 'p1', self.body(preparation))
        preparation, _ = apply_preparation(preparation, 'p1', self.body(preparation, 'cancel'))
        self.assertFalse(preparation['players']['p1']['ready'])
        preparation['players']['p1']['active']['cards'].pop()
        restored = next_preparation(preparation)
        self.assertEqual(restored['players']['p1']['active'], baseline(self.snapshot()))

    def test_simulator_has_no_cards_or_effects_before_confirmation(self):
        session = create_simulator_session('A', 'B', self.deck, self.deck)
        self.assertEqual(session.document['state']['players']['p1']['hp'], 0)
        self.assertFalse(session.document['state']['players']['p1']['zones']['passive'])
        for side in ('p1', 'p2'):
            body = self.body(session.document['preparation'])
            body.update(seat=side, seat_token=getattr(session, 'player1_token' if side == 'p1' else 'player2_token'))
            session = perform_simulator_preparation(session, body)
        player = session.document['state']['players']['p1']
        self.assertEqual(player['hp'], 5000)
        self.assertEqual([c['card_id'] for c in player['zones']['passive']], [self.trait.pk])
        public = serialize_simulator_session(session)
        self.assertNotIn('registered', public['preparation']['players']['p1'])
        with self.assertRaises(PermissionDenied):
            perform_simulator_preparation(session, {**self.body(session.document['preparation']), 'seat': 'p2', 'seat_token': session.player1_token})

    def test_stale_edit_does_not_change_ready_player(self):
        preparation = create_preparation({'p1': self.snapshot(), 'p2': self.snapshot()})
        old = self.body(preparation, 'save')
        preparation, _ = apply_preparation(preparation, 'p1', self.body(preparation))
        with self.assertRaises(ValueError):
            apply_preparation(preparation, 'p2', old)

    def test_public_swaps_never_reveal_opening_placement(self):
        preparation = create_preparation({'p1': self.snapshot(swaps_public=True), 'p2': self.snapshot()})
        preparation, _ = apply_preparation(preparation, 'p1', self.body(preparation))
        self.assertNotIn('active', preparation_view(preparation)['players']['p1'])
        preparation, _ = apply_preparation(preparation, 'p2', self.body(preparation))
        public = preparation_view(preparation)['players']['p1']['active']
        self.assertTrue(public['cards'])
        self.assertTrue(all(set(row) == {'card_id', 'count'} for row in public['cards']))

    def test_automatic_engine_starts_once_after_both_players_confirm(self):
        from .models import RulesetRelease
        from .game.catalog import build_ruleset_snapshot
        from .game.engine import IllegalAction
        from .automatic_services import perform_automatic_command, reconcile_automatic_session
        release = RulesetRelease.objects.create(version='test-selected-trait', content_hash='f' * 64, snapshot=build_ruleset_snapshot())
        with patch('battlelog.automatic_services.automatic_mode_release', return_value=release):
            session = create_simulator_session('A', 'B', self.deck, self.deck, mode='automatic')
        self.assertNotIn('engine', session.document['state'])
        session = reconcile_automatic_session(session)
        self.assertEqual(session.mode, 'automatic')
        with self.assertRaises(IllegalAction):
            perform_automatic_command(session, {'command_id': 'too-early', 'action_id': 'any', 'expected_version': session.version, 'seat': 'p1', 'seat_token': session.player1_token})
        session.refresh_from_db()
        self.assertEqual(session.mode, 'automatic')
        for side in ('p1', 'p2'):
            request = {**self.body(session.document['preparation']), 'seat': side, 'seat_token': getattr(session, 'player1_token' if side == 'p1' else 'player2_token')}
            session = perform_simulator_preparation(session, request)
        self.assertIn('engine', session.document['state'])
        self.assertEqual(len([e for e in session.document['events'] if e.get('type') == 'automatic_game_started']), 1)
        version = session.version
        session = perform_simulator_preparation(session, request)
        self.assertEqual(session.version, version)
