"""튜토리얼 단원 정의 (docs/TUTORIAL.md).

단원은 각본(단계·문구)과 카드 배정(setup)으로 나뉜다. 각본은 카드를 역할 이름
(A, B, D …)으로만 부르고, 실제 카드는 setup이 정한다. setup은 운영진이 고르므로
코드 대신 ``settings.LUMEN_TUTORIAL_SETUP[lesson_id]``로도 줄 수 있다(그쪽이 우선).

setup 모양::

    {
        'characters': {'p1': <Character id>, 'p2': <Character id>},
        'cards': {'A': '<카드 코드>', 'B': ..., ...},   # 각본의 모든 역할
    }

각 단계의 ``allow``는 p1이, ``opponent``는 각본 상대(p2)가 그 단계에 해야 할 행동이다.
둘 다 끝나면 다음 단계로 넘어간다. ``expect``는 그 단계를 끝낸 명령에서 나와야 할
판정이다(p1 기준 ``battle_judged`` 결과, 승자). 다르면 튜토리얼을 실패로 끝낸다.

문구 자리 표시자: ``{A}`` 카드명, ``{A.frame}`` 속도, ``{A.damage}`` 데미지, ``{A.pos}`` 위치,
``{D.guard}`` 수비 카드가 방어하는 위치.
``focus``: ``{'kind': 'action'}`` 허용 행동, ``{'kind': 'card', 'card': 'A'}``,
``{'kind': 'zone', 'zone': 'p1.hand'}``, ``{'kind': 'hud', 'hud': 'p2.hp'}`` (``phase`` 포함).
"""

from django.conf import settings


def _text(ko, en, ja):
    return {'ko': ko, 'en': en, 'ja': ja}


def _message(ko, en, ja, focus=None):
    return {'text': _text(ko, en, ja), 'focus': focus}


ACTION = {'kind': 'action'}


BASIC_1 = {
    'id': 'basic-1',
    'version': 1,
    'title': _text('한 턴의 흐름', 'The flow of a turn', 'ターンの流れ'),
    # 운영진이 고를 카드(docs/TUTORIAL.md 2절 조건). 비어 있으면 튜토리얼을 열지 않는다.
    'setup': None,
    'roles': ('A', 'B', 'D', 'P1_EXTRA', 'X', 'Y', 'Z', 'P2_EXTRA_1', 'P2_EXTRA_2'),
    'board': {
        'p1': {'hand': ['A', 'B'], 'list': ['D', 'P1_EXTRA']},
        'p2': {'hand': ['X', 'Y', 'Z'], 'list': ['P2_EXTRA_1', 'P2_EXTRA_2']},
    },
    # 상대 체력 = 이 카드들의 데미지 합. 1턴 카운터와 3턴 히트로 정확히 0이 된다.
    'p2_hp_from_damage': ('A', 'B'),
    'steps': [
        {
            'id': 't1-ready',
            'allow': [('ready_card', 'A')],
            'opponent': [('ready_card', 'X')],
            'expect': {'battle': 'counter'},
            'messages': [
                _message(
                    '루멘콘덴서에 오신 것을 환영합니다! 공격과 수비를 주고받아 상대 체력을 0으로 만들면 이깁니다.',
                    'Welcome to Lumen Condenser! Trade attacks and defenses, and bring your opponent\'s HP to 0 to win.',
                    'ルーメンコンデンサーへようこそ！攻撃と守備を応酬し、相手の体力を0にすれば勝利です。',
                    {'kind': 'hud', 'hud': 'p2.hp'},
                ),
                _message(
                    '한 턴은 루멘 → 레디 → 배틀 → 겟 → 리커버리 순서로 진행됩니다. 지금은 레디 페이즈입니다.',
                    'A turn goes Lumen → Ready → Battle → Get → Recovery. It is now the Ready phase.',
                    '1ターンはルーメン → レディ → バトル → ゲット → リカバリーの順に進みます。今はレディフェイズです。',
                    {'kind': 'hud', 'hud': 'phase'},
                ),
                _message(
                    '손패에서 사용할 카드 1장을 골라 레디합니다. 레디한 카드는 바꿀 수 없어요. {A}를 배틀 존으로 끌어 놓거나 눌러서 레디하세요.',
                    'Pick one card from your hand and Ready it. A readied card cannot be changed. Drag {A} to the battle zone or tap it.',
                    '手札から使うカードを1枚選んでレディします。レディしたカードは変更できません。{A}をバトルゾーンへドラッグするかタップしてください。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't1-get',
            'allow': [('select_get_card', 'D')],
            'opponent': [('select_get_card', 'P2_EXTRA_1')],
            'messages': [
                _message(
                    '공격끼리 부딪치면 속도 숫자가 작은 쪽이 빠릅니다. {A}의 속도는 {A.frame}, {X}의 속도는 {X.frame}. 더 빠른 {A}가 카운터! 상대에게 {A.damage} 데미지를 주었습니다.',
                    'When two attacks clash, the lower speed number is faster. {A} (speed {A.frame}) beat {X} (speed {X.frame}) — a Counter! You dealt {A.damage} damage.',
                    '攻撃同士がぶつかると、速度の数字が小さい方が速いです。{A}（速度{A.frame}）が{X}（速度{X.frame}）より速くカウンター！相手に{A.damage}ダメージを与えました。',
                    {'kind': 'hud', 'hud': 'p2.hp'},
                ),
                _message(
                    '배틀에 쓴 카드는 손패로 돌아옵니다. 겟 페이즈에는 리스트에서 카드 1장을 가져올 수 있어요. 수비 카드 {D}를 가져오세요.',
                    'Cards used in battle return to your hand. In the Get phase you take one card from your list. Take the defense card {D}.',
                    'バトルで使ったカードは手札に戻ります。ゲットフェイズではリストからカードを1枚手札に加えます。守備カード{D}を加えましょう。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't2-ready',
            'allow': [('ready_card', 'D')],
            'opponent': [('ready_card', 'Y')],
            'expect': {'battle': 'guard'},
            'messages': [
                _message(
                    '턴이 끝나면 다시 루멘 페이즈부터 시작합니다. 2턴 레디 페이즈입니다.',
                    'When a turn ends, the next one starts again from the Lumen phase. This is the Ready phase of turn 2.',
                    'ターンが終わると、再びルーメンフェイズから始まります。2ターン目のレディフェイズです。',
                    {'kind': 'hud', 'hud': 'phase'},
                ),
                _message(
                    '상대는 {Y}로 {Y.pos}을 노리는 것 같습니다. 수비 카드는 적힌 위치의 공격을 막습니다. {D}는 {D.guard}을 방어해요.',
                    'Your opponent seems to be aiming at {Y.pos} with {Y}. A defense card stops attacks at the positions printed on it. {D} guards {D.guard}.',
                    '相手は{Y}で{Y.pos}を狙っているようです。守備カードは書かれた位置への攻撃を防ぎます。{D}は{D.guard}を防御します。',
                    {'kind': 'card', 'card': 'D'},
                ),
                _message(
                    '{D}를 레디하세요.',
                    'Ready {D}.',
                    '{D}をレディしてください。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't2-get',
            'allow': [('select_get_card', 'P1_EXTRA')],
            'opponent': [('select_get_card', 'P2_EXTRA_2')],
            'messages': [
                _message(
                    '수비 위치가 공격 위치와 맞아 방어! 방어하면 상대 공격의 데미지를 받지 않습니다.',
                    'The defense position matched the attack — a Guard! A guarded attack deals no damage.',
                    '守備の位置が攻撃の位置と一致して防御！防御すると相手の攻撃のダメージを受けません。',
                    {'kind': 'hud', 'hud': 'p1.hp'},
                ),
                _message(
                    '이번 겟 페이즈에도 리스트에서 1장을 가져오세요.',
                    'Take one card from your list again in this Get phase.',
                    'このゲットフェイズでもリストから1枚手札に加えましょう。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't3-ready',
            'allow': [('ready_card', 'B')],
            'opponent': [('ready_card', 'Z')],
            'expect': {'battle': 'hit', 'winner': 'p1'},
            'messages': [
                _message(
                    '상대 체력은 {B.damage} 남았습니다. 이번에는 직접 골라 보세요. {B}의 공격 위치는 {B.pos}입니다.',
                    'Your opponent has {B.damage} HP left. This time, choose on your own. {B} attacks {B.pos}.',
                    '相手の体力は残り{B.damage}です。今度は自分で選んでみましょう。{B}の攻撃位置は{B.pos}です。',
                    ACTION,
                ),
            ],
        },
    ],
    'completed': [
        _message(
            '상대가 수비했지만 {B.pos}은 막지 못해 히트! 상대 체력이 0이 되어 승리했습니다.',
            'Your opponent defended, but could not cover {B.pos} — a Hit! Their HP reached 0 and you win.',
            '相手は守備しましたが{B.pos}は防げずヒット！相手の体力が0になり勝利しました。',
            {'kind': 'hud', 'hud': 'p2.hp'},
        ),
        _message(
            '배운 것: ① 한 턴은 다섯 페이즈 ② 공격끼리는 속도가 빠른 쪽이 카운터 ③ 수비는 위치가 맞으면 방어, 아니면 히트.',
            'You learned: ① a turn has five phases ② between attacks the faster one counters ③ a defense guards a matching position, otherwise it gets hit.',
            '学んだこと：① 1ターンは5つのフェイズ ② 攻撃同士は速い方がカウンター ③ 守備は位置が合えば防御、合わなければヒット。',
        ),
    ],
}


LESSONS = {BASIC_1['id']: BASIC_1}

FAILED_MESSAGE = _message(
    '튜토리얼을 이어 갈 수 없습니다. 카드 규칙이 바뀌어 각본과 다른 결과가 나왔습니다. 운영진에게 알렸습니다.',
    'The tutorial cannot continue: card rules changed and the result differs from the script. The team has been notified.',
    'チュートリアルを続行できません。カードのルールが変わり、台本と異なる結果になりました。運営に通知しました。',
)


def get_lesson(lesson_id):
    return LESSONS.get(str(lesson_id or ''))


def lesson_setup(lesson):
    configured = (getattr(settings, 'LUMEN_TUTORIAL_SETUP', None) or {}).get(lesson['id'])
    return configured or lesson.get('setup')
