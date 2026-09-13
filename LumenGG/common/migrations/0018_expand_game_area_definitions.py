from datetime import date

from django.db import migrations


LANGUAGES = ('ko', 'en', 'ja')

AREA_ROOT_CONTENT = {
    'ko': '''<p>카드가 놓이는 장소를 <strong>존</strong>이라 합니다. 존에 따라 용도, 허용되는 카드, 앞·뒷면, 공개 범위, 매수 제한과 이동 결과가 달라집니다. <strong>FP 영역</strong>은 카드를 놓는 존이 아니라 수치를 표시하는 게임 영역입니다.</p>
<h2>영역 속성 요약</h2>
<table><thead><tr><th>영역</th><th>용도·허용 카드</th><th>기본 상태</th><th>내용 공개</th><th>매수·순서</th></tr></thead><tbody>
<tr><td>캐릭터 존</td><td>플레이어를 대변하는 캐릭터 카드</td><td>앞면</td><td>공개</td><td>준비 시 1장·순서 없음</td></tr>
<tr><td>특성 존</td><td>캐릭터의 고유 효과를 가진 특성 카드</td><td>앞면</td><td>공개</td><td>준비 시 1장·순서 없음</td></tr>
<tr><td>패</td><td>레디하거나 효과로 사용할 수 있는 기술 카드</td><td>비공개</td><td>소유자만 확인, 초기 패만 상호 확인</td><td>현재 체력 구간의 패 매수 상한·순서 없음</td></tr>
<tr><td>리스트</td><td>레디 페이즈에 사용하지 않는 공개 기술</td><td>준비 완료 전 뒷면, 게임 시작 후 앞면</td><td>게임 시작 후 공개</td><td>최대 14장·순서 없음</td></tr>
<tr><td>사이드 덱</td><td>초기 패·리스트에 넣지 않은 기술 및 특수 기술</td><td>뒷면</td><td>매수만 공개, 내용·순서는 상대에게 비공개</td><td>소유자가 순서를 정하고 확인 가능</td></tr>
<tr><td>배틀 존</td><td>패에서 레디한 기술</td><td>레디 중 뒷면, 배틀 공개 후 앞면</td><td>뒷면은 상대에게 비공개, 공개 후 공개</td><td>각 플레이어의 레디 카드 1장</td></tr>
<tr><td>루멘 존</td><td>카드 효과로 배치된 카드</td><td>효과가 정함, 명시가 없으면 검토 초안상 앞면</td><td>효과가 정함, 명시가 없으면 검토 초안상 공개</td><td>고정 상한 없음·효과에 따름</td></tr>
<tr><td>얼티밋 존</td><td>채용한 얼티밋 기술</td><td>앞면이 기본, 효과로 뒷면 가능</td><td>앞면인 동안 공개</td><td>준비 시 0~1장</td></tr>
<tr><td>브레이크 존</td><td>브레이크된 카드</td><td>앞면</td><td>공개</td><td>고정 상한 없음·순서 없음</td></tr>
<tr><td>FP 영역</td><td>각 플레이어의 현재 FP 수치</td><td>공개 수치</td><td>공개</td><td>카드 매수·순서 없음</td></tr>
</tbody></table>
<blockquote><p><span class="v2-rulebook-badge">WARNING</span> 루멘 존에 카드를 놓게 한 효과가 표시 상태나 공개 범위를 정하지 않은 경우의 기본값은 아직 정식 확정이 필요합니다. 이 문서에서는 그 경우를 앞면·공개로 처리하는 검토 초안을 사용합니다.</p></blockquote>''',
    'en': '''<p>An area where cards are placed is called a <strong>zone</strong>. A zone determines its purpose, permitted cards, face-up or face-down state, visibility, capacity, and the result of moving a card into it. The <strong>FP Area</strong> is a game area used to display values, not a zone that holds cards.</p>
<h2>Area Attribute Summary</h2>
<table><thead><tr><th>Area</th><th>Purpose and permitted cards</th><th>Default state</th><th>Visibility</th><th>Capacity and order</th></tr></thead><tbody>
<tr><td>Character Zone</td><td>Character Card representing the player</td><td>Face up</td><td>Public</td><td>1 at setup; no order</td></tr>
<tr><td>Trait Zone</td><td>Trait Card containing the character's unique effects</td><td>Face up</td><td>Public</td><td>1 at setup; no order</td></tr>
<tr><td>Hand</td><td>Technique Cards available to Ready or use through effects</td><td>Hidden</td><td>Owner only; initial hand is mutually checked</td><td>Current HP bracket's hand limit; no order</td></tr>
<tr><td>List</td><td>Public Techniques not being used during the Ready Phase</td><td>Face down before setup completes; face up after the game begins</td><td>Public after the game begins</td><td>Maximum 14; no order</td></tr>
<tr><td>Side Deck</td><td>Techniques and Special Techniques not placed in the initial hand or List</td><td>Face down</td><td>Count is public; contents and order are hidden from the opponent</td><td>Owner may set and inspect the order</td></tr>
<tr><td>Battle Zone</td><td>Technique readied from the hand</td><td>Face down while Ready; face up after reveal</td><td>Hidden from the opponent while face down; public after reveal</td><td>1 Ready card per player</td></tr>
<tr><td>Lumen Zone</td><td>Cards placed there by a card effect</td><td>As specified by the effect; draft default is face up</td><td>As specified by the effect; draft default is public</td><td>No fixed maximum; follows the effect</td></tr>
<tr><td>Ultimate Zone</td><td>The selected Ultimate Technique</td><td>Face up by default; may be face down by an effect</td><td>Public while face up</td><td>0–1 at setup</td></tr>
<tr><td>Break Zone</td><td>Broken cards</td><td>Face up</td><td>Public</td><td>No fixed maximum; no order</td></tr>
<tr><td>FP Area</td><td>Each player's current FP value</td><td>Public value</td><td>Public</td><td>No card capacity or order</td></tr>
</tbody></table>
<blockquote><p><span class="v2-rulebook-badge">WARNING</span> The default state and visibility of a card placed in the Lumen Zone remain to be officially confirmed when the placing effect does not specify them. This review draft treats such a card as face up and public.</p></blockquote>''',
    'ja': '''<p>カードを置く場所を<strong>ゾーン</strong>といいます。ゾーンごとに用途、置くことができるカード、表裏、公開範囲、枚数上限、移動結果が異なります。<strong>FP領域</strong>はカードを置くゾーンではなく、数値を表示するゲーム領域です。</p>
<h2>領域属性の要約</h2>
<table><thead><tr><th>領域</th><th>用途・置くことができるカード</th><th>基本状態</th><th>公開範囲</th><th>枚数・順序</th></tr></thead><tbody>
<tr><td>キャラクターゾーン</td><td>プレイヤーを表すキャラクターカード</td><td>表向き</td><td>公開</td><td>準備時1枚・順序なし</td></tr>
<tr><td>特性ゾーン</td><td>キャラクター固有の効果を持つ特性カード</td><td>表向き</td><td>公開</td><td>準備時1枚・順序なし</td></tr>
<tr><td>手札</td><td>レディまたは効果で使用できる技カード</td><td>非公開</td><td>所有者のみ確認、初期手札のみ相互確認</td><td>現在の体力区分の手札枚数上限・順序なし</td></tr>
<tr><td>リスト</td><td>レディフェイズに使用していない公開技</td><td>準備完了前は裏向き、ゲーム開始後は表向き</td><td>ゲーム開始後は公開</td><td>最大14枚・順序なし</td></tr>
<tr><td>サイドデッキ</td><td>初期手札・リストに入れなかった技および特殊技</td><td>裏向き</td><td>枚数のみ公開、内容・順序は相手に非公開</td><td>所有者が順序を決めて確認可能</td></tr>
<tr><td>バトルゾーン</td><td>手札からレディした技</td><td>レディ中は裏向き、公開後は表向き</td><td>裏向きの間は相手に非公開、公開後は公開</td><td>各プレイヤーのレディカード1枚</td></tr>
<tr><td>ルーメンゾーン</td><td>カード効果で配置されたカード</td><td>効果が指定、指定がなければレビュードラフト上は表向き</td><td>効果が指定、指定がなければレビュードラフト上は公開</td><td>固定上限なし・効果に従う</td></tr>
<tr><td>アルティメットゾーン</td><td>採用したアルティメット技</td><td>表向きが基本、効果で裏向きになり得る</td><td>表向きの間は公開</td><td>準備時0～1枚</td></tr>
<tr><td>ブレイクゾーン</td><td>ブレイクされたカード</td><td>表向き</td><td>公開</td><td>固定上限なし・順序なし</td></tr>
<tr><td>FP領域</td><td>各プレイヤーの現在のFP値</td><td>公開数値</td><td>公開</td><td>カードの枚数・順序なし</td></tr>
</tbody></table>
<blockquote><p><span class="v2-rulebook-badge">WARNING</span> ルーメンゾーンにカードを置く効果が表示状態や公開範囲を指定していない場合の基本値は、まだ正式な確認が必要です。本レビュードラフトでは、そのカードを表向き・公開として扱います。</p></blockquote>''',
}


CLAUSES = {
    'common': {
        'titles': {'ko': '영역과 플레이어의 연결', 'en': 'Areas Connected to Players', 'ja': '領域とプレイヤーの対応'},
        'contents': {
            'ko': '캐릭터 존, 특성 존, 패, 리스트, 사이드 덱, 배틀 존, 루멘 존, 얼티밋 존과 브레이크 존은 각 플레이어와 하나씩 연결되어 있으므로 게임 중 각 종류가 2곳 존재한다. 각 플레이어에게 연결된 영역을 그 플레이어의 영역이라 한다. 카드 효과나 규칙이 별도로 정하지 않으면, 카드는 이동하려는 존의 허용 카드, 표시 상태, 공개 범위와 매수 제한을 따른다.',
            'en': "Each player has one connected Character Zone, Trait Zone, Hand, List, Side Deck, Battle Zone, Lumen Zone, Ultimate Zone, and Break Zone, so two of each kind exist during a game. An area connected to a player is that player's area. Unless a card effect or rule says otherwise, a card moving to a zone follows that zone's permitted-card, display-state, visibility, and capacity rules.",
            'ja': 'キャラクターゾーン、特性ゾーン、手札、リスト、サイドデッキ、バトルゾーン、ルーメンゾーン、アルティメットゾーン、ブレイクゾーンは、各プレイヤーに1つずつ対応しているため、ゲーム中は各種類につき2か所存在する。プレイヤーに対応する領域を、そのプレイヤーの領域という。カード効果やルールに別の指定がない限り、移動するカードは移動先ゾーンのカード種別、表示状態、公開範囲、枚数上限に関する規則に従う。',
        },
    },
    'character': {
        'titles': {'ko': '캐릭터 존', 'en': 'Character Zone', 'ja': 'キャラクターゾーン'},
        'contents': {
            'ko': '캐릭터 존은 플레이어를 대변하고 잔존 체력을 표시하는 캐릭터 카드를 두는 곳이다. 캐릭터 존은 각 플레이어에게 하나씩 연결되어 있으며, 각 플레이어는 게임 준비 시 자신의 캐릭터 카드 1장을 앞면으로 놓는다. 캐릭터 카드의 정보와 현재 체력 표시는 공개 정보이며 모든 플레이어가 확인할 수 있다. 일반적인 덱에는 캐릭터 카드가 1장만 들어가므로, 카드 효과나 규칙이 달리 정하지 않는 한 캐릭터 존에는 그 카드 1장만 놓인다.',
            'en': "The Character Zone holds the Character Card that represents the player and displays their remaining HP. Each player has one connected Character Zone and places their one Character Card there face up during setup. The card's information and current HP display are public information that every player may inspect. A normal deck contains only one Character Card, so that one card remains in the Character Zone unless a card effect or rule says otherwise.",
            'ja': 'キャラクターゾーンは、プレイヤーを表し、残り体力を表示するキャラクターカードを置く場所である。各プレイヤーにはキャラクターゾーンが1つ対応し、ゲーム準備時に自分のキャラクターカード1枚を表向きで置く。キャラクターカードの情報と現在の体力表示は公開情報であり、すべてのプレイヤーが確認できる。通常のデッキにはキャラクターカードが1枚だけ含まれるため、カード効果やルールに別の指定がない限り、その1枚だけがキャラクターゾーンに置かれる。',
        },
    },
    'trait': {
        'titles': {'ko': '특성 존', 'en': 'Trait Zone', 'ja': '特性ゾーン'},
        'contents': {
            'ko': '특성 존은 캐릭터의 고유 기능과 효과를 가진 특성 카드를 두는 곳이다. 특성 존은 각 플레이어에게 하나씩 연결되어 있으며, 각 플레이어는 게임 준비 시 자신의 특성 카드 1장을 캐릭터 카드 옆에 앞면으로 놓는다. 특성 카드의 정보는 공개되어 모든 플레이어가 확인할 수 있고, 그 기능과 효과는 게임 시작 직후부터 적용된다. 카드 효과나 규칙이 달리 정하지 않는 한 특성 존에는 그 카드 1장만 놓이며 카드의 순서는 의미가 없다.',
            'en': "The Trait Zone holds the Trait Card containing a character's unique functions and effects. Each player has one connected Trait Zone and places their one Trait Card face up beside their Character Card during setup. Its information is public to every player, and its functions and effects apply immediately after the game begins. Unless a card effect or rule says otherwise, that one card is the only card in the Trait Zone and card order has no rules meaning.",
            'ja': '特性ゾーンは、キャラクター固有の機能と効果を持つ特性カードを置く場所である。各プレイヤーには特性ゾーンが1つ対応し、ゲーム準備時に自分の特性カード1枚をキャラクターカードの隣へ表向きで置く。特性カードの情報は公開され、すべてのプレイヤーが確認でき、その機能と効果はゲーム開始直後から適用される。カード効果やルールに別の指定がない限り、その1枚だけが特性ゾーンに置かれ、カードの順序にルール上の意味はない。',
        },
    },
    'hand': {
        'titles': {'ko': '패', 'en': 'Hand', 'ja': '手札'},
        'contents': {
            'ko': '패는 플레이어가 레디하거나 카드 효과로 사용할 수 있는 기술 카드를 보유하는 비공개 존이다. 패는 각 플레이어에게 하나씩 연결되어 있으며, 공격·수비 기술과 패에 넣을 수 있는 얼티밋 공격·수비 기술을 둘 수 있지만 특수 기술은 둘 수 없다. 소유자는 자신의 패 내용 전체를 확인할 수 있고 카드 순서는 규칙상 의미가 없지만, 상대는 게임 중 그 내용을 확인할 수 없다. 다만 게임 준비 시 초기 패를 서로 확인한 뒤 소유자에게 돌려주며, 게임 시작 후에는 다시 비공개로 취급한다. 패의 매수는 공개 정보이고 최대 매수는 캐릭터 카드의 현재 체력 구간에 표시된 [[rule-3-2-2|패 매수 상한]]을 따르며, 하나의 처리 단위가 끝난 뒤 상한을 넘으면 [[rule-3-2-3|초과분을 즉시 버린다]].',
            'en': 'The Hand is a hidden zone holding Technique Cards that a player may Ready or use through card effects. Each player has one Hand. It may contain Attack and Defense Techniques and Ultimate Attack or Defense Techniques that are permitted to enter the Hand, but it cannot contain Special Techniques. The owner may inspect their entire Hand and card order has no rules meaning, while the opponent may not inspect its contents during the game. As an exception, players mutually check their initial hands during setup, return them to their owners, and treat them as hidden again once the game begins. Hand size is public information; its maximum is the [[rule-3-2-2|hand limit]] shown for the Character Card\'s current HP bracket, and any excess is [[rule-3-2-3|discarded immediately]] after a processing unit ends.',
            'ja': '手札は、プレイヤーがレディまたはカード効果で使用できる技カードを保持する非公開ゾーンである。各プレイヤーには手札が1つ対応する。攻撃・防御技および手札に入れることができるアルティメット攻撃・防御技を置けるが、特殊技を置くことはできない。所有者は自分の手札の内容をすべて確認でき、カードの順序にルール上の意味はないが、相手はゲーム中にその内容を確認できない。ただし、ゲーム準備時には初期手札を互いに確認して所有者へ戻し、ゲーム開始後は再び非公開として扱う。手札枚数は公開情報であり、最大枚数はキャラクターカードの現在の体力区分に示された[[rule-3-2-2|手札枚数上限]]に従い、1つの処理単位が終わった後に上限を超えていれば[[rule-3-2-3|超過分を直ちに捨てる]]。',
        },
    },
    'list': {
        'titles': {'ko': '리스트', 'en': 'List', 'ja': 'リスト'},
        'contents': {
            'ko': '리스트는 각 플레이어가 레디 페이즈에 사용하지 않는 공개된 기술을 모아 두는 존이다. 리스트는 각 플레이어에게 하나씩 연결되어 있으므로 게임 중 2곳 존재한다. 리스트의 최대 매수는 14장이며, 리스트의 카드 매수는 이 상한을 넘을 수 없다. 리스트가 14장인 상태에서 카드가 리스트로 이동하려 하면 그 카드는 리스트로 이동하는 대신 [[rule-10-2-1|브레이크]]된다. 초기 리스트는 게임 준비가 끝날 때까지 뒷면 비공개 상태로 두고 양쪽 플레이어가 준비를 마친 뒤 동시에 앞면으로 공개하며, 게임 시작 후에는 앞면 공개 상태를 유지한다. 리스트의 앞면 카드 정보와 카드 매수는 모든 플레이어가 확인할 수 있고, 카드의 순서는 규칙상 의미가 없다.',
            'en': 'The List is a zone that holds each player\'s public Techniques that are not being used during the Ready Phase. Each player has one connected List, so two Lists exist during a game. A List has a maximum capacity of 14 cards and may never contain more than that number. If a card would move to a List that already contains 14 cards, it is [[rule-10-2-1|Broken]] instead of moving to the List. The initial List remains face down and hidden until setup is complete, is revealed simultaneously after both players are ready, and remains face up after the game begins. Every player may inspect the information and count of face-up cards in a List, and card order has no rules meaning.',
            'ja': 'リストは、各プレイヤーがレディフェイズに使用していない公開された技をまとめて置くゾーンである。各プレイヤーにはリストが1つ対応するため、ゲーム中は2か所存在する。リストの最大枚数は14枚であり、この上限を超えることはできない。リストに14枚ある状態でカードがリストへ移動しようとする場合、そのカードはリストへ移動する代わりに[[rule-10-2-1|ブレイク]]される。初期リストはゲーム準備が終わるまで裏向き・非公開で置き、両プレイヤーの準備が終わった後に同時に表向きで公開し、ゲーム開始後は表向き・公開の状態を維持する。リストの表向きカードの情報と枚数はすべてのプレイヤーが確認でき、カードの順序にルール上の意味はない。',
        },
    },
    'side': {
        'titles': {'ko': '사이드 덱', 'en': 'Side Deck', 'ja': 'サイドデッキ'},
        'contents': {
            'ko': '사이드 덱은 초기 패와 초기 리스트에 넣지 않은 기술 카드와 특수 기술 카드를 두는 뒷면 존이다. 사이드 덱은 각 플레이어에게 하나씩 연결되어 있으므로 게임 중 2곳 존재한다. 일반적인 20장 기술 카드 구성에서는 초기 패 5장과 초기 리스트 9장을 제외한 6장으로 게임을 시작하지만, 덱 구성이나 준비를 바꾸는 효과가 있으면 그 효과를 따른다. 사이드 덱의 카드 매수는 공개 정보지만 내용과 순서는 상대에게 비공개이며, 소유자는 게임 시작 전에 순서를 정하고 게임 중 자신의 사이드 덱 내용과 순서를 확인할 수 있다. 게임 중 고정된 최대 매수는 없으며 카드 효과와 존 이동에 따라 매수가 바뀔 수 있다.',
            'en': 'The Side Deck is a face-down zone holding Technique Cards and Special Technique Cards not placed in the initial hand or initial List. Each player has one connected Side Deck, so two Side Decks exist during a game. With the normal twenty-Technique deck composition, it begins with six cards after removing the five-card initial hand and nine-card initial List; an effect that changes deck construction or setup takes precedence. Its card count is public information, but its contents and order are hidden from the opponent. The owner may set the order before the game and inspect the contents and order of their Side Deck during the game. It has no fixed maximum during play, and its count may change through card effects and zone movement.',
            'ja': 'サイドデッキは、初期手札と初期リストに入れなかった技カードおよび特殊技カードを置く裏向きのゾーンである。各プレイヤーにはサイドデッキが1つ対応するため、ゲーム中は2か所存在する。通常の技カード20枚構成では、初期手札5枚と初期リスト9枚を除いた6枚でゲームを開始するが、デッキ構築や準備を変更する効果がある場合はその効果に従う。サイドデッキの枚数は公開情報だが、内容と順序は相手に非公開である。所有者はゲーム開始前に順序を決め、ゲーム中に自分のサイドデッキの内容と順序を確認できる。ゲーム中の固定された最大枚数はなく、カード効果やゾーン移動によって枚数が変化し得る。',
        },
    },
    'battle': {
        'titles': {'ko': '배틀 존', 'en': 'Battle Zone', 'ja': 'バトルゾーン'},
        'contents': {
            'ko': '배틀 존은 레디 페이즈에 패에서 선택한 기술 카드 1장을 놓고 레디를 선언하는 존이다. 배틀 존은 각 플레이어에게 하나씩 연결되어 있으므로 게임 중 2곳 존재하며, 각 플레이어의 일반적인 레디 카드 수용량은 1장이다. 레디한 카드는 배틀 페이즈가 시작될 때까지 뒷면으로 두므로 상대는 그 내용을 확인할 수 없고, 레디 선언 후에는 카드를 바꾸거나 선언을 취소할 수 없다. 배틀 페이즈에는 양쪽 레디 카드를 동시에 앞면으로 공개하며, 공개된 카드의 정보는 모든 플레이어가 확인할 수 있다. 배틀 종료 시 레디 카드는 기본적으로 패로 돌아가지만 콤보, 캐치, 브레이크 등 별도 이동 규칙이 있으면 그 규칙을 따른다.',
            'en': 'The Battle Zone is where a player places one Technique Card chosen from their Hand and declares it Ready during the Ready Phase. Each player has one connected Battle Zone, so two Battle Zones exist during a game, and the normal capacity is one Ready card per player. A Ready card remains face down until the Battle Phase begins, so the opponent may not inspect its contents, and the player may not change the card or cancel the declaration after declaring Ready. Both Ready cards are revealed face up simultaneously during the Battle Phase, after which every player may inspect their information. At the end of the battle, a Ready card normally returns to the Hand, but separate movement rules for Combos, Catches, Break, and similar cases take precedence.',
            'ja': 'バトルゾーンは、レディフェイズに手札から選んだ技カード1枚を置いてレディを宣言するゾーンである。各プレイヤーにはバトルゾーンが1つ対応するため、ゲーム中は2か所存在し、通常のレディカードの収容枚数は各プレイヤー1枚である。レディしたカードはバトルフェイズ開始まで裏向きで置くため、相手はその内容を確認できず、レディ宣言後はカードを変更したり宣言を取り消したりできない。バトルフェイズには両方のレディカードを同時に表向きで公開し、公開後はすべてのプレイヤーがその情報を確認できる。バトル終了時、レディカードは通常手札に戻るが、コンボ、キャッチ、ブレイクなど別の移動規則がある場合はその規則に従う。',
        },
    },
    'lumen': {
        'titles': {'ko': '루멘 존', 'en': 'Lumen Zone', 'ja': 'ルーメンゾーン'},
        'contents': {
            'ko': '루멘 존은 카드 효과가 “루멘 존에 배치한다”고 지정한 카드를 두는 존이다. 루멘 존은 각 플레이어에게 하나씩 연결되어 있으므로 게임 중 2곳 존재하며, 주로 사용 절차를 마친 특수 기술이 놓이지만 실제로 놓을 수 있는 카드와 이동 시점은 해당 효과를 따른다. 카드의 체류 기간, 이동 방법, 매수와 순서는 그 카드를 배치한 효과가 정하며 고정된 최대 매수는 없다. 효과가 앞·뒷면이나 공개 범위를 정하면 그 지시를 따르고, 명시가 없으면 이 검토 초안에서는 앞면 공개 상태로 놓아 모든 플레이어가 정보를 확인할 수 있는 것으로 처리한다. <span class="v2-rulebook-badge">확인 필요</span>',
            'en': 'The Lumen Zone holds a card that a card effect instructs a player to “place in the Lumen Zone.” Each player has one connected Lumen Zone, so two Lumen Zones exist during a game. It mainly holds Special Techniques after their use procedure, but the placing effect determines which cards may enter it and when they move. That effect also determines the card\'s duration, movement, count, and order, and the zone has no fixed maximum. If an effect specifies the face-up or face-down state or visibility, follow that instruction; if it does not, this review draft treats the card as face up and public to every player. <span class="v2-rulebook-badge">Confirmation required</span>',
            'ja': 'ルーメンゾーンは、カード効果が「ルーメンゾーンに配置する」と指定したカードを置くゾーンである。各プレイヤーにはルーメンゾーンが1つ対応するため、ゲーム中は2か所存在する。主に使用手順を終えた特殊技が置かれるが、実際に置くことができるカードと移動時点はその効果に従う。カードの滞在期間、移動方法、枚数、順序はそのカードを配置した効果が定め、固定された最大枚数はない。効果が表裏や公開範囲を指定する場合はその指示に従い、指定がない場合、本レビュードラフトでは表向き・公開で置き、すべてのプレイヤーが情報を確認できるものとして扱う。<span class="v2-rulebook-badge">確認が必要</span>',
        },
    },
    'ultimate': {
        'titles': {'ko': '얼티밋 존', 'en': 'Ultimate Zone', 'ja': 'アルティメットゾーン'},
        'contents': {
            'ko': '얼티밋 존은 덱에 채용한 얼티밋 기술 카드를 두는 존이다. 얼티밋 존은 각 플레이어에게 하나씩 연결되어 있으므로 게임 중 2곳 존재하지만, 얼티밋 기술을 채용하지 않은 플레이어의 얼티밋 존은 비어 있다. 플레이어는 게임 준비 시 채용한 얼티밋 기술 0장 또는 1장을 앞면으로 놓고, 앞면인 동안 그 카드 정보는 모든 플레이어가 확인할 수 있다. 카드 효과가 명시하면 뒷면이 될 수 있으며 그때의 공개 범위는 해당 효과를 따른다. 얼티밋 공격·수비 기술이 이 존을 떠난 뒤에는 일반 기술과 같은 이동 규칙을 적용하고 얼티밋 존으로 자동 복귀하지 않으며, 얼티밋 특수 기술은 패에 넣을 수 없다.',
            'en': 'The Ultimate Zone holds the Ultimate Technique selected for the deck. Each player has one connected Ultimate Zone, so two Ultimate Zones exist during a game, but the zone is empty for a player who did not include an Ultimate Technique. During setup, a player places zero or one selected Ultimate Technique face up, and every player may inspect its information while it is face up. A card effect may turn it face down, in which case that effect determines its visibility. After an Ultimate Attack or Defense Technique leaves this zone, it follows the same movement rules as a normal Technique and does not automatically return; an Ultimate Special Technique cannot enter the Hand.',
            'ja': 'アルティメットゾーンは、デッキに採用したアルティメット技カードを置くゾーンである。各プレイヤーにはアルティメットゾーンが1つ対応するため、ゲーム中は2か所存在するが、アルティメット技を採用していないプレイヤーのゾーンは空になる。ゲーム準備時に採用したアルティメット技0枚または1枚を表向きで置き、表向きの間はすべてのプレイヤーがそのカード情報を確認できる。カード効果が指定した場合は裏向きになり、そのときの公開範囲は該当する効果に従う。アルティメット攻撃・防御技がこのゾーンを離れた後は通常の技と同じ移動規則を適用し、アルティメットゾーンへ自動的には戻らない。アルティメット特殊技は手札に入れることができない。',
        },
    },
    'break': {
        'titles': {'ko': '브레이크 존', 'en': 'Break Zone', 'ja': 'ブレイクゾーン'},
        'contents': {
            'ko': '브레이크 존은 규칙이나 카드 효과로 브레이크된 카드를 두는 공개 존이다. 브레이크 존은 각 플레이어에게 하나씩 연결되어 있으므로 게임 중 2곳 존재한다. 브레이크된 카드는 앞면으로 놓고 그 정보와 매수는 모든 플레이어가 확인할 수 있으며, 카드의 순서는 규칙상 의미가 없고 고정된 최대 매수도 없다. 브레이크 존의 카드는 일반적으로 그 게임에서 다시 사용할 수 없지만, 카드 효과나 규칙이 별도 이동을 지시하면 그 지시를 따른다. 패·리스트·루멘 존·배틀 존에서 공격 또는 수비 기술이 브레이크되면 [[rule-10-2-1|브레이크 보충 규칙]]을 적용하고, 특수 기술에는 그 보충을 적용하지 않는다.',
            'en': 'The Break Zone is a public zone holding cards Broken by a rule or card effect. Each player has one connected Break Zone, so two Break Zones exist during a game. Broken cards are placed face up; every player may inspect their information and count; card order has no rules meaning; and the zone has no fixed maximum. A card in the Break Zone generally cannot be used again during that game, but a card effect or rule that instructs another movement takes precedence. When an Attack or Defense Technique is Broken from a Hand, List, Lumen Zone, or Battle Zone, apply the [[rule-10-2-1|Break replenishment rule]]; Special Techniques do not receive that replenishment.',
            'ja': 'ブレイクゾーンは、ルールまたはカード効果によってブレイクされたカードを置く公開ゾーンである。各プレイヤーにはブレイクゾーンが1つ対応するため、ゲーム中は2か所存在する。ブレイクされたカードは表向きで置き、その情報と枚数はすべてのプレイヤーが確認できる。カードの順序にルール上の意味はなく、固定された最大枚数もない。ブレイクゾーンのカードは通常そのゲーム中に再使用できないが、カード効果やルールが別の移動を指示する場合はその指示に従う。手札・リスト・ルーメンゾーン・バトルゾーンから攻撃または防御技がブレイクされた場合は[[rule-10-2-1|ブレイク補充規則]]を適用し、特殊技にはその補充を適用しない。',
        },
    },
    'fp': {
        'titles': {'ko': 'FP 영역', 'en': 'FP Area', 'ja': 'FP領域'},
        'contents': {
            'ko': 'FP 영역은 카드를 두는 존이 아니라 각 플레이어의 현재 FP 수치를 구분하여 표시하는 게임 영역이다. 각 플레이어는 서로 독립된 FP 수치 하나를 가지며, 양쪽 FP는 모두 공개 정보로서 모든 플레이어가 확인할 수 있다. FP는 양수, 0 또는 음수가 될 수 있고 정해진 상한과 하한은 없으며, 카드 매수나 카드 순서에 관한 규칙은 적용하지 않는다. FP는 우선권 결정과 공격 속도 계산 등에 사용하며, 배틀에서는 양쪽이 보유한 FP 전부를 적용한 뒤 0으로 만든다.',
            'en': "The FP Area is not a card-holding zone; it is a game area that separately displays each player's current FP value. Each player has one independent FP value, and both values are public information that every player may inspect. FP may be positive, zero, or negative and has no defined upper or lower limit; card-capacity and card-order rules do not apply. FP is used for matters such as determining Priority and calculating attack Speed, and during battle each player applies all FP they hold and then resets it to zero.",
            'ja': 'FP領域はカードを置くゾーンではなく、各プレイヤーの現在のFP値を区別して表示するゲーム領域である。各プレイヤーは互いに独立したFP値を1つ持ち、両方のFPはすべてのプレイヤーが確認できる公開情報である。FPは正数、0、または負数になり得る。定められた上限と下限はなく、カードの枚数や順序に関する規則は適用しない。FPは優先権の決定や攻撃速度の計算などに使用し、バトルでは両プレイヤーが保有するFPをすべて適用した後に0にする。',
        },
    },
}


PUBLIC_CONTENT = {
    'ko': '각 존의 카드 매수와 양쪽 플레이어의 현재 체력·FP는 우선권 비교와 합법성 확인에 필요한 공개 정보다. 공개 존의 앞면 카드에 적힌 정보는 모든 플레이어가 확인할 수 있다. 패와 뒷면 카드처럼 비공개로 정한 정보는 소유자 또는 해당 존의 규정이 허용한 플레이어만 확인할 수 있으며, 게임 준비 중 서로 확인하는 초기 패는 예외로 한다. 상대의 공개 카드를 손으로 들어 확인해야 할 때에는 먼저 허가를 받고 확인한 뒤 원래 위치와 순서를 유지해야 한다.',
    'en': "The number of cards in each zone and both players' current HP and FP are public information needed to compare Priority and confirm legal play. Every player may inspect the information printed on face-up cards in a public zone. Hidden information, including Hands and face-down cards, may be inspected only by the owner or a player permitted by that zone's rules; the mutual check of initial hands during setup is an exception. A player who needs to pick up an opponent's public card to inspect it must first obtain permission and must return it without changing its position or order.",
    'ja': '各ゾーンのカード枚数と両プレイヤーの現在の体力・FPは、優先権の比較と適法性の確認に必要な公開情報である。公開ゾーンにある表向きカードの記載情報は、すべてのプレイヤーが確認できる。手札や裏向きカードのように非公開と定められた情報は、所有者またはそのゾーンの規則で許可されたプレイヤーだけが確認でき、ゲーム準備時に初期手札を互いに確認する場合は例外とする。相手の公開カードを手に取って確認する必要がある場合は、先に許可を得て、確認後は元の位置と順序を維持しなければならない。',
}


APPENDIX_CONTENT = {
    'ko': '''<p>정식 종합 규칙 발행 전에 다음 항목을 확정해야 합니다.</p><ul>
<li>[ ] <strong>문서 우선순위:</strong> 정오표·카드 판정·카드 텍스트·종합 규칙·입문서·예시의 정확한 우선순위와 기준 언어</li>
<li>[ ] <strong>루멘 존 기본 공개 상태:</strong> 배치 효과가 앞·뒷면과 공개 범위를 정하지 않았을 때 적용할 기본값</li>
<li>[ ] <strong>끼어들기 분류:</strong> 어떤 카드 효과가 끼어들기인지 식별할 공통 문구, 아이콘 또는 카드별 판정 목록</li>
<li>[ ] <strong>0 데미지 콤보:</strong> 콤보 시 효과 처리 뒤 데미지가 0 이하가 된 카드의 효과 되돌림, 패 복귀, 재선택과 콤보 종료 여부</li>
<li>[ ] <strong>2·3콤보 중 예외:</strong> 합법적으로 선언한 2·3콤보가 예상하지 못한 끼어들기로 불법이 되었을 때 되돌리는 범위</li>
<li>[ ] <strong>표준 가상 기술:</strong> 미대응 시 사용하는 가상 기술의 공격/수비 종류, 위치 판정, 속도 수치</li>
</ul><hr>''',
    'en': '''<p>The following items must be finalized before the Comprehensive Rules are formally published.</p><ul>
<li>[ ] <strong>Document priority:</strong> The exact precedence and controlling language of errata, card rulings, card text, the Comprehensive Rules, introductory guides, and examples</li>
<li>[ ] <strong>Default Lumen Zone visibility:</strong> The default face-up or face-down state and visibility when the placing effect does not specify them</li>
<li>[ ] <strong>Interrupt classification:</strong> Common wording, icons, or a card-by-card ruling list that identifies interrupt effects</li>
<li>[ ] <strong>0-damage Combo:</strong> Whether to reverse effects, return the card to the Hand, reselect, or end the Combo when a card's damage becomes 0 or less after effect processing</li>
<li>[ ] <strong>Exceptions during 2- and 3-Combos:</strong> What to reverse when an unexpected interrupt makes a legally declared Combo illegal</li>
<li>[ ] <strong>Standard virtual Technique:</strong> The attack or defense type, position ruling, and Speed of the virtual Technique used for Failure to Respond</li>
</ul><hr>''',
    'ja': '''<p>総合ルールを正式に発行する前に、次の項目を確定する必要があります。</p><ul>
<li>[ ] <strong>文書の優先順位:</strong> 正誤表・カード裁定・カードテキスト・総合ルール・入門書・例の正確な優先順位と基準言語</li>
<li>[ ] <strong>ルーメンゾーンの基本公開状態:</strong> 配置効果が表裏や公開範囲を指定していない場合に適用する基本値</li>
<li>[ ] <strong>割り込みの分類:</strong> どのカード効果が割り込みかを識別する共通文言、アイコン、またはカード別裁定一覧</li>
<li>[ ] <strong>0ダメージコンボ:</strong> 効果処理後にダメージが0以下になったカードの効果を戻すか、手札へ戻すか、再選択するか、コンボを終了するか</li>
<li>[ ] <strong>2・3コンボ中の例外:</strong> 合法に宣言したコンボが予期しない割り込みで不適法になった場合に戻す範囲</li>
<li>[ ] <strong>標準仮想技:</strong> 未対応時に使用する仮想技の攻撃・防御種別、位置判定、速度値</li>
</ul><hr>''',
}


REVISION_CONTENT = {
    'ko': '''<table><thead><tr><th>버전</th><th>기준일</th><th>주요 내용</th><th>상태</th></tr></thead><tbody>
<tr><td>v0.4-web</td><td>2026-09-01</td><td>각 게임 영역의 용도·귀속·공개 상태·매수 제한·이동 예외 상세화</td><td>검토 초안</td></tr>
<tr><td>v0.3-web</td><td>2026-09-01</td><td>종합 규칙서의 장 구성과 배치 순서 재정리</td><td>검토 초안</td></tr>
<tr><td>v0.1</td><td>2026-08-13</td><td>기존 룰북의 규칙 인벤토리와 공식 결정 65개 통합</td><td>검토 초안</td></tr>
<tr><td>v0.1-web</td><td>2026-08-24</td><td>웹 편집용 Markdown, 안정적 규칙 앵커와 시각화 지시 추가</td><td>검토 초안</td></tr>
</tbody></table>''',
    'en': '''<table><thead><tr><th>Version</th><th>Date</th><th>Highlights</th><th>Status</th></tr></thead><tbody>
<tr><td>v0.4-web</td><td>2026-09-01</td><td>Expanded every game area's purpose, player association, visibility, capacity, and movement exceptions</td><td>Review draft</td></tr>
<tr><td>v0.3-web</td><td>2026-09-01</td><td>Reorganized the chapter structure and reading order of the Comprehensive Rules</td><td>Review draft</td></tr>
<tr><td>v0.1</td><td>2026-08-13</td><td>Integrated the existing rule inventory and 65 official ruling answers</td><td>Review draft</td></tr>
<tr><td>v0.1-web</td><td>2026-08-24</td><td>Added web-editing Markdown, stable rule anchors, and visualization instructions</td><td>Review draft</td></tr>
</tbody></table>''',
    'ja': '''<table><thead><tr><th>バージョン</th><th>基準日</th><th>主な内容</th><th>状態</th></tr></thead><tbody>
<tr><td>v0.4-web</td><td>2026-09-01</td><td>各ゲーム領域の用途・プレイヤーとの対応・公開状態・枚数上限・移動例外を詳細化</td><td>レビュードラフト</td></tr>
<tr><td>v0.3-web</td><td>2026-09-01</td><td>総合ルールの章構成と配置順を再整理</td><td>レビュードラフト</td></tr>
<tr><td>v0.1</td><td>2026-08-13</td><td>既存ルールブックのルール一覧と65件の公式裁定を統合</td><td>レビュードラフト</td></tr>
<tr><td>v0.1-web</td><td>2026-08-24</td><td>ウェブ編集用Markdown、安定したルールアンカー、可視化指示を追加</td><td>レビュードラフト</td></tr>
</tbody></table>''',
}


ZONE_ORDER = (
    ('common', 'rule-game-area-common-rules'),
    ('character', 'rule-2-1-4'),
    ('trait', 'rule-2-1-5'),
    ('hand', 'rule-1-2-1'),
    ('list', 'rule-2-1-1'),
    ('side', 'rule-2-1-2'),
    ('battle', 'rule-2-1-6'),
    ('lumen', 'rule-2-1-7'),
    ('ultimate', 'rule-2-1-9'),
    ('break', 'rule-2-1-3'),
    ('fp', 'rule-2-1-8'),
)


def _alias_map(rules):
    aliases = {}
    for rule in rules:
        for alias in [rule.reference_name, *(rule.reference_aliases or [])]:
            aliases.setdefault(alias, rule)
    return aliases


def _set_translations(RuleTranslation, rule, titles, contents):
    for language in LANGUAGES:
        RuleTranslation.objects.update_or_create(
            rule_id=rule.pk,
            language=language,
            defaults={
                'title': titles[language],
                'content': f'<p>{contents[language]}</p>',
            },
        )


def _set_root_content(RuleTranslation, root):
    for language in LANGUAGES:
        translation = RuleTranslation.objects.filter(
            rule_id=root.pk,
            language=language,
        ).first()
        if translation is None:
            continue
        translation.content = AREA_ROOT_CONTENT[language]
        translation.save(update_fields=['content'])


def _set_html_translations(RuleTranslation, rule, titles, contents):
    for language in LANGUAGES:
        RuleTranslation.objects.update_or_create(
            rule_id=rule.pk,
            language=language,
            defaults={
                'title': titles[language],
                'content': contents[language],
            },
        )


def expand_game_area_definitions(apps, schema_editor):
    Rulebook = apps.get_model('common', 'Rulebook')
    Rule = apps.get_model('common', 'Rule')
    RuleTranslation = apps.get_model('common', 'RuleTranslation')

    try:
        book = Rulebook.objects.get(slug='comprehensive')
    except Rulebook.DoesNotExist:
        return

    rules = list(Rule.objects.filter(rulebook_id=book.pk).order_by('priority', 'pk'))
    if not rules:
        return
    aliases = _alias_map(rules)

    required_aliases = [
        'chapter-2', 'rule-1-2-1', 'rule-2-2-1',
        *(f'rule-2-1-{index}' for index in range(1, 10)),
    ]
    found = [alias for alias in required_aliases if alias in aliases]
    if not found:
        return
    missing = [alias for alias in required_aliases if alias not in aliases]
    if missing:
        raise RuntimeError(
            '종합 규칙서의 영역 조항 앵커가 일부 누락되어 '
            f'v0.4 상세 정의 마이그레이션을 적용할 수 없습니다: {", ".join(missing)}'
        )

    area_root = aliases['chapter-2']
    zone_section = Rule.objects.get(pk=aliases['rule-2-1-1'].parent_id)
    public_section = Rule.objects.get(pk=aliases['rule-2-2-1'].parent_id)
    if zone_section.parent_id != area_root.pk or public_section.parent_id != area_root.pk:
        raise RuntimeError('종합 규칙서 영역 절의 계층이 v0.3 배치와 일치하지 않습니다.')

    common = aliases.get('rule-game-area-common-rules')
    if common is None:
        reference_name = 'rule-game-area-common-rules'
        suffix = 2
        while Rule.objects.filter(reference_name=reference_name).exists():
            reference_name = f'rule-game-area-common-rules-{suffix}'
            suffix += 1
        common = Rule.objects.create(
            rulebook_id=book.pk,
            parent_id=zone_section.pk,
            reference_name=reference_name,
            reference_aliases=(
                [] if reference_name == 'rule-game-area-common-rules'
                else ['rule-game-area-common-rules']
            ),
            priority=10,
            show_in_toc=False,
            is_public=True,
        )

    rule_by_key = {'common': common}
    for key, alias in ZONE_ORDER[1:]:
        rule_by_key[key] = aliases[alias]

    for key, _alias in ZONE_ORDER:
        rule = rule_by_key[key]
        rule.parent_id = zone_section.pk
        rule.show_in_toc = False
        rule.is_public = True
        rule.save(update_fields=['parent', 'show_in_toc', 'is_public'])
        _set_translations(
            RuleTranslation,
            rule,
            CLAUSES[key]['titles'],
            CLAUSES[key]['contents'],
        )

    desired_ids = [rule_by_key[key].pk for key, _alias in ZONE_ORDER]
    remaining = list(
        Rule.objects
        .filter(rulebook_id=book.pk, parent_id=zone_section.pk)
        .exclude(pk__in=desired_ids)
        .order_by('priority', 'pk')
    )
    for index, rule in enumerate(
        [*(rule_by_key[key] for key, _alias in ZONE_ORDER), *remaining],
        start=1,
    ):
        Rule.objects.filter(pk=rule.pk).update(priority=index * 10)

    public_rule = aliases['rule-2-2-1']
    public_rule.parent_id = public_section.pk
    public_rule.priority = 10
    public_rule.show_in_toc = False
    public_rule.is_public = True
    public_rule.save(update_fields=['parent', 'priority', 'show_in_toc', 'is_public'])
    _set_translations(
        RuleTranslation,
        public_rule,
        {'ko': '존별 공개 정보', 'en': 'Public Information by Zone', 'ja': 'ゾーン別公開情報'},
        PUBLIC_CONTENT,
    )
    for index, rule in enumerate(
        Rule.objects
        .filter(rulebook_id=book.pk, parent_id=public_section.pk)
        .exclude(pk=public_rule.pk)
        .order_by('priority', 'pk'),
        start=2,
    ):
        Rule.objects.filter(pk=rule.pk).update(priority=index * 10)

    _set_root_content(RuleTranslation, area_root)

    appendix = aliases.get('appendix-c')
    if appendix is not None:
        _set_html_translations(
            RuleTranslation,
            appendix,
            {'ko': '부록 C. 편집 확인 목록', 'en': 'Appendix C. Edit Checklist', 'ja': '付録C. 編集確認リスト'},
            APPENDIX_CONTENT,
        )

    appendix_t = aliases.get('appendix-t')
    if appendix_t is not None:
        revision = (
            Rule.objects
            .filter(
                rulebook_id=book.pk,
                parent_id=None,
                priority__gt=appendix_t.priority,
            )
            .order_by('priority', 'pk')
            .first()
        )
        if revision is not None:
            _set_html_translations(
                RuleTranslation,
                revision,
                {'ko': '개정 이력', 'en': 'Revision History', 'ja': '改訂履歴'},
                REVISION_CONTENT,
            )

    book.version = '0.4-web'
    book.updated_on = date(2026, 9, 1)
    book.save(update_fields=['version', 'updated_on'])


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0017_reorder_comprehensive_rulebook'),
    ]

    operations = [
        migrations.RunPython(expand_game_area_definitions, migrations.RunPython.noop),
    ]
