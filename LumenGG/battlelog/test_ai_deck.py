"""AI 덱: TOML 설정(성향·상황별 선호·콤보 루트), 대처 카드 계산, 패배 확정 회피, 로비 연결."""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from deck.models import Deck

from . import test_automatic_engine as engine_tests
from .game.ai import DEFAULT_POLICY_WEIGHTS, choose_action, counter_targets, score_action
from .game.ai_preview import certain_loss, minimum_answer_cards, preview_battle
from .game.ai_profile import (
    ProfileError,
    condition_matches,
    default_ai_profile_text,
    normalize_profile,
    parse_profile_text,
    profile_bonus,
    profile_weights,
)
from .game.engine import AutomaticGameEngine
from .models import LumenSimulatorSession, SimulatorAIDeck
from .test_automatic_engine import attack, base_state, defense, ruleset


def card_action(action_type, *codes, action_id=None):
    cards = [{'code': code, 'type': '공격', 'frame': 5, 'damage': 300} for code in codes]
    action = {'type': action_type, 'action_id': action_id or f'{action_type}:{"-".join(codes)}'}
    if len(cards) == 1:
        action['card'] = cards[0]
    else:
        action['cards'] = cards
    return action


def observation(*, my_hp=5000, rival_hp=5000, turn=1, combo=None, my_hand=(), rival=None, my_list=()):
    state = {
        'turn': turn,
        'players': {
            'p1': {'hp': my_hp, 'fp': 0, 'zones': {'hand': list(my_hand), 'list': list(my_list)}},
            'p2': {'hp': rival_hp, 'fp': 0, 'zones': rival or {}},
        },
        'engine': {},
    }
    if combo:
        state['engine']['combo'] = {'owner': 'p1', 'used_codes': [], 'selected_first_code': None, **combo}
    return {'state': state}


def visible(card):
    return {**card, 'hidden': False}


class AIProfileTextTests(SimpleTestCase):
    def test_template_parses_to_safe_defaults(self):
        profile = parse_profile_text(default_ai_profile_text())

        self.assertEqual(profile['style'], 'balanced')
        self.assertEqual(profile['combos'], [])
        self.assertTrue(profile['counter']['enabled'])
        self.assertTrue(profile['safety']['avoid_certain_loss'])

    def test_full_profile_text(self):
        profile = parse_profile_text('''
style = "aggressive"
[weights]
card_speed = 0.5
[prefer]
"A" = 2
[[situation]]
name = "지고 있을 때"
when = { hp_lead_max = -1000, action = ["ready"] }
prefer = { "B" = 3 }
[[combo]]
name = "기본"
cards = ["A", "B", "C"]
[[combo]]
name = "마무리"
cards = ["A", "D"]
bonus = 5
when = { rival_hp_max = 1500 }
[counter]
scope = "hand_and_list"
[safety]
avoid_certain_loss = false
''', allowed_codes={'A', 'B', 'C', 'D'})

        self.assertEqual(profile['weights'], {'card_speed': 0.5})
        self.assertEqual(profile['situations'][0]['when'], {'hp_lead_max': -1000.0, 'action': ['ready']})
        self.assertEqual([route['name'] for route in profile['combos']], ['기본', '마무리'])
        self.assertEqual(profile['combos'][0]['bonus'], 3.0)
        self.assertEqual(profile['counter']['scope'], 'hand_and_list')
        self.assertFalse(profile['safety']['avoid_certain_loss'])

    def test_errors_are_collected_in_korean(self):
        with self.assertRaises(ProfileError) as caught:
            parse_profile_text('''
style = "reckless"
mystery = 1
[weights]
concede = 5
[prefer]
"ZZZ" = 1
[[situation]]
when = { moon_phase = 1 }
prefer = { "A" = 1 }
[[combo]]
cards = ["A"]
''', allowed_codes={'A'})

        message = str(caught.exception)
        for expected in (
            '알 수 없는 항목입니다: mystery', '알 수 없는 성향', '조절할 수 없는 가중치입니다: concede',
            '덱에 없는 카드 코드입니다: ZZZ', '알 수 없는 조건입니다: moon_phase', 'cards는 2~',
        ):
            self.assertIn(expected, message)

    def test_toml_syntax_error_is_reported(self):
        with self.assertRaisesRegex(ProfileError, 'TOML 문법 오류'):
            parse_profile_text('style = ')


class AIProfileScoringTests(SimpleTestCase):
    def test_style_weights_and_situations_never_touch_safety(self):
        profile = normalize_profile({
            'style': 'aggressive', 'weights': {'card_speed': 0.5},
            'situation': [{'when': {'my_hp_max': 1000}, 'weights': {'card_defense': 4}}],
        })

        calm = profile_weights(DEFAULT_POLICY_WEIGHTS, profile, observation(my_hp=4000), 'p1')
        danger = profile_weights(DEFAULT_POLICY_WEIGHTS, profile, observation(my_hp=800), 'p1')

        self.assertEqual(calm['card_attack'], 2.5)
        self.assertEqual(calm['card_speed'], 0.5)
        self.assertEqual(calm['card_defense'], -0.5)
        self.assertEqual(danger['card_defense'], 4)
        self.assertEqual(danger['concede'], DEFAULT_POLICY_WEIGHTS['concede'])

    def test_conditions(self):
        obs = observation(
            my_hp=1200, rival_hp=3000, turn=4,
            my_hand=[visible(attack('mine', 'p1', code='MINE'))],
            rival={'hand': [visible(attack('shown', 'p2', code='SHOWN')), {'hidden': True, 'code': 'SECRET'}]},
        )
        ready = card_action('ready_card', 'X')

        self.assertTrue(condition_matches({'my_hp_max': 1500, 'turn_min': 3, 'hp_lead_max': -1000}, obs, 'p1', ready))
        self.assertFalse(condition_matches({'rival_hp_max': 2000}, obs, 'p1', ready))
        self.assertTrue(condition_matches({'action': ['ready', 'catch']}, obs, 'p1', ready))
        self.assertFalse(condition_matches({'action': ['get']}, obs, 'p1', ready))
        self.assertTrue(condition_matches({'rival_shows': ['SHOWN']}, obs, 'p1', ready))
        self.assertFalse(condition_matches({'rival_shows': ['SECRET']}, obs, 'p1', ready))
        self.assertTrue(condition_matches({'i_hold': ['MINE']}, obs, 'p1', ready))

    def test_preferences_apply_always_and_by_situation(self):
        profile = normalize_profile({
            'prefer': {'A': 2},
            'situation': [{'when': {'rival_hp_max': 1500}, 'prefer': {'A': 3, 'B': 1}}],
        })

        self.assertEqual(profile_bonus(observation(), 'p1', card_action('ready_card', 'A'), profile), 2)
        self.assertEqual(profile_bonus(observation(rival_hp=1000), 'p1', card_action('ready_card', 'A'), profile), 5)
        self.assertEqual(profile_bonus(observation(rival_hp=1000), 'p1', {'type': 'pass_phase'}, profile), 0)

    def test_combo_route_rewards_cards_that_continue_it(self):
        profile = normalize_profile({'combo': [{'cards': ['A', 'B', 'C', 'D'], 'bonus': 2}]})
        start = observation(combo={'source_code': 'A'})

        self.assertEqual(profile_bonus(start, 'p1', card_action('play_combo_pair', 'B', 'C'), profile), 4)
        self.assertEqual(profile_bonus(start, 'p1', card_action('play_combo_pair', 'C', 'B'), profile), 0)
        self.assertEqual(profile_bonus(
            observation(combo={'source_code': 'A', 'used_codes': ['B', 'C']}), 'p1',
            card_action('play_combo_card', 'D'), profile,
        ), 2 + 1)
        self.assertEqual(profile_bonus(
            observation(combo={'source_code': 'A', 'selected_first_code': 'B'}), 'p1',
            card_action('select_combo_followup', 'C'), profile,
        ), 2)

    def test_situational_routes_switch_with_the_board(self):
        profile = normalize_profile({'combo': [
            {'name': '평소', 'cards': ['A', 'B'], 'bonus': 2},
            {'name': '마무리', 'cards': ['A', 'C'], 'bonus': 4, 'when': {'rival_hp_max': 1500}},
        ]})
        pair_b = card_action('play_combo_card', 'B')
        pair_c = card_action('play_combo_card', 'C')

        early = observation(combo={'source_code': 'A'})
        late = observation(rival_hp=1200, combo={'source_code': 'A'})

        self.assertGreater(profile_bonus(early, 'p1', pair_b, profile), profile_bonus(early, 'p1', pair_c, profile))
        self.assertGreater(profile_bonus(late, 'p1', pair_c, profile), profile_bonus(late, 'p1', pair_b, profile))

    def test_route_starter_and_members_are_worth_readying_and_getting(self):
        profile = normalize_profile({'combo': [{'cards': ['A', 'B', 'C'], 'bonus': 4}]})

        self.assertEqual(profile_bonus(observation(), 'p1', card_action('ready_card', 'A'), profile), 2)
        self.assertEqual(profile_bonus(observation(), 'p1', card_action('ready_card', 'B'), profile), 0)
        self.assertAlmostEqual(profile_bonus(observation(), 'p1', card_action('select_get_card', 'C'), profile), 1.2)

    def test_score_action_includes_profile_bonus(self):
        profile = normalize_profile({'prefer': {'A': 3}})
        action = card_action('ready_card', 'A')

        self.assertAlmostEqual(
            score_action({}, 'p1', action, DEFAULT_POLICY_WEIGHTS, profile)
            - score_action({}, 'p1', action, DEFAULT_POLICY_WEIGHTS),
            3,
        )


class BattlePreviewTests(SimpleTestCase):
    def test_base_stat_battle_preview(self):
        fast = attack('fast', 'p1', frame=4, position='상단')
        slow = attack('slow', 'p2', frame=7, position='중단')
        guard_top = defense('guard', 'p2', top='방어')

        self.assertEqual(preview_battle(fast, slow), ('counter', 'countered'))
        self.assertEqual(preview_battle(slow, fast), ('countered', 'counter'))
        self.assertEqual(preview_battle(fast, guard_top), ('guarded', 'guard'))
        self.assertEqual(preview_battle(slow, guard_top), ('hit', 'failed_defense'))
        # FP는 속도를 줄여 준다.
        self.assertEqual(preview_battle(slow, fast, my_fp=4), ('counter', 'countered'))

    def test_certain_loss_needs_every_rival_option_visible(self):
        slow = attack('slow', 'p1', frame=9)
        fast = visible(attack('fast', 'p2', frame=3))
        faster = visible(attack('faster', 'p2', frame=2))

        known = observation(rival={'hand': [fast, faster]})
        partly_hidden = observation(rival={'hand': [fast, {'hidden': True}]})
        guard_option = observation(rival={'hand': [fast, visible(defense('g', 'p2', top='방어'))]})

        self.assertTrue(certain_loss(known, 'p1', slow))
        self.assertFalse(certain_loss(partly_hidden, 'p1', slow))
        self.assertFalse(certain_loss(guard_option, 'p1', slow))
        self.assertFalse(certain_loss(observation(rival={'hand': []}), 'p1', slow))

    def test_minimum_answer_set_covers_open_threats(self):
        top = visible(attack('top', 'p2', frame=3, position='상단'))
        low = visible(attack('low', 'p2', frame=3, position='하단'))
        guard_top = defense('guard-top', 'p1', top='방어')
        guard_low = defense('guard-low', 'p1', top=None, bottom='방어')
        guard_both = defense('guard-both', 'p1', top='방어', bottom='방어')
        obs = observation(rival={'hand': [top, low]})

        _threats, covers = minimum_answer_cards(obs, 'p1', [guard_top, guard_low, guard_both])

        self.assertEqual(covers, [{'guard-both'}])

    def test_threats_already_answered_in_hand_need_nothing(self):
        top = visible(attack('top', 'p2', frame=3, position='상단'))
        obs = observation(rival={'hand': [top]}, my_hand=[defense('held', 'p1', top='방어')])

        self.assertEqual(minimum_answer_cards(obs, 'p1', [defense('more', 'p1', top='방어')]), ([], []))


class AIEngineIntegrationTests(SimpleTestCase):
    def combo_engine(self):
        starter = attack('route-starter', 'p1', frame=5, hit='콤보')
        equal = attack('route-equal', 'p1', frame=5)
        rising = attack('route-rising', 'p1', frame=6)
        later = attack('route-later', 'p1', frame=7)
        opposing = attack('route-opposing', 'p2', frame=7)
        state = base_state([], [])
        state['phase'] = 'battle'
        state['players']['p1']['zones']['battle'] = [starter]
        state['players']['p1']['zones']['hand'] = [equal, rising, later]
        state['players']['p2']['zones']['battle'] = [opposing]
        engine = AutomaticGameEngine.initialize(
            state, ruleset(starter, equal, rising, later, opposing), seed='ai-route',
        )
        engine.state['phase'] = 'battle'
        engine.engine_state['battle'] = {
            'p1': {'instance_id': starter['instance_id'], 'card': starter},
            'p2': {'instance_id': opposing['instance_id'], 'card': opposing},
        }
        engine.grant_combo('p1', source=starter['instance_id'])
        return engine

    def test_observation_exposes_public_combo_progress(self):
        combo = self.combo_engine().observe('p2')['state']['engine']['combo']

        self.assertEqual(combo['owner'], 'p1')
        self.assertEqual(combo['source_code'], 'ROUTE-STARTER')
        self.assertEqual(combo['used_codes'], [])
        self.assertIsNone(combo['selected_first_code'])

    def test_ai_follows_registered_route_through_the_opening_pair(self):
        engine = self.combo_engine()
        profile = normalize_profile({'combo': [{
            'cards': ['ROUTE-STARTER', 'ROUTE-RISING', 'ROUTE-LATER'], 'bonus': 5,
        }]})

        plain = choose_action(engine.observe('p1'), 'p1', seed='route', temperature=0)
        first = choose_action(engine.observe('p1'), 'p1', seed='route', temperature=0, profile=profile)

        # 기본 정책은 더 빠른 카드부터 내지만, 루트가 있으면 루트 순서를 따른다.
        self.assertEqual(plain.action['type'], 'select_combo_first')
        self.assertEqual(plain.action['card']['code'], 'ROUTE-EQUAL')
        self.assertEqual(first.action['card']['code'], 'ROUTE-RISING')
        engine.submit_action('p1', first.action['action_id'], first.selections, command_id='route-first')
        self.assertEqual(engine.observe('p1')['state']['engine']['combo']['selected_first_code'], 'ROUTE-RISING')
        followup = choose_action(engine.observe('p1'), 'p1', seed='route', temperature=0, profile=profile)
        self.assertEqual(followup.action['type'], 'select_combo_followup')
        self.assertEqual(followup.action['card']['code'], 'ROUTE-LATER')

    def ready_engine(self, p1_hand, p2_hand):
        state = base_state([], [])
        state['players']['p1']['zones']['hand'] = p1_hand
        state['players']['p2']['zones']['hand'] = p2_hand
        engine = AutomaticGameEngine.initialize(state, ruleset(*p1_hand, *p2_hand), seed='ai-ready')
        for side in ('p1', 'p2'):
            action = next(item for item in engine.legal_actions(side) if item['type'] == 'pass_phase')
            engine.submit_action(side, action['action_id'], {}, command_id=f'pass-{side}')
        return engine

    def test_ai_never_readies_a_card_that_loses_to_every_known_rival_card(self):
        # 빠르지만 상대 수비에 막히는 카드보다, 느려도 지지 않는 카드를 낸다.
        p1_hand = [
            attack('strong-but-doomed', 'p1', frame=9, damage=900),
            defense('safe-guard', 'p1', top=None, mid='방어'),
        ]
        p2_hand = [
            {**attack('rival-fast', 'p2', frame=3, position='중단'), 'publicly_known': True},
            {**attack('rival-faster', 'p2', frame=2, position='중단'), 'publicly_known': True},
        ]
        engine = self.ready_engine(p1_hand, p2_hand)
        obs = engine.observe('p1')
        self.assertEqual(engine.state['phase'], 'ready')

        picks = {
            choose_action(obs, 'p1', seed=f'doom-{index}').action['card']['instance_id']
            for index in range(20)
        }

        self.assertEqual(picks, {'safe-guard'})

    def test_counter_targets_pick_the_list_card_that_answers_rival_threats(self):
        obs = observation(
            rival={'hand': [visible(attack('rival-top', 'p2', frame=3, position='상단'))]},
            my_list=[
                attack('useless', 'p1', frame=9, position='상단'),
                defense('answer', 'p1', top='방어'),
            ],
        )
        candidates = [
            {'type': 'select_get_card', 'action_id': 'get-useless', 'card': {'instance_id': 'useless', 'code': 'USELESS'}},
            {'type': 'select_get_card', 'action_id': 'get-answer', 'card': {'instance_id': 'answer', 'code': 'ANSWER'}},
        ]

        self.assertEqual(counter_targets(obs, 'p1', candidates), {'answer'})
        self.assertEqual(counter_targets(obs, 'p1', candidates, normalize_profile({'counter': {'enabled': False}})), set())


class AIDeckSessionTests(TestCase):
    # 검증된 전체 카드 릴리스, 활성 AI 정책, 카드 코드 AIH-000~019의 덱 두 개
    setUp = engine_tests.SimulatorAIHTTPTests.setUp

    PROFILE = '''
style = "aggressive"
[prefer]
"AIH-001" = 2
[[combo]]
cards = ["AIH-001", "AIH-002"]
'''

    def make_ai_deck(self, **fields):
        values = {'name': '연습 상대', 'deck': self.decks[1], 'profile_text': self.PROFILE, **fields}
        return SimulatorAIDeck.objects.create(**values)

    def new_game(self, **body):
        payload = {'p1_deck': self.decks[0].id, 'opponent': 'ai', **body}
        return self.client.post(
            reverse('battlelog:playNew'), data=json.dumps(payload), content_type='application/json',
        )

    def test_new_ai_deck_starts_with_the_template(self):
        ai_deck = SimulatorAIDeck(name='새 AI', deck=self.decks[1])

        self.assertIn('[[combo]]', ai_deck.profile_text)
        ai_deck.full_clean()

    def test_clean_checks_codes_against_the_deck(self):
        ai_deck = self.make_ai_deck(profile_text='[prefer]\n"NOT-IN-DECK" = 1\n')

        with self.assertRaises(ValidationError) as caught:
            ai_deck.full_clean()

        self.assertIn('NOT-IN-DECK', str(caught.exception))
        self.make_ai_deck().full_clean()

    def test_lobby_lists_only_active_and_valid_ai_decks(self):
        shown = self.make_ai_deck(description='콤보 연습용')
        self.make_ai_deck(name='숨김', is_active=False)
        self.make_ai_deck(name='고장', profile_text='style = ')

        rows = self.client.get(reverse('battlelog:playAIDecks')).json()['ai_decks']

        self.assertEqual([row['id'] for row in rows], [shown.id])
        self.assertEqual(rows[0]['style_label'], '공격적')
        self.assertEqual(rows[0]['character'], 'AI HTTP Character')
        self.assertEqual(rows[0]['description'], '콤보 연습용')

    def test_mobile_api_lists_the_same_ai_decks_and_starts_a_game_with_one(self):
        from rest_framework.test import APIClient

        shown = self.make_ai_deck(description='콤보 연습용')
        self.make_ai_deck(name='숨김', is_active=False)
        web = self.client.get(reverse('battlelog:playAIDecks')).json()['ai_decks']
        client = APIClient()

        rows = client.get('/api/mobile/v1/simulator/ai-decks?language=ko').json()['ai_decks']

        self.assertEqual([row['id'] for row in rows], [row['id'] for row in web])
        self.assertEqual(rows[0]['id'], shown.id)
        self.assertEqual(rows[0]['character_id'], self.decks[1].character_id)
        self.assertEqual(rows[0]['style_label'], '공격적')
        response = client.post('/api/mobile/v1/simulator/sessions', {
            'p1_deck': self.decks[0].id, 'ai_deck': shown.id, 'opponent': 'ai', 'mode': 'automatic',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(response.json()['urls']['p1'].startswith('http'))
        session = LumenSimulatorSession.objects.get(view_token=response.json()['view_token'])
        self.assertEqual(session.document['ai_deck']['id'], shown.id)

    def test_new_game_with_ai_deck_pins_the_profile_even_for_a_private_deck(self):
        stranger = User.objects.create_user(username='ai-deck-owner', password='pw')
        self.decks[1].author = stranger
        self.decks[1].visibility = Deck.VISIBILITY_PRIVATE
        self.decks[1].save()
        ai_deck = self.make_ai_deck()

        response = self.new_game(ai_deck=ai_deck.id)

        self.assertEqual(response.status_code, 201, response.content)
        session = LumenSimulatorSession.objects.get(view_token=response.json()['view_token'])
        pinned = session.document['ai_deck']
        self.assertEqual(pinned['id'], ai_deck.id)
        self.assertEqual(pinned['style'], 'aggressive')
        self.assertEqual(pinned['prefer'], {'AIH-001': 2.0})
        self.assertTrue(session.player2_name.startswith('연습 상대'))
        # 이후 수정은 이미 만든 세션에 영향이 없다.
        ai_deck.profile_text = '[prefer]\n"AIH-003" = 5\n'
        ai_deck.save()
        session.refresh_from_db()
        self.assertEqual(session.document['ai_deck']['prefer'], {'AIH-001': 2.0})

    def test_inactive_or_unknown_ai_deck_is_refused(self):
        hidden = self.make_ai_deck(is_active=False)

        for value in (hidden.id, 999999, 'x'):
            response = self.new_game(ai_deck=value)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()['error'], 'AI 덱을 찾을 수 없습니다.')

    def test_old_clients_sending_a_deck_still_get_its_registered_profile(self):
        ai_deck = self.make_ai_deck()

        response = self.new_game(p2_deck=self.decks[1].id)
        unregistered = self.new_game(p2_deck=self.decks[0].id)

        self.assertEqual(response.status_code, 201, response.content)
        session = LumenSimulatorSession.objects.get(view_token=response.json()['view_token'])
        self.assertEqual(session.document['ai_deck']['id'], ai_deck.id)
        self.assertEqual(unregistered.status_code, 201, unregistered.content)
        other = LumenSimulatorSession.objects.get(view_token=unregistered.json()['view_token'])
        self.assertNotIn('ai_deck', other.document)

    def test_ai_driver_passes_the_pinned_profile_to_the_policy(self):
        ai_deck = self.make_ai_deck()
        response = self.new_game(ai_deck=ai_deck.id)
        session = LumenSimulatorSession.objects.get(view_token=response.json()['view_token'])
        from .automatic_services import advance_ai_session

        with patch('battlelog.game.ai.choose_action', wraps=choose_action) as chooser:
            advance_ai_session(session)

        for call in chooser.call_args_list:
            self.assertEqual(call.kwargs['profile']['style'], 'aggressive')

    def test_admin_form_shows_template_cards_and_reference_tables(self):
        admin = User.objects.create_superuser(username='ai-deck-admin', password='pw')
        self.cards[1].hit = '콤보'
        self.cards[1].save()
        ai_deck = self.make_ai_deck()
        self.client.force_login(admin)

        change = self.client.get(reverse('admin:battlelog_simulatoraideck_change', args=[ai_deck.id]))
        add = self.client.get(reverse('admin:battlelog_simulatoraideck_add'))

        self.assertContains(change, 'AIH-001')
        self.assertContains(change, '콤보 시작(히트)')
        self.assertContains(change, 'card_speed')
        self.assertContains(change, 'rival_shows')
        self.assertContains(change, '성향: 공격적')
        self.assertContains(add, '[[combo]]')
        self.assertContains(add, '[[effect]]')
        self.assertContains(change, 'st2-ps1-charge-enter')
