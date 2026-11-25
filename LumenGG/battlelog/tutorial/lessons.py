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

단원 설정

- ``board``: 시작 손패·리스트(역할 이름). ``hp``: 시작 체력(``{'p1': 4200}``),
  ``priority``: 시작 우선권(기본 p1), ``p2_hp_from_damage``: 상대 체력을 이 카드들의 데미지 합으로.
- ``finish``: ``'win'``(기본, 마지막 단계에서 p1이 이겨야 완료) 또는 ``'concede'``
  (마지막 단계를 마치면 완료하고 각본 상대가 기권해 게임을 끝낸다. 짧은 단원용).

문구 자리 표시자

- 카드: ``{A}`` 카드명, ``{A.frame}`` 속도, ``{A.damage}`` 데미지, ``{A.pos}`` 위치, ``{A.body}`` 손/발,
  ``{A.fp_hit}``·``{A.fp_guard}``·``{A.fp_counter}`` 판정 결과 FP(+1처럼 부호를 붙인다),
  ``{D.guard}`` 수비 카드가 방어하는 위치, ``{D.defense}`` 위치별 수비 판정 전체.
- 계산: ``{B.frame-p1.fp}``(두 값의 차. 앞은 카드, 뒤는 카드나 현재 상태).
- 현재 상태: ``{p1.hp}``, ``{p1.fp}``, ``{p1.hand}`` 손패 장수, ``{p1.limit}`` 손패 상한(p2도 같다).

``focus``: ``{'kind': 'action'}`` 허용 행동, ``{'kind': 'card', 'card': 'A'}``,
``{'kind': 'zone', 'zone': 'p1.hand'}``, ``{'kind': 'hud', 'hud': 'p2.hp'}``
(``p1.fp``, ``priority``, ``p1.hand-count``, ``phase`` 포함),
``{'kind': 'anatomy', 'card': 'A', 'part': 'speed'}`` 카드를 크게 띄우고 한 부분을 비춘다
(``ANATOMY_PARTS``).
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
ANATOMY_PARTS = ('name', 'speed', 'pos', 'damage', 'fp', 'text', 'guard')


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


BASIC_2 = {
    'id': 'basic-2',
    'version': 1,
    'title': _text('카드 읽는 법', 'Reading a card', 'カードの読み方'),
    'summary': _text(
        '속도·위치·데미지·FP·수비 판정이 카드 어디에 있는지 봅니다.',
        'Find speed, position, damage, FP and defense marks on a card.',
        '速度・位置・ダメージ・FP・守備判定がカードのどこにあるかを見ます。',
    ),
    'setup': None,
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
                    '맨 위 가운데는 기술 이름, 그 아래는 손/발 판정입니다. {A}는 {A.body} 기술이에요.',
                    'The top centre shows the technique name, and below it whether it is a Hand or Foot technique. {A} is a {A.body} technique.',
                    '上の中央は技の名前、その下は手/足の判定です。{A}は{A.body}の技です。',
                    _anatomy('A', 'name'),
                ),
                _message(
                    '왼쪽 위 숫자는 속도입니다. 숫자가 작을수록 빠릅니다. {A}의 속도는 {A.frame}.',
                    'The number at the top left is the speed. The lower the number, the faster. {A} has speed {A.frame}.',
                    '左上の数字は速度です。数字が小さいほど速くなります。{A}の速度は{A.frame}です。',
                    _anatomy('A', 'speed'),
                ),
                _message(
                    '오른쪽 위 마크는 공격 위치입니다. 상단·중단·하단 중 하나로, {A}는 {A.pos} 공격이에요.',
                    'The mark at the top right is the attack position: High, Mid or Low. {A} attacks {A.pos}.',
                    '右上のマークは攻撃位置です。上段・中段・下段のいずれかで、{A}は{A.pos}攻撃です。',
                    _anatomy('A', 'pos'),
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
                    '가운데 글은 카드 효과입니다. 대전 중 카드를 누르면(PC는 오른쪽 클릭도) 크게 보고 효과 설명을 읽을 수 있어요.',
                    'The text in the middle is the card\'s effect. During a match, tap a card (or right-click on PC) to see it large with the effect explained.',
                    '中央の文章はカードの効果です。対戦中にカードを押すと（PCは右クリックも）大きく表示して効果の説明を読めます。',
                    _anatomy('A', 'text'),
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
            '배운 것: ① 왼쪽 위 속도, 오른쪽 위 위치, 아래 데미지 ② 왼쪽 아이콘은 공격이면 결과별 FP, 수비면 위치별 수비 판정 ③ 카드를 누르면 크게 볼 수 있다.',
            'You learned: ① speed top left, position top right, damage at the bottom ② the left icons are FP per result on attacks, and defense marks per position on defenses ③ tap a card to see it large.',
            '学んだこと：① 左上は速度、右上は位置、下はダメージ ② 左のアイコンは攻撃なら結果ごとのFP、守備なら位置ごとの守備判定 ③ カードを押すと大きく見られる。',
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
    'setup': None,
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
    'setup': None,
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


LESSONS = {lesson['id']: lesson for lesson in (BASIC_1, BASIC_2, BASIC_3, BASIC_4)}

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
