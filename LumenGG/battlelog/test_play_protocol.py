"""Contract tests for the game client protocol (docs/PLAY_PROTOCOL.md).

Set ``LUMEN_PLAY_FIXTURE_DIR`` to also write the envelopes these tests produce
as JSON fixtures for ``play/`` (see scripts/export-play-fixtures.ps1).
"""

import inspect
import json
import os
import re
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from .automatic_services import (
    automatic_session_settings, initialize_automatic_document, perform_automatic_command,
)
from .game.engine import ACTION_UI_KINDS, AutomaticGameEngine, IllegalAction
from .models import LumenSimulatorSession, RulesetRelease
from .play_protocol import PLAY_PROTOCOL_VERSION, validate_play_envelope
from .routing import websocket_urlpatterns
from .simulator_services import _filtered_event, serialize_simulator_session
from .test_automatic_engine import attack, base_state, defense, ruleset


FIXED_NOW = datetime(2026, 11, 9, 12, 0, tzinfo=dt_timezone.utc)
ROLES = (('p1', 'p1-play-token'), ('p2', 'p2-play-token'), ('viewer', ''))


# Display data for the synthetic cards, so fixtures look like real cards once
# sanitize_automatic_state() fills visible cards from the release by card_id.
PLAY_CARD_DISPLAY = {
    'P1-STRIKE': (101, '섬광 베기', '상대에게 빠르게 파고드는 기본 공격.'),
    'P1-LOW': (102, '하단 쓸기', '하단을 노리는 묵직한 공격.'),
    'P1-GUARD': (103, '반사 방어', '상단 공격을 막아낸다.'),
    'P1-RUSH': (104, '돌진', '거리를 좁히며 몰아친다.'),
    'P1-LIST': (105, '연속 찌르기', '리스트에서 획득할 수 있는 공격.'),
    'P1-LIST2': (106, '회전 차기', '리스트에서 획득할 수 있는 공격.'),
    'P2-STRIKE': (201, '그림자 일격', '그림자 속에서 날아드는 공격.'),
    'P2-GUARD': (202, '철벽', '상단과 중단을 막아낸다.'),
    'P2-HEAVY': (203, '대지 가르기', '느리지만 강한 공격.'),
    'P2-LIST': (204, '암영 표창', '리스트에서 획득할 수 있는 공격.'),
}


def _play_cards():
    p1_hand = [
        attack('p1-strike', 'p1', code='P1-STRIKE', frame=4, damage=500),
        attack('p1-low', 'p1', code='P1-LOW', frame=6, damage=300, position='하단'),
        attack('p1-rush', 'p1', code='P1-RUSH', frame=5, damage=400, position='중단'),
        defense('p1-guard', 'p1'),
    ]
    p1_hand[3]['code'] = 'P1-GUARD'
    p2_hand = [
        attack('p2-strike', 'p2', code='P2-STRIKE', frame=5, damage=400),
        attack('p2-heavy', 'p2', code='P2-HEAVY', frame=8, damage=800, position='중단'),
        defense('p2-guard', 'p2', mid='방어'),
    ]
    p2_hand[2]['code'] = 'P2-GUARD'
    p1_list = [
        attack('p1-list', 'p1', code='P1-LIST', frame=3, damage=200),
        attack('p1-list2', 'p1', code='P1-LIST2', frame=7, damage=600, position='상단'),
    ]
    p2_list = [attack('p2-list', 'p2', code='P2-LIST', frame=3, damage=200)]
    for card in p1_list + p2_list:
        card['face_up'] = True
    for card in (*p1_hand, *p2_hand, *p1_list, *p2_list):
        card_id, name, text = PLAY_CARD_DISPLAY[card['code']]
        card.update({'card_id': card_id, 'name': name, 'text': text})
    return p1_hand, p2_hand, p1_list, p2_list


def _play_ruleset(cards, characters):
    snapshot = ruleset(*cards)
    for card in cards:
        snapshot['cards'][card['code']].update({
            'id': card['card_id'], 'text': card.get('text') or '',
            'ultimate': bool(card.get('ultimate')),
        })
    snapshot['characters'] = characters
    return snapshot


def _real_sample():
    """Real cards exported by ``manage.py export_play_sample`` (optional)."""
    path = os.environ.get('LUMEN_PLAY_SAMPLE')
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _play_scenario(sample=None):
    """Return (initial state, ruleset snapshot, card metadata by card_id).

    Effects are left empty so the scripted game stays deterministic; only the
    display data (names, stats, text, images) come from the real cards.
    """
    state = base_state()
    cards = []
    characters = {}
    if sample:
        metadata = sample['cards']
        for side in ('p1', 'p2'):
            source = sample['players'][side]
            player = state['players'][side]
            player.update({
                'name': source['name'], 'initial_hp': source['initial_hp'],
                'hp': source['initial_hp'], 'character': source['character'],
            })
            characters[str(source['character']['id'])] = source['ruleset_character']
            for zone, zone_cards in source['zones'].items():
                player['zones'][zone] = zone_cards
                cards.extend(zone_cards)
        return state, _play_ruleset(cards, characters), metadata

    p1_hand, p2_hand, p1_list, p2_list = _play_cards()
    zones = {'p1': {'hand': p1_hand, 'list': p1_list}, 'p2': {'hand': p2_hand, 'list': p2_list}}
    for side, character_id, name, color in (
        ('p1', 1, '하이토', '#e0654a'), ('p2', 2, '루나', '#5a7be0'),
    ):
        player = state['players'][side]
        player['name'] = f'{name} 플레이어'
        player['initial_hp'] = 5000
        player['character'] = {
            'id': character_id, 'name': name, 'color': color, 'img': None, 'icon_img': None,
        }
        characters[str(character_id)] = {'name': name, 'datas': {}}
        for zone, zone_cards in zones[side].items():
            player['zones'][zone] = zone_cards
            cards.extend(zone_cards)
    metadata = {
        str(card['card_id']): {
            key: card.get(key)
            for key in (
                'card_id', 'name', 'code', 'type', 'frame', 'damage', 'pos', 'special',
                'g_top', 'g_mid', 'g_bot', 'text', 'detail_text', 'ultimate',
            )
        } | {'img': None, 'img_sm': None}
        for card in cards
    }
    return state, _play_ruleset(cards, characters), metadata


class PlayActionUiTableTests(SimpleTestCase):
    def test_every_dispatched_action_type_has_an_ui_kind(self):
        source = inspect.getsource(AutomaticGameEngine._dispatch)
        dispatched = set(re.findall(r"action_type == '([a-z_]+)'", source))
        for group in re.findall(r"action_type in \{([^}]*)\}", source):
            dispatched.update(re.findall(r"'([a-z_]+)'", group))

        self.assertTrue(dispatched)
        self.assertEqual(sorted(dispatched - set(ACTION_UI_KINDS)), [])

    def test_card_action_without_a_card_is_shown_as_a_button(self):
        # 시크릿 타임(Q-AUTO-007): 무작위 뒷면 캐치는 캐치를 정한 뒤에 카드를 뽑는다.
        engine = AutomaticGameEngine.initialize(base_state(), ruleset(), seed='random-catch-ui')
        [action] = engine._with_action_ui('p1', [engine._action(
            'play_catch_card', label='무작위 뒷면 카드로 캐치', payload={'random_pick': True},
        )])
        self.assertEqual(action['ui'], {'kind': 'secondary', 'cards': []})


class PlayPrivateEventTests(SimpleTestCase):
    def test_hidden_card_move_keeps_zones_but_not_identity(self):
        event = {
            'id': 'e1', 'type': 'card_moved', 'actor': 'p1', 'visibility': 'private',
            'payload': {
                'card_instance_id': 'secret-id', 'card_id': 7, 'card_code': 'SECRET',
                'card_label': '비밀 카드', 'reason': 'effect',
                'from_player': 'p1', 'from_zone': 'hand',
                'to_player': 'p1', 'to_zone': 'list',
            },
            'created_at': FIXED_NOW.isoformat(),
        }

        filtered = _filtered_event(event, base_state(), 'p2')

        self.assertEqual(filtered['type'], 'private_event')
        self.assertEqual(filtered['payload'], {
            'redacted': True, 'event_type': 'card_moved',
            'from_player': 'p1', 'from_zone': 'hand',
            'to_player': 'p1', 'to_zone': 'list',
        })
        self.assertEqual(_filtered_event(event, base_state(), 'p1')['payload']['card_label'], '비밀 카드')

    def test_unlisted_private_event_type_is_fully_redacted(self):
        event = {
            'id': 'e2', 'type': 'yohan_declare', 'actor': 'p1', 'visibility': 'private',
            'payload': {'declaration': 'secret'}, 'created_at': FIXED_NOW.isoformat(),
        }

        filtered = _filtered_event(event, base_state(), 'viewer')

        self.assertEqual(filtered['payload'], {'redacted': True})


class PlayEnvelopeContractTests(TestCase):
    max_steps = 24

    def setUp(self):
        state, snapshot, self.card_metadata = _play_scenario(_real_sample())
        self.release = RulesetRelease.objects.create(
            version='play-protocol-v1',
            snapshot=snapshot,
            content_hash='b' * 64,
            source_manifest={},
        )
        with patch('django.utils.timezone.now', return_value=FIXED_NOW):
            document = initialize_automatic_document(state, self.release, seed='play-protocol')
        self.session = LumenSimulatorSession.objects.create(
            view_token='play-protocol-view',
            player1_token=ROLES[0][1],
            player2_token=ROLES[1][1],
            mode=LumenSimulatorSession.MODE_AUTOMATIC,
            player1_controller=LumenSimulatorSession.CONTROLLER_HUMAN,
            player2_controller=LumenSimulatorSession.CONTROLLER_HUMAN,
            ruleset_release=self.release,
            document=document,
        )

    def envelopes(self):
        return {
            role: serialize_simulator_session(self.session, role, token)
            for role, token in ROLES
        }

    def choose(self, envelope):
        actions = envelope['legal_actions']
        for kind in ('decision', 'card', 'primary', 'secondary'):
            action = next((item for item in actions if item['ui']['kind'] == kind), None)
            if action is None:
                continue
            selections = {}
            if kind == 'decision':
                decision = envelope['pending_decision'] or {}
                default = decision.get('default') or []
                minimum = max(1, int(decision.get('minimum') or 1))
                selections = {'selected': default or [
                    option['id'] for option in (action.get('options') or [])[:minimum]
                ]}
            return action, selections
        return None, None

    def play(self):
        """Yield (step, envelopes) until the game ends or max_steps is hit."""
        for step in range(self.max_steps):
            with patch('django.utils.timezone.now', return_value=FIXED_NOW):
                envelopes = self.envelopes()
            yield step, envelopes
            if envelopes['viewer']['engine_status'].get('status') != 'running':
                return
            for role, token in ROLES[:2]:
                action, selections = self.choose(envelopes[role])
                if action is not None:
                    break
            else:
                return
            with patch('django.utils.timezone.now', return_value=FIXED_NOW):
                self.session = perform_automatic_command(self.session, {
                    'command_id': f'play-step-{step}',
                    'action_id': action['action_id'],
                    'expected_version': self.session.version,
                    'selections': selections,
                    'seat': role, 'seat_token': token,
                })

    def test_scripted_game_envelopes_satisfy_the_contract(self):
        fixture_dir = os.environ.get('LUMEN_PLAY_FIXTURE_DIR')
        seen_kinds = set()
        seen_phases = set()
        hidden_moves = 0
        steps = 0
        for step, envelopes in self.play():
            steps += 1
            for role, envelope in envelopes.items():
                errors = validate_play_envelope(envelope)
                self.assertEqual(errors, [], f'step {step} role {role}: {errors[:5]}')
                self.assertEqual(envelope['protocol_version'], PLAY_PROTOCOL_VERSION)
                seen_kinds.update(action['ui']['kind'] for action in envelope['legal_actions'])
                seen_phases.add(envelope['state']['phase'])
                if role == 'viewer':
                    self.assertEqual(envelope['legal_actions'], [])
                    hidden_moves += sum(
                        1 for event in envelope['events']
                        if event['payload'].get('event_type') == 'card_moved'
                    )
            if fixture_dir:
                self.write_fixture(Path(fixture_dir), step, envelopes)

        self.assertGreater(steps, 3)
        self.assertTrue({'card', 'primary'} <= seen_kinds, seen_kinds)
        self.assertTrue({'lumen', 'ready'} <= seen_phases, seen_phases)
        self.assertGreater(hidden_moves, 0)

    def test_card_refs_point_at_the_acting_players_own_cards(self):
        for _step, envelopes in self.play():
            for role in ('p1', 'p2'):
                for action in envelopes[role]['legal_actions']:
                    for ref in action['ui']['cards']:
                        self.assertEqual(ref['owner'], role, action['type'])
                        self.assertIn('instance_id', ref)

    def write_fixture(self, directory, step, envelopes):
        directory.mkdir(parents=True, exist_ok=True)
        if step == 0:
            # Same shape as GET simulator/<token>/card-metadata/ → {"cards": {...}}
            (directory / 'cards.json').write_text(
                json.dumps({'cards': self.card_metadata}, ensure_ascii=False, indent=2) + '\n',
                encoding='utf-8',
            )
        phase = envelopes['viewer']['state']['phase']
        engine_step = envelopes['viewer']['engine_status'].get('step') or 'none'
        name = f'step-{step:02d}-{phase}-{engine_step}.json'
        (directory / name).write_text(
            json.dumps(envelopes, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
            encoding='utf-8',
        )


class PlayBundleExportTests(TestCase):
    def test_bundle_export_refuses_without_a_validated_release(self):
        with self.assertRaisesMessage(CommandError, '자동 룰셋'):
            call_command('export_play_bundle', out=os.devnull)


class PlayClockBroadcastTests(TransactionTestCase):
    """A seat's state read that settles an elapsed timer must reach every client."""

    def setUp(self):
        p1_card = attack('clock-p1-card', 'p1', code='CLOCK-P1')
        p2_card = attack('clock-p2-card', 'p2', code='CLOCK-P2')
        release = RulesetRelease.objects.create(
            version='play-clock-v1', snapshot=ruleset(p1_card, p2_card),
            content_hash='c' * 64, source_manifest={},
        )
        document = initialize_automatic_document(
            base_state([p1_card], [p2_card]), release, seed='play-clock',
            settings=automatic_session_settings(ready_timeout_seconds=15, effect_timeout_seconds=None),
        )
        session = LumenSimulatorSession.objects.create(
            view_token='play-clock-view', player1_token='clock-p1', player2_token='clock-p2',
            mode=LumenSimulatorSession.MODE_AUTOMATIC, ruleset_release=release, document=document,
        )
        envelope = serialize_simulator_session(session, 'p1', 'clock-p1')
        ready = next(action for action in envelope['legal_actions'] if action['type'] == 'ready_card')
        session = perform_automatic_command(session, {
            'command_id': 'clock-ready', 'action_id': ready['action_id'],
            'expected_version': session.version, 'selections': {},
            'seat': 'p1', 'seat_token': 'clock-p1',
        })
        clock = session.document['state']['engine']['clock']
        self.assertEqual(clock['owner'], 'p2')
        # p2's ready timer ran out while nobody was asking for the state.
        clock['deadline'] = '2000-01-01T00:00:00+00:00'
        session.save(update_fields=['document'])
        self.version = session.version

    def test_settling_a_timer_on_connect_notifies_spectators(self):
        async_to_sync(self._exercise)()

    async def _exercise(self):
        app = URLRouter(websocket_urlpatterns)
        viewer = WebsocketCommunicator(app, '/ws/battlelog/simulator/play-clock-view/')
        self.assertTrue((await viewer.connect())[0])
        try:
            first = await viewer.receive_json_from(timeout=2)
            self.assertEqual(first['type'], 'state')
            self.assertEqual(first['state']['version'], self.version)

            seat = WebsocketCommunicator(app, '/ws/battlelog/simulator/play-clock-view/?seat=p2&seat_token=clock-p2')
            self.assertTrue((await seat.connect())[0])
            try:
                for _attempt in range(6):
                    message = await viewer.receive_json_from(timeout=2)
                    if message['type'] == 'state_dirty':
                        break
                else:
                    self.fail('관전자가 state_dirty를 받지 못했습니다.')
                self.assertGreater(message['version'], self.version)
            finally:
                await seat.disconnect()
        finally:
            await viewer.disconnect()


class GetPhaseSkipRuleTests(SimpleTestCase):
    """Comprehensive rules 4.5.3: only a hand at the hand limit may skip the get action."""

    def engine(self, hand_size):
        from datetime import datetime, timezone as tz

        hand = [attack(f'get-hand-{index}', 'p1') for index in range(hand_size)]
        listed = attack('get-list', 'p1')
        listed['face_up'] = True
        state = base_state(hand, [])
        state['players']['p1']['zones']['list'] = [listed]
        state['players']['p1']['character'] = {'id': 1, 'name': 'Get', 'hand_table': {'5000': 4}}
        engine = AutomaticGameEngine.initialize(
            state, ruleset(*hand, listed), now=datetime(2026, 11, 9, tzinfo=tz.utc), seed='get-skip',
        )
        engine.state['phase'] = 'get'
        engine.engine_state.update({'step': 'get_actions', 'current_actor': 'p1', 'get_order': ['p1'], 'get_done': []})
        return engine

    def types(self, engine):
        return [action['type'] for action in engine.legal_actions('p1')]

    def test_below_the_hand_limit_the_card_must_be_taken(self):
        types = self.types(self.engine(hand_size=2))
        self.assertIn('select_get_card', types)
        self.assertNotIn('pass_phase', types)

    def test_at_the_hand_limit_the_get_may_be_skipped(self):
        types = self.types(self.engine(hand_size=4))
        self.assertIn('select_get_card', types)
        self.assertIn('pass_phase', types)


class DecisionDestinationTests(SimpleTestCase):
    """ui.to_zone tells the game client where chosen cards go (drag and drop)."""

    def destination(self, continuation):
        engine = AutomaticGameEngine.initialize(base_state(), ruleset(), seed='destination')
        return engine._decision_destination({'continuation': continuation})

    def test_known_moves(self):
        self.assertEqual(self.destination({'type': 'hand_limit_discard'}), 'list')
        # 버리기는 카드마다 정한다(특수 기술 → 브레이크 존, 그 밖 → 리스트).
        self.assertEqual(self.destination({'type': 'play_cost', 'cost': {'operation': 'discard'}}), 'discard')
        for kind in ('defense_cost', 'combo_speed_cost', 'battle_reveal_play_cost'):
            self.assertEqual(self.destination({'type': kind, 'cost': {'operation': 'move_card', 'to_zone': 'lumen'}}), 'lumen')
        self.assertEqual(self.destination({'type': 'effect_choice', 'effects': [{'op': 'force_ready'}]}), 'battle')
        self.assertEqual(self.destination({'type': 'play_cost', 'cost': {'operation': 'move_card', 'to_zone': 'lumen'}}), 'lumen')
        self.assertEqual(self.destination({'type': 'effect_choice', 'effects': [
            {'op': 'request_amount'}, {'op': 'move_card', 'to_zone': 'lumen'},
        ]}), 'lumen')
        self.assertEqual(self.destination({'type': 'effect_choice', 'effects': [{'op': 'break_card'}]}), 'break')

    def test_discard_hint_is_per_card(self):
        normal = attack('discard-normal', 'p1')
        special = attack('discard-special', 'p1')
        special['type'] = '특수'
        engine = AutomaticGameEngine.initialize(base_state([normal, special], []), ruleset(normal, special), seed='discard-hint')
        options = [{'id': 'discard-normal'}, {'id': 'discard-special'}]
        engine._attach_option_ui('p1', options, 'discard')
        self.assertEqual([option['ui']['to_zone'] for option in options], ['list', 'break'])

    def test_side_replenishment_moves_side_to_list(self):
        self.assertEqual(self.destination({'type': 'break_replenish'}), 'list')
        spare = attack('side-spare', 'p1')
        state = base_state()
        state['players']['p1']['zones']['side'] = [spare]
        engine = AutomaticGameEngine.initialize(state, ruleset(spare), seed='replenish')
        engine._start_break_replenishment('p1')
        options = {option['id']: option for option in engine.observe('p1')['pending_decision']['options']}
        self.assertEqual(options['side-spare']['ui']['card']['zone'], 'side')
        self.assertEqual(options['side-spare']['ui']['to_zone'], 'list')
        # "보충하지 않음"은 카드가 아니므로 도착 존이 없다(위쪽 안내의 버튼).
        self.assertEqual(options['decline']['ui'], {})

    def test_unknown_moves_have_no_hint(self):
        self.assertIsNone(self.destination({'type': 'optional_effect'}))
        self.assertIsNone(self.destination({'type': 'effect_choice', 'effects': [{'op': 'reveal'}]}))


class ComboWithoutPairDoesNotStallTests(SimpleTestCase):
    """A Combo judgment without a legal two-card pair must not freeze the match.

    The empty Combo is closed through the combo_end pipeline; the engine has to
    keep going afterwards (previously it stopped with no legal action for anyone).
    """

    def act(self, engine, role, action_type):
        action = next(item for item in engine.legal_actions(role) if item['type'] == action_type)
        engine.submit_action(role, action['action_id'])

    def test_match_continues_after_skipped_combo(self):
        from datetime import datetime, timezone as tz

        fast = attack('combo-fast', 'p1', frame=3, damage=300, counter='콤보')
        slow = attack('combo-slow', 'p2', frame=9, damage=300)
        engine = AutomaticGameEngine.initialize(
            base_state([fast], [slow]), ruleset(fast, slow),
            now=datetime(2026, 11, 10, tzinfo=tz.utc), seed='combo-without-pair',
        )
        self.act(engine, 'p1', 'pass_phase')
        self.act(engine, 'p2', 'pass_phase')
        self.act(engine, 'p1', 'ready_card')
        self.act(engine, 'p2', 'ready_card')

        self.assertTrue(any(
            event['type'] == 'combo_skipped'
            and event['payload'].get('reason') == 'normal_combo_requires_two_cards'
            for event in engine.events
        ))
        self.assertNotEqual(engine.engine_state.get('step'), 'combo_end')
        self.assertIsNone(engine.engine_state.get('pipeline'))
        playable = [
            action['type']
            for role in ('p1', 'p2')
            for action in engine.legal_actions(role)
            if action['type'] != 'concede'
        ]
        self.assertTrue(playable, engine.engine_state.get('step'))


class UnavailableBranchOptionTests(TestCase):
    """막혀서 고를 수 없는 효과 선택지는 사라지지 않고 이유와 함께 보인다(제출은 여전히 불가)."""

    def test_blocked_break_option_is_shown_with_reason(self):
        technique = attack('nya-tech', 'p1')
        technique['character_key'] = 'nya'
        technique['face_up'] = True
        shield = attack('exceed', 'p1')
        shield.update({'name': '프로토콜: 익시드', 'character_key': 'nya', 'face_up': True})
        state = base_state([attack('spare-a', 'p1'), attack('spare-b', 'p1')], [])
        state['players']['p1']['zones']['lumen'] = [technique, shield]
        engine = AutomaticGameEngine.initialize(
            state, ruleset(technique, shield),
            now=datetime(2026, 11, 10, tzinfo=dt_timezone.utc), seed="unavailable-branch",
        )
        engine.engine_state.setdefault('replacements', []).append({
            'op': 'prevent', 'kind': 'break', 'player': 'p1',
            'where': {'character_key': 'nya'}, 'target_zones': ['lumen'],
            'duration': 'continuous', 'controller_only': True, 'scope': 'all',
            'controller': 'p1', 'source': 'exceed',
        })
        break_selector = {
            'kind': 'card', 'player': {'controller': True}, 'zones': ['lumen'],
            'min': 1, 'max': 1, 'where': {'character_key': 'nya', 'is_technique': True},
            'as_operation': 'break_card',
        }
        send_selector = {
            'kind': 'card', 'player': {'controller': True}, 'zones': ['hand'],
            'min': 2, 'max': 2, 'where': {'is_technique': True},
        }
        engine.resolver.execute_effects([{
            'op': 'choose_effect', 'player': {'controller': True}, 'prompt': '유지 비용',
            'options': [
                {'id': 'break_nya', 'label': '루멘 존의 냐 기술 브레이크',
                 'selector_available': break_selector, 'effects': []},
                {'id': 'send_two', 'label': '기술 2장 이동',
                 'selector_available': send_selector, 'effects': []},
            ],
        }], {'controller': 'p1', 'source_card_instance_id': 'exceed'})

        decision = engine.observe('p1')['pending_decision']
        self.assertEqual([option['id'] for option in decision['options']], ['send_two'])
        self.assertEqual(decision['unavailable_options'], [{
            'id': 'break_nya', 'label': '루멘 존의 냐 기술 브레이크',
            'reason': '「프로토콜: 익시드」 효과로 브레이크할 수 없습니다.',
        }])
        with self.assertRaises(IllegalAction):
            engine._submit_decision('p1', decision['id'], ['break_nya'])


class ComboPairPresentedTogetherTests(SimpleTestCase):
    """1·2콤보는 함께 배틀 존에 놓인 뒤 각각의 효과를 처리한다(2콤보가 손패에 남아 있지 않는다)."""

    def setup_combo(self):
        starter = attack('pair-starter', 'p1', frame=5, hit='콤보')
        first = attack('pair-first', 'p1', frame=5)
        second = attack('pair-second', 'p1', frame=6)
        opposing = attack('pair-opposing', 'p2', frame=7)
        state = base_state([], [])
        state['phase'] = 'battle'
        state['players']['p1']['zones']['battle'] = [starter]
        state['players']['p1']['zones']['hand'] = [first, second]
        state['players']['p2']['zones']['battle'] = [opposing]
        engine = AutomaticGameEngine.initialize(
            state, ruleset(starter, first, second, opposing), seed='combo-presented',
        )
        engine.state['phase'] = 'battle'
        engine.engine_state['battle'] = {
            'p1': {'instance_id': 'pair-starter', 'card': starter},
            'p2': {'instance_id': 'pair-opposing', 'card': opposing},
        }
        engine.grant_combo('p1', source='pair-starter')
        return engine

    def test_second_card_is_on_battle_zone_before_first_resolves(self):
        engine = self.setup_combo()
        engine._play_combo('p1', ['pair-first', 'pair-second'])
        engine._continue()
        events = engine.events
        index = {
            ('moved', event['payload']['card_instance_id'], event['payload'].get('reason')): position
            for position, event in enumerate(events) if event['type'] == 'card_moved'
        }
        first_used = next(
            position for position, event in enumerate(events)
            if event['type'] == 'combo_card_used' and event['payload']['card_instance_id'] == 'pair-first'
        )
        # 2콤보 카드는 1콤보 효과 처리 전에 이미 배틀 존에 있다.
        self.assertLess(index[('moved', 'pair-second', 'combo_presented')], first_used)
        # 자기 차례에는 다시 옮기지 않고(손패를 거치지 않음) 그대로 사용한다.
        self.assertNotIn(('moved', 'pair-second', 'combo'), index)
        self.assertEqual(
            [event['payload']['card_instance_id'] for event in events if event['type'] == 'combo_card_used'],
            ['pair-first', 'pair-second'],
        )

    def test_unused_presented_card_returns_when_combo_ends(self):
        engine = self.setup_combo()
        combo = engine.engine_state['combo']
        engine._present_combo_cards('p1', combo, ['pair-second'])
        self.assertEqual(engine._find_location('pair-second')[1], 'battle')
        engine.end_combo()
        self.assertEqual(engine._find_location('pair-second')[1], 'hand')
