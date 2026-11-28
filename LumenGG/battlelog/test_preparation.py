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
        # 다른 사람에게는 준비 여부와 덱의 캐릭터만 보인다(덱 구성·손패는 감춘다).
        self.assertEqual(set(public['players']['p1']), {'ready', 'character'})
        self.assertTrue(public['players']['p1']['ready'])
        rival = preparation_view(preparation, 'p2')['players']['p1']
        self.assertNotIn('registered', rival)
        self.assertNotIn('active', rival)
        self.assertEqual(rival['character']['name'], self.snapshot()['character']['name'])
        self.assertNotIn('datas', rival['character'])
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
        # 세션에 고정한 AI 덱 설정은 준비가 끝나 문서를 다시 만들어도 남아야 한다.
        session.document['ai_deck'] = {'id': 7, 'style': 'defensive'}
        session.save(update_fields=['document'])
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
        self.assertEqual(session.document['ai_deck'], {'id': 7, 'style': 'defensive'})
        version = session.version
        session = perform_simulator_preparation(session, request)
        self.assertEqual(session.version, version)


class PartialReleaseTests(TestCase):
    """릴리스 뒤에 추가된 카드: 릴리스 카드만 쓰는 덱은 시작하고, 아닌 덱은 막는다."""

    setUp = fixtures.RegulationTests.setUp

    def release(self, *, drop=()):
        from .models import RulesetRelease
        from .game.catalog import _json_hash, build_ruleset_snapshot
        from .game.spec import EFFECT_SCHEMA_VERSION

        snapshot = build_ruleset_snapshot()
        for code in drop:
            snapshot['cards'].pop(code)
        return RulesetRelease.objects.create(
            version=f'partial-{len(drop)}', schema_version=EFFECT_SCHEMA_VERSION, snapshot=snapshot,
            content_hash=_json_hash(snapshot), is_active=True,
            source_manifest={'validation': {'is_valid': True, 'card_count': len(snapshot['cards'])}},
        )

    def test_release_with_fewer_cards_than_the_catalog_opens_automatic_mode(self):
        from .automatic_services import automatic_mode_release
        from .game.catalog import EXPECTED_CARD_COUNT

        release = self.release()
        self.assertLess(len(release.snapshot['cards']), EXPECTED_CARD_COUNT)
        with patch('battlelog.automatic_services.RULEBOOK_SHA256', (release.snapshot.get('rulebook') or {}).get('sha256') or ''):
            self.assertEqual(automatic_mode_release(), release)

    def test_inconsistent_validation_count_still_blocks(self):
        from .automatic_services import automatic_mode_release

        release = self.release()
        release.source_manifest = {'validation': {'is_valid': True, 'card_count': len(release.snapshot['cards']) + 1}}
        type(release).objects.filter(pk=release.pk).update(source_manifest=release.source_manifest)
        with patch('battlelog.automatic_services.RULEBOOK_SHA256', (release.snapshot.get('rulebook') or {}).get('sha256') or ''):
            self.assertIsNone(automatic_mode_release())

    def test_deck_with_an_unreleased_card_cannot_start(self):
        entry = self.deck.cids.select_related('card').first()
        release = self.release(drop=[entry.card.code])
        with patch('battlelog.automatic_services.automatic_mode_release', return_value=release):
            with self.assertRaises(ValueError) as raised:
                create_simulator_session('A', 'B', self.deck, self.deck, mode='automatic')
        self.assertIn('자동 모드를 지원하지 않는 카드', str(raised.exception))
        self.assertIn(entry.card.name, str(raised.exception))

    def test_deck_of_released_cards_starts(self):
        release = self.release()
        with patch('battlelog.automatic_services.automatic_mode_release', return_value=release):
            session = create_simulator_session('A', 'B', self.deck, self.deck, mode='automatic')
        self.assertEqual(session.mode, 'automatic')

    def test_direct_validation_names_the_unreleased_card(self):
        from deck.game_validation import validate_automatic_deck

        entry = self.deck.cids.select_related('card').first()
        release = self.release(drop=[entry.card.code])
        report = validate_automatic_deck(self.deck, ruleset=release.snapshot, check_setup=False)
        self.assertEqual(len(report.errors), 1)
        self.assertIn(entry.card.name, report.errors[0])


class MatchFormatTests(TestCase):
    """같은 상대와 이어 하는 게임: 진행 방식(단판·3판 2선승·무한)과 다음 게임의 덱 변경."""

    setUp = fixtures.RegulationTests.setUp

    def session(self, match_format):
        return create_simulator_session('A', 'B', self.deck, self.deck, match_format=match_format)

    def prepare(self, session, side, action='ready', user=None, **extra):
        body = {
            'request_id': str(uuid.uuid4()), 'expected_version': session.document['preparation']['version'],
            'preparation_action': action, 'seat': side,
            'seat_token': session.player1_token if side == 'p1' else session.player2_token, **extra,
        }
        return perform_simulator_preparation(session, body, user=user)

    def play_game(self, session, winner):
        for side in ('p1', 'p2'):
            session = self.prepare(session, side)
        self.assertEqual(session.document['preparation']['status'], 'playing')
        document = session.document
        document['state']['engine'] = {'status': 'finished', 'winner': winner}
        session.document = document
        session.save(update_fields=['document'])
        return session

    def other_deck(self, **kwargs):
        from card.models import Card, Character
        from deck.models import CardInDeck, Deck

        character = Character.objects.create(name='Other', datas={'hand': {'5000': 5}})
        trait = Card.objects.create(name='Other trait', code='O-PS-001', type='특성', character=character,
            effect_definition={'deck_rules': {'main_size': 20}})
        cards = [Card.objects.create(name=f'Other {n}', code=f'O-AT-{n:03}', type='공격', character=character) for n in range(20)]
        deck = Deck.objects.create(name='Other', author=self.user, character=character, trait_card=trait, schema_version=2, **kwargs)
        CardInDeck.objects.bulk_create([CardInDeck(deck=deck, card=c, hand=int(i < 5), side=int(i >= 14)) for i, c in enumerate(cards)])
        return deck

    def test_single_game_has_no_next_game(self):
        from .play_match import match_view

        session = self.play_game(self.session('single'), 'p1')
        view = serialize_simulator_session(session)['match']
        self.assertEqual((view['format'], view['over'], view['winner']), ('single', True, 'p1'))
        self.assertEqual(view, match_view(session.document))
        with self.assertRaisesMessage(ValueError, '단판'):
            self.prepare(session, 'p1', 'next_game')

    def test_best_of_three_ends_when_a_player_wins_twice(self):
        from .play_match import match_view

        session = self.play_game(self.session('bo3'), 'p2')
        self.assertFalse(match_view(session.document)['over'])
        session = self.prepare(session, 'p1', 'next_game')
        self.assertEqual(session.document['match'], {'format': 'bo3'})
        # 다음 게임 준비 중에는 지난 게임 전적만 센다.
        self.assertEqual(match_view(session.document)['wins'], {'p1': 0, 'p2': 1})
        session = self.play_game(session, 'p2')
        view = match_view(session.document)
        self.assertEqual(view['wins'], {'p1': 0, 'p2': 2})
        self.assertEqual((view['over'], view['winner'], view['game_number']), (True, 'p2', 2))
        with self.assertRaisesMessage(ValueError, '매치가 끝났습니다'):
            self.prepare(session, 'p2', 'next_game')

    def test_endless_keeps_going_and_next_game_can_change_deck(self):
        from .play_match import match_view

        other = self.other_deck()
        session = self.play_game(self.session('endless'), 'p1')
        session = self.prepare(session, 'p1', 'next_game')
        self.assertEqual(session.document['preparation']['game_number'], 2)
        # 준비 완료한 채로는 덱을 바꿀 수 없다.
        session = self.prepare(session, 'p1', 'ready')
        with self.assertRaises(ValueError):
            self.prepare(session, 'p1', 'select_deck', deck_id=other.id)
        session = self.prepare(session, 'p1', 'cancel')
        session = self.prepare(session, 'p2', 'ready')
        session = self.prepare(session, 'p1', 'select_deck', deck_id=other.id)
        players = session.document['preparation']['players']
        self.assertEqual(players['p1']['registered']['deck_id'], other.id)
        # 상대 캐릭터가 바뀌었으니 상대 준비도 풀린다.
        self.assertFalse(players['p2']['ready'])
        rival = preparation_view(session.document['preparation'], 'p2')['players']['p1']
        self.assertEqual(rival['character']['name'], 'Other')
        session = self.play_game(session, 'p2')
        self.assertEqual(session.document['state']['players']['p1']['zones']['character'][0]['name'], 'Other')
        view = match_view(session.document)
        self.assertEqual((view['wins'], view['over'], view['game_number']), ({'p1': 1, 'p2': 1}, False, 2))

    def test_deck_change_needs_the_next_game_and_deck_permission(self):
        from django.contrib.auth.models import User

        session = self.session('endless')
        with self.assertRaisesMessage(ValueError, '다음 게임'):
            self.prepare(session, 'p1', 'select_deck', deck_id=self.deck.id)
        session = self.play_game(session, 'p1')
        session = self.prepare(session, 'p1', 'next_game')
        private = self.other_deck(visibility='private')
        with self.assertRaisesMessage(ValueError, '권한'):
            self.prepare(session, 'p1', 'select_deck', deck_id=private.id)
        stranger = User.objects.create_user('stranger')
        with self.assertRaisesMessage(ValueError, '권한'):
            self.prepare(session, 'p1', 'select_deck', deck_id=private.id, user=stranger)
        session = self.prepare(session, 'p1', 'select_deck', deck_id=private.id, user=self.user)
        self.assertEqual(session.document['preparation']['players']['p1']['registered']['deck_id'], private.id)

    def test_sessions_without_a_format_keep_unlimited_next_games(self):
        session = self.play_game(create_simulator_session('A', 'B', self.deck, self.deck), 'p1')
        self.assertIsNone(serialize_simulator_session(session)['match'])
        session = self.prepare(session, 'p1', 'next_game')
        self.assertEqual(session.document['preparation']['game_number'], 2)
