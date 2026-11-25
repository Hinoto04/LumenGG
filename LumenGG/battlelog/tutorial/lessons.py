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
둘 다 끝나면 다음 단계로 넘어간다. 항목은 ``(행동, 카드 역할)``이고, 선택 창(``submit_decision``)에 역할을 주면
그 카드만 고를 수 있다. 세 번째 값 ``'optional'``은 카드 효과에 따라 생길 수도 있는 행동이다(없어도 단계가 끝난다). ``expect``는 그 단계를 끝낸 명령에서 나와야 할
판정이다(p1 기준 ``battle_judged`` 결과, 승자). 다르면 튜토리얼을 실패로 끝낸다.

단원 설정

- ``board``: 시작 손패·리스트(역할 이름). ``hp``: 시작 체력(``{'p1': 4200}``),
  ``priority``: 시작 우선권(기본 p1), ``p2_hp_from_damage``: 상대 체력을 이 카드들의 데미지 합으로.
- ``finish``: ``'win'``(기본, 마지막 단계에서 p1이 이겨야 완료) 또는 ``'concede'``
  (마지막 단계를 마치면 완료하고 각본 상대가 기권해 게임을 끝낸다. 짧은 단원용).

문구 자리 표시자

- 카드: ``{A}`` 카드명, ``{A.frame}`` 속도, ``{A.damage}`` 데미지, ``{A.pos}`` 위치, ``{A.body}`` 손/발,
  ``{A.fp_hit}``·``{A.fp_guard}``·``{A.fp_counter}`` 판정 결과 FP(+1처럼 부호를 붙인다),
  ``{B.special}`` 특수 판정, ``{D.guard}`` 수비 카드가 방어하는 위치, ``{D.defense}`` 위치별 수비 판정 전체.
- 계산: ``{B.frame-p1.fp}``(두 값의 차. 앞은 카드, 뒤는 카드나 현재 상태).
- 현재 상태: ``{p1.hp}``, ``{p1.fp}``, ``{p1.hand}`` 손패 장수, ``{p1.limit}`` 손패 상한(p2도 같다).

``focus``: ``{'kind': 'action'}`` 허용 행동, ``{'kind': 'card', 'card': 'A'}``,
``{'kind': 'zone', 'zone': 'p1.hand'}``, ``{'kind': 'hud', 'hud': 'p2.hp'}``
(``p1.fp``, ``priority``, ``p1.hand-count``, ``phase`` 포함),
``{'kind': 'anatomy', 'card': 'A', 'part': 'speed'}`` 카드를 크게 띄우고 한 부분을 비춘다
(``ANATOMY_PARTS``). 화면에는 카드 디자인(``card_design``)을 함께 보내 디자인별 자리를 비춘다.
"""

from django.conf import settings


def _text(ko, en, ja):
    return {'ko': ko, 'en': en, 'ja': ja}


def _message(ko, en, ja, focus=None):
    return {'text': _text(ko, en, ja), 'focus': focus}


def _anatomy(card, part):
    return {'kind': 'anatomy', 'card': card, 'part': part}


ACTION = {'kind': 'action'}
# 카드 이미지에서 비출 수 있는 부분(play/src/components/TutorialCoach.tsx의 ANATOMY_BOXES와 같다).
ANATOMY_PARTS = ('name', 'speed', 'pos', 'body', 'damage', 'fp', 'special', 'text', 'guard')
# 예전 카드 디자인을 쓰는 팩(카드 코드 앞부분). 그 밖의 팩은 신규 디자인이다.
# 예전: 속도는 왼쪽 위 동그라미, 위치 마크는 오른쪽 위, 손/발은 이름 아래.
# 신규: 속도를 감싼 마름모의 빛나는 꼭짓점이 위치, 이름 아래 대사, 손/발 아이콘은 오른쪽 위,
#       특수 판정은 효과 글 위의 띠.
CLASSIC_DESIGN_SETS = ('ST1', 'ST2', 'ST3', 'ST4', 'ST5', 'ST6', 'AWL', 'UNC')


def card_design(code):
    """카드 코드로 본 인쇄 디자인: 'classic'(예전) 또는 'current'(신규)."""
    return 'classic' if str(code or '').split('-')[0] in CLASSIC_DESIGN_SETS else 'current'


BASIC_1 = {
    'id': 'basic-1',
    'version': 1,
    'title': _text('한 턴의 흐름', 'The flow of a turn', 'ターンの流れ'),
    'summary': _text(
        '레디·배틀·겟으로 한 판을 끝까지 해 봅니다.',
        'Play a whole match: Ready, Battle and Get.',
        'レディ・バトル・ゲットで1ゲームを最後まで遊びます。',
    ),
    # 운영진이 고를 카드(docs/TUTORIAL.md 2절 조건). 비어 있으면 튜토리얼을 열지 않는다.
    # 검증한 배정(2026.11.16-CB04, check_tutorials·브라우저로 끝까지 진행). 설정 LUMEN_TUTORIAL_SETUP이 우선한다.
    'setup': {
        'characters': {'p1': 3, 'p2': 2},
        'cards': {
            'A': 'ST2-001',
            'B': 'ST2-002',
            'D': 'ST2-010',
            'P1_EXTRA': 'ST2-005',
            'X': 'ST1-006',
            'Y': 'ST1-002',
            'Z': 'ST1-010',
            'P2_EXTRA_1': 'ST1-007',
            'P2_EXTRA_2': 'ST1-008',
        },
    },
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


BASIC_2 = {
    'id': 'basic-2',
    'version': 2,
    'title': _text('카드 읽는 법', 'Reading a card', 'カードの読み方'),
    'summary': _text(
        '속도·위치·데미지·FP·수비 판정이 카드 어디에 있는지 봅니다. 예전 디자인 카드도 함께.',
        'Find speed, position, damage, FP and defense marks on a card — old card designs included.',
        '速度・位置・ダメージ・FP・守備判定がカードのどこにあるかを見ます。旧デザインのカードも一緒に。',
    ),
    # 검증한 배정(2026.11.16-CB04, check_tutorials·브라우저로 끝까지 진행). 설정 LUMEN_TUTORIAL_SETUP이 우선한다.
    'setup': {
        'characters': {'p1': 14, 'p2': 2},
        'cards': {
            'A': 'CB02-AT-003',
            'B': 'CB02-AT-007',
            'D': 'CB02-AT-012',
            'P1_EXTRA': 'CB02-AT-005',
            'W': 'ST1-010',
            'X': 'ST1-006',
            'P2_EXTRA_1': 'ST1-002',
        },
    },
    # A·B·D·P1_EXTRA는 신규 디자인 카드, 상대 리스트의 P2_EXTRA_1은 예전 디자인 카드로 고른다.
    # A: 손/발 판정이 있는 상단·하단 공격, B: 특수 판정(회피·상쇄 등)이 있는 공격, D: 수비,
    # W: A의 위치를 막지 못하는 상대 수비.
    'roles': ('A', 'B', 'D', 'P1_EXTRA', 'W', 'X', 'P2_EXTRA_1'),
    'board': {
        'p1': {'hand': ['A', 'B'], 'list': ['D', 'P1_EXTRA']},
        'p2': {'hand': ['W', 'X'], 'list': ['P2_EXTRA_1']},
    },
    'finish': 'concede',
    'steps': [
        {
            'id': 't1-ready',
            'allow': [('ready_card', 'A')],
            'opponent': [('ready_card', 'W')],
            'expect': {'battle': 'hit'},
            'messages': [
                _message(
                    '카드에는 배틀에 필요한 정보가 모두 적혀 있습니다. 손패의 공격 카드 {A}를 함께 읽어 봅시다.',
                    'A card shows everything you need for a battle. Let\'s read the attack card {A} in your hand.',
                    'カードにはバトルに必要な情報がすべて書かれています。手札の攻撃カード{A}を一緒に読んでみましょう。',
                    {'kind': 'card', 'card': 'A'},
                ),
                _message(
                    '왼쪽 위 마름모 안의 숫자는 속도입니다. 숫자가 작을수록 빠릅니다. {A}의 속도는 {A.frame}.',
                    'The number in the diamond at the top left is the speed. The lower the number, the faster. {A} has speed {A.frame}.',
                    '左上のひし形の中の数字は速度です。数字が小さいほど速くなります。{A}の速度は{A.frame}です。',
                    _anatomy('A', 'speed'),
                ),
                _message(
                    '마름모에서 빛나는 꼭짓점이 공격 위치입니다. 위는 상단, 양옆은 중단, 아래는 하단. {A}는 {A.pos} 공격이에요.',
                    'The lit corner of the diamond is the attack position: top for High, both sides for Mid, bottom for Low. {A} attacks {A.pos}.',
                    'ひし形の光っている角が攻撃位置です。上は上段、左右は中段、下は下段。{A}は{A.pos}攻撃です。',
                    _anatomy('A', 'pos'),
                ),
                _message(
                    '맨 위 가운데는 기술 이름, 그 아래는 기술의 대사입니다.',
                    'The top centre shows the technique name, with the technique\'s quote below it.',
                    '上の中央は技の名前、その下は技のセリフです。',
                    _anatomy('A', 'name'),
                ),
                _message(
                    '오른쪽 위 아이콘은 손/발 판정입니다. {A}는 {A.body} 기술이에요. 손/발 표시가 없는 기술도 있습니다.',
                    'The icon at the top right is the Hand/Foot mark. {A} is a {A.body} technique. Some techniques have no Hand/Foot mark.',
                    '右上のアイコンは手/足の判定です。{A}は{A.body}の技です。手/足の表示がない技もあります。',
                    _anatomy('A', 'body'),
                ),
                _message(
                    '아래쪽 큰 숫자는 데미지입니다. 공격이 히트하거나 카운터하면 상대 체력이 이만큼 줄어듭니다. {A}는 {A.damage}.',
                    'The big number at the bottom is the damage. When the attack hits or counters, the opponent loses this much HP. {A} deals {A.damage}.',
                    '下の大きな数字はダメージです。攻撃がヒットかカウンターすると、相手の体力がこの分減ります。{A}は{A.damage}です。',
                    _anatomy('A', 'damage'),
                ),
                _message(
                    '왼쪽 아이콘 세 개는 판정 결과에 따라 얻는 FP입니다. {A}는 히트 {A.fp_hit}, 가드(방어당함) {A.fp_guard}, 카운터 {A.fp_counter}. FP는 다음 단원에서 배웁니다.',
                    'The three icons on the left are the FP you gain for each result. {A}: Hit {A.fp_hit}, Guarded {A.fp_guard}, Counter {A.fp_counter}. FP comes in the next lesson.',
                    '左の3つのアイコンは判定結果で得るFPです。{A}はヒット{A.fp_hit}、ガード（防御された）{A.fp_guard}、カウンター{A.fp_counter}。FPは次の単元で学びます。',
                    _anatomy('A', 'fp'),
                ),
                _message(
                    '특수 판정이 있는 기술은 효과 글 위의 띠에 적혀 있습니다. 손패의 {B}는 {B.special}.',
                    'A technique with a special judgment shows it on the band above the effect text. {B} in your hand has {B.special}.',
                    '特殊判定がある技は、効果文の上の帯に書かれています。手札の{B}は{B.special}です。',
                    _anatomy('B', 'special'),
                ),
                _message(
                    '그 아래 글은 카드 효과입니다. 대전 중 카드를 누르면(PC는 오른쪽 클릭도) 크게 보고 효과 설명을 읽을 수 있어요.',
                    'The text below it is the card\'s effect. During a match, tap a card (or right-click on PC) to see it large with the effect explained.',
                    'その下の文章はカードの効果です。対戦中にカードを押すと（PCは右クリックも）大きく表示して効果の説明を読めます。',
                    _anatomy('B', 'text'),
                ),
                _message(
                    '{A}를 레디하세요.',
                    'Ready {A}.',
                    '{A}をレディしてください。',
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
                    '상대의 수비 {W}는 {W.guard}만 막아서 {A.pos} 공격이 히트했습니다! {A.damage} 데미지.',
                    'Your opponent\'s {W} only guards {W.guard}, so your {A.pos} attack hit! {A.damage} damage.',
                    '相手の守備{W}は{W.guard}しか防げないので、{A.pos}攻撃がヒットしました！{A.damage}ダメージ。',
                    {'kind': 'hud', 'hud': 'p2.hp'},
                ),
                _message(
                    '이번에는 수비 카드를 읽어 봅시다. 리스트의 {D}입니다. 수비 카드에는 속도와 데미지가 없습니다.',
                    'Now let\'s read a defense card: {D} in your list. Defense cards have no speed or damage.',
                    '今度は守備カードを読んでみましょう。リストの{D}です。守備カードには速度とダメージがありません。',
                    {'kind': 'card', 'card': 'D'},
                ),
                _message(
                    '왼쪽 아이콘이 수비 판정입니다. 위에서부터 상단·중단·하단에 방어·회피·상쇄 중 무엇을 하는지 적혀 있어요. {D}: {D.defense}.',
                    'The icons on the left are its defense marks: from the top, what it does against High, Mid and Low — Guard, Dodge or Clash. {D}: {D.defense}.',
                    '左のアイコンが守備判定です。上から上段・中段・下段に対してガード・回避・相殺のどれをするかが書かれています。{D}：{D.defense}。',
                    _anatomy('D', 'guard'),
                ),
                _message(
                    '상대 리스트는 언제나 공개되어 있습니다. 상대 카드도 같은 방법으로 읽고 다음 수를 짐작할 수 있어요.',
                    'Your opponent\'s list is always face up. Read their cards the same way to guess what they will do next.',
                    '相手のリストは常に公開されています。相手のカードも同じように読んで、次の手を予想できます。',
                    {'kind': 'zone', 'zone': 'p2.list'},
                ),
                _message(
                    '상대 리스트의 카드 「{P2_EXTRA_1}」처럼 스타터 덱 등 초기 카드는 예전 디자인입니다. 속도는 왼쪽 위 동그라미 안에 있고, 공격 위치는 오른쪽 위에 따로 마크로 표시됩니다. 이 카드는 속도 {P2_EXTRA_1.frame}, 위치 {P2_EXTRA_1.pos}.',
                    '{P2_EXTRA_1} in your opponent\'s list uses the old card design, found on starter decks and other early cards. The speed is in the circle at the top left, and the attack position has its own mark at the top right. {P2_EXTRA_1}: speed {P2_EXTRA_1.frame}, {P2_EXTRA_1.pos}.',
                    '相手のリストの{P2_EXTRA_1}は旧デザインのカードです。スターターデッキなど初期のカードはこのデザインです。速度は左上の円の中にあり、攻撃位置は右上に別のマークで表示されます。{P2_EXTRA_1}は速度{P2_EXTRA_1.frame}、{P2_EXTRA_1.pos}です。',
                    _anatomy('P2_EXTRA_1', 'pos'),
                ),
                _message(
                    '예전 디자인은 손/발 판정이 이름 바로 아래에 글자로 적혀 있습니다. 데미지·FP·효과의 자리는 신규 디자인과 같아요.',
                    'On the old design, Hand/Foot is written right under the name. Damage, FP and the effect are in the same places as on the new design.',
                    '旧デザインでは手/足の判定が名前のすぐ下に文字で書かれています。ダメージ・FP・効果の位置は新デザインと同じです。',
                    _anatomy('P2_EXTRA_1', 'body'),
                ),
                _message(
                    '겟 페이즈입니다. {D}를 가져오세요.',
                    'It is the Get phase. Take {D}.',
                    'ゲットフェイズです。{D}を手札に加えましょう。',
                    ACTION,
                ),
            ],
        },
    ],
    'completed': [
        _message(
            '배운 것: ① 왼쪽 위 마름모는 속도, 빛나는 꼭짓점은 위치 ② 아래 큰 숫자는 데미지, 왼쪽 아이콘은 공격이면 결과별 FP, 수비면 위치별 수비 판정 ③ 예전 디자인은 위치 마크가 오른쪽 위, 손/발이 이름 아래.',
            'You learned: ① the top-left diamond is the speed, and its lit corner the position ② the big number at the bottom is damage; the left icons are FP per result on attacks and defense marks per position on defenses ③ the old design puts the position mark at the top right and Hand/Foot under the name.',
            '学んだこと：① 左上のひし形は速度、光っている角は位置 ② 下の大きな数字はダメージ、左のアイコンは攻撃なら結果ごとのFP、守備なら位置ごとの守備判定 ③ 旧デザインは位置マークが右上、手/足は名前の下。',
        ),
    ],
}


BASIC_3 = {
    'id': 'basic-3',
    'version': 1,
    'title': _text('FP와 우선권', 'FP and priority', 'FPと優先権'),
    'summary': _text(
        'FP로 공격을 빠르게 하고, 우선권이 어떻게 정해지는지 봅니다.',
        'Speed up an attack with FP and see how priority is decided.',
        'FPで攻撃を速くし、優先権の決まり方を見ます。',
    ),
    # 검증한 배정(2026.11.16-CB04, check_tutorials·브라우저로 끝까지 진행). 설정 LUMEN_TUTORIAL_SETUP이 우선한다.
    'setup': {
        'characters': {'p1': 3, 'p2': 2},
        'cards': {
            'A': 'ST2-009',
            'B': 'ST2-005',
            'P1_EXTRA': 'ST2-007',
            'W': 'ST1-010',
            'X': 'ST1-002',
            'P2_EXTRA_1': 'ST1-007',
        },
    },
    'roles': ('A', 'B', 'P1_EXTRA', 'W', 'X', 'P2_EXTRA_1'),
    'board': {
        'p1': {'hand': ['A', 'B'], 'list': ['P1_EXTRA']},
        'p2': {'hand': ['W', 'X'], 'list': ['P2_EXTRA_1']},
    },
    # 처음 우선권은 상대에게 두고, FP를 얻은 뒤 겟 페이즈에서 넘어오는 것을 보여 준다.
    'priority': 'p2',
    'p2_hp_from_damage': ('A', 'B'),
    'steps': [
        {
            'id': 't1-ready',
            'allow': [('ready_card', 'A')],
            'opponent': [('ready_card', 'W')],
            'expect': {'battle': 'hit'},
            'messages': [
                _message(
                    'FP는 공격의 속도를 바꾸는 수치입니다. 캐릭터 옆에 표시되며, 지금은 둘 다 0입니다.',
                    'FP is a value that changes the speed of your attacks. It is shown by your character; right now both players have 0.',
                    'FPは攻撃の速度を変える数値です。キャラクターの横に表示され、今はどちらも0です。',
                    {'kind': 'hud', 'hud': 'p1.fp'},
                ),
                _message(
                    'FP는 배틀 결과로 얻습니다. 공격 카드 왼쪽 아이콘을 보세요. {A}는 히트하면 {A.fp_hit} FP를 얻습니다.',
                    'You gain FP from battle results. Look at the icons on the left of an attack card: {A} gains {A.fp_hit} FP on a Hit.',
                    'FPはバトルの結果で得ます。攻撃カードの左のアイコンを見てください。{A}はヒットすると{A.fp_hit}FPを得ます。',
                    _anatomy('A', 'fp'),
                ),
                _message(
                    '{A}를 레디하세요.',
                    'Ready {A}.',
                    '{A}をレディしてください。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't1-get',
            'allow': [('select_get_card', 'P1_EXTRA')],
            'opponent': [('select_get_card', 'P2_EXTRA_1')],
            'messages': [
                _message(
                    '히트! {A.damage} 데미지를 주고 FP를 {A.fp_hit} 얻어 지금 FP는 {p1.fp}입니다.',
                    'A Hit! You dealt {A.damage} damage and gained {A.fp_hit} FP. Your FP is now {p1.fp}.',
                    'ヒット！{A.damage}ダメージを与え、FPを{A.fp_hit}得て今のFPは{p1.fp}です。',
                    {'kind': 'hud', 'hud': 'p1.fp'},
                ),
                _message(
                    '우선권은 양쪽이 같은 때 행동할 때 먼저 하는 권리입니다. 겟 페이즈마다 FP → 체력 → 손패 장수 순으로 비교해 높은 쪽이 갖습니다.',
                    'Priority decides who acts first when both players act at the same time. Every Get phase it goes to the player with more FP, then more HP, then more cards in hand.',
                    '優先権は両者が同じタイミングで行動するときに先に行動する権利です。ゲットフェイズごとにFP → 体力 → 手札の枚数の順に比べ、高い方が持ちます。',
                    {'kind': 'hud', 'hud': 'priority'},
                ),
                _message(
                    '처음에는 상대에게 있었지만, 이제 FP가 더 높은 당신에게 넘어왔습니다. 그래서 겟도 당신이 먼저 합니다. 리스트에서 {P1_EXTRA}를 가져오세요.',
                    'Your opponent had it at first, but now it is yours because your FP is higher — so you take your Get card first. Take {P1_EXTRA} from your list.',
                    '最初は相手が持っていましたが、FPが高いあなたに移りました。だからゲットもあなたが先です。リストから{P1_EXTRA}を手札に加えましょう。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't2-ready',
            'allow': [('ready_card', 'B')],
            'opponent': [('ready_card', 'X')],
            'expect': {'battle': 'counter', 'winner': 'p1'},
            'messages': [
                _message(
                    '상대는 속도 {X.frame}인 {X}를 낼 것 같습니다. {B}의 속도는 {B.frame}. 원래대로라면 더 느립니다.',
                    'Your opponent looks set to use {X} (speed {X.frame}). {B} has speed {B.frame}, so normally it would be slower.',
                    '相手は速度{X.frame}の{X}を出しそうです。{B}の速度は{B.frame}なので、本来は遅いです。',
                    _anatomy('B', 'speed'),
                ),
                _message(
                    '하지만 배틀에서는 공격의 속도 숫자에서 FP만큼 뺍니다. {B.frame} − {p1.fp} = {B.frame-p1.fp}. 이제 {X}보다 빠릅니다! {B}를 레디하세요.',
                    'But in battle, your FP is subtracted from your attack\'s speed: {B.frame} − {p1.fp} = {B.frame-p1.fp}. Now it is faster than {X}! Ready {B}.',
                    'しかしバトルでは攻撃の速度の数字からFPを引きます。{B.frame} − {p1.fp} = {B.frame-p1.fp}。これで{X}より速くなります！{B}をレディしてください。',
                    ACTION,
                ),
            ],
        },
    ],
    'completed': [
        _message(
            'FP 덕분에 {B}가 카운터! 배틀에서는 가지고 있던 FP를 모두 씁니다(수비 카드를 내도 사라져요). 그리고 판정 결과로 FP를 새로 얻습니다. 이번에는 카운터 {B.fp_counter}.',
            'Thanks to FP, {B} countered! A battle spends all the FP you had (even if you play a defense card), and then the result gives you new FP — this time Counter {B.fp_counter}.',
            'FPのおかげで{B}がカウンター！バトルでは持っていたFPをすべて使います（守備カードを出してもなくなります）。そして判定結果でFPを新しく得ます。今回はカウンター{B.fp_counter}。',
            {'kind': 'hud', 'hud': 'p1.fp'},
        ),
        _message(
            '배운 것: ① 공격 결과로 FP를 얻는다 ② 배틀에서는 속도 숫자 − FP로 판정하고 가진 FP를 모두 쓴다 ③ 우선권은 FP → 체력 → 손패 순으로 겟 페이즈마다 다시 정한다.',
            'You learned: ① attack results give FP ② in battle, speed − FP is compared and all your FP is spent ③ priority is decided each Get phase by FP, then HP, then hand size.',
            '学んだこと：① 攻撃の結果でFPを得る ② バトルでは速度 − FPで判定し、持っているFPをすべて使う ③ 優先権はFP → 体力 → 手札の順でゲットフェイズごとに決め直す。',
        ),
    ],
}


BASIC_4 = {
    'id': 'basic-4',
    'version': 1,
    'title': _text('손패와 겟', 'Your hand and the Get phase', '手札とゲット'),
    'summary': _text(
        '손패 상한이 체력에 따라 바뀌는 것과 겟을 건너뛰는 때를 봅니다.',
        'See how your hand limit follows your HP, and when you may skip a Get.',
        '手札の上限が体力で変わることと、ゲットを飛ばせるときを見ます。',
    ),
    # 검증한 배정(2026.11.16-CB04, check_tutorials·브라우저로 끝까지 진행). 설정 LUMEN_TUTORIAL_SETUP이 우선한다.
    'setup': {
        'characters': {'p1': 3, 'p2': 2},
        'cards': {
            'A': 'ST2-005',
            'D': 'ST2-010',
            'H1': 'ST2-001',
            'H2': 'ST2-002',
            'H3': 'ST2-003',
            'H4': 'ST2-006',
            'E': 'ST2-007',
            'L1': 'ST2-009',
            'X': 'ST1-002',
            'P2_EXTRA_1': 'ST1-007',
            'P2_EXTRA_2': 'ST1-008',
        },
    },
    'roles': ('A', 'D', 'H1', 'H2', 'H3', 'H4', 'E', 'L1', 'X', 'P2_EXTRA_1', 'P2_EXTRA_2'),
    'board': {
        'p1': {'hand': ['A', 'D', 'H1', 'H2', 'H3', 'H4'], 'list': ['E', 'L1']},
        'p2': {'hand': ['X'], 'list': ['P2_EXTRA_1', 'P2_EXTRA_2']},
    },
    # 상한이 한 장 늘어나는 경계(4000) 바로 위에서 시작한다. 카드 배정 시 X의 데미지로 경계를 넘어야 한다.
    'hp': {'p1': 4200},
    'finish': 'concede',
    'steps': [
        {
            'id': 't1-ready',
            'allow': [('ready_card', 'A')],
            'opponent': [('ready_card', 'X')],
            'expect': {'battle': 'countered'},
            'messages': [
                _message(
                    '손패 옆 숫자는 "지금 장수 / 손패 상한"입니다. 지금은 {p1.hand}장 / {p1.limit}장으로 꽉 차 있어요.',
                    'The numbers by your hand read "cards now / hand limit". You have {p1.hand} of {p1.limit} — a full hand.',
                    '手札の横の数字は「今の枚数 / 手札の上限」です。今は{p1.hand}枚 / {p1.limit}枚で満杯です。',
                    {'kind': 'hud', 'hud': 'p1.hand-count'},
                ),
                _message(
                    '손패 상한은 캐릭터 카드에 체력 구간별로 적혀 있습니다. 체력이 줄수록 상한이 늘어나 선택지가 많아집니다.',
                    'The hand limit is printed on your character card for each HP range. The lower your HP, the higher the limit, giving you more options.',
                    '手札の上限はキャラクターカードに体力の区間ごとに書かれています。体力が減るほど上限が増え、選択肢が多くなります。',
                    {'kind': 'hud', 'hud': 'p1.hp'},
                ),
                _message(
                    '이번 턴에는 일부러 속도 {A.frame}인 느린 {A}를 내서 공격을 맞아 봅시다. {A}를 레디하세요.',
                    'This turn, play the slow {A} (speed {A.frame}) on purpose and take a hit. Ready {A}.',
                    'このターンはわざと遅い{A}（速度{A.frame}）を出して攻撃を受けてみましょう。{A}をレディしてください。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't1-get',
            'allow': [('select_get_card', 'E')],
            'opponent': [('select_get_card', 'P2_EXTRA_1')],
            'messages': [
                _message(
                    '상대의 더 빠른 {X}에 카운터당해 체력이 {p1.hp}가 되었습니다. 그 대신 손패 상한이 {p1.limit}장으로 늘었어요.',
                    'The faster {X} countered you and your HP is now {p1.hp}. In exchange, your hand limit rose to {p1.limit}.',
                    '相手のより速い{X}にカウンターされ、体力が{p1.hp}になりました。その代わり手札の上限が{p1.limit}枚に増えました。',
                    {'kind': 'hud', 'hud': 'p1.hand-count'},
                ),
                _message(
                    '배틀에 쓴 {A}는 손패로 돌아와 손패는 {p1.hand}장. 상한보다 적으면 겟 페이즈에 반드시 1장을 가져와야 합니다. {E}를 가져오세요.',
                    '{A} came back to your hand, so you hold {p1.hand} cards. Below the limit, you must take one card in the Get phase. Take {E}.',
                    'バトルで使った{A}は手札に戻り、手札は{p1.hand}枚。上限より少ないとゲットフェイズに必ず1枚加えなければなりません。{E}を加えましょう。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't2-ready',
            'allow': [('ready_card', 'D')],
            'opponent': [('ready_card', 'X')],
            'expect': {'battle': 'guard'},
            'messages': [
                _message(
                    '이제 손패가 {p1.hand}장 / {p1.limit}장으로 다시 꽉 찼습니다. 상대가 또 {X}로 {X.pos}을 노리니 {D}로 막아 봅시다. {D}를 레디하세요.',
                    'Your hand is full again: {p1.hand} of {p1.limit}. Your opponent is going for {X.pos} with {X} again, so block it with {D}. Ready {D}.',
                    'これで手札は{p1.hand}枚 / {p1.limit}枚で再び満杯です。相手はまた{X}で{X.pos}を狙うので、{D}で防ぎましょう。{D}をレディしてください。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't2-get',
            'allow': [('pass_phase', None)],
            'opponent': [('select_get_card', 'P2_EXTRA_2')],
            'messages': [
                _message(
                    '방어 성공! 손패가 상한에 닿아 있을 때는 겟을 건너뛸 수 있습니다. 리스트에 카드를 남겨 두고 싶을 때 쓰는 선택이에요.',
                    'Guarded! When your hand is at its limit, you may skip the Get. Use this when you would rather keep cards in your list.',
                    '防御成功！手札が上限に達しているときはゲットを飛ばせます。リストにカードを残しておきたいときの選択です。',
                    {'kind': 'hud', 'hud': 'p1.hand-count'},
                ),
                _message(
                    '"획득하지 않음"을 눌러 이번 겟을 건너뛰세요.',
                    'Press "Take nothing" to skip this Get.',
                    '「獲得しない」を押して今回のゲットを飛ばしましょう。',
                    ACTION,
                ),
            ],
        },
    ],
    'completed': [
        _message(
            '배운 것: ① 손패 옆 숫자는 장수 / 상한 ② 체력이 줄면 상한이 늘어난다 ③ 상한보다 적으면 겟은 필수, 상한이면 건너뛸 수 있다.',
            'You learned: ① the numbers by your hand are count / limit ② lower HP raises the limit ③ below the limit the Get is required; at the limit you may skip it.',
            '学んだこと：① 手札の横の数字は枚数 / 上限 ② 体力が減ると上限が増える ③ 上限より少なければゲットは必須、上限なら飛ばせる。',
        ),
    ],
}


BASIC_5 = {
    'id': 'basic-5',
    'version': 1,
    'title': _text('콤보와 캐치', 'Combos and Catches', 'コンボとキャッチ'),
    'summary': _text(
        '콤보 타임에 공격을 잇는 법과, 배틀 끝에 FP로 캐치하는 법을 배웁니다.',
        'Learn to chain attacks in Combo Time and to Catch with FP at the end of a battle.',
        'コンボタイムで攻撃をつなぐ方法と、バトルの最後にFPでキャッチする方法を学びます。',
    ),
    # 검증한 배정(2026.11.16-CB04, check_tutorials·브라우저로 끝까지 진행). 설정 LUMEN_TUTORIAL_SETUP이 우선한다.
    'setup': {
        'characters': {'p1': 3, 'p2': 2},
        'cards': {
            'A': 'ST2-004',
            'C1': 'ST2-001',
            'C2': 'ST2-002',
            'T': 'ST2-009',
            'K': 'UNC-AT-018',
            'L1': 'ST2-007',
            'W': 'ST1-008',
            'Z': 'ST1-010',
            'P2_EXTRA_1': 'ST1-002',
            'P2_EXTRA_2': 'ST1-007',
        },
    },
    'roles': ('A', 'C1', 'C2', 'T', 'K', 'L1', 'W', 'Z', 'P2_EXTRA_1', 'P2_EXTRA_2'),
    'board': {
        'p1': {'hand': ['A', 'C1', 'C2', 'T', 'K'], 'list': ['L1']},
        'p2': {'hand': ['W', 'Z'], 'list': ['P2_EXTRA_1', 'P2_EXTRA_2']},
    },
    'finish': 'concede',
    'steps': [
        {
            'id': 't1-ready',
            'allow': [('ready_card', 'A')],
            'opponent': [('ready_card', 'W')],
            'expect': {'battle': 'counter'},
            'messages': [
                _message(
                    '{A}의 판정 결과 FP를 보세요. 히트·카운터 자리에 숫자 대신 "콤보"가 적혀 있습니다.',
                    'Look at the result FP of {A}. Its hit and counter slots say "Combo" instead of a number.',
                    '{A}の判定結果FPを見てください。ヒット・カウンターの欄に数字ではなく「コンボ」と書かれています。',
                    _anatomy('A', 'fp'),
                ),
                _message(
                    '이런 콤보 판정 공격이 히트하거나 카운터하면 그 공격이 1콤보가 되고 콤보 타임이 시작됩니다.',
                    'When an attack with a Combo result hits or counters, it becomes Combo 1 and Combo Time begins.',
                    'このようなコンボ判定の攻撃がヒットかカウンターすると、その攻撃が1コンボになりコンボタイムが始まります。',
                ),
                _message(
                    '상대는 속도 {W.frame}인 느린 {W}를 냅니다. 속도 {A.frame}인 {A}를 레디하세요.',
                    'Your opponent plays the slow {W} (speed {W.frame}). Ready {A}, speed {A.frame}.',
                    '相手は遅い{W}（速度{W.frame}）を出します。速度{A.frame}の{A}をレディしてください。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't1-combo',
            'allow': [('select_combo_first', 'C1'), ('select_combo_followup', 'C2')],
            'opponent': [],
            'messages': [
                _message(
                    '카운터! {A}가 1콤보가 되어 콤보 타임이 시작되었습니다.',
                    'Counter! {A} is Combo 1, and Combo Time has begun.',
                    'カウンター！{A}が1コンボになり、コンボタイムが始まりました。',
                    {'kind': 'hud', 'hud': 'p2.hp'},
                ),
                _message(
                    '콤보를 이으려면 손패의 공격 2장을 함께 냅니다. 두 번째 카드는 첫 카드보다 속도 숫자가 정확히 1 커야 해요. 속도 {C1.frame}인 {C1} 다음에 속도 {C2.frame}인 {C2}를 이을 수 있습니다.',
                    'To continue, put out two attacks from your hand together. The second must have a speed exactly 1 higher than the first: {C1} (speed {C1.frame}) can be followed by {C2} (speed {C2.frame}).',
                    'コンボを続けるには手札の攻撃2枚を一緒に出します。2枚目は1枚目より速度の数字がちょうど1大きくなければなりません。{C1}（速度{C1.frame}）の次に{C2}（速度{C2.frame}）をつなげます。',
                    {'kind': 'zone', 'zone': 'p1.hand'},
                ),
                _message(
                    '콤보 카드는 판정 없이 바로 데미지를 줍니다. 대신 이어질수록 데미지가 줄어, 2콤보는 −100, 3콤보는 −200입니다.',
                    'Combo cards deal damage right away, with no judgment. But damage drops the longer the chain: −100 at Combo 2, −200 at Combo 3.',
                    'コンボのカードは判定なしでそのままダメージを与えます。その代わりつなぐほどダメージが減り、2コンボは−100、3コンボは−200です。',
                ),
                _message(
                    '첫 카드로 {C1}를 고른 뒤, 이어서 {C2}를 고르세요.',
                    'Choose {C1} as the first card, then choose {C2}.',
                    '1枚目に{C1}を選び、続けて{C2}を選んでください。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't1-combo-end',
            'allow': [('end_combo', None)],
            'opponent': [],
            'messages': [
                _message(
                    '3콤보까지 들어갔습니다! 이 뒤로는 직전 카드보다 속도 숫자가 1 큰 공격(효과로 이을 수 있는 카드 포함)을 한 장씩 더 이을 수 있어요. 4콤보는 −300입니다.',
                    'That is Combo 3! After this you may add one attack at a time whose speed is 1 higher than the last card (or one whose effect lets it follow). Combo 4 is −300.',
                    '3コンボまで入りました！この後は直前のカードより速度の数字が1大きい攻撃（効果でつなげるカードを含む）を1枚ずつつなげます。4コンボは−300です。',
                    {'kind': 'hud', 'hud': 'p2.hp'},
                ),
                _message(
                    '{T}는 다음 턴에 쓸 테니 여기서 끝냅시다. 콤보 타임이 끝나면 콤보에 쓴 카드는 모두 리스트로 가고, 양쪽 FP는 0이 되며, 배틀 페이즈가 바로 끝납니다. "콤보 종료"를 누르세요.',
                    'Save {T} for next turn and stop here. When Combo Time ends, every card used in the combo goes to the list, both FP become 0, and the Battle phase ends at once. Press "End combo".',
                    '{T}は次のターンに使うので、ここで終えましょう。コンボタイムが終わると、コンボに使ったカードはすべてリストへ行き、双方のFPは0になり、バトルフェイズはすぐ終わります。「コンボ終了」を押してください。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't1-get',
            'allow': [('select_get_card', 'L1')],
            'opponent': [('select_get_card', 'P2_EXTRA_1')],
            'messages': [
                _message(
                    '콤보에 쓴 {A}·{C1}·{C2}가 리스트로 갔습니다. 콤보는 강하지만 쓴 카드가 손패를 떠나요.',
                    '{A}, {C1} and {C2} went to the list. Combos hit hard, but the cards you use leave your hand.',
                    'コンボに使った{A}・{C1}・{C2}がリストへ行きました。コンボは強力ですが、使ったカードは手札を離れます。',
                    {'kind': 'zone', 'zone': 'p1.list'},
                ),
                _message(
                    '{L1}를 가져오세요.',
                    'Take {L1}.',
                    '{L1}を加えましょう。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't2-ready',
            'allow': [('ready_card', 'T')],
            'opponent': [('ready_card', 'Z')],
            'expect': {'battle': 'hit'},
            'messages': [
                _message(
                    '이번에는 캐치입니다. 캐치는 배틀이 끝날 때 FP로 거는 추가 공격이에요.',
                    'Now for the Catch: an extra attack you make with FP at the end of a battle.',
                    '今度はキャッチです。キャッチはバトルの最後にFPで仕掛ける追加の攻撃です。',
                ),
                _message(
                    '상대는 {Z.guard}만 막는 {Z}를 냅니다. {T.pos} 공격인 {T}는 히트해서 FP {T.fp_hit}를 얻어요. {T}를 레디하세요.',
                    'Your opponent plays {Z}, which only guards {Z.guard}. {T}, a {T.pos} attack, will hit and gain {T.fp_hit} FP. Ready {T}.',
                    '相手は{Z.guard}しか防がない{Z}を出します。{T.pos}攻撃の{T}はヒットしてFP{T.fp_hit}を得ます。{T}をレディしてください。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't2-catch',
            'allow': [('play_catch_card', 'K')],
            'opponent': [],
            'messages': [
                _message(
                    '히트! 내 FP는 {p1.fp}, 상대 FP는 {p2.fp}. 내 FP가 0보다 크고 상대 FP가 0이면 캐치할 수 있습니다.',
                    "Hit! Your FP is {p1.fp} and your opponent's is {p2.fp}. With your FP above 0 and theirs at 0, you can Catch.",
                    'ヒット！自分のFPは{p1.fp}、相手のFPは{p2.fp}。自分のFPが0より大きく相手のFPが0ならキャッチできます。',
                    {'kind': 'hud', 'hud': 'p1.fp'},
                ),
                _message(
                    '캐치에는 속도가 내 FP({p1.fp}) 이하인 공격을 씁니다. {K}의 속도는 {K.frame}. 조건에 맞아 쓸 수 있어요.',
                    'A Catch uses an attack whose speed is at most your FP ({p1.fp}). {K} has speed {K.frame}, so it qualifies.',
                    'キャッチには速度が自分のFP（{p1.fp}）以下の攻撃を使います。{K}は速度{K.frame}なので使えます。',
                    {'kind': 'card', 'card': 'K'},
                ),
                _message(
                    '캐치하면 먼저 양쪽 FP가 0이 되고, 캐치 공격은 자동으로 히트합니다. 방어·회피·상쇄로 막을 수 없어요. {K}로 캐치하세요.',
                    'A Catch first sets both FP to 0, then hits automatically. It cannot be guarded, dodged or clashed. Catch with {K}.',
                    'キャッチするとまず双方のFPが0になり、キャッチの攻撃は自動でヒットします。防御・回避・相殺で防げません。{K}でキャッチしましょう。',
                    ACTION,
                ),
            ],
        },
    ],
    'completed': [
        _message(
            '배운 것: ① 판정 결과 FP가 "콤보"인 공격이 히트·카운터하면 콤보 타임 ② 속도 숫자가 1씩 커지는 공격을 이어 붙이고, 이어질수록 데미지 −100씩 ③ 콤보에 쓴 카드는 리스트로, FP는 0 ④ 내 FP > 0·상대 FP = 0이면 내 FP 이하 속도의 공격으로 캐치(자동 히트). 내 FP가 0이고 상대 FP가 음수일 때도 상대가 잃은 만큼의 속도까지 캐치할 수 있습니다.',
            'You learned: ① an attack with a "Combo" result that hits or counters starts Combo Time ② chain attacks whose speed rises by 1 each; damage drops by 100 per step ③ combo cards go to the list and FP becomes 0 ④ with your FP above 0 and theirs at 0, Catch with an attack no faster than your FP (it hits automatically). If your FP is 0 and theirs is negative, you may Catch with speed up to the FP they lost.',
            '学んだこと：① 判定結果FPが「コンボ」の攻撃がヒット・カウンターするとコンボタイム ② 速度の数字が1ずつ大きい攻撃をつなぎ、つなぐほどダメージ−100ずつ ③ コンボに使ったカードはリストへ、FPは0 ④ 自分のFP > 0・相手のFP = 0なら自分のFP以下の速度の攻撃でキャッチ（自動ヒット）。自分のFPが0で相手のFPがマイナスのときも、相手が失った分の速度までキャッチできます。',
        ),
    ],
}

BASIC_6 = {
    'id': 'basic-6',
    'version': 1,
    'title': _text('특수 판정과 브레이크', 'Special judgments and Break', '特殊判定とブレイク'),
    'summary': _text(
        '그랩·상쇄·회피를 직접 겪고, 카드를 브레이크해 그랩을 무효로 하고 사이드 덱에서 보충합니다.',
        'Experience Grab, Clash and Dodge, break a card to negate a Grab, and refill from the side deck.',
        'グラブ・相殺・回避を体験し、カードをブレイクしてグラブを無効にし、サイドデッキから補充します。',
    ),
    # 검증한 배정(2026.11.16-CB04, check_tutorials·브라우저로 끝까지 진행). 설정 LUMEN_TUTORIAL_SETUP이 우선한다.
    'setup': {
        'characters': {'p1': 3, 'p2': 2},
        'cards': {
            'S': 'ST2-007',
            'G': 'CB01-AT-010',
            'V': 'CB02-AT-015',
            'R': 'ST2-006',
            'L1': 'ST2-008',
            'SD': 'ST2-003',
            'GR': 'CB01-AT-007',
            'Y': 'ST1-001',
            'E4': 'ST1-004',
            'P2_EXTRA_1': 'ST1-002',
            'P2_EXTRA_2': 'ST1-003',
        },
    },
    'roles': ('S', 'G', 'V', 'R', 'L1', 'SD', 'GR', 'Y', 'E4', 'P2_EXTRA_1', 'P2_EXTRA_2'),
    'board': {
        'p1': {'hand': ['S', 'G', 'V', 'R'], 'list': ['L1'], 'side': ['SD']},
        'p2': {'hand': ['GR', 'Y', 'E4'], 'list': ['P2_EXTRA_1', 'P2_EXTRA_2']},
    },
    'finish': 'concede',
    'steps': [
        {
            'id': 't1-ready',
            'allow': [('ready_card', 'S')],
            'opponent': [('ready_card', 'GR')],
            # 그랩 무효 선택 창은 판정 결과를 적용하기 전에 열린다(판정 이벤트 없음).
            'messages': [
                _message(
                    '특수 판정은 카드에 적힌 특별한 판정으로, 회피·상쇄·그랩이 있습니다. {G}의 특수 판정은 {G.special}입니다.',
                    'Special judgments are extra rules printed on a card: Dodge, Clash and Grab. The special judgment of {G} is {G.special}.',
                    '特殊判定はカードに書かれた特別な判定で、回避・相殺・グラブがあります。{G}の特殊判定は{G.special}です。',
                    _anatomy('G', 'special'),
                ),
                _message(
                    '그랩 공격은 보통 공격처럼 판정하지만, 맞을 때 손패의 그랩 기술 1장을 브레이크하면 무효로 할 수 있습니다.',
                    'A Grab is judged like any attack, but when it lands you may break a Grab from your hand to negate it.',
                    'グラブ攻撃は普通の攻撃のように判定しますが、受けるときに手札のグラブ技1枚をブレイクすれば無効にできます。',
                ),
                _message(
                    '상대가 속도 {GR.frame}인 그랩 기술 {GR}를 냅니다. 일부러 속도 {S.frame}인 느린 {S}를 레디해 그랩을 맞아 봅시다.',
                    'Your opponent plays the Grab {GR} (speed {GR.frame}). Ready the slow {S} (speed {S.frame}) on purpose and take the Grab.',
                    '相手はグラブ技{GR}（速度{GR.frame}）を出します。わざと遅い{S}（速度{S.frame}）をレディしてグラブを受けてみましょう。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't1-grab',
            'allow': [('submit_decision', 'G')],
            'opponent': [],
            'messages': [
                _message(
                    '상대 그랩이 카운터로 들어오려 합니다! 판정을 적용하기 직전, 손패의 그랩 기술 {G}를 브레이크해 무효로 할 수 있어요.',
                    'The Grab is about to counter you! Right before it is applied, you may break the Grab {G} from your hand to negate it.',
                    '相手のグラブがカウンターで入ろうとしています！判定を適用する直前に、手札のグラブ技{G}をブレイクして無効にできます。',
                    {'kind': 'card', 'card': 'G'},
                ),
                _message(
                    '브레이크한 카드는 브레이크 존으로 가서 그 게임에서 다시 쓸 수 없습니다. 카드 효과나, 리스트가 14장일 때 리스트로 가려던 카드도 브레이크돼요. {G}를 골라 그랩을 무효로 하세요.',
                    'A broken card goes to the Break zone and cannot be used again this game. Card effects can break cards too, as can a card moving to a list that already holds 14. Choose {G} to negate the Grab.',
                    'ブレイクしたカードはブレイクゾーンへ行き、そのゲームでは二度と使えません。カード効果や、リストが14枚のときにリストへ行こうとしたカードもブレイクされます。{G}を選んでグラブを無効にしましょう。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't1-replenish',
            'allow': [('submit_decision', 'SD')],
            'opponent': [],
            'messages': [
                _message(
                    '그랩 무효! 공격·수비 기술이 브레이크되면 사이드 덱의 공격·수비 기술 1장을 리스트에 보충할 수 있습니다.',
                    'Grab negated! When an attack or defense card is broken, you may put one attack or defense card from your side deck into your list.',
                    'グラブ無効！攻撃・守備技がブレイクされると、サイドデッキの攻撃・守備技1枚をリストに補充できます。',
                    {'kind': 'zone', 'zone': 'p1.list'},
                ),
                _message(
                    '{SD}를 골라 리스트에 보충하세요.',
                    'Choose {SD} to add it to your list.',
                    '{SD}を選んでリストに補充しましょう。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't1-reready',
            'allow': [('ready_card', 'V')],
            'opponent': [('ready_card', 'Y')],
            'expect': {'battle': 'clash'},
            'messages': [
                _message(
                    '그랩을 무효로 하면 양쪽 레디 카드가 손패로 돌아가고, 같은 턴의 레디 페이즈를 다시 합니다.',
                    'Negating a Grab returns both ready cards to hand and repeats the Ready phase of the same turn.',
                    'グラブを無効にすると双方のレディカードが手札に戻り、同じターンのレディフェイズをやり直します。',
                    {'kind': 'zone', 'zone': 'p1.hand'},
                ),
                _message(
                    '{V}의 특수 판정은 {V.special}입니다. 상대 공격이 그 위치이고 내 공격보다 빠르면 서로 상쇄되어, 데미지가 낮은 쪽이 차이만큼만 체력을 잃어요.',
                    'The special judgment of {V} is {V.special}. If the opposing attack is at that position and faster than yours, the two clash: the side with less damage loses only the difference.',
                    '{V}の特殊判定は{V.special}です。相手の攻撃がその位置で自分の攻撃より速いと互いに相殺され、ダメージの低い側が差の分だけ体力を失います。',
                    _anatomy('V', 'special'),
                ),
                _message(
                    '상대는 속도 {Y.frame}인 빠른 {Y.pos} 공격 {Y}를 냅니다. {V}를 레디하세요.',
                    'Your opponent plays the fast {Y.pos} attack {Y} (speed {Y.frame}). Ready {V}.',
                    '相手は速い{Y.pos}攻撃{Y}（速度{Y.frame}）を出します。{V}をレディしてください。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't1-get',
            'allow': [('select_get_card', 'L1')],
            # Y에 사용 후 효과(랩 캐츠: 리스트 카드 1장을 루멘 존에)가 있으면 상대가 먼저 고른다.
            'opponent': [('submit_decision', 'P2_EXTRA_1', 'optional'), ('select_get_card', 'P2_EXTRA_2')],
            'messages': [
                _message(
                    '상쇄! 데미지 {V.damage}와 {Y.damage}의 차이 {V.damage-Y.damage}만큼만 상대 체력이 줄었습니다.',
                    'Clash! Your opponent lost only the difference between {V.damage} and {Y.damage}: {V.damage-Y.damage}.',
                    '相殺！ダメージ{V.damage}と{Y.damage}の差{V.damage-Y.damage}だけ相手の体力が減りました。',
                    {'kind': 'hud', 'hud': 'p2.hp'},
                ),
                _message(
                    '{L1}를 가져오세요.',
                    'Take {L1}.',
                    '{L1}を加えましょう。',
                    ACTION,
                ),
            ],
        },
        {
            'id': 't2-ready',
            'allow': [('ready_card', 'R')],
            'opponent': [('ready_card', 'E4')],
            'expect': {'battle': 'counter'},
            'messages': [
                _message(
                    '{R}의 특수 판정은 {R.special}입니다. 상대 공격이 그 위치면 피해서 데미지를 받지 않아요. 효과 글에 회피할 수 있는 속도 같은 조건이 붙기도 합니다.',
                    'The special judgment of {R} is {R.special}. An attack at that position is dodged and deals no damage. The effect text may add conditions, such as which speeds it can dodge.',
                    '{R}の特殊判定は{R.special}です。相手の攻撃がその位置なら避けてダメージを受けません。効果文に回避できる速度などの条件が付くこともあります。',
                    _anatomy('R', 'special'),
                ),
                _message(
                    '상대는 속도 {E4.frame}인 {E4.pos} 공격 {E4}를 냅니다. {R}가 더 느려도, 회피하면서 공격하면 카운터가 됩니다. {R}를 레디하세요.',
                    'Your opponent plays the {E4.pos} attack {E4} (speed {E4.frame}). Even though {R} is slower, dodging while attacking counts as a counter. Ready {R}.',
                    '相手は{E4.pos}攻撃{E4}（速度{E4.frame}）を出します。{R}のほうが遅くても、回避しながら攻撃すればカウンターになります。{R}をレディしてください。',
                    ACTION,
                ),
            ],
        },
    ],
    'completed': [
        _message(
            '배운 것: ① 특수 판정은 카드에 적힌 회피·상쇄·그랩 ② 회피: 그 위치의 공격을 피하고, 피하면서 공격하면 카운터 ③ 상쇄: 그 위치의 더 빠른 공격과 상쇄해 데미지 차이만 받는다 ④ 그랩: 맞을 때 손패의 그랩을 브레이크해 무효로 하고 레디를 다시 한다 ⑤ 브레이크한 카드는 다시 쓸 수 없고, 공격·수비 기술이면 사이드 덱에서 1장 보충한다.',
            'You learned: ① special judgments are Dodge, Clash and Grab printed on a card ② Dodge avoids an attack at that position; dodging while attacking is a counter ③ Clash meets a faster attack at that position and only the damage difference applies ④ Grab: break a Grab from your hand to negate it, then Ready again ⑤ a broken card cannot be used again; for an attack or defense card, refill one from your side deck.',
            '学んだこと：① 特殊判定はカードに書かれた回避・相殺・グラブ ② 回避：その位置の攻撃を避け、避けながら攻撃するとカウンター ③ 相殺：その位置のより速い攻撃と相殺し、ダメージの差だけ受ける ④ グラブ：受けるときに手札のグラブをブレイクして無効にし、レディをやり直す ⑤ ブレイクしたカードは二度と使えず、攻撃・守備技ならサイドデッキから1枚補充する。',
        ),
    ],
}


LESSONS = {lesson['id']: lesson for lesson in (BASIC_1, BASIC_2, BASIC_3, BASIC_4, BASIC_5, BASIC_6)}

FAILED_MESSAGE = _message(
    '튜토리얼을 이어 갈 수 없습니다. 카드 규칙이 바뀌어 각본과 다른 결과가 나왔습니다. 운영진에게 알렸습니다.',
    'The tutorial cannot continue: card rules changed and the result differs from the script. The team has been notified.',
    'チュートリアルを続行できません。カードのルールが変わり、台本と異なる結果になりました。運営に通知しました。',
)


def get_lesson(lesson_id):
    return LESSONS.get(str(lesson_id or ''))


def next_lesson_id(lesson_id):
    """목록에서 다음 단원(마지막이면 None)."""
    ids = list(LESSONS)
    try:
        index = ids.index(str(lesson_id or ''))
    except ValueError:
        return None
    return ids[index + 1] if index + 1 < len(ids) else None


def lesson_setup(lesson):
    configured = (getattr(settings, 'LUMEN_TUTORIAL_SETUP', None) or {}).get(lesson['id'])
    return configured or lesson.get('setup')
