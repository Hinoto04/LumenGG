"""튜토리얼 단원(docs/TUTORIAL.md) 회귀 테스트.

실제 카드 대신 각본 조건에 맞는 합성 카드로 단원을 처음부터 끝까지 진행한다.
"""

import copy
import json

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from card.models import Card, Character

from . import test_automatic_engine as engine_tests
from .automatic_services import advance_ai_session, perform_automatic_command
from .game.catalog import _json_hash
from .game.engine import IllegalAction
from .models import LumenSimulatorSession, RulesetRelease
from .play_protocol import validate_play_envelope
from .simulator_services import serialize_simulator_session
from .tutorial import create_tutorial_session, tutorial_of

EMPTY_EFFECT = {'schema_version': 1, 'reviewed': True, 'abilities': []}
# 역할 → (종류, 속도, 데미지, 위치, 상단 방어)
TUTORIAL_CARDS = {
    'A': ('공격', 3, 500, '상단', None),
    'B': ('공격', 5, 600, '하단', None),
    'D': ('수비', None, None, None, '방어'),
    'P1_EXTRA': ('공격', 9, 100, '상단', None),
    'X': ('공격', 7, 400, '상단', None),
    'Y': ('공격', 5, 400, '상단', None),
    'Z': ('수비', None, None, None, '방어'),
    'P2_EXTRA_1': ('공격', 9, 100, '상단', None),
    'P2_EXTRA_2': ('공격', 9, 100, '중단', None),
}
# 2~4단원용 합성 카드: 코드 → (종류, 속도, 데미지, 위치, {수비 위치: 판정}, 히트 FP)
EXTRA_CARDS = {
    'MID_GUARD': ('수비', None, None, None, {'g_mid': '방어'}, None),
    'FP_ATK': ('공격', 8, 800, '상단', {}, '6'),
    'SLOW_MID': ('공격', 9, 600, '중단', {}, '2'),
    'QUICK_MID': ('공격', 6, 400, '중단', {}, '1'),
    'FILL_1': ('공격', 9, 100, '상단', {}, '0'),
    'FILL_2': ('공격', 9, 100, '하단', {}, '0'),
    'FILL_3': ('공격', 10, 100, '상단', {}, '0'),
    'FILL_4': ('공격', 10, 100, '하단', {}, '0'),
}
# 단원 → 역할 → 카드(TUTORIAL_CARDS의 역할이나 EXTRA_CARDS의 코드)
LESSON_CARDS = {
    'basic-2': {
        'A': 'A', 'B': 'B', 'D': 'D', 'P1_EXTRA': 'P1_EXTRA',
        'W': 'MID_GUARD', 'X': 'X', 'P2_EXTRA_1': 'P2_EXTRA_1',
    },
    'basic-3': {
        'A': 'FP_ATK', 'B': 'SLOW_MID', 'P1_EXTRA': 'P1_EXTRA',
        'W': 'MID_GUARD', 'X': 'QUICK_MID', 'P2_EXTRA_1': 'P2_EXTRA_1',
    },
    'basic-4': {
        'A': 'SLOW_MID', 'D': 'MID_GUARD', 'H1': 'FILL_1', 'H2': 'FILL_2', 'H3': 'FILL_3', 'H4': 'FILL_4',
        'E': 'P1_EXTRA', 'L1': 'FILL_1',
        'X': 'QUICK_MID', 'P2_EXTRA_1': 'P2_EXTRA_1', 'P2_EXTRA_2': 'P2_EXTRA_2',
    },
}


class TutorialTestBase(TestCase):
    setUp_base = engine_tests.SimulatorAIHTTPTests.setUp

    def setUp(self):
        self.setUp_base()
        self.codes = {}
        snapshot = copy.deepcopy(self.release.snapshot)
        for role, (card_type, frame, damage, position, guard) in TUTORIAL_CARDS.items():
            card = Card.objects.create(
                name=f'튜토리얼 {role}', code=f'TUT-{role}', character=self.character,
                type=card_type, frame=frame, damage=damage, pos=position, g_top=guard,
                effect_definition=EMPTY_EFFECT,
            )
            self.codes[role] = card.code
            snapshot['cards'][card.code] = {
                'id': card.id, 'code': card.code, 'name': card.name, 'type': card_type,
                'frame': frame, 'damage': damage, 'pos': position, 'special': None,
                'hit': '0', 'guard': '0', 'counter': '0',
                'g_top': guard, 'g_mid': None, 'g_bot': None, 'ultimate': False,
                'character_id': self.character.id, 'effect_definition': EMPTY_EFFECT,
            }
        for key, (card_type, frame, damage, position, guards, hit_fp) in EXTRA_CARDS.items():
            card = Card.objects.create(
                name=f'튜토리얼 {key}', code=f'TUT-{key}', character=self.character,
                type=card_type, frame=frame, damage=damage, pos=position, effect_definition=EMPTY_EFFECT,
                **guards,
            )
            self.codes[key] = card.code
            snapshot['cards'][card.code] = {
                'id': card.id, 'code': card.code, 'name': card.name, 'type': card_type,
                'frame': frame, 'damage': damage, 'pos': position, 'special': None, 'body': '손',
                'hit': hit_fp, 'guard': '0' if hit_fp else None, 'counter': '3' if hit_fp else None,
                'g_top': None, 'g_mid': None, 'g_bot': None, **guards, 'ultimate': False,
                'character_id': self.character.id, 'effect_definition': EMPTY_EFFECT,
            }
        self.publish(snapshot)
        # 4단원: 체력 4000 이하에서 손패 상한이 6 → 7로 늘어나는 캐릭터
        self.hand_character = Character.objects.create(
            id=9002, name='Tutorial Hand Character', localization_key='tutorial_hand_character',
            description='', group='Test', datas={'hand': {'4000': 7, '5000': 6}},
            img='https://example.invalid/character.png',
        )
        self.setup = {
            'characters': {'p1': self.character.id, 'p2': self.character.id},
            'cards': {role: self.codes[role] for role in TUTORIAL_CARDS},
        }
        self.setups = {'basic-1': self.setup}
        for lesson_id, roles in LESSON_CARDS.items():
            p1 = self.hand_character.id if lesson_id == 'basic-4' else self.character.id
            self.setups[lesson_id] = {
                'characters': {'p1': p1, 'p2': self.character.id},
                'cards': {role: self.codes[key] for role, key in roles.items()},
            }
        override = override_settings(LUMEN_TUTORIAL_SETUP=self.setups)
        override.enable()
        self.addCleanup(override.disable)

    def publish(self, snapshot):
        RulesetRelease.objects.filter(is_active=True).update(is_active=False)
        self.release = RulesetRelease.objects.create(
            version=f'tutorial-rules-{RulesetRelease.objects.count()}', schema_version=1,
            snapshot=snapshot, content_hash=_json_hash(snapshot), is_active=True,
            source_manifest={'validation': {'is_valid': True, 'card_count': len(snapshot['cards'])}},
        )

    def envelope(self, session, role='p1', language='ko'):
        token = session.player1_token if role == 'p1' else session.player2_token
        return serialize_simulator_session(session, role, token, language)

    def act(self, session, action, label):
        session = perform_automatic_command(session, {
            'command_id': f'tutorial-{label}',
            'action_id': action['action_id'],
            'expected_version': session.version,
            'selections': {},
            'seat': 'p1', 'seat_token': session.player1_token,
        })
        return advance_ai_session(session)

    def playable(self, envelope):
        return [a for a in envelope['legal_actions'] if a['type'] not in ('concede', 'pause_clock', 'resume_clock')]


class TutorialPlaythroughTests(TutorialTestBase):
    def test_lesson_runs_counter_guard_hit_and_p1_wins(self):
        session = create_tutorial_session('basic-1')
        state = session.document['state']
        self.assertEqual(state['players']['p2']['hp'], 1100)  # A(500) + B(600)
        self.assertEqual(state['phase'], 'ready')  # 빈 루멘 페이즈는 자동으로 넘어간다

        seen_steps = []
        for turn in range(12):
            envelope = self.envelope(session)
            self.assertEqual(validate_play_envelope(envelope), [], envelope.get('tutorial'))
            view = envelope['tutorial']
            if view['status'] != 'running':
                break
            seen_steps.append(view['step_id'])
            actions = self.playable(envelope)
            self.assertEqual(len(actions), 1, (view['step_id'], [a['type'] for a in actions]))
            self.assertTrue(view['messages'])
            session = self.act(session, actions[0], turn)

        self.assertEqual(seen_steps, ['t1-ready', 't1-get', 't2-ready', 't2-get', 't3-ready'])
        tutorial = tutorial_of(session.document)
        self.assertEqual(tutorial['status'], 'completed', tutorial.get('reason'))
        results = [
            event['payload']['result']['p1'] for event in session.document['events']
            if event['type'] == 'battle_judged'
        ]
        self.assertEqual(results, ['counter', 'guard', 'hit'])
        self.assertEqual(session.document['state']['engine']['winner'], 'p1')
        view = self.envelope(session)['tutorial']
        self.assertEqual(view['step_id'], 'completed')
        self.assertEqual(len(view['messages']), 2)

    def test_messages_fill_card_placeholders_in_each_language(self):
        session = create_tutorial_session('basic-1')
        session = self.act(session, self.playable(self.envelope(session))[0], 'a')
        for language in ('ko', 'en', 'ja'):
            view = self.envelope(session, language=language)['tutorial']
            self.assertEqual(view['step_id'], 't1-get')
            text = view['messages'][0]['text']
            self.assertIn('튜토리얼 A', text)
            self.assertIn('3', text)
            self.assertNotIn('{', text)

    def test_card_focus_points_at_the_card_on_the_board(self):
        session = create_tutorial_session('basic-1')
        for label in ('a', 'd'):
            session = self.act(session, self.playable(self.envelope(session))[0], label)
        view = self.envelope(session)['tutorial']
        self.assertEqual(view['step_id'], 't2-ready')
        focus = view['messages'][1]['focus']
        self.assertEqual(focus['kind'], 'card')
        self.assertEqual(focus['card']['instance_id'], 'p1-tutorial-d')
        self.assertEqual(focus['card']['zone'], 'hand')

    def test_only_p1_gets_tutorial_messages(self):
        session = create_tutorial_session('basic-1')
        self.assertIsNone(self.envelope(session, role='viewer')['tutorial'])


class KoreanParticleTests(SimpleTestCase):
    def render(self, text, values):
        from .tutorial.runtime import _render

        return _render(text, lambda role, field: values.get(role), 'ko')

    def test_particle_follows_the_final_consonant(self):
        self.assertEqual(self.render('{A}를 레디', {'A': '하이 잽'}), '하이 잽을 레디')
        self.assertEqual(self.render('{A}을 레디', {'A': '버스트 레이'}), '버스트 레이를 레디')
        self.assertEqual(self.render('{A}가 빠름', {'A': '하이 잽'}), '하이 잽이 빠름')
        self.assertEqual(self.render('{A}는', {'A': '상단'}), '상단은')
        self.assertEqual(self.render('{A}으로', {'A': '레이'}), '레이로')
        self.assertEqual(self.render('{A}로', {'A': '하이 잽'}), '하이 잽으로')
        self.assertEqual(self.render('{A}으로', {'A': '스매실'}), '스매실로')  # ㄹ 받침

    def test_digits_and_latin(self):
        self.assertEqual(self.render('{A}을', {'A': '300'}), '300을')
        self.assertEqual(self.render('{A}을', {'A': '5'}), '5를')
        self.assertEqual(self.render('{A}을', {'A': 'EX'}), 'EX을')  # 판단할 수 없으면 쓴 그대로

    def test_other_languages_are_left_alone(self):
        from .tutorial.runtime import _render

        self.assertEqual(_render('{A}を', lambda role, field: 'X', 'ja'), 'Xを')


class TutorialRestrictionTests(TutorialTestBase):
    def test_off_script_action_is_hidden_and_rejected(self):
        session = create_tutorial_session('basic-1')
        envelope = self.envelope(session)
        offered = {a['payload'].get('card_instance_id') for a in self.playable(envelope)}
        self.assertEqual(offered, {'p1-tutorial-a'})
        from .automatic_services import _session_engine

        other = next(
            action for action in _session_engine(session).legal_actions('p1')
            if (action.get('payload') or {}).get('card_instance_id') == 'p1-tutorial-b'
        )
        with self.assertRaises(IllegalAction):
            self.act(session, other, 'b')

    def test_concede_is_always_allowed_and_ends_the_tutorial(self):
        session = create_tutorial_session('basic-1')
        concede = next(a for a in self.envelope(session)['legal_actions'] if a['type'] == 'concede')
        session = self.act(session, concede, 'concede')
        self.assertEqual(tutorial_of(session.document)['status'], 'ended')
        self.assertEqual(self.envelope(session)['tutorial']['messages'], [])

    def test_rule_change_that_breaks_the_script_fails_without_manual_fallback(self):
        snapshot = copy.deepcopy(self.release.snapshot)
        snapshot['cards'][self.codes['X']]['frame'] = 2  # 상대가 더 빨라 카운터가 나오지 않는다
        self.publish(snapshot)
        session = create_tutorial_session('basic-1')
        session = self.act(session, self.playable(self.envelope(session))[0], 'a')
        tutorial = tutorial_of(session.document)
        self.assertEqual(tutorial['status'], 'failed')
        self.assertIn('counter', tutorial['reason'])
        self.assertEqual(session.mode, LumenSimulatorSession.MODE_AUTOMATIC)
        envelope = self.envelope(session)
        self.assertEqual([a['type'] for a in envelope['legal_actions']], ['concede'])
        self.assertEqual(envelope['tutorial']['step_id'], 'failed')
        self.assertEqual(validate_play_envelope(envelope), [])


class TutorialCheckCommandTests(TutorialTestBase):
    def run_check(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        try:
            call_command('check_tutorials', *args, stdout=out)
            code = 0
        except SystemExit as exc:
            code = exc.code
        return code, out.getvalue()

    def test_passes_on_a_release_that_keeps_the_script(self):
        sessions = LumenSimulatorSession.objects.count()
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn('completed', out)
        self.assertIn("['counter', 'guard', 'hit']", out)
        self.assertEqual(out.count('completed'), 4, out)
        self.assertEqual(LumenSimulatorSession.objects.count(), sessions)  # 아무것도 저장하지 않는다

    def test_fails_on_a_release_that_breaks_the_script(self):
        snapshot = copy.deepcopy(self.release.snapshot)
        snapshot['cards'][self.codes['Z']]['g_bot'] = '방어'  # 3턴 히트가 방어가 된다
        snapshot['cards'][self.codes['Z']]['g_top'] = None
        self.publish(snapshot)
        code, out = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn('t3-ready', out)


class TutorialApiTests(TutorialTestBase):
    def test_lists_and_starts_the_lesson_without_login(self):
        listing = self.client.get(reverse('battlelog:playTutorials')).json()['tutorials']
        self.assertEqual(
            [(row['id'], row['available']) for row in listing],
            [('basic-1', True), ('basic-2', True), ('basic-3', True), ('basic-4', True)],
        )
        self.assertTrue(all(row['summary'] for row in listing))
        response = self.client.post(
            reverse('battlelog:playTutorialNew'), data=json.dumps({'lesson': 'basic-1'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertIn('p1', body['urls'])
        self.assertNotIn('p2', body['urls'])
        session = LumenSimulatorSession.objects.get(view_token=body['view_token'])
        self.assertEqual(tutorial_of(session.document)['lesson'], 'basic-1')

    def test_unconfigured_lesson_is_unavailable(self):
        with override_settings(LUMEN_TUTORIAL_SETUP={}):
            listing = self.client.get(reverse('battlelog:playTutorials')).json()['tutorials']
            self.assertFalse(any(row['available'] for row in listing))
            response = self.client.post(
                reverse('battlelog:playTutorialNew'), data=json.dumps({'lesson': 'basic-1'}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 503)

    def test_unknown_lesson_is_unavailable(self):
        response = self.client.post(
            reverse('battlelog:playTutorialNew'), data=json.dumps({'lesson': 'nope'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 503)


class LaterLessonTests(TutorialTestBase):
    """2~4단원: 카드 읽기, FP와 우선권, 손패와 겟."""

    def play(self, lesson_id, inspect=None):
        """각본대로 끝까지 진행한다. inspect(step_id, envelope)로 단계마다 화면을 본다."""
        session = create_tutorial_session(lesson_id)
        steps = []
        for turn in range(12):
            envelope = self.envelope(session)
            self.assertEqual(validate_play_envelope(envelope), [], envelope.get('tutorial'))
            view = envelope['tutorial']
            if view['status'] != 'running':
                break
            steps.append(view['step_id'])
            if inspect:
                inspect(view['step_id'], envelope)
            actions = self.playable(envelope)
            self.assertEqual(len(actions), 1, (view['step_id'], [a['type'] for a in actions]))
            session = self.act(session, actions[0], f'{lesson_id}-{turn}')
        return session, steps

    def results(self, session):
        return [
            event['payload']['result']['p1'] for event in session.document['events']
            if event['type'] == 'battle_judged'
        ]

    def assert_completed(self, session):
        tutorial = tutorial_of(session.document)
        self.assertEqual(tutorial['status'], 'completed', tutorial.get('reason'))
        self.assertEqual(session.document['state']['engine']['winner'], 'p1')
        envelope = self.envelope(session)
        self.assertEqual(validate_play_envelope(envelope), [])
        self.assertEqual(envelope['tutorial']['step_id'], 'completed')
        self.assertTrue(envelope['tutorial']['messages'])
        return envelope['tutorial']

    def test_card_reading_lesson_points_at_card_parts_and_ends_by_concession(self):
        seen = {}

        def inspect(step_id, envelope):
            seen[step_id] = envelope['tutorial']

        session, steps = self.play('basic-2', inspect)
        self.assertEqual(steps, ['t1-ready', 't1-get'])
        self.assertEqual(self.results(session), ['hit'])
        self.assert_completed(session)  # 짧은 단원은 상대 기권으로 끝난다
        ready = seen['t1-ready']['messages']
        parts = [m['focus']['part'] for m in ready if (m['focus'] or {}).get('kind') == 'anatomy']
        self.assertEqual(parts, ['name', 'speed', 'pos', 'damage', 'fp', 'text'])
        self.assertEqual(ready[1]['focus']['card']['instance_id'], 'p1-tutorial-a')
        guard = next(m for m in seen['t1-get']['messages'] if (m['focus'] or {}).get('part') == 'guard')
        self.assertEqual(guard['focus']['card']['zone'], 'list')
        self.assertIn('상단 방어', guard['text'])
        self.assertEqual(seen['t1-ready']['next']['lesson'], 'basic-3')

    def test_fp_lesson_moves_priority_and_speeds_up_the_attack(self):
        seen = {}

        def inspect(step_id, envelope):
            seen[step_id] = (envelope['tutorial'], envelope['state']['priority_player'])

        session, steps = self.play('basic-3', inspect)
        self.assertEqual(steps, ['t1-ready', 't1-get', 't2-ready'])
        self.assertEqual(seen['t1-ready'][1], 'p2')  # 처음 우선권은 상대
        self.assertEqual(seen['t1-get'][1], 'p1')  # FP가 높아져 넘어온다
        self.assertIn('+6', seen['t1-ready'][0]['messages'][1]['text'])
        self.assertIn('지금 FP는 6', seen['t1-get'][0]['messages'][0]['text'])
        self.assertIn('9 − 6 = 3', seen['t2-ready'][0]['messages'][1]['text'])
        self.assertEqual(self.results(session), ['hit', 'counter'])
        self.assert_completed(session)

    def test_hand_lesson_raises_the_limit_and_skips_the_get(self):
        seen = {}

        def inspect(step_id, envelope):
            seen[step_id] = envelope

        session, steps = self.play('basic-4', inspect)
        self.assertEqual(steps, ['t1-ready', 't1-get', 't2-ready', 't2-get'])
        self.assertEqual(self.results(session), ['countered', 'guard'])
        self.assertIn('6장 / 6장', seen['t1-ready']['tutorial']['messages'][0]['text'])
        self.assertIn('체력이 3800', seen['t1-get']['tutorial']['messages'][0]['text'])
        self.assertIn('7장으로', seen['t1-get']['tutorial']['messages'][0]['text'])
        self.assertIn('7장 / 7장', seen['t2-ready']['tutorial']['messages'][0]['text'])
        self.assertEqual([a['type'] for a in self.playable(seen['t2-get'])], ['pass_phase'])
        view = self.assert_completed(session)
        self.assertNotIn('next', view)  # 마지막 단원


class PlaceholderTests(SimpleTestCase):
    def test_difference_and_fp_sign(self):
        from .tutorial.runtime import _fp_text, _render

        values = {('B', 'frame'): '9', ('p1', 'fp'): '6'}

        def lookup(role, field):
            return values.get((role, field))

        self.assertEqual(_render('{B.frame} − {p1.fp} = {B.frame-p1.fp}', lookup, 'ko'), '9 − 6 = 3')
        self.assertEqual(_render('{B.frame-Q.frame}', lookup, 'ko'), '{B.frame-Q.frame}')
        self.assertEqual(_fp_text('3', 'ko'), '+3')
        self.assertEqual(_fp_text('-6', 'ko'), '-6')
        self.assertEqual(_fp_text('콤보', 'en'), 'Combo')
