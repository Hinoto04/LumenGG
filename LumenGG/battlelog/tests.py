import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from card.models import Card, Character
from deck.models import CardInDeck, Deck
from tournament.models import Tournament, TournamentDeckSubmission, TournamentMatch, TournamentParticipant, TournamentRound

from .models import BattleEvent, BattleSession, LumenSimulatorSession, RealtimePresence
from .event_buffer import flush_session_events
from .presence import battle_presence_counts, register_presence, simulator_presence_counts, unregister_presence
from .services import _passive_ui, cleanup_expired_sessions, create_standalone_session, get_or_create_tournament_session
from .simulator_services import create_simulator_session, serialize_simulator_card_metadata, serialize_simulator_session


class BattleCalculatorTests(TestCase):
    def setUp(self):
        self.char_a = Character.objects.create(
            name='니아',
            description='',
            group='',
            datas={'hand': {'5000': 6, '4000': 7, '3000': 8}},
            img='https://example.com/nia.png',
        )
        self.char_b = Character.objects.create(
            name='루트',
            description='',
            group='',
            datas={'hand': {'4500': 6, '3000': 8}},
            img='https://example.com/root.png',
        )
        self.char_c = Character.objects.create(
            name='델피',
            description='',
            group='',
            datas={'hand': {'5200': 6, '4000': 7}},
            img='https://example.com/delphi.png',
        )

    def post_json(self, url, payload):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_anonymous_user_can_create_standalone_session_and_control_by_token(self):
        response = self.client.post(reverse('battlelog:sim'), {
            'player1_name': 'A',
            'player2_name': 'B',
            'player1_character': self.char_a.id,
            'player2_character': self.char_b.id,
        })

        self.assertEqual(response.status_code, 302)
        session = BattleSession.objects.get()
        self.assertEqual(session.session_type, BattleSession.SESSION_STANDALONE)
        self.assertEqual(session.player1_hp, 5000)
        self.assertEqual(session.player2_hp, 4500)
        self.assertIsNotNone(session.expires_at)

        action_url = reverse('battlelog:sessionAction', kwargs={'view_token': session.view_token})
        forbidden = self.post_json(action_url, {'action': 'hp', 'target': 'p1', 'amount': -100})
        self.assertEqual(forbidden.status_code, 403)

        allowed = self.post_json(action_url, {
            'action': 'hp',
            'target': 'p1',
            'amount': -300,
            'control_token': session.control_token,
        })
        self.assertEqual(allowed.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.player1_hp, 4700)
        flush_session_events(session.id)
        self.assertEqual(BattleEvent.objects.filter(event_type=BattleEvent.EVENT_HP).count(), 1)

    def test_batch_action_applies_calculator_actions_once(self):
        session = BattleSession.objects.create(
            session_type=BattleSession.SESSION_STANDALONE,
            view_token='batch-view',
            control_token='batch-control',
            player1_character=self.char_a,
            player2_character=self.char_b,
            player1_initial_hp=5000,
            player2_initial_hp=4500,
            player1_hp=5000,
            player2_hp=4500,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        action_url = reverse('battlelog:sessionAction', kwargs={'view_token': session.view_token})

        response = self.post_json(action_url, {
            'action': 'batch',
            'control_token': session.control_token,
            'actions': [
                {'action': 'hp', 'target': 'p1', 'amount': -100},
                {'action': 'fp', 'target': 'p1', 'amount': 2},
                {'action': 'passive', 'target': 'p1', 'key': 'count', 'delta': 3, 'label': '카운트'},
            ],
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.player1_hp, 4900)
        self.assertEqual(session.player1_fp, 2)
        self.assertEqual(session.player1_passive_state['count']['count'], 3)
        self.assertEqual(session.version, 2)

    def test_calculator_passive_ui_can_disable_cmyk_and_toggle_yohan_disaster_one(self):
        cmyk = Character.objects.create(
            name='CMYK',
            description='',
            group='',
            datas={
                'battle_passive_ui': {'disabled': True},
                'simulator_passive_ui': {
                    'template': 'battlelog/passive_ui/cmyk_simulator.html',
                    'css': 'battlelog/passive_ui/character_simulator.css',
                    'js': 'battlelog/passive_ui/cmyk_simulator.js',
                },
            },
            img='https://example.com/cmyk.png',
        )
        yohan = Character.objects.create(
            name='요한',
            description='',
            group='',
            datas={
                'battle_passive_ui': {
                    'template': 'battlelog/passive_ui/configurable.html',
                    'css': 'battlelog/passive_ui/configurable.css',
                    'js': 'battlelog/passive_ui/configurable.js',
                    'options': {
                        'title': '예지',
                        'controls': [
                            {'type': 'counter', 'key': 'foresight_counter', 'label': '예지 카운터', 'max': 10},
                            {'type': 'toggle', 'key': 'disaster_one', 'label': '디제스터 원'},
                        ],
                    },
                },
            },
            img='https://example.com/yohan.png',
        )

        self.assertEqual(_passive_ui(cmyk, context='battle'), {})
        self.assertTrue(_passive_ui(cmyk, context='simulator')['html'])
        yohan_controls = _passive_ui(yohan, context='battle')['options']['controls']
        self.assertEqual([control['key'] for control in yohan_controls], ['foresight_counter', 'disaster_one'])
        self.assertEqual(yohan_controls[1]['type'], 'toggle')

        session = create_standalone_session('요한', '상대', yohan, self.char_b)
        self.assertEqual(session.player1_passive_state['foresight_counter']['count'], 2)

    def test_undo_reverts_last_hp_event(self):
        session = BattleSession.objects.create(
            session_type=BattleSession.SESSION_STANDALONE,
            view_token='view',
            control_token='control',
            player1_character=self.char_a,
            player2_character=self.char_b,
            player1_initial_hp=5000,
            player2_initial_hp=4500,
            player1_hp=5000,
            player2_hp=4500,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        action_url = reverse('battlelog:sessionAction', kwargs={'view_token': session.view_token})
        self.post_json(action_url, {
            'action': 'hp',
            'target': 'p2',
            'amount': -500,
            'control_token': session.control_token,
        })
        response = self.post_json(action_url, {'action': 'undo', 'control_token': session.control_token})

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.player2_hp, 4500)
        flush_session_events(session.id)
        self.assertTrue(BattleEvent.objects.get(event_type=BattleEvent.EVENT_HP).undone)

    def test_tournament_player_can_control_match_session_without_control_token(self):
        owner = User.objects.create_user(username='owner', password='pw')
        p1_user = User.objects.create_user(username='p1', password='pw')
        p2_user = User.objects.create_user(username='p2', password='pw')
        tournament = Tournament.objects.create(name='테스트 대회', organizer=owner)
        deck1 = Deck.objects.create(name='D1', author=p1_user, character=self.char_a)
        deck2 = Deck.objects.create(name='D2', author=p2_user, character=self.char_b)
        participant1 = TournamentParticipant.objects.create(tournament=tournament, user=p1_user, deck=deck1)
        participant2 = TournamentParticipant.objects.create(tournament=tournament, user=p2_user, deck=deck2)
        round_obj = TournamentRound.objects.create(tournament=tournament, number=1)
        match = TournamentMatch.objects.create(round=round_obj, table_no=1, player1=participant1, player2=participant2)
        session = get_or_create_tournament_session(match)

        self.client.login(username='p1', password='pw')
        response = self.post_json(reverse('battlelog:sessionAction', kwargs={'view_token': session.view_token}), {
            'action': 'hp',
            'target': 'p2',
            'amount': -100,
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.player2_hp, 4400)

    def test_multi_deck_player_can_choose_character_again_on_next_set(self):
        owner = User.objects.create_user(username='owner2', password='pw')
        p1_user = User.objects.create_user(username='p1_multi', password='pw')
        p2_user = User.objects.create_user(username='p2_single', password='pw')
        tournament = Tournament.objects.create(name='다중 덱 테스트', organizer=owner, decklist_required_count=2)
        deck1 = Deck.objects.create(name='D1', author=p1_user, character=self.char_a)
        deck2 = Deck.objects.create(name='D2', author=p1_user, character=self.char_c)
        deck3 = Deck.objects.create(name='D3', author=p2_user, character=self.char_b)
        participant1 = TournamentParticipant.objects.create(tournament=tournament, user=p1_user, deck=deck1)
        participant2 = TournamentParticipant.objects.create(tournament=tournament, user=p2_user, deck=deck3)
        TournamentDeckSubmission.objects.create(participant=participant1, deck=deck1, slot=1)
        TournamentDeckSubmission.objects.create(participant=participant1, deck=deck2, slot=2)
        TournamentDeckSubmission.objects.create(participant=participant2, deck=deck3, slot=1)
        round_obj = TournamentRound.objects.create(tournament=tournament, number=1, set_count=3)
        match = TournamentMatch.objects.create(round=round_obj, table_no=1, player1=participant1, player2=participant2)
        session = get_or_create_tournament_session(match)

        self.assertIsNone(session.player1_character)
        self.assertEqual(session.player2_character, self.char_b)

        action_url = reverse('battlelog:sessionAction', kwargs={'view_token': session.view_token})
        self.client.login(username='p1_multi', password='pw')
        response = self.post_json(action_url, {
            'action': 'character',
            'target': 'p1',
            'character_id': self.char_a.id,
        })
        self.assertEqual(response.status_code, 200)

        response = self.post_json(action_url, {
            'action': 'hp',
            'target': 'p2',
            'amount': -5000,
        })
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        self.client.login(username='owner2', password='pw')
        response = self.post_json(action_url, {
            'action': 'force_set_result',
            'winner': 'p1',
        })
        self.assertEqual(response.status_code, 200)

        session.refresh_from_db()
        self.assertEqual(session.sets.filter(status='finished').count(), 1)
        self.assertEqual(session.sets.filter(status='running').get().set_number, 2)
        self.assertIsNone(session.player1_character)
        self.assertEqual(session.player1_hp, 0)
        self.assertEqual(session.player2_character, self.char_b)
        self.assertEqual(session.player2_hp, 4500)

        self.client.logout()
        self.client.login(username='p1_multi', password='pw')
        response = self.post_json(action_url, {
            'action': 'character',
            'target': 'p1',
            'character_id': self.char_c.id,
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.player1_character, self.char_c)
        self.assertEqual(session.player1_hp, 5200)

    def test_sudden_death_resets_hp_fp_unlocks_time_over_match_and_resolves_after_three_turns(self):
        owner = User.objects.create_user(username='sudden_owner', password='pw')
        p1_user = User.objects.create_user(username='sudden_p1', password='pw')
        p2_user = User.objects.create_user(username='sudden_p2', password='pw')
        tournament = Tournament.objects.create(name='서든 테스트', organizer=owner)
        deck1 = Deck.objects.create(name='D1', author=p1_user, character=self.char_a)
        deck2 = Deck.objects.create(name='D2', author=p2_user, character=self.char_b)
        participant1 = TournamentParticipant.objects.create(tournament=tournament, user=p1_user, deck=deck1)
        participant2 = TournamentParticipant.objects.create(tournament=tournament, user=p2_user, deck=deck2)
        round_obj = TournamentRound.objects.create(
            tournament=tournament,
            number=1,
            started_at=timezone.now() - timedelta(minutes=20),
            duration_minutes=1,
        )
        match = TournamentMatch.objects.create(round=round_obj, table_no=1, player1=participant1, player2=participant2)
        session = get_or_create_tournament_session(match)
        action_url = reverse('battlelog:sessionAction', kwargs={'view_token': session.view_token})

        self.client.login(username='sudden_p1', password='pw')
        locked_response = self.post_json(action_url, {'action': 'hp', 'target': 'p2', 'amount': -100})
        self.assertEqual(locked_response.status_code, 403)

        self.client.logout()
        self.client.login(username='sudden_owner', password='pw')
        response = self.post_json(action_url, {'action': 'fp', 'target': 'p1', 'amount': 3})
        self.assertEqual(response.status_code, 200)
        response = self.post_json(action_url, {'action': 'sudden_death', 'enabled': True})
        self.assertEqual(response.status_code, 200)

        session.refresh_from_db()
        self.assertTrue(session.sudden_death)
        self.assertEqual(session.sudden_death_turns_remaining, 3)
        self.assertEqual(session.player1_hp, 1000)
        self.assertEqual(session.player2_hp, 1000)
        self.assertEqual(session.player1_fp, 0)
        self.assertEqual(session.player2_fp, 0)

        self.client.logout()
        self.client.login(username='sudden_p1', password='pw')
        response = self.post_json(action_url, {'action': 'hp', 'target': 'p2', 'amount': -100})
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.player2_hp, 900)

        for _ in range(3):
            response = self.post_json(action_url, {'action': 'sudden_turn'})
            self.assertEqual(response.status_code, 200)

        session.refresh_from_db()
        match.refresh_from_db()
        self.assertFalse(session.sudden_death)
        self.assertEqual(session.sudden_death_turns_remaining, 0)
        self.assertEqual(match.status, match.STATUS_REPORTED)
        self.assertEqual(match.winner, participant1)
        self.assertEqual(match.player1_score, 1)
        self.assertEqual(match.player2_score, 0)

    def test_cleanup_deletes_expired_standalone_sessions(self):
        BattleSession.objects.create(
            session_type=BattleSession.SESSION_STANDALONE,
            view_token='expired',
            control_token='expired-control',
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        BattleSession.objects.create(
            session_type=BattleSession.SESSION_STANDALONE,
            view_token='active',
            control_token='active-control',
            expires_at=timezone.now() + timedelta(minutes=30),
        )

        cleanup_expired_sessions()

        self.assertFalse(BattleSession.objects.filter(view_token='expired').exists())
        self.assertTrue(BattleSession.objects.filter(view_token='active').exists())

    def test_realtime_presence_counts_by_link_role(self):
        register_presence(RealtimePresence.SCOPE_BATTLE, 'battle-presence', 'control', 'battle-control')
        register_presence(RealtimePresence.SCOPE_BATTLE, 'battle-presence', 'viewer', 'battle-viewer')
        register_presence(RealtimePresence.SCOPE_SIMULATOR, 'sim-presence', 'p1', 'sim-p1')
        register_presence(RealtimePresence.SCOPE_SIMULATOR, 'sim-presence', 'p2', 'sim-p2')
        register_presence(RealtimePresence.SCOPE_SIMULATOR, 'sim-presence', 'viewer', 'sim-viewer')

        self.assertEqual(battle_presence_counts('battle-presence'), {'control': 1, 'viewer': 1})
        self.assertEqual(simulator_presence_counts('sim-presence'), {'p1': 1, 'p2': 1, 'viewer': 1})

        unregister_presence('battle-control')
        self.assertEqual(battle_presence_counts('battle-presence'), {'control': 0, 'viewer': 1})


class LumenSimulatorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sim_owner', password='pw')
        self.char_a = Character.objects.create(
            name='시뮬A',
            description='',
            group='',
            datas={
                'hand': {'5000': 6, '3000': 8},
                'battle_passive_ui': {
                    'title': '시뮬 패시브',
                    'controls': [
                        {'type': 'counter', 'key': 'sim_counter', 'label': '시뮬 카운터', 'max': 3},
                        {'type': 'toggle', 'key': 'sim_toggle', 'label': '시뮬 상태'},
                    ],
                },
            },
            img='https://example.com/a.png',
        )
        self.char_b = Character.objects.create(
            name='시뮬B',
            description='',
            group='',
            datas={'hand': {'4500': 6, '3000': 8}},
            img='https://example.com/b.png',
        )
        Card.objects.create(
            name='A 특성',
            type='특성',
            character=self.char_a,
            img='https://example.com/passive-a.png',
        )
        Card.objects.create(
            name='B 특성',
            type='특성',
            character=self.char_b,
            img='https://example.com/passive-b.png',
        )
        self.card_a = Card.objects.create(
            name='A 공격',
            type='공격',
            frame=5,
            damage=400,
            body='손',
            special='상쇄',
            hit='+2',
            guard='-1',
            counter='+4',
            text='A 효과',
            detail_text='A 상세',
            character=self.char_a,
            img='https://example.com/a-card.png',
        )
        self.ultimate_a = Card.objects.create(
            name='A 얼티밋',
            type='공격',
            frame=3,
            damage=900,
            ultimate=True,
            character=self.char_a,
            img='https://example.com/a-ult.png',
        )
        self.card_b = Card.objects.create(
            name='B 수비',
            type='수비',
            frame=6,
            damage=300,
            g_top='O',
            g_mid='-',
            g_bot='X',
            text='B 효과',
            character=self.char_b,
            img='https://example.com/b-card.png',
        )
        self.external_card = Card.objects.create(
            name='외부 카드',
            type='특수 기술',
            text='외부 효과',
            character=self.char_a,
            img='https://example.com/external.png',
        )
        self.deck_a = Deck.objects.create(name='A 덱', author=self.user, character=self.char_a)
        self.deck_b = Deck.objects.create(name='B 덱', author=self.user, character=self.char_b)
        CardInDeck.objects.create(deck=self.deck_a, card=self.card_a, count=3, hand=1, side=1)
        CardInDeck.objects.create(deck=self.deck_a, card=self.ultimate_a, count=1)
        CardInDeck.objects.create(deck=self.deck_b, card=self.card_b, count=2, hand=1, side=0)

    def post_json(self, url, payload):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_simulator_start_creates_deck_based_session(self):
        response = self.client.post(reverse('battlelog:simulatorStart'), {
            'player1_name': 'A',
            'player2_name': 'B',
            'player1_deck': self.deck_a.id,
            'player2_deck': self.deck_b.id,
        })

        self.assertEqual(response.status_code, 302)
        session = LumenSimulatorSession.objects.get()
        state = session.document['state']
        self.assertEqual(state['players']['p1']['name'], 'A(시뮬A)')
        self.assertEqual(state['players']['p2']['name'], 'B(시뮬B)')
        self.assertEqual(state['players']['p1']['hp'], 5000)
        self.assertEqual(len(state['players']['p1']['zones']['hand']), 1)
        self.assertEqual(len(state['players']['p1']['zones']['side']), 1)
        self.assertEqual(len(state['players']['p1']['zones']['list']), 1)
        self.assertEqual(len(state['players']['p1']['zones']['ultimate']), 1)
        self.assertEqual(len(state['players']['p1']['zones']['passive']), 1)
        passive_options = state['players']['p1']['character']['passive_ui']['options']
        self.assertEqual(passive_options['controls'][0]['key'], 'sim_counter')
        requested = [
            side for side in ('p1', 'p2')
            if state['status'][side]['requested']
        ]
        self.assertEqual(len(requested), 1)
        self.assertFalse(state['status'][requested[0]]['done'])
        self.assertEqual(state['priority_player'], requested[0])

    def test_simulator_deck_search_returns_assignable_decks(self):
        response = self.client.get(reverse('battlelog:simulatorDeckSearch'), {'q': '시뮬A'})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data[0]['id'], self.deck_a.id)
        self.assertEqual(data[0]['character'], '시뮬A')
        self.assertEqual(data[0]['author'], self.user.username)

    def test_simulator_private_cards_are_filtered_by_role(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)

        viewer_state = serialize_simulator_session(session)['state']
        p1_state = serialize_simulator_session(session, 'p1', session.player1_token)['state']

        viewer_hand = viewer_state['players']['p1']['zones']['hand'][0]
        p1_hand = p1_state['players']['p1']['zones']['hand'][0]
        p1_opponent_hand = p1_state['players']['p2']['zones']['hand'][0]
        self.assertTrue(viewer_hand['hidden'])
        self.assertNotIn('card_id', viewer_hand)
        self.assertFalse(p1_hand['hidden'])
        self.assertEqual(p1_hand['card_id'], self.card_a.id)
        self.assertTrue(p1_opponent_hand['hidden'])
        self.assertEqual(p1_opponent_hand['card_id'], self.card_b.id)
        metadata = serialize_simulator_card_metadata([p1_hand['card_id']])
        self.assertEqual(metadata[str(self.card_a.id)]['name'], 'A 공격')

    def test_hand_visibility_action_reveals_and_hides_own_hand(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        response = self.post_json(action_url, {
            'action': 'set_hand_visibility',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'target': 'p1',
                'face_up': True,
            },
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        hand = session.document['state']['players']['p1']['zones']['hand']
        self.assertTrue(all(card['face_up'] for card in hand))
        self.assertEqual(session.document['events'][-1]['type'], 'set_hand_visibility')
        self.assertEqual(session.document['events'][-1]['payload']['count'], len(hand))
        viewer_hand = serialize_simulator_session(session)['state']['players']['p1']['zones']['hand'][0]
        self.assertFalse(viewer_hand['hidden'])
        self.assertEqual(viewer_hand['card_id'], self.card_a.id)

        response = self.post_json(action_url, {
            'action': 'set_hand_visibility',
            'seat': 'p2',
            'seat_token': session.player2_token,
            'payload': {
                'target': 'p1',
                'face_up': False,
            },
        })
        self.assertEqual(response.status_code, 403)

        response = self.post_json(action_url, {
            'action': 'set_hand_visibility',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'target': 'p1',
                'face_up': False,
            },
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertFalse(any(
            card['face_up']
            for card in session.document['state']['players']['p1']['zones']['hand']
        ))
        viewer_hand = serialize_simulator_session(session)['state']['players']['p1']['zones']['hand'][0]
        self.assertTrue(viewer_hand['hidden'])

    def test_simulator_card_metadata_is_loaded_separately(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        document = session.document
        metadata_fields = [
            'type', 'frame', 'damage', 'pos', 'body', 'special', 'hit', 'guard',
            'counter', 'g_top', 'g_mid', 'g_bot', 'text', 'detail_text',
        ]
        legacy_attack = document['state']['players']['p1']['zones']['list'][0]
        legacy_defense = document['state']['players']['p2']['zones']['list'][0]
        for card in (legacy_attack, legacy_defense):
            for field in metadata_fields:
                card.pop(field, None)
        session.document = document
        session.save(update_fields=['document'])

        viewer_state = serialize_simulator_session(session)['state']
        attack = viewer_state['players']['p1']['zones']['list'][0]
        defense = viewer_state['players']['p2']['zones']['list'][0]

        self.assertEqual(attack['card_id'], self.card_a.id)
        self.assertNotIn('hit', attack)
        self.assertNotIn('text', attack)
        metadata = serialize_simulator_card_metadata([attack['card_id'], defense['card_id']])
        self.assertEqual(metadata[str(self.card_a.id)]['hit'], '+2')
        self.assertEqual(metadata[str(self.card_a.id)]['guard'], '-1')
        self.assertEqual(metadata[str(self.card_a.id)]['counter'], '+4')
        self.assertEqual(metadata[str(self.card_a.id)]['text'], 'A 효과')
        self.assertEqual(metadata[str(self.card_a.id)]['detail_text'], 'A 상세')
        self.assertEqual(metadata[str(self.card_b.id)]['g_top'], 'O')
        self.assertEqual(metadata[str(self.card_b.id)]['g_mid'], '-')
        self.assertEqual(metadata[str(self.card_b.id)]['g_bot'], 'X')
        self.assertEqual(metadata[str(self.card_b.id)]['text'], 'B 효과')

    def test_simulator_actions_reveal_battle_phase_and_undo(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        hand_card = session.document['state']['players']['p1']['zones']['hand'][0]

        response = self.post_json(action_url, {
            'action': 'move_card',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': hand_card['instance_id'],
                'to_player': 'p1',
                'to_zone': 'battle',
            },
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        spectator = serialize_simulator_session(session)['state']
        self.assertTrue(spectator['players']['p1']['zones']['battle'][0]['hidden'])

        response = self.post_json(action_url, {
            'action': 'set_phase',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'phase': 'battle'},
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        spectator = serialize_simulator_session(session)['state']
        self.assertFalse(spectator['players']['p1']['zones']['battle'][0]['hidden'])
        self.assertEqual(session.document['events'][-1]['payload']['revealed_counts']['p1'], 1)
        self.assertEqual(session.document['events'][-1]['payload']['revealed_cards']['p1'][0]['card_label'], 'A 공격')
        spectator_events = serialize_simulator_session(session)['events']
        self.assertEqual(spectator_events[-1]['payload']['revealed_cards']['p1'][0]['card_label'], 'A 공격')

        response = self.post_json(action_url, {
            'action': 'undo',
            'seat': 'p1',
            'seat_token': session.player1_token,
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.document['state']['phase'], 'lumen')

        response = self.post_json(action_url, {
            'action': 'undo',
            'seat': 'p1',
            'seat_token': session.player1_token,
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(len(session.document['state']['players']['p1']['zones']['hand']), 1)
        self.assertEqual(len(session.document['events']), 0)

    def test_battle_zone_card_enters_face_up_after_ready_phase(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        response = self.post_json(action_url, {
            'action': 'set_phase',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'phase': 'get'},
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()

        hand_card = session.document['state']['players']['p1']['zones']['hand'][0]
        response = self.post_json(action_url, {
            'action': 'move_card',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': hand_card['instance_id'],
                'to_player': 'p1',
                'to_zone': 'battle',
            },
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        spectator = serialize_simulator_session(session)['state']
        battle_card = spectator['players']['p1']['zones']['battle'][0]
        self.assertFalse(battle_card['hidden'])
        self.assertTrue(battle_card['face_up'])

    def test_card_moved_to_hand_during_get_phase_stays_public(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        response = self.post_json(action_url, {
            'action': 'set_phase',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'phase': 'get'},
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        list_card = session.document['state']['players']['p1']['zones']['list'][0]

        response = self.post_json(action_url, {
            'action': 'move_card',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': list_card['instance_id'],
                'to_player': 'p1',
                'to_zone': 'hand',
            },
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        moved = next(
            card for card in session.document['state']['players']['p1']['zones']['hand']
            if card['instance_id'] == list_card['instance_id']
        )
        spectator = serialize_simulator_session(session)['state']
        spectator_card = next(
            card for card in spectator['players']['p1']['zones']['hand']
            if card['instance_id'] == list_card['instance_id']
        )
        self.assertTrue(moved['face_up'])
        self.assertFalse(spectator_card['hidden'])

    def test_get_phase_end_hides_all_hands(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        response = self.post_json(action_url, {
            'action': 'set_phase',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'phase': 'get'},
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        p1_list_card = session.document['state']['players']['p1']['zones']['list'][0]
        p2_list_card = session.document['state']['players']['p2']['zones']['list'][0]

        for seat, token, card in (
            ('p1', session.player1_token, p1_list_card),
            ('p2', session.player2_token, p2_list_card),
        ):
            response = self.post_json(action_url, {
                'action': 'move_card',
                'seat': seat,
                'seat_token': token,
                'payload': {
                    'card_instance_id': card['instance_id'],
                    'to_player': seat,
                    'to_zone': 'hand',
                },
            })
            self.assertEqual(response.status_code, 200)
            session.refresh_from_db()

        response = self.post_json(action_url, {
            'action': 'set_phase',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'phase': 'recovery'},
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()

        state = session.document['state']
        self.assertTrue(all(not card['face_up'] for card in state['players']['p1']['zones']['hand']))
        self.assertTrue(all(not card['face_up'] for card in state['players']['p2']['zones']['hand']))
        spectator = serialize_simulator_session(session)['state']
        self.assertTrue(all(card['hidden'] for card in spectator['players']['p1']['zones']['hand']))
        self.assertTrue(all(card['hidden'] for card in spectator['players']['p2']['zones']['hand']))
        self.assertEqual(session.document['events'][-1]['payload']['hidden_hand_counts']['p1'], 2)
        self.assertEqual(session.document['events'][-1]['payload']['hidden_hand_counts']['p2'], 2)

    def test_public_card_name_stays_visible_in_move_log_when_moved_private(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        list_card = session.document['state']['players']['p1']['zones']['list'][0]

        response = self.post_json(action_url, {
            'action': 'move_card',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': list_card['instance_id'],
                'to_player': 'p1',
                'to_zone': 'hand',
            },
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        spectator = serialize_simulator_session(session)
        moved_card = next(
            card
            for card in spectator['state']['players']['p1']['zones']['hand']
            if card['instance_id'] == list_card['instance_id']
        )
        self.assertTrue(moved_card['hidden'])
        self.assertEqual(spectator['events'][-1]['payload']['card_label'], 'A 공격')

    def test_phase_start_requests_priority_player_except_ready(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        document = session.document
        state = document['state']
        state['players']['p1']['fp'] = 1
        state['players']['p2']['fp'] = 3
        state['priority_player'] = 'p1'
        session.document = document
        session.save(update_fields=['document'])

        response = self.post_json(action_url, {
            'action': 'set_phase',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'phase': 'get'},
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        state = session.document['state']
        self.assertTrue(state['status']['p2']['requested'])
        self.assertFalse(state['status']['p1']['requested'])
        self.assertEqual(state['priority_player'], 'p2')
        self.assertEqual(session.document['events'][-1]['payload']['priority_player'], 'p2')

        response = self.post_json(action_url, {
            'action': 'set_phase',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'phase': 'ready'},
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertFalse(session.document['state']['status']['p1']['requested'])
        self.assertFalse(session.document['state']['status']['p2']['requested'])

        response = self.post_json(action_url, {
            'action': 'set_phase',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'phase': 'battle'},
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertFalse(session.document['state']['status']['p1']['requested'])
        self.assertFalse(session.document['state']['status']['p2']['requested'])

    def test_done_auto_advances_phase_when_opponent_is_done(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        document = session.document
        state = document['state']
        state['phase'] = 'recovery'
        state['turn'] = 1
        state['priority_player'] = 'p2'
        state['players']['p1']['hp'] = 5000
        state['players']['p2']['hp'] = 5000
        state['players']['p1']['fp'] = 0
        state['players']['p2']['fp'] = 0
        state['status'] = {
            'p1': {'requested': True, 'done': False},
            'p2': {'requested': False, 'done': True},
        }
        session.document = document
        session.save(update_fields=['document'])

        response = self.post_json(action_url, {
            'action': 'set_done',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'done': True},
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        state = session.document['state']
        phase_event = session.document['events'][-1]
        done_event = session.document['events'][-2]
        self.assertEqual(state['turn'], 2)
        self.assertEqual(state['phase'], 'lumen')
        self.assertTrue(state['status']['p2']['requested'])
        self.assertFalse(state['status']['p1']['done'])
        self.assertEqual(done_event['type'], 'set_done')
        self.assertEqual(phase_event['type'], 'phase_advance')
        self.assertEqual(phase_event['payload']['from_phase'], 'recovery')
        self.assertEqual(phase_event['payload']['to_phase'], 'lumen')

    def test_done_requests_opponent_when_opponent_is_not_done(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        document = session.document
        document['state']['status'] = {
            'p1': {'requested': True, 'done': False},
            'p2': {'requested': False, 'done': False},
        }
        session.document = document
        session.save(update_fields=['document'])

        response = self.post_json(action_url, {
            'action': 'set_done',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'done': True},
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        state = session.document['state']
        event = session.document['events'][-1]
        self.assertTrue(state['status']['p1']['done'])
        self.assertFalse(state['status']['p1']['requested'])
        self.assertTrue(state['status']['p2']['requested'])
        self.assertFalse(state['status']['p2']['done'])
        self.assertEqual(event['payload']['requested_opponent'], 'p2')

    def test_simulator_tracks_hp_fp_changes_for_current_turn(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        for action, payload in [
            ('hp', {'target': 'p1', 'amount': -500}),
            ('hp', {'target': 'p1', 'amount': 100}),
            ('fp', {'target': 'p1', 'amount': 2}),
            ('fp_reset', {'target': 'p1'}),
        ]:
            response = self.post_json(action_url, {
                'action': action,
                'seat': 'p1',
                'seat_token': session.player1_token,
                'payload': payload,
            })
            self.assertEqual(response.status_code, 200)
            session.refresh_from_db()

        state = session.document['state']
        self.assertEqual(state['players']['p1']['hp'], state['players']['p1']['initial_hp'] - 400)
        self.assertEqual(state['players']['p1']['fp'], 0)
        self.assertEqual(state['turn_changes']['p1']['hp'], -400)
        self.assertEqual(state['turn_changes']['p1']['fp'], 0)
        self.assertTrue(state['turn_changes']['p1']['hp_changed'])
        self.assertTrue(state['turn_changes']['p1']['fp_changed'])

        response = self.post_json(action_url, {
            'action': 'next_turn',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {},
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.document['state']['turn'], 2)
        self.assertEqual(session.document['state']['turn_changes']['p1']['hp'], 0)
        self.assertEqual(session.document['state']['turn_changes']['p1']['fp'], 0)
        self.assertFalse(session.document['state']['turn_changes']['p1']['hp_changed'])
        self.assertFalse(session.document['state']['turn_changes']['p1']['fp_changed'])

    def test_simulator_rejects_stale_hp_fp_counter_revision(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        initial_hp = session.document['state']['players']['p1']['hp']

        response = self.post_json(action_url, {
            'action': 'hp',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'target': 'p1', 'amount': -500, 'base_revision': 0},
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.document['state']['players']['p1']['hp'], initial_hp - 500)
        self.assertEqual(session.document['state']['counter_revisions']['p1']['hp'], 1)

        response = self.post_json(action_url, {
            'action': 'hp',
            'seat': 'p2',
            'seat_token': session.player2_token,
            'payload': {'target': 'p1', 'amount': -500, 'base_revision': 0},
        })
        self.assertEqual(response.status_code, 400)
        session.refresh_from_db()
        self.assertEqual(session.document['state']['players']['p1']['hp'], initial_hp - 500)
        self.assertEqual(session.document['state']['counter_revisions']['p1']['hp'], 1)

        response = self.post_json(action_url, {
            'action': 'fp',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'target': 'p1', 'amount': 1, 'base_revision': 0},
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.document['state']['players']['p1']['fp'], 1)
        self.assertEqual(session.document['state']['counter_revisions']['p1']['fp'], 1)

        response = self.post_json(action_url, {
            'action': 'fp_reset',
            'seat': 'p2',
            'seat_token': session.player2_token,
            'payload': {'target': 'p1', 'base_revision': 0},
        })
        self.assertEqual(response.status_code, 400)
        session.refresh_from_db()
        self.assertEqual(session.document['state']['players']['p1']['fp'], 1)
        self.assertEqual(session.document['state']['counter_revisions']['p1']['fp'], 1)

    def test_simulator_signal_logs_and_updates_last_signal(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        response = self.post_json(action_url, {
            'action': 'signal',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'signal': 'combo'},
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        event = session.document['events'][-1]
        last_signal = session.document['state']['last_signal']
        self.assertEqual(event['type'], 'signal')
        self.assertEqual(event['payload']['signal'], 'combo')
        self.assertEqual(event['payload']['label'], '콤보 타임')
        self.assertEqual(last_signal['id'], event['id'])
        self.assertEqual(last_signal['actor'], 'p1')
        self.assertEqual(last_signal['label'], '콤보 타임')

    def test_battle_phase_cleanup_moves_ready_cards_to_private_hand_and_others_to_list(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        hand_card = session.document['state']['players']['p1']['zones']['hand'][0]
        list_card = session.document['state']['players']['p1']['zones']['list'][0]

        response = self.post_json(action_url, {
            'action': 'move_card',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': hand_card['instance_id'],
                'to_player': 'p1',
                'to_zone': 'battle',
            },
        })
        self.assertEqual(response.status_code, 200)

        response = self.post_json(action_url, {
            'action': 'set_phase',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'phase': 'battle'},
        })
        self.assertEqual(response.status_code, 200)

        response = self.post_json(action_url, {
            'action': 'move_card',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': list_card['instance_id'],
                'to_player': 'p1',
                'to_zone': 'battle',
            },
        })
        self.assertEqual(response.status_code, 200)

        response = self.post_json(action_url, {
            'action': 'set_phase',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'phase': 'get'},
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        state = session.document['state']
        self.assertEqual(state['players']['p1']['zones']['battle'], [])
        ready_card = next(card for card in state['players']['p1']['zones']['hand'] if card['instance_id'] == hand_card['instance_id'])
        other_card = next(card for card in state['players']['p1']['zones']['list'] if card['instance_id'] == list_card['instance_id'])
        self.assertFalse(ready_card['face_up'])
        self.assertTrue(other_card['face_up'])
        self.assertEqual(session.document['events'][-1]['payload']['battle_cleanup']['hand']['p1'], 1)
        self.assertEqual(session.document['events'][-1]['payload']['battle_cleanup']['list']['p1'], 1)

    def test_import_card_creates_face_up_card_in_actor_lumen_zone(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        response = self.post_json(action_url, {
            'action': 'import_card',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'card_name': '외부 카드'},
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        lumen_cards = session.document['state']['players']['p1']['zones']['lumen']
        self.assertEqual(len(lumen_cards), 1)
        self.assertEqual(lumen_cards[0]['name'], '외부 카드')
        self.assertEqual(lumen_cards[0]['owner'], 'p1')
        self.assertTrue(lumen_cards[0]['face_up'])
        self.assertTrue(lumen_cards[0]['instance_id'].startswith('p1-external-'))
        viewer_state = serialize_simulator_session(session)['state']
        viewer_card = viewer_state['players']['p1']['zones']['lumen'][0]
        self.assertFalse(viewer_card['hidden'])
        metadata = serialize_simulator_card_metadata([viewer_card['card_id']])
        self.assertEqual(metadata[str(self.external_card.id)]['text'], '외부 효과')

        response = self.post_json(action_url, {
            'action': 'undo',
            'seat': 'p1',
            'seat_token': session.player1_token,
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.document['state']['players']['p1']['zones']['lumen'], [])

    def test_timer_timeout_is_logged_once_by_opponent(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        response = self.post_json(action_url, {
            'action': 'timer',
            'seat': 'p1',
            'seat_token': session.player1_token,
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.document['state']['timer']['owner'], 'p1')

        document = session.document
        document['state']['timer']['started_at'] = (timezone.now() - timedelta(seconds=11)).isoformat()
        session.document = document
        session.save(update_fields=['document'])

        response = self.post_json(action_url, {
            'action': 'timer_timeout',
            'seat': 'p2',
            'seat_token': session.player2_token,
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.document['events'][-1]['type'], 'timer_timeout')
        self.assertEqual(session.document['events'][-1]['payload']['target'], 'p1')
        self.assertTrue(session.document['state']['timer']['timeout_reported'])
        event_count = len(session.document['events'])

        response = self.post_json(action_url, {
            'action': 'timer_timeout',
            'seat': 'p2',
            'seat_token': session.player2_token,
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(len(session.document['events']), event_count)

    def test_card_can_move_to_opponent_lumen_or_battle_but_visibility_stays_with_owner(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        hand_card = session.document['state']['players']['p1']['zones']['hand'][0]

        response = self.post_json(action_url, {
            'action': 'move_card',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': hand_card['instance_id'],
                'to_player': 'p2',
                'to_zone': 'battle',
            },
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        moved_card = session.document['state']['players']['p2']['zones']['battle'][0]
        self.assertEqual(moved_card['owner'], 'p1')
        self.assertFalse(moved_card['face_up'])
        self.assertEqual(session.document['state']['players']['p1']['zones']['hand'], [])

        p2_state = serialize_simulator_session(session, 'p2', session.player2_token)['state']
        self.assertTrue(p2_state['players']['p2']['zones']['battle'][0]['hidden'])

        response = self.post_json(action_url, {
            'action': 'set_visibility',
            'seat': 'p2',
            'seat_token': session.player2_token,
            'payload': {
                'card_instance_id': hand_card['instance_id'],
                'face_up': True,
            },
        })
        self.assertEqual(response.status_code, 403)

        response = self.post_json(action_url, {
            'action': 'set_visibility',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': hand_card['instance_id'],
                'face_up': True,
            },
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        p2_state = serialize_simulator_session(session, 'p2', session.player2_token)['state']
        self.assertFalse(p2_state['players']['p2']['zones']['battle'][0]['hidden'])

        response = self.post_json(action_url, {
            'action': 'move_card',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': hand_card['instance_id'],
                'to_player': 'p2',
                'to_zone': 'hand',
            },
        })
        self.assertEqual(response.status_code, 400)

        response = self.post_json(action_url, {
            'action': 'bulk_move',
            'seat': 'p2',
            'seat_token': session.player2_token,
            'payload': {
                'player': 'p2',
                'from_zone': 'battle',
                'to_zone': 'hand',
            },
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.document['state']['players']['p2']['zones']['battle'], [])
        self.assertEqual(len(session.document['state']['players']['p1']['zones']['hand']), 1)
        self.assertEqual(session.document['state']['players']['p1']['zones']['hand'][0]['owner'], 'p1')
        self.assertTrue(session.document['state']['players']['p1']['zones']['hand'][0]['face_up'])

    def test_public_card_becomes_private_when_moved_to_private_zone(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        list_card = session.document['state']['players']['p1']['zones']['list'][0]

        response = self.post_json(action_url, {
            'action': 'move_card',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': list_card['instance_id'],
                'to_player': 'p1',
                'to_zone': 'hand',
            },
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        moved_card = [
            card for card in session.document['state']['players']['p1']['zones']['hand']
            if card['instance_id'] == list_card['instance_id']
        ][0]
        self.assertFalse(moved_card['face_up'])
        viewer_state = serialize_simulator_session(session)['state']
        viewer_card = [
            card for card in viewer_state['players']['p1']['zones']['hand']
            if card['instance_id'] == list_card['instance_id']
        ][0]
        self.assertTrue(viewer_card['hidden'])

    def test_visibility_is_preserved_between_toggleable_zones(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        hand_card = session.document['state']['players']['p1']['zones']['hand'][0]

        response = self.post_json(action_url, {
            'action': 'set_visibility',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': hand_card['instance_id'],
                'face_up': True,
            },
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertTrue(session.document['state']['players']['p1']['zones']['hand'][0]['face_up'])

        response = self.post_json(action_url, {
            'action': 'move_card',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': hand_card['instance_id'],
                'to_player': 'p1',
                'to_zone': 'lumen',
            },
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertTrue(session.document['state']['players']['p1']['zones']['lumen'][0]['face_up'])

    def test_visibility_log_keeps_card_name_after_card_is_hidden_again(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        hand_card = session.document['state']['players']['p1']['zones']['hand'][0]

        response = self.post_json(action_url, {
            'action': 'set_visibility',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': hand_card['instance_id'],
                'face_up': True,
            },
        })
        self.assertEqual(response.status_code, 200)

        response = self.post_json(action_url, {
            'action': 'set_visibility',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': hand_card['instance_id'],
                'face_up': False,
            },
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()

        spectator = serialize_simulator_session(session)
        self.assertTrue(spectator['state']['players']['p1']['zones']['hand'][0]['hidden'])
        self.assertEqual(spectator['events'][-2]['payload']['card_label'], 'A 공격')
        self.assertEqual(spectator['events'][-1]['payload']['card_label'], 'A 공격')
        self.assertFalse(spectator['events'][-1]['payload']['face_up'])

    def test_blackout_random_get_moves_random_opponent_list_card_to_public_hand(self):
        blackout = Card.objects.create(
            name='블랙아웃',
            type='특수 기술',
            text='상대 리스트를 뒷면으로 셔플한다.',
            character=self.char_a,
            img='https://example.com/blackout.png',
        )
        CardInDeck.objects.create(deck=self.deck_a, card=blackout, count=1)
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        source_card = [
            card for card in session.document['state']['players']['p1']['zones']['list']
            if card['name'] == '블랙아웃'
        ][0]
        opponent_card = session.document['state']['players']['p2']['zones']['list'][0]

        response = self.post_json(action_url, {
            'action': 'blackout_random_get',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'source_card_instance_id': source_card['instance_id'],
            },
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        state = session.document['state']
        self.assertEqual(state['players']['p2']['zones']['list'], [])
        moved_card = [
            card for card in state['players']['p2']['zones']['hand']
            if card['instance_id'] == opponent_card['instance_id']
        ][0]
        self.assertTrue(moved_card['face_up'])
        event = session.document['events'][-1]
        self.assertEqual(event['type'], 'blackout_random_get')
        self.assertEqual(event['payload']['source_card_label'], '블랙아웃')
        self.assertEqual(event['payload']['card_label'], 'B 수비')

        response = self.post_json(action_url, {
            'action': 'undo',
            'seat': 'p1',
            'seat_token': session.player1_token,
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(len(session.document['state']['players']['p2']['zones']['list']), 1)

    def test_shuffle_hand_reorders_hand_and_replays_with_undo(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        for source_zone in ('list', 'side'):
            card = session.document['state']['players']['p1']['zones'][source_zone][0]
            response = self.post_json(action_url, {
                'action': 'move_card',
                'seat': 'p1',
                'seat_token': session.player1_token,
                'payload': {
                    'card_instance_id': card['instance_id'],
                    'to_player': 'p1',
                    'to_zone': 'hand',
                },
            })
            self.assertEqual(response.status_code, 200)
            session.refresh_from_db()

        before_order = [
            card['instance_id']
            for card in session.document['state']['players']['p1']['zones']['hand']
        ]
        shuffled_order = list(reversed(before_order))

        response = self.post_json(action_url, {
            'action': 'shuffle_hand',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'player': 'p1',
                'order': shuffled_order,
            },
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(
            [card['instance_id'] for card in session.document['state']['players']['p1']['zones']['hand']],
            shuffled_order,
        )
        self.assertEqual(session.document['events'][-1]['payload']['order'], shuffled_order)

        response = self.post_json(action_url, {
            'action': 'undo',
            'seat': 'p1',
            'seat_token': session.player1_token,
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(
            [card['instance_id'] for card in session.document['state']['players']['p1']['zones']['hand']],
            before_order,
        )

    def test_shuffle_hand_has_short_cooldown(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        for source_zone in ('list', 'side'):
            card = session.document['state']['players']['p1']['zones'][source_zone][0]
            response = self.post_json(action_url, {
                'action': 'move_card',
                'seat': 'p1',
                'seat_token': session.player1_token,
                'payload': {
                    'card_instance_id': card['instance_id'],
                    'to_player': 'p1',
                    'to_zone': 'hand',
                },
            })
            self.assertEqual(response.status_code, 200)
            session.refresh_from_db()

        order = [
            card['instance_id']
            for card in session.document['state']['players']['p1']['zones']['hand']
        ]
        first_response = self.post_json(action_url, {
            'action': 'shuffle_hand',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'player': 'p1',
                'order': list(reversed(order)),
            },
        })
        self.assertEqual(first_response.status_code, 200)
        session.refresh_from_db()
        self.assertIn('p1', session.document['state']['hand_shuffle_cooldowns'])

        second_response = self.post_json(action_url, {
            'action': 'shuffle_hand',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'player': 'p1',
                'order': order,
            },
        })
        self.assertEqual(second_response.status_code, 400)

    def test_yohan_declaration_reveals_random_opponent_private_hand_card(self):
        yohan = Character.objects.create(
            name='요한',
            description='',
            group='',
            datas={'hand': {'5000': 6}},
            img='https://example.com/yohan.png',
        )
        yohan_deck = Deck.objects.create(name='요한 덱', author=self.user, character=yohan)
        session = create_simulator_session('요한', 'B', yohan_deck, self.deck_b)
        self.assertEqual(
            session.document['state']['players']['p1']['passive_state']['foresight_counter']['count'],
            2,
        )
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        response = self.post_json(action_url, {
            'action': 'yohan_declare_reveal',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'target': 'p1',
                'declaration': 'odd',
            },
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        revealed = session.document['state']['players']['p2']['zones']['hand'][0]
        event = session.document['events'][-1]
        self.assertTrue(revealed['face_up'])
        self.assertEqual(event['type'], 'yohan_declare_reveal')
        self.assertEqual(event['payload']['declaration_label'], '홀수')
        self.assertEqual(event['payload']['card_instance_id'], revealed['instance_id'])
        self.assertEqual(event['payload']['card_label'], 'B 수비')

        viewer_events = serialize_simulator_session(session)['events']
        self.assertEqual(viewer_events[-1]['payload']['card_label'], 'B 수비')

    def test_yohan_foresight_reveals_random_opponent_private_hand_card(self):
        yohan = Character.objects.create(
            name='요한',
            description='',
            group='',
            datas={'hand': {'5000': 6}},
            img='https://example.com/yohan.png',
        )
        yohan_deck = Deck.objects.create(name='요한 덱', author=self.user, character=yohan)
        session = create_simulator_session('요한', 'B', yohan_deck, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        response = self.post_json(action_url, {
            'action': 'yohan_foresight_reveal',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'target': 'p1',
            },
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        revealed = session.document['state']['players']['p2']['zones']['hand'][0]
        event = session.document['events'][-1]
        self.assertTrue(revealed['face_up'])
        self.assertEqual(event['type'], 'yohan_foresight_reveal')
        self.assertEqual(event['payload']['card_instance_id'], revealed['instance_id'])
        self.assertEqual(event['payload']['card_label'], 'B 수비')

    def test_nia_moves_attack_and_defense_cards_from_lumen_to_owner_list(self):
        nia = Character.objects.create(
            name='니아',
            description='',
            group='',
            datas={'hand': {'5000': 6}},
            img='https://example.com/nia-sim.png',
        )
        attack = Card.objects.create(
            name='니아 공격',
            type='공격',
            character=nia,
            img='https://example.com/nia-attack.png',
        )
        defense = Card.objects.create(
            name='니아 수비',
            type='수비',
            character=nia,
            img='https://example.com/nia-defense.png',
        )
        special = Card.objects.create(
            name='니아 특수',
            type='특수 기술',
            character=nia,
            img='https://example.com/nia-special.png',
        )
        nia_deck = Deck.objects.create(name='니아 덱', author=self.user, character=nia)
        CardInDeck.objects.create(deck=nia_deck, card=attack, count=1)
        CardInDeck.objects.create(deck=nia_deck, card=defense, count=1)
        CardInDeck.objects.create(deck=nia_deck, card=special, count=1)
        session = create_simulator_session('니아', 'B', nia_deck, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        for card in list(session.document['state']['players']['p1']['zones']['list']):
            response = self.post_json(action_url, {
                'action': 'move_card',
                'seat': 'p1',
                'seat_token': session.player1_token,
                'payload': {
                    'card_instance_id': card['instance_id'],
                    'to_player': 'p1',
                    'to_zone': 'lumen',
                },
            })
            self.assertEqual(response.status_code, 200)
            session.refresh_from_db()

        response = self.post_json(action_url, {
            'action': 'nia_lumen_cards_to_list',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'target': 'p1'},
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        state = session.document['state']
        self.assertEqual([card['name'] for card in state['players']['p1']['zones']['lumen']], ['니아 특수'])
        self.assertEqual(
            sorted(card['name'] for card in state['players']['p1']['zones']['list']),
            ['니아 공격', '니아 수비'],
        )
        self.assertEqual(session.document['events'][-1]['payload']['count'], 2)

    def test_cmyk_new_single_creates_ten_tokens_once_and_can_be_undone(self):
        cmyk = Character.objects.create(
            name='CMYK',
            description='',
            group='',
            datas={'hand': {'5000': 6}},
            img='https://example.com/cmyk.png',
        )
        new_single = Card.objects.create(
            name='뉴 싱글',
            type='토큰',
            character=cmyk,
            img='https://example.com/new-single.png',
        )
        cmyk_deck = Deck.objects.create(name='CMYK 덱', author=self.user, character=cmyk)
        session = create_simulator_session('CMYK', 'B', cmyk_deck, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})

        response = self.post_json(action_url, {
            'action': 'cmyk_new_single',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'target': 'p1'},
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        lumen_cards = session.document['state']['players']['p1']['zones']['lumen']
        passive_state = session.document['state']['players']['p1']['passive_state']
        self.assertEqual(len(lumen_cards), 10)
        self.assertTrue(all(card['card_id'] == new_single.id for card in lumen_cards))
        self.assertTrue(all(card['face_up'] for card in lumen_cards))
        self.assertTrue(passive_state['new_single_created']['value'])
        self.assertEqual(session.document['events'][-1]['payload']['count'], 10)
        self.assertEqual(len(session.document['events'][-1]['payload']['cards']), 10)

        token_card = lumen_cards[0]
        response = self.post_json(action_url, {
            'action': 'move_card',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'card_instance_id': token_card['instance_id'],
                'to_player': 'p1',
                'to_zone': 'break',
            },
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(len(session.document['state']['players']['p1']['zones']['lumen']), 9)
        self.assertEqual(session.document['state']['players']['p1']['zones']['break'], [])
        self.assertTrue(session.document['events'][-1]['payload']['deleted_token'])

        response = self.post_json(action_url, {
            'action': 'undo',
            'seat': 'p1',
            'seat_token': session.player1_token,
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(len(session.document['state']['players']['p1']['zones']['lumen']), 10)

        response = self.post_json(action_url, {
            'action': 'cmyk_new_single',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {'target': 'p1'},
        })
        self.assertEqual(response.status_code, 400)

        response = self.post_json(action_url, {
            'action': 'undo',
            'seat': 'p1',
            'seat_token': session.player1_token,
        })
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.document['state']['players']['p1']['zones']['lumen'], [])
        self.assertNotIn('new_single_created', session.document['state']['players']['p1']['passive_state'])

    def test_batch_action_applies_simulator_actions_in_order(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        list_card = session.document['state']['players']['p1']['zones']['list'][0]
        side_card = session.document['state']['players']['p1']['zones']['side'][0]

        response = self.post_json(action_url, {
            'action': 'batch',
            'seat': 'p1',
            'seat_token': session.player1_token,
            'payload': {
                'actions': [
                    {
                        'action': 'move_card',
                        'payload': {
                            'card_instance_id': list_card['instance_id'],
                            'to_player': 'p1',
                            'to_zone': 'hand',
                        },
                    },
                    {
                        'action': 'move_card',
                        'payload': {
                            'card_instance_id': side_card['instance_id'],
                            'to_player': 'p1',
                            'to_zone': 'hand',
                        },
                    },
                    {
                        'action': 'passive',
                        'payload': {
                            'target': 'p1',
                            'key': 'sim_counter',
                            'delta': 2,
                            'label': '시뮬 카운터',
                        },
                    },
                ],
            },
        })

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(len(session.document['state']['players']['p1']['zones']['hand']), 3)
        self.assertEqual(session.document['state']['players']['p1']['passive_state']['sim_counter']['count'], 2)
        self.assertEqual([event['type'] for event in session.document['events'][-3:]], ['move_card', 'move_card', 'passive'])
        self.assertEqual(session.version, 2)

    def test_simulator_compacts_large_event_log(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        action_url = reverse('battlelog:simulatorAction', kwargs={'view_token': session.view_token})
        batch = [
            {
                'action': 'passive',
                'payload': {
                    'target': 'p1',
                    'key': 'sim_counter',
                    'delta': 1,
                    'label': '시뮬 카운터',
                },
            }
            for _ in range(100)
        ]

        for _ in range(9):
            response = self.post_json(action_url, {
                'action': 'batch',
                'seat': 'p1',
                'seat_token': session.player1_token,
                'payload': {'actions': batch},
            })
            self.assertEqual(response.status_code, 200)
            session.refresh_from_db()

        document = session.document
        self.assertEqual(document['state']['players']['p1']['passive_state']['sim_counter']['count'], 900)
        self.assertEqual(document['archived_event_count'], 400)
        self.assertEqual(len(document['events']), 500)
        payload = serialize_simulator_session(session, 'p1', session.player1_token)
        self.assertEqual(payload['event_count'], 900)
        self.assertEqual(len(payload['events']), 150)

    def test_cleanup_removes_expired_simulator_sessions(self):
        session = create_simulator_session('A', 'B', self.deck_a, self.deck_b)
        session.expires_at = timezone.now() - timedelta(minutes=1)
        session.save(update_fields=['expires_at'])

        deleted = cleanup_expired_sessions()

        self.assertGreaterEqual(deleted, 1)
        self.assertFalse(LumenSimulatorSession.objects.exists())
