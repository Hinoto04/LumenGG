"""튜토리얼 세션 생성과 각본 진행 (docs/TUTORIAL.md 4절).

튜토리얼은 자동 판정 시나리오 세션이다. ``document['tutorial']``이 있으면

- 양쪽의 합법 행동을 현재 단계가 허용한 것으로 좁히고(관찰·명령 검증 모두 ``filter_actions``),
- 각 명령 뒤에 단계를 진행하며 각본과 다른 판정이 나오면 실패로 끝내고(``after_command``),
- p2(AI 좌석)는 AI 정책 대신 각본 행동을 고른다(``opponent_decision``).

엔진은 그대로이므로 판정은 일반 대전과 같다.
"""

import copy
import logging
import re
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone

from card.models import Card, Character
from common.language import DEFAULT_LANGUAGE, game_term, normalize_language, translated_card_field

from ..models import LumenSimulatorSession
from .lessons import FAILED_MESSAGE, get_lesson, lesson_setup

logger = logging.getLogger(__name__)

SIDES = ('p1', 'p2')
# 단계와 상관없이 언제나 할 수 있는 행동(그만두기, 일시 정지).
SYSTEM_ACTIONS = frozenset({'concede', 'pause_clock', 'resume_clock'})
# 튜토리얼 세션 설정: 빈 페이즈는 넘기고, 되감기·시작 패 확인·타이머는 쓰지 않는다.
TUTORIAL_SETTINGS = {
    'auto_advance_empty_phases': True,
    'rewind_enabled': False,
    'opening_review': False,
    'ready_timeout_seconds': None,
    'effect_timeout_seconds': None,
}
CARD_STAT_KEYS = (
    'card_id', 'code', 'name', 'type', 'frame', 'damage', 'pos', 'g_top', 'g_mid', 'g_bot',
)
GUARD_POSITIONS = (('g_top', '상단'), ('g_mid', '중단'), ('g_bot', '하단'))
# 자리 표시자 바로 뒤의 조사는 한국어에서 받침에 맞게 고른다({A}를 → 하이 잽을).
PLACEHOLDER = re.compile(r'\{([A-Z][A-Z0-9_]*)(?:\.([a-z_]+))?\}(으로|을|를|이|가|은|는|과|와|로)?')
JOSA_PAIRS = {'을': ('을', '를'), '를': ('을', '를'), '이': ('이', '가'), '가': ('이', '가'),
              '은': ('은', '는'), '는': ('은', '는'), '과': ('과', '와'), '와': ('과', '와'),
              '으로': ('으로', '로'), '로': ('으로', '로')}
# 숫자로 끝나면 읽는 소리의 받침: 0영 1일 3삼 6육 7칠 8팔은 받침이 있고 2이 4사 5오 9구는 없다.
DIGIT_BATCHIM = {'0': 21, '1': 8, '2': 0, '3': 16, '4': 0, '5': 0, '6': 1, '7': 8, '8': 8, '9': 0}


class TutorialUnavailable(ValueError):
    """단원이 없거나 아직 카드가 배정되지 않았거나, 공개된 규칙 릴리스가 없다."""


# --------------------------------------------------------------------------
# 세션 생성


def _instance_id(side, role):
    return f'{side}-tutorial-{role.lower()}'


def _role_sides(lesson):
    return {
        role: side
        for side, zones in lesson['board'].items()
        for roles in zones.values()
        for role in roles
    }


def _release_card(snapshot, code):
    return (snapshot.get('cards') or {}).get(code) or {}


def lesson_available(lesson, release):
    """(사용 가능 여부, 사유). 카드 배정과 릴리스만 본다(각본 검증은 check_tutorials)."""
    setup = lesson_setup(lesson)
    if not setup:
        return False, 'not_configured'
    if release is None:
        return False, 'no_release'
    cards = setup.get('cards') or {}
    missing = [role for role in lesson['roles'] if not cards.get(role)]
    if missing or not all((setup.get('characters') or {}).get(side) for side in SIDES):
        return False, 'not_configured'
    snapshot = release.snapshot or {}
    if any(not _release_card(snapshot, cards[role]) for role in lesson['roles']):
        return False, 'not_released'
    return True, ''


def build_tutorial_state(lesson, setup, release):
    """단원 보드로 시작 상태를 만든다(게임 준비가 끝난 상태)."""
    from ..simulator_services import (
        _card_payload,
        _character_payload,
        _initial_counter_revisions,
        _initial_turn_changes,
        _player_display_name,
        ZONES,
    )
    from ..services import (
        character_hand_table,
        initial_hp_for_character,
        initial_passive_state_for_character,
    )

    codes = setup['cards']
    cards = {card.code: card for card in Card.objects.filter(code__in=[codes[r] for r in lesson['roles']])}
    missing = sorted({codes[role] for role in lesson['roles']} - set(cards))
    if missing:
        raise TutorialUnavailable(f'튜토리얼 카드를 찾을 수 없습니다: {", ".join(missing)}')
    snapshot = release.snapshot or {}
    players = {}
    for side in SIDES:
        character = Character.objects.filter(pk=setup['characters'][side]).first()
        if character is None:
            raise TutorialUnavailable('튜토리얼 캐릭터를 찾을 수 없습니다.')
        initial_hp = initial_hp_for_character(character)
        player = {
            'name': _player_display_name(side, '', character),
            'deck_id': None,
            'deck_name': '',
            'character': {
                'id': character.id,
                'trait_card_id': None,
                'trait_config': {},
                'name': character.name,
                'img': character.body_img or character.sd_img or character.img,
                'icon_img': character.icon_img,
                'color': character.color,
                'hand_table': character_hand_table(character),
                'passive_ui': None,
            },
            'initial_hp': initial_hp,
            'hp': initial_hp,
            'fp': 0,
            'passive_state': initial_passive_state_for_character(character),
            'zones': {zone: [] for zone in ZONES},
        }
        player['zones']['character'].append(_character_payload(character, side))
        for zone, roles in lesson['board'][side].items():
            for role in roles:
                player['zones'][zone].append(_card_payload(
                    cards[codes[role]], side, _instance_id(side, role), face_up=(zone == 'list'),
                ))
        players[side] = player
    p2_hp = sum(
        int(_release_card(snapshot, codes[role]).get('damage') or cards[codes[role]].damage or 0)
        for role in lesson.get('p2_hp_from_damage') or ()
    )
    if p2_hp > 0:
        players['p2']['hp'] = min(p2_hp, players['p2']['initial_hp'] or p2_hp)
    return {
        'turn': 1,
        'phase': 'lumen',
        'status': {side: {'requested': side == 'p1', 'done': False} for side in SIDES},
        'priority_player': 'p1',
        'timer': {'started_at': None, 'duration_seconds': 10},
        'turn_changes': _initial_turn_changes(),
        'counter_revisions': _initial_counter_revisions(),
        'players': players,
    }


def _pinned_cards(lesson, setup, release):
    snapshot = release.snapshot or {}
    pinned = {}
    for role in lesson['roles']:
        code = setup['cards'][role]
        data = _release_card(snapshot, code)
        pinned[role] = {key: data.get(key) for key in CARD_STAT_KEYS if key != 'card_id'}
        pinned[role]['card_id'] = data.get('id')
        pinned[role]['code'] = code
    return pinned


def _available_lesson(lesson_id, release):
    lesson = get_lesson(lesson_id)
    if lesson is None:
        raise TutorialUnavailable('튜토리얼 단원을 찾을 수 없습니다.')
    available, reason = lesson_available(lesson, release)
    if not available:
        raise TutorialUnavailable(
            '검증된 카드 규칙 릴리스가 없어 튜토리얼을 시작할 수 없습니다.'
            if reason == 'no_release' else '튜토리얼을 준비 중입니다.'
        )
    return lesson


def tutorial_document(lesson, release, seed):
    """세션 문서(저장 전). DB는 카드·캐릭터를 읽기만 한다."""
    from ..automatic_services import initialize_automatic_scenario_document

    setup = lesson_setup(lesson)
    state = build_tutorial_state(lesson, setup, release)
    document = initialize_automatic_scenario_document(
        state, release, seed=seed, phase='lumen', priority_player='p1',
        settings=TUTORIAL_SETTINGS,
    )
    sides = _role_sides(lesson)
    document['tutorial'] = {
        'lesson': lesson['id'],
        'lesson_version': lesson['version'],
        'ruleset_version': release.version,
        'status': 'running',
        'step': 0,
        'done': {'p1': [], 'p2': []},
        'reason': '',
        'created_at': timezone.now().isoformat(),
        # 진행 중에 단원 파일이 바뀌어도 이 세션은 만든 때의 각본으로 끝까지 간다.
        'steps': copy.deepcopy(lesson['steps']),
        'completed': copy.deepcopy(lesson['completed']),
        'title': copy.deepcopy(lesson['title']),
        'instances': {role: _instance_id(side, role) for role, side in sides.items()},
        'cards': _pinned_cards(lesson, setup, release),
    }
    return document


def create_tutorial_session(lesson_id):
    from ..automatic_services import advance_ai_session, automatic_mode_release
    from ..simulator_services import _unique_token, simulator_session_expires_at

    release = automatic_mode_release()
    lesson = _available_lesson(lesson_id, release)
    view_token = _unique_token('view_token')
    document = tutorial_document(lesson, release, f'tutorial:{view_token}:{release.content_hash}')
    players = document['state']['players']
    session = LumenSimulatorSession.objects.create(
        view_token=view_token,
        player1_token=_unique_token('player1_token'),
        player2_token=_unique_token('player2_token'),
        player1_name=players['p1']['name'],
        player2_name=players['p2']['name'],
        player1_controller=LumenSimulatorSession.CONTROLLER_HUMAN,
        player2_controller=LumenSimulatorSession.CONTROLLER_AI,
        mode=LumenSimulatorSession.MODE_AUTOMATIC,
        ruleset_release=release,
        document=document,
        expires_at=simulator_session_expires_at(),
    )
    return advance_ai_session(session)


# --------------------------------------------------------------------------
# 행동 제한과 단계 진행


def tutorial_of(document):
    tutorial = (document or {}).get('tutorial')
    return tutorial if isinstance(tutorial, dict) else None


def is_tutorial(session):
    return tutorial_of(session.document) is not None


def _entries(tutorial, role):
    steps = tutorial.get('steps') or []
    index = int(tutorial.get('step') or 0)
    if index >= len(steps):
        return []
    return list(steps[index].get('allow' if role == 'p1' else 'opponent') or [])


def _matches(tutorial, action, entry):
    action_type, card_role = entry
    if action.get('type') != action_type:
        return False
    if card_role is None:
        return True
    instance = (tutorial.get('instances') or {}).get(card_role)
    return (action.get('payload') or {}).get('card_instance_id') == instance


def _pending_entry(tutorial, role, action):
    """현재 단계에서 아직 하지 않은 항목 중 이 행동이 맞는 것의 번호."""
    if tutorial.get('status') != 'running':
        return None
    done = set((tutorial.get('done') or {}).get(role) or [])
    for index, entry in enumerate(_entries(tutorial, role)):
        if index not in done and _matches(tutorial, action, entry):
            return index
    return None


def is_allowed(document, role, action):
    tutorial = tutorial_of(document)
    if tutorial is None:
        return True
    if action.get('type') == 'concede':
        return True
    if tutorial.get('status') != 'running':
        return False
    if action.get('type') in SYSTEM_ACTIONS:
        return True
    return _pending_entry(tutorial, role, action) is not None


def filter_actions(document, role, actions):
    if tutorial_of(document) is None:
        return actions
    return [action for action in actions if is_allowed(document, role, action)]


def _fail(tutorial, reason):
    tutorial['status'] = 'failed'
    tutorial['reason'] = reason
    logger.warning('튜토리얼 각본 실패 (%s, 단계 %s): %s', tutorial.get('lesson'), tutorial.get('step'), reason)


def _judged(events):
    return [((event.get('payload') or {}).get('result') or {}) for event in events if event.get('type') == 'battle_judged']


def _winner(events):
    for event in events:
        if event.get('type') == 'game_finished':
            return (event.get('payload') or {}).get('winner') or ''
    return None


def after_command(document, role, action, new_events):
    """명령 하나가 반영된 뒤 단계를 진행한다. ``document``를 직접 고친다."""
    tutorial = tutorial_of(document)
    if tutorial is None or tutorial.get('status') != 'running':
        return
    if action.get('type') == 'concede':
        tutorial['status'] = 'ended'
        tutorial['reason'] = f'{role} 기권'
        return
    if action.get('type') in SYSTEM_ACTIONS:
        return
    index = _pending_entry(tutorial, role, action)
    if index is None:
        _fail(tutorial, f'각본에 없는 행동: {role} {action.get("type")}')
        return
    done = tutorial.setdefault('done', {'p1': [], 'p2': []})
    done.setdefault(role, []).append(index)

    steps = tutorial.get('steps') or []
    step = steps[int(tutorial.get('step') or 0)]
    judged = _judged(new_events)
    winner = _winner(new_events)
    complete = all(
        len(done.get(side) or []) >= len(_entries(tutorial, side)) for side in SIDES
    )
    if not complete:
        if judged or winner is not None:
            _fail(tutorial, '단계가 끝나기 전에 배틀이 판정되었습니다.')
        return

    expect = step.get('expect') or {}
    if 'battle' in expect:
        results = [result.get('p1') for result in judged]
        if results != [expect['battle']]:
            _fail(tutorial, f'{step["id"]}: 판정 {results or "없음"}, 기대 {expect["battle"]}')
            return
    elif judged:
        _fail(tutorial, f'{step["id"]}: 기대하지 않은 판정 {[r.get("p1") for r in judged]}')
        return
    if expect.get('winner') and winner != expect['winner']:
        _fail(tutorial, f'{step["id"]}: 승자 {winner or "없음"}, 기대 {expect["winner"]}')
        return
    if winner is not None and not expect.get('winner'):
        _fail(tutorial, f'{step["id"]}: 각본보다 일찍 게임이 끝났습니다(승자 {winner}).')
        return

    tutorial['step'] = int(tutorial.get('step') or 0) + 1
    tutorial['done'] = {'p1': [], 'p2': []}
    if tutorial['step'] >= len(steps):
        if winner == 'p1':
            tutorial['status'] = 'completed'
            tutorial['completed_at'] = timezone.now().isoformat()
        else:
            _fail(tutorial, '마지막 단계 뒤에도 게임이 끝나지 않았습니다.')


# --------------------------------------------------------------------------
# 각본 상대


def _engine_status(session):
    return (((session.document or {}).get('state') or {}).get('engine') or {}).get('status')


def opponent_decision(session, role):
    """각본 상대의 다음 행동. 할 것이 없으면 None(사람 차례).

    양쪽 모두 각본상 할 행동이 없는데 게임이 진행 중이면 엔진이 각본과 다른 곳에
    멈춘 것이므로 실패로 끝낸다.
    """
    from ..automatic_services import _session_engine

    document = session.document or {}
    tutorial = tutorial_of(document)
    if tutorial is None or tutorial.get('status') != 'running':
        return None
    engine = _session_engine(session)
    actions = [
        action for action in filter_actions(document, role, engine.legal_actions(role))
        if action.get('type') not in SYSTEM_ACTIONS
    ]
    if actions:
        return SimpleNamespace(action=actions[0], selections={}, score=0.0)
    human = [
        action for action in filter_actions(document, 'p1', engine.legal_actions('p1'))
        if action.get('type') not in SYSTEM_ACTIONS
    ]
    if not human and _engine_status(session) == 'running':
        engine_step = (engine.engine_state or {}).get('step')
        fail_session(session, f'단계 {tutorial.get("step")}: 각본의 행동을 할 수 없는 상태입니다(엔진 {engine_step}).')
    return None


def fail_session(session, reason):
    with transaction.atomic():
        locked = LumenSimulatorSession.objects.select_for_update().get(pk=session.pk)
        document = copy.deepcopy(locked.document or {})
        tutorial = tutorial_of(document)
        if tutorial is None or tutorial.get('status') != 'running':
            return locked
        _fail(tutorial, reason)
        locked.document = document
        locked.version += 1
        locked.save(update_fields=['document', 'version', 'updated_at'])
        return locked


# --------------------------------------------------------------------------
# 점검 (check_tutorials)


def simulate_lesson(lesson_id, release, *, max_commands=60):
    """각본대로 끝까지 진행해 본 결과. 메모리에서만 돌고 아무것도 저장하지 않는다.

    반환: ``{'status', 'reason', 'steps': [완료한 단계 id], 'results': [p1 판정]}``
    """
    from ..game.engine import AutomaticGameEngine

    lesson = _available_lesson(lesson_id, release)
    seed = f'tutorial-check:{release.content_hash}'
    document = tutorial_document(lesson, release, seed)
    tutorial = document['tutorial']
    ruleset = copy.deepcopy(release.snapshot or {})
    ruleset['version'] = release.version
    finished_steps = []
    for index in range(max_commands):
        if tutorial['status'] != 'running':
            break
        engine = AutomaticGameEngine(
            document['state'], ruleset, events=document['events'], seed=seed,
        )
        if engine.engine_state.get('status') != 'running':
            _fail(tutorial, '각본이 끝나기 전에 게임이 끝났습니다.')
            break
        chosen = None
        for role in ('p2', 'p1'):
            actions = [
                action for action in filter_actions(document, role, engine.legal_actions(role))
                if action.get('type') not in SYSTEM_ACTIONS
            ]
            if actions:
                chosen = (role, actions[0])
                break
        if chosen is None:
            _fail(tutorial, f'단계 {tutorial.get("step")}: 각본의 행동을 할 수 없는 상태입니다'
                            f'(엔진 {engine.engine_state.get("step")}).')
            break
        role, action = chosen
        before = len(engine.events)
        step_before = tutorial['step']
        engine.submit_action(role, action['action_id'], {}, command_id=f'tutorial-check-{index}')
        after_command(document, role, action, engine.events[before:])
        document['state'], document['events'] = engine.state, engine.events
        if tutorial['step'] != step_before:
            finished_steps.append(tutorial['steps'][step_before]['id'])
    return {
        'status': tutorial['status'],
        'reason': tutorial.get('reason') or '',
        'steps': finished_steps,
        'results': [
            ((event.get('payload') or {}).get('result') or {}).get('p1')
            for event in document['events'] if event.get('type') == 'battle_judged'
        ],
    }


# --------------------------------------------------------------------------
# 화면에 보낼 정보 (envelope['tutorial'])


def _pick(text, language):
    if isinstance(text, dict):
        return text.get(language) or text.get(DEFAULT_LANGUAGE) or ''
    return str(text or '')


def _card_values(tutorial, language):
    pinned = tutorial.get('cards') or {}
    models = {
        card.id: card
        for card in Card.objects.prefetch_related('translations').filter(
            id__in=[data.get('card_id') for data in pinned.values() if data.get('card_id')],
        )
    }

    def values(role):
        data = pinned.get(role) or {}
        model = models.get(data.get('card_id'))
        guard = [game_term(label, language) for key, label in GUARD_POSITIONS if data.get(key) == '방어']
        return {
            'name': translated_card_field(model, language, 'name') if model else (data.get('name') or role),
            'frame': '' if data.get('frame') is None else str(data.get('frame')),
            'damage': '' if data.get('damage') is None else str(data.get('damage')),
            'pos': game_term(data.get('pos') or '', language) if data.get('pos') else '',
            'guard': ' · '.join(guard),
        }

    cache = {}

    def lookup(role, field):
        if role not in pinned:
            return None
        if role not in cache:
            cache[role] = values(role)
        return cache[role].get(field or 'name')

    return lookup


def _final_batchim(word):
    """마지막 글자의 받침 번호(0 = 없음). 판단할 수 없으면 None."""
    word = str(word or '').rstrip()
    if not word:
        return None
    last = word[-1]
    if '가' <= last <= '힣':
        return (ord(last) - 0xAC00) % 28
    return DIGIT_BATCHIM.get(last)


def _josa(word, written):
    batchim = _final_batchim(word)
    if batchim is None:
        return written
    with_batchim, without = JOSA_PAIRS[written]
    if with_batchim == '으로':  # ㄹ 받침 뒤에는 '로'
        return without if batchim in (0, 8) else with_batchim
    return with_batchim if batchim else without


def _render(text, lookup, language=DEFAULT_LANGUAGE):
    def replace(match):
        value = lookup(match.group(1), match.group(2))
        if value is None:
            return match.group(0)
        josa = match.group(3) or ''
        if josa and language == 'ko':
            josa = _josa(value, josa)
        return value + josa
    return PLACEHOLDER.sub(replace, text)


def _card_ref(state, instance_id, viewer):
    for side, player in ((state or {}).get('players') or {}).items():
        for zone, cards in (player.get('zones') or {}).items():
            for index, card in enumerate(cards):
                if card.get('instance_id') == instance_id:
                    ref = {'owner': side, 'zone': zone, 'index': index}
                    # 보이는 카드에만 instance_id를 붙인다(CardRef 규칙과 같다).
                    if side == viewer or card.get('face_up'):
                        ref['instance_id'] = instance_id
                    return ref
    return None


def _focus(tutorial, focus, state, viewer):
    if not focus:
        return None
    focus = dict(focus)
    if focus.get('kind') == 'card':
        instance = (tutorial.get('instances') or {}).get(focus.pop('card', None))
        ref = _card_ref(state, instance, viewer) if instance else None
        if ref is None:
            return None
        focus['card'] = ref
    return focus


def tutorial_view(document, role, language=DEFAULT_LANGUAGE):
    """p1 화면의 튜토리얼 안내. 튜토리얼이 아니거나 p1이 아니면 None."""
    tutorial = tutorial_of(document)
    if tutorial is None or role != 'p1':
        return None
    language = normalize_language(language)
    steps = tutorial.get('steps') or []
    status = tutorial.get('status') or 'running'
    index = min(int(tutorial.get('step') or 0), len(steps))
    if status == 'running' and index < len(steps):
        step_id = steps[index].get('id')
        messages = steps[index].get('messages') or []
    elif status == 'completed':
        step_id = 'completed'
        messages = tutorial.get('completed') or []
    elif status == 'failed':
        step_id = 'failed'
        messages = [FAILED_MESSAGE]
    else:
        step_id = status
        messages = []
    lookup = _card_values(tutorial, language)
    state = (document or {}).get('state') or {}
    return {
        'lesson': tutorial.get('lesson'),
        'title': _pick(tutorial.get('title'), language),
        'status': status,
        'step': index,
        'steps': len(steps),
        'step_id': step_id,
        'messages': [
            {
                'text': _render(_pick(message.get('text'), language), lookup, language),
                'focus': _focus(tutorial, message.get('focus'), state, role),
            }
            for message in messages
        ],
    }
