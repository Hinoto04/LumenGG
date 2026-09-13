from datetime import date

from django.db import migrations


LANGUAGES = ('ko', 'en', 'ja')

ROOT_CONTENT = {
    'ko': '<p><strong>게임 객체</strong>란 규칙이나 카드 효과가 대상으로 지정할 수 있는 것을 말합니다. 게임 객체는 <strong>플레이어</strong>와 <strong>카드</strong> 두 종류입니다. 덱은 게임 준비에 사용하는 카드 구성이며, 존과 FP 영역은 게임 영역이므로 그 자체는 게임 객체가 아닙니다.</p>',
    'en': '<p>A <strong>game object</strong> is something that a rule or card effect can designate as a target. The two kinds of game objects are <strong>players</strong> and <strong>cards</strong>. A deck is a card configuration used during setup, while zones and the FP Area are game areas; none of them is itself a game object.</p>',
    'ja': '<p><strong>ゲームオブジェクト</strong>とは、ルールやカード効果が対象として指定できるものをいいます。ゲームオブジェクトは<strong>プレイヤー</strong>と<strong>カード</strong>の2種類です。デッキはゲーム準備に使用するカード構成であり、ゾーンとFP領域はゲーム領域であるため、それ自体はゲームオブジェクトではありません。</p>',
}

SECTION_TITLES = {
    'player': {'ko': '플레이어', 'en': 'Players', 'ja': 'プレイヤー'},
    'card': {'ko': '카드', 'en': 'Cards', 'ja': 'カード'},
}

CLAUSES = {
    'player': {
        'titles': {'ko': '플레이어', 'en': 'Player', 'ja': 'プレイヤー'},
        'contents': {
            'ko': '플레이어는 게임에 참여하여 규칙과 카드 효과의 대상을 될 수 있는 게임 객체다. 한 게임에는 두 플레이어가 있으며, 각 플레이어는 자신과 자신이 아닌 상대 플레이어로 구분된다.',
            'en': 'A player is a game object that participates in the game and may be targeted by rules and card effects. A game has two players, distinguished as yourself and the other player, your opponent.',
            'ja': 'プレイヤーはゲームに参加し、ルールやカード効果の対象になり得るゲームオブジェクトである。1つのゲームには2人のプレイヤーが存在し、各プレイヤーから見て自分と、自分ではない相手プレイヤーに区別する。',
        },
    },
    'player_info': {
        'titles': {'ko': '플레이어 정보', 'en': 'Player Information', 'ja': 'プレイヤー情報'},
        'contents': {
            'ko': '''플레이어 객체는 다음 정보를 가진다. 규칙이나 카드 효과가 이 정보의 일부를 확인하거나 변경할 수 있다.
<table><thead><tr><th>정보</th><th>설명</th></tr></thead><tbody>
<tr><td>자신·상대 구분</td><td>효과를 발생시킨 카드의 소유자를 자신, 다른 플레이어를 상대로 구분한다.</td></tr>
<tr><td>현재 체력</td><td>캐릭터 카드에 표시하는 현재 잔존 체력이다.</td></tr>
<tr><td>현재 FP</td><td>FP 영역에 표시하는 양수·0·음수의 공개 수치다.</td></tr>
<tr><td>패 매수</td><td>현재 패에 있는 카드 수이며 공개 정보다.</td></tr>
<tr><td>패 매수 상한</td><td>캐릭터 카드의 현재 체력 구간에 표시된 패의 최대 매수다. 체력이 바뀌면 처리 단위 종료 후 다시 계산한다.</td></tr>
<tr><td>우선권</td><td>동시에 처리할 행동이나 효과의 처리 순서를 정하는 보유 여부다.</td></tr>
<tr><td>캐릭터 마크</td><td>자신의 캐릭터 카드에 표시된 마크이며 덱 구성과 일부 효과가 참조한다.</td></tr>
<tr><td>연결 영역</td><td>자신의 패와 각 존처럼 그 플레이어에게 연결된 게임 영역이다.</td></tr>
</tbody></table>''',
            'en': '''A player object has the following information. Rules and card effects may inspect or change some of this information.
<table><thead><tr><th>Information</th><th>Description</th></tr></thead><tbody>
<tr><td>Self or opponent</td><td>The owner of the card producing an effect is yourself; the other player is the opponent.</td></tr>
<tr><td>Current HP</td><td>The player's remaining HP, displayed on their Character Card.</td></tr>
<tr><td>Current FP</td><td>A public positive, zero, or negative value displayed in the FP Area.</td></tr>
<tr><td>Hand size</td><td>The number of cards currently in the Hand; this is public information.</td></tr>
<tr><td>Hand limit</td><td>The maximum Hand size shown in the Character Card's current HP bracket. Recalculate it after a processing unit ends if HP changed.</td></tr>
<tr><td>Priority</td><td>Whether the player currently determines the order of simultaneous actions or effects.</td></tr>
<tr><td>Character Emblem</td><td>The emblem printed on the player's Character Card, referenced by deck construction and some effects.</td></tr>
<tr><td>Connected areas</td><td>Game areas connected to that player, such as their Hand and zones.</td></tr>
</tbody></table>''',
            'ja': '''プレイヤーオブジェクトは次の情報を持つ。ルールやカード効果は、これらの情報の一部を確認または変更できる。
<table><thead><tr><th>情報</th><th>説明</th></tr></thead><tbody>
<tr><td>自分・相手の区別</td><td>効果を発生させたカードの所有者を自分、もう一方のプレイヤーを相手とする。</td></tr>
<tr><td>現在の体力</td><td>キャラクターカードに表示するプレイヤーの残り体力。</td></tr>
<tr><td>現在のFP</td><td>FP領域に表示する正数・0・負数の公開値。</td></tr>
<tr><td>手札枚数</td><td>現在の手札にあるカード枚数であり、公開情報である。</td></tr>
<tr><td>手札枚数上限</td><td>キャラクターカードの現在の体力区分に示された手札の最大枚数。体力が変化した場合、処理単位の終了後に再計算する。</td></tr>
<tr><td>優先権</td><td>同時に処理する行動や効果の順序を決める保有状態。</td></tr>
<tr><td>キャラクターマーク</td><td>自分のキャラクターカードに表示されたマークで、デッキ構築や一部の効果が参照する。</td></tr>
<tr><td>対応する領域</td><td>自分の手札や各ゾーンなど、そのプレイヤーに対応するゲーム領域。</td></tr>
</tbody></table>''',
        },
    },
    'hand_excess': {
        'titles': {'ko': '패 상한 초과', 'en': 'Exceeding the Hand Limit', 'ja': '手札上限の超過'},
        'contents': {
            'ko': '처리 단위 종료 후 플레이어의 패가 현재 패 매수 상한을 초과하면, 그 플레이어는 상한을 초과한 만큼 즉시 버린다. 이 처리는 다음 효과를 처리하기 전에 수행한다.',
            'en': "If a player's Hand exceeds their current Hand limit after a processing unit ends, that player immediately discards the excess. Perform this before processing the next effect.",
            'ja': '処理単位の終了後、プレイヤーの手札が現在の手札枚数上限を超えている場合、そのプレイヤーは超過分を直ちに捨てる。この処理は次の効果を処理する前に行う。',
        },
    },
    'player_target': {
        'titles': {'ko': '자신과 상대', 'en': 'You and Your Opponent', 'ja': '自分と相手'},
        'contents': {
            'ko': '카드 텍스트가 “자신”을 지정하면 그 효과를 발생시킨 카드의 소유자인 플레이어 객체를, “상대”를 지정하면 다른 플레이어 객체를 뜻한다. 카드 효과가 플레이어를 대상으로 지정하면 카드나 존이 아니라 해당 플레이어 객체를 대상으로 한다.',
            'en': 'In card text, “you” designates the player object who owns the card producing the effect, and “your opponent” designates the other player object. An effect that targets a player targets that player object, not a card or zone.',
            'ja': 'カードテキストが「自分」を指定する場合、その効果を発生させたカードの所有者であるプレイヤーオブジェクトを指し、「相手」を指定する場合、もう一方のプレイヤーオブジェクトを指す。プレイヤーを対象とする効果は、カードやゾーンではなく、そのプレイヤーオブジェクトを対象とする。',
        },
    },
    'card': {
        'titles': {'ko': '카드 객체', 'en': 'Card Object', 'ja': 'カードオブジェクト'},
        'contents': {
            'ko': '카드는 게임에 사용하는 인쇄물로서 규칙과 카드 효과의 대상이 될 수 있는 게임 객체다. 카드 객체는 존을 이동하거나 앞·뒷면 상태가 바뀌어도 같은 객체로 취급한다.',
            'en': 'A card is a printed game component that may be targeted by rules and card effects. A card remains the same object when it moves between zones or changes between face-up and face-down states.',
            'ja': 'カードはゲームに使用する印刷物であり、ルールやカード効果の対象になり得るゲームオブジェクトである。カードはゾーンを移動したり表向き・裏向きの状態が変化したりしても、同じオブジェクトとして扱う。',
        },
    },
    'card_info': {
        'titles': {'ko': '카드 정보', 'en': 'Card Information', 'ja': 'カード情報'},
        'contents': {
            'ko': '''카드 객체는 다음 공통 정보를 가지며, 카드 종류에 따라 일부 정보가 없을 수 있다.
<table><thead><tr><th>정보</th><th>설명</th></tr></thead><tbody>
<tr><td>소유자</td><td>그 카드를 자신의 덱에 넣고 게임을 시작한 플레이어다. 카드가 다른 존으로 이동해도 소유자는 바뀌지 않으며, 별도 지시가 있을 때만 변경된다.</td></tr>
<tr><td>카드 명칭</td><td>카드의 이름이며 동명 카드 판정과 카드 효과의 참조에 사용한다.</td></tr>
<tr><td>카드 종류·분류</td><td>캐릭터, 특성, 공격·수비·특수 기술과 얼티밋 여부 등 카드가 속한 분류다.</td></tr>
<tr><td>캐릭터 마크</td><td>덱 구성 가능 여부와 카드 효과가 참조하는 마크다. 중립 기술은 중립 마크를 가진다.</td></tr>
<tr><td>기능·효과</td><td>카드가 항상 적용하는 기능과 정해진 시점에 처리하는 효과다.</td></tr>
<tr><td>수치·판정 정보</td><td>체력, 패 상한, 속도, 데미지, FP, 위치, 특수 판정처럼 카드 종류에 따라 사용하는 정보다.</td></tr>
<tr><td>표시 상태·현재 존</td><td>카드가 앞면인지 뒷면인지와 현재 놓인 존이다. 공개 범위와 사용할 수 있는 규칙을 정할 때 참조한다.</td></tr>
<tr><td>수록 식별 정보</td><td>카드 넘버, 일러스트, 수록판처럼 카드를 정리하고 판본을 식별하는 정보다.</td></tr>
</tbody></table>''',
            'en': '''A card object has the following common information, though some information may not apply to every card type.
<table><thead><tr><th>Information</th><th>Description</th></tr></thead><tbody>
<tr><td>Owner</td><td>The player who began the game with that card in their deck. Moving the card to another zone does not change its owner unless an instruction expressly says so.</td></tr>
<tr><td>Card name</td><td>The card's name, used for same-name determinations and references in card effects.</td></tr>
<tr><td>Card type and classifications</td><td>Character, Trait, Attack, Defense, or Special Technique, plus classifications such as Ultimate.</td></tr>
<tr><td>Character Emblem</td><td>An emblem referenced by deck construction and card effects. A Neutral Technique has the Neutral Emblem.</td></tr>
<tr><td>Functions and effects</td><td>Functions that continuously apply and effects processed at specified times.</td></tr>
<tr><td>Values and ruling information</td><td>Type-specific information such as HP, Hand limit, Speed, damage, FP, position, and special rulings.</td></tr>
<tr><td>Display state and current zone</td><td>Whether the card is face up or face down and the zone it currently occupies. These determine visibility and which rules may use the card.</td></tr>
<tr><td>Printing identifiers</td><td>Card number, illustration, and edition information used to organize and identify a printing.</td></tr>
</tbody></table>''',
            'ja': '''カードオブジェクトは次の共通情報を持つ。ただし、カードの種類によっては一部の情報を持たない。
<table><thead><tr><th>情報</th><th>説明</th></tr></thead><tbody>
<tr><td>所有者</td><td>そのカードを自分のデッキに入れてゲームを開始したプレイヤー。カードが別のゾーンへ移動しても所有者は変わらず、別の指示がある場合にのみ変更される。</td></tr>
<tr><td>カード名</td><td>カードの名称であり、同名カードの判定やカード効果の参照に使用する。</td></tr>
<tr><td>カード種類・分類</td><td>キャラクター、特性、攻撃・防御・特殊技、およびアルティメットであるかなどの分類。</td></tr>
<tr><td>キャラクターマーク</td><td>デッキに入れられるかどうかやカード効果が参照するマーク。ニュートラル技はニュートラルマークを持つ。</td></tr>
<tr><td>機能・効果</td><td>常に適用する機能と、指定された時点に処理する効果。</td></tr>
<tr><td>数値・判定情報</td><td>体力、手札上限、速度、ダメージ、FP、位置、特殊判定など、カード種類に応じて使用する情報。</td></tr>
<tr><td>表示状態・現在のゾーン</td><td>カードが表向きか裏向きか、および現在置かれているゾーン。公開範囲や使用可能なルールを決める際に参照する。</td></tr>
<tr><td>収録識別情報</td><td>カード番号、イラスト、収録版など、カードを整理し版を識別する情報。</td></tr>
</tbody></table>''',
        },
    },
    'character_card': {
        'titles': {'ko': '캐릭터 카드', 'en': 'Character Card', 'ja': 'キャラクターカード'},
        'contents': {
            'ko': '캐릭터 카드는 플레이어를 대변하는 카드다. 캐릭터 정보로 소속·이명·이름 등을, 게임 정보로 체력 구간별 체력과 패 매수 상한, 캐릭터 마크를 가지며 카드 넘버를 수록 식별 정보로 가진다. 게임 중 플레이어의 현재 체력과 패 매수 상한은 이 카드에 표시한다.',
            'en': "A Character Card represents a player. It has character information such as affiliation, epithet, and name; game information such as HP and Hand limits by HP bracket and a Character Emblem; and a card number as printing identification. During the game, it displays the player's current HP and Hand limit.",
            'ja': 'キャラクターカードはプレイヤーを表すカードである。所属・異名・名前などのキャラクター情報、体力区分ごとの体力と手札枚数上限およびキャラクターマークというゲーム情報、収録識別情報としてのカード番号を持つ。ゲーム中は、このカードにプレイヤーの現在の体力と手札枚数上限を表示する。',
        },
    },
    'trait': {
        'titles': {'ko': '특성 카드', 'en': 'Trait Card', 'ja': '特性カード'},
        'contents': {
            'ko': '특성 카드는 캐릭터 고유의 기능과 효과를 가진 카드다. 카드 명칭, 특성 분류, 기능·효과, 캐릭터 마크를 가지며 게임 준비 시 캐릭터 카드 옆의 특성 존에 놓는다.',
            'en': "A Trait Card contains a character's unique functions and effects. It has a card name, Trait classification, functions and effects, and Character Emblem, and is placed in the Trait Zone beside the Character Card during setup.",
            'ja': '特性カードはキャラクター固有の機能と効果を持つカードである。カード名、特性分類、機能・効果、キャラクターマークを持ち、ゲーム準備時にキャラクターカードの隣の特性ゾーンへ置く。',
        },
    },
    'trait_timing': {
        'titles': {'ko': '적용 시점', 'en': 'Application Timing', 'ja': '適用時点'},
        'contents': {
            'ko': '특성 카드의 기능과 효과는 게임 시작 직후부터 적용한다.',
            'en': "A Trait Card's functions and effects apply immediately after the game begins.",
            'ja': '特性カードの機能と効果はゲーム開始直後から適用する。',
        },
    },
    'attack': {
        'titles': {'ko': '공격 기술 정보', 'en': 'Attack Technique Information', 'ja': '攻撃技の情報'},
        'contents': {
            'ko': '공격 기술 카드는 배틀 존에 사용하여 상대에게 데미지를 줄 수 있는 기술 카드다. 카드 명칭, 공격 위치, 속도, 손·발 판정, 판정 결과별 FP, 특수 판정, 기능·효과, 캐릭터 마크, 데미지와 플레이버 텍스트를 정보로 가질 수 있다.',
            'en': 'An Attack Technique Card is a Technique Card used in the Battle Zone to deal damage to the opponent. Its information may include card name, attack position, Speed, hand or foot designation, FP by ruling result, special rulings, functions and effects, Character Emblem, damage, and flavor text.',
            'ja': '攻撃技カードはバトルゾーンで使用し、相手にダメージを与えることができる技カードである。カード名、攻撃位置、速度、手・足判定、判定結果別FP、特殊判定、機能・効果、キャラクターマーク、ダメージ、フレーバーテキストを情報として持つことがある。',
        },
    },
    'defense': {
        'titles': {'ko': '수비 기술 정보', 'en': 'Defense Technique Information', 'ja': '防御技の情報'},
        'contents': {
            'ko': '수비 기술 카드는 배틀 존에 사용하여 상대 공격을 방어하거나 회피하는 기술 카드다. 카드 명칭, 방어하거나 회피할 위치, 특수 판정, 기능·효과, 캐릭터 마크와 플레이버 텍스트를 정보로 가질 수 있다.',
            'en': 'A Defense Technique Card is a Technique Card used in the Battle Zone to guard against or evade an opposing attack. Its information may include card name, guarded or evaded positions, special rulings, functions and effects, Character Emblem, and flavor text.',
            'ja': '防御技カードはバトルゾーンで使用し、相手の攻撃を防御または回避する技カードである。カード名、防御または回避する位置、特殊判定、機能・効果、キャラクターマーク、フレーバーテキストを情報として持つことがある。',
        },
    },
    'special': {
        'titles': {'ko': '특수 기술 정보', 'en': 'Special Technique Information', 'ja': '特殊技の情報'},
        'contents': {
            'ko': '특수 기술 카드는 기재된 사용 조건을 만족했을 때 효과를 처리하는 기술 카드다. 카드 명칭, 특수 기술 분류, 사용 조건, 기능·효과, 캐릭터 마크와 배치할 존 등의 정보를 가질 수 있다. 사용할 때에는 조건 확인, 카드 공개, 지정된 존 배치, 효과 처리 순서로 진행하며, 조건을 충족하지 못하면 공개하거나 배치할 수 없다.',
            'en': 'A Special Technique Card is a Technique Card whose effect is processed when its printed use condition is met. Its information may include card name, Special Technique classification, use condition, functions and effects, Character Emblem, and the zone where it is placed. To use it, check the condition, reveal the card, place it in the designated zone, and process the effect in that order. A Special Technique whose condition is not met cannot be revealed or placed.',
            'ja': '特殊技カードは、記載された使用条件を満たしたときに効果を処理する技カードである。カード名、特殊技分類、使用条件、機能・効果、キャラクターマーク、配置するゾーンなどの情報を持つことがある。使用時は、条件確認、カード公開、指定されたゾーンへの配置、効果処理の順に進め、条件を満たしていない場合は公開または配置できない。',
        },
    },
    'special_zones': {
        'titles': {'ko': '특수 기술의 존', 'en': 'Special Technique Zones', 'ja': '特殊技のゾーン'},
        'contents': {
            'ko': '특수 기술 카드는 사이드 덱, 루멘 존, 얼티밋 존, 브레이크 존에만 존재할 수 있으며 패에 넣을 수 없다.',
            'en': 'A Special Technique Card may exist only in the Side Deck, Lumen Zone, Ultimate Zone, or Break Zone and cannot enter the Hand.',
            'ja': '特殊技カードは、サイドデッキ、ルーメンゾーン、アルティメットゾーン、ブレイクゾーンにのみ存在でき、手札に入れることはできない。',
        },
    },
    'ultimate': {
        'titles': {'ko': '얼티밋 분류', 'en': 'Ultimate Classification', 'ja': 'アルティメット分類'},
        'contents': {
            'ko': '얼티밋은 공격·수비·특수 기술 카드가 추가로 가질 수 있는 분류다. 얼티밋 기술 카드는 기본 카드 종류의 정보에 더해 얼티밋 여부를 가지며, 덱에 0장 또는 1장 채용하고 게임 시작 시 얼티밋 존에 앞면으로 공개한다. 프로텍터는 다른 기술 카드와 같은 것을 사용한다.',
            'en': 'Ultimate is an additional classification that an Attack, Defense, or Special Technique Card may have. An Ultimate Technique has the information of its base card type plus its Ultimate classification. A deck may include zero or one Ultimate Technique, which is revealed face up in the Ultimate Zone at the start of the game. It uses the same card sleeve as the other Technique Cards.',
            'ja': 'アルティメットは、攻撃・防御・特殊技カードが追加で持つことができる分類である。アルティメット技カードは基本となるカード種類の情報に加えてアルティメット分類を持ち、デッキに0枚または1枚採用し、ゲーム開始時にアルティメットゾーンで表向きに公開する。スリーブは他の技カードと同じものを使用する。',
        },
    },
    'ultimate_normal': {
        'titles': {'ko': '얼티밋 공격·수비', 'en': 'Ultimate Attack and Defense', 'ja': 'アルティメット攻撃・防御'},
        'contents': {
            'ko': '얼티밋 공격·수비 기술은 패에 넣은 뒤 일반 공격·수비 기술과 같은 규칙으로 처리한다. 사용 후에도 패·리스트·브레이크 존 등 실제 이동 결과가 유지되며 얼티밋 존으로 자동으로 돌아가지 않는다.',
            'en': 'After an Ultimate Attack or Defense Technique enters the Hand, process it under the same rules as a normal Attack or Defense Technique. After use, its actual movement to the Hand, List, Break Zone, or another zone remains in effect; it does not automatically return to the Ultimate Zone.',
            'ja': 'アルティメット攻撃・防御技は手札に入った後、通常の攻撃・防御技と同じルールで処理する。使用後も手札・リスト・ブレイクゾーンなどへの実際の移動結果を維持し、アルティメットゾーンへ自動的には戻らない。',
        },
    },
    'ultimate_special': {
        'titles': {'ko': '얼티밋 특수', 'en': 'Ultimate Special', 'ja': 'アルティメット特殊'},
        'contents': {
            'ko': '얼티밋 특수 기술은 조건을 만족했을 때 카드에 기재된 절차로 루멘 존 등에 배치하며 패에 넣을 수 없다.',
            'en': 'When its condition is met, place an Ultimate Special Technique in the Lumen Zone or another designated zone according to the procedure printed on the card. It cannot enter the Hand.',
            'ja': 'アルティメット特殊技は条件を満たしたとき、カードに記載された手順でルーメンゾーンなどに配置し、手札に入れることはできない。',
        },
    },
    'ultimate_list': {
        'titles': {'ko': '리스트 이동', 'en': 'Movement to the List', 'ja': 'リストへの移動'},
        'contents': {
            'ko': '얼티밋 공격·수비 기술이 리스트로 보내지면 일반 공격·수비 기술과 동일하게 리스트에 남는다.',
            'en': 'If an Ultimate Attack or Defense Technique is sent to the List, it remains there under the same rules as a normal Attack or Defense Technique.',
            'ja': 'アルティメット攻撃・防御技がリストへ送られた場合、通常の攻撃・防御技と同じくリストに残る。',
        },
    },
    'ultimate_side': {
        'titles': {'ko': '사이드 덱 이동', 'en': 'Movement to the Side Deck', 'ja': 'サイドデッキへの移動'},
        'contents': {
            'ko': '얼티밋 특수 기술이 사이드 덱으로 보내지면 사이드 덱에 놓는다.',
            'en': 'If an Ultimate Special Technique is sent to the Side Deck, place it in the Side Deck.',
            'ja': 'アルティメット特殊技がサイドデッキへ送られた場合、サイドデッキに置く。',
        },
    },
    'deck': {
        'titles': {'ko': '덱', 'en': 'Deck', 'ja': 'デッキ'},
        'contents': {
            'ko': '덱은 게임 준비에 사용하는 카드 묶음이며 게임 객체가 아니다. 스타터 덱은 개봉 즉시 사용할 수 있고, 직접 구축한 덱은 이 절의 덱 구성 제한을 지켜야 한다.',
            'en': 'A deck is a group of cards used during game setup and is not a game object. A starter deck can be used immediately after opening; a custom-built deck must follow the construction restrictions in this section.',
            'ja': 'デッキはゲーム準備に使用するカードの組であり、ゲームオブジェクトではない。スターターデッキは開封後すぐに使用でき、構築したデッキは本節のデッキ構築制限に従わなければならない。',
        },
    },
}

REVISION_CONTENT = {
    'ko': '''<table><thead><tr><th>버전</th><th>기준일</th><th>주요 내용</th><th>상태</th></tr></thead><tbody>
<tr><td>v0.5-web</td><td>2026-09-01</td><td>게임 객체를 플레이어·카드로 재정의하고 객체별 정보와 조항 표시 방식 정리</td><td>검토 초안</td></tr>
<tr><td>v0.4-web</td><td>2026-09-01</td><td>각 게임 영역의 용도·귀속·공개 상태·매수 제한·이동 예외 상세화</td><td>검토 초안</td></tr>
<tr><td>v0.3-web</td><td>2026-09-01</td><td>종합 규칙서의 장 구성과 배치 순서 재정리</td><td>검토 초안</td></tr>
<tr><td>v0.1</td><td>2026-08-13</td><td>기존 룰북의 규칙 인벤토리와 공식 결정 65개 통합</td><td>검토 초안</td></tr>
<tr><td>v0.1-web</td><td>2026-08-24</td><td>웹 편집용 Markdown, 안정적 규칙 앵커와 시각화 지시 추가</td><td>검토 초안</td></tr>
</tbody></table>''',
    'en': '''<table><thead><tr><th>Version</th><th>Date</th><th>Highlights</th><th>Status</th></tr></thead><tbody>
<tr><td>v0.5-web</td><td>2026-09-01</td><td>Redefined game objects as players and cards, detailed their information, and simplified clause display</td><td>Review draft</td></tr>
<tr><td>v0.4-web</td><td>2026-09-01</td><td>Expanded every game area's purpose, player association, visibility, capacity, and movement exceptions</td><td>Review draft</td></tr>
<tr><td>v0.3-web</td><td>2026-09-01</td><td>Reorganized the chapter structure and reading order of the Comprehensive Rules</td><td>Review draft</td></tr>
<tr><td>v0.1</td><td>2026-08-13</td><td>Integrated the existing rule inventory and 65 official ruling answers</td><td>Review draft</td></tr>
<tr><td>v0.1-web</td><td>2026-08-24</td><td>Added web-editing Markdown, stable rule anchors, and visualization instructions</td><td>Review draft</td></tr>
</tbody></table>''',
    'ja': '''<table><thead><tr><th>バージョン</th><th>基準日</th><th>主な内容</th><th>状態</th></tr></thead><tbody>
<tr><td>v0.5-web</td><td>2026-09-01</td><td>ゲームオブジェクトをプレイヤーとカードに再定義し、オブジェクト別情報と条項表示を整理</td><td>レビュードラフト</td></tr>
<tr><td>v0.4-web</td><td>2026-09-01</td><td>各ゲーム領域の用途・プレイヤーとの対応・公開状態・枚数上限・移動例外を詳細化</td><td>レビュードラフト</td></tr>
<tr><td>v0.3-web</td><td>2026-09-01</td><td>総合ルールの章構成と配置順を再整理</td><td>レビュードラフト</td></tr>
<tr><td>v0.1</td><td>2026-08-13</td><td>既存ルールブックのルール一覧と65件の公式裁定を統合</td><td>レビュードラフト</td></tr>
<tr><td>v0.1-web</td><td>2026-08-24</td><td>ウェブ編集用Markdown、安定したルールアンカー、可視化指示を追加</td><td>レビュードラフト</td></tr>
</tbody></table>''',
}

PLAYER_ORDER = (
    ('player', 'rule-3-2-1'),
    ('player_info', 'rule-3-2-2'),
    ('hand_excess', 'rule-3-2-3'),
    ('player_target', 'rule-3-2-4'),
)

CARD_ORDER = (
    ('card', 'rule-game-object-card'),
    ('card_info', 'rule-card-common-information'),
    ('character_card', 'rule-card-character-information'),
    ('trait', 'rule-3-3-1'),
    ('trait_timing', 'rule-3-3-2'),
    ('attack', 'rule-3-4-1'),
    ('defense', 'rule-3-4-2'),
    ('special', 'rule-11-1-1'),
    ('special_zones', 'rule-11-1-2'),
    ('ultimate', 'rule-11-2-1'),
    ('ultimate_normal', 'rule-11-2-2'),
    ('ultimate_special', 'rule-11-2-3'),
    ('ultimate_list', 'rule-11-2-4'),
    ('ultimate_side', 'rule-11-2-5'),
)

CORE_REQUIRED = [
    *(alias for _key, alias in CARD_ORDER[3:]),
    'rule-3-5-1',
    'chapter-1',
]


def _alias_map(rules):
    aliases = {}
    for rule in rules:
        for alias in [rule.reference_name, *(rule.reference_aliases or [])]:
            aliases.setdefault(alias, rule)
    return aliases


def _add_alias(rule, alias):
    aliases = list(rule.reference_aliases or [])
    if alias and alias != rule.reference_name and alias not in aliases:
        aliases.append(alias)
        rule.reference_aliases = aliases


def _set_translation(RuleTranslation, rule, data):
    for language in LANGUAGES:
        content = data['contents'][language]
        if not content.lstrip().startswith('<'):
            first_line, separator, remainder = content.partition('\n')
            content = f'<p>{first_line}</p>{remainder if separator else ""}'
        RuleTranslation.objects.update_or_create(
            rule_id=rule.pk,
            language=language,
            defaults={
                'title': data['titles'][language],
                'content': content,
            },
        )


def _set_section(RuleTranslation, rule, titles, contents=None):
    contents = contents or {language: '' for language in LANGUAGES}
    for language in LANGUAGES:
        RuleTranslation.objects.update_or_create(
            rule_id=rule.pk,
            language=language,
            defaults={'title': titles[language], 'content': contents[language]},
        )


def _merge_section(Rule, RuleTranslation, RuleVisualGuide, source, target):
    if source.pk == target.pk:
        return
    Rule.objects.filter(parent_id=source.pk).update(parent_id=target.pk)
    RuleVisualGuide.objects.filter(rule_id=source.pk).update(
        rule_id=target.pk,
        rulebook_id=target.rulebook_id,
    )
    target_translations = {
        item.language: item
        for item in RuleTranslation.objects.filter(rule_id=target.pk)
    }
    for source_translation in RuleTranslation.objects.filter(rule_id=source.pk):
        source_content = (source_translation.content or '').strip()
        target_translation = target_translations.get(source_translation.language)
        if source_content and target_translation and source_content not in (target_translation.content or ''):
            target_translation.content = ''.join((target_translation.content or '', source_content))
            target_translation.save(update_fields=['content'])
    for alias in [source.reference_name, *(source.reference_aliases or [])]:
        _add_alias(target, alias)
    target.save(update_fields=['reference_aliases'])
    source.delete()


def _new_rule(Rule, book, parent, reference):
    candidate = reference
    suffix = 2
    while Rule.objects.filter(reference_name=candidate).exists():
        candidate = f'{reference}-{suffix}'
        suffix += 1
    return Rule.objects.create(
        rulebook_id=book.pk,
        parent_id=parent.pk,
        reference_name=candidate,
        reference_aliases=[] if candidate == reference else [reference],
        priority=10,
        show_in_toc=False,
        is_public=True,
    )


def _update_judgment_map(RuleVisualGuideTranslation, book):
    replacements = {
        'ko': (
            '플레이어, 캐릭터·특성·기술 카드, 덱과 얼티밋 기술의 정의를 확인합니다.',
            '대상으로 지정할 수 있는 게임 객체인 플레이어와 카드, 그리고 각 객체가 가진 정보를 확인합니다.',
            '플레이어 · 카드 · 덱',
            '플레이어 · 카드',
        ),
        'en': (
            'Review the definitions of players, Character, Trait, and Technique Cards, decks, and Ultimate Techniques.',
            'Review players and cards as targetable game objects and the information each object can have.',
            'Players · Cards · Decks',
            'Players · Cards',
        ),
        'ja': (
            'プレイヤー、キャラクター・特性・技カード、デッキ、アルティメット技の定義を確認します。',
            '対象に指定できるゲームオブジェクトであるプレイヤーとカード、および各オブジェクトが持つ情報を確認します。',
            'プレイヤー · カード · デッキ',
            'プレイヤー · カード',
        ),
    }
    for translation in RuleVisualGuideTranslation.objects.filter(
        guide__rulebook_id=book.pk,
        guide__rule_id=None,
    ):
        values = replacements.get(translation.language)
        if not values:
            continue
        old_text, new_text, old_hint, new_hint = values
        updated = (translation.content or '').replace(old_text, new_text).replace(old_hint, new_hint)
        if updated != translation.content:
            translation.content = updated
            translation.save(update_fields=['content'])


def restructure_game_objects(apps, schema_editor):
    Rulebook = apps.get_model('common', 'Rulebook')
    Rule = apps.get_model('common', 'Rule')
    RuleTranslation = apps.get_model('common', 'RuleTranslation')
    RuleVisualGuide = apps.get_model('common', 'RuleVisualGuide')
    RuleVisualGuideTranslation = apps.get_model('common', 'RuleVisualGuideTranslation')

    try:
        book = Rulebook.objects.get(slug='comprehensive')
    except Rulebook.DoesNotExist:
        return
    rules = list(Rule.objects.filter(rulebook_id=book.pk).order_by('priority', 'pk'))
    if not rules:
        return
    aliases = _alias_map(rules)
    found = [alias for alias in CORE_REQUIRED if alias in aliases]
    if not found:
        return
    missing = [alias for alias in CORE_REQUIRED if alias not in aliases]
    if missing:
        raise RuntimeError(
            '종합 규칙서의 객체 조항 앵커가 일부 누락되어 '
            f'v0.5 객체 마이그레이션을 적용할 수 없습니다: {", ".join(missing)}'
        )

    object_root = aliases['chapter-1']
    setup_deck_section = Rule.objects.get(pk=aliases['rule-3-5-1'].parent_id)

    player_clause = aliases.get('rule-3-2-1')
    if player_clause is not None and player_clause.parent_id:
        player_section = Rule.objects.get(pk=player_clause.parent_id)
    else:
        player_section = aliases.get('rule-players')
        if player_section is None or player_section.parent_id != object_root.pk:
            player_section = _new_rule(Rule, book, object_root, 'rule-players')
            player_section.show_in_toc = True
            player_section.save(update_fields=['show_in_toc'])

    deck_clause = aliases.get('rule-3-1-1')

    new_aliases = ('rule-game-object-card', 'rule-card-common-information', 'rule-card-character-information')
    if 'rule-game-object-card' in aliases:
        card_section = Rule.objects.get(pk=aliases['rule-game-object-card'].parent_id)
    elif deck_clause is not None and deck_clause.parent_id:
        card_section = Rule.objects.get(pk=deck_clause.parent_id)
    else:
        card_section = aliases.get('rule-meaning-of-deck')
        if card_section is None or card_section.parent_id != object_root.pk:
            card_section = (
                Rule.objects
                .filter(rulebook_id=book.pk, parent_id=object_root.pk)
                .exclude(pk=player_section.pk)
                .order_by('priority', 'pk')
                .first()
            )
        if card_section is None:
            card_section = _new_rule(Rule, book, object_root, 'rule-cards')
            card_section.show_in_toc = True
            card_section.save(update_fields=['show_in_toc'])

    old_card_sections = []
    for alias in ('rule-3-3-1', 'rule-3-4-1', 'rule-11-1-1', 'rule-11-2-1'):
        section = Rule.objects.get(pk=aliases[alias].parent_id)
        if section.pk not in {card_section.pk, player_section.pk, setup_deck_section.pk}:
            old_card_sections.append(section)
    for section in {item.pk: item for item in old_card_sections}.values():
        _merge_section(Rule, RuleTranslation, RuleVisualGuide, section, card_section)

    if deck_clause is None:
        deck_clause = _new_rule(Rule, book, setup_deck_section, 'rule-3-1-1')
        aliases['rule-3-1-1'] = deck_clause
    deck_clause.parent_id = setup_deck_section.pk
    deck_clause.show_in_toc = False
    deck_clause.is_public = True
    deck_clause.save(update_fields=['parent', 'show_in_toc', 'is_public'])

    player_section.parent_id = object_root.pk
    player_section.priority = 10
    player_section.show_in_toc = True
    player_section.is_public = True
    player_section.save(update_fields=['parent', 'priority', 'show_in_toc', 'is_public'])
    card_section.parent_id = object_root.pk
    card_section.priority = 20
    card_section.show_in_toc = True
    card_section.is_public = True
    card_section.save(update_fields=['parent', 'priority', 'show_in_toc', 'is_public'])
    _add_alias(player_section, 'rule-players')
    _add_alias(card_section, 'rule-cards')
    player_section.save(update_fields=['reference_aliases'])
    card_section.save(update_fields=['reference_aliases'])
    _set_section(RuleTranslation, player_section, SECTION_TITLES['player'])
    _set_section(RuleTranslation, card_section, SECTION_TITLES['card'])
    _set_section(
        RuleTranslation,
        object_root,
        {'ko': '게임 내 객체의 정의', 'en': 'Definitions of Game Objects', 'ja': 'ゲーム内オブジェクトの定義'},
        ROOT_CONTENT,
    )

    for reference in new_aliases:
        if reference not in aliases:
            aliases[reference] = _new_rule(Rule, book, card_section, reference)

    for _key, reference in PLAYER_ORDER:
        if reference not in aliases:
            aliases[reference] = _new_rule(Rule, book, player_section, reference)

    for key, alias in PLAYER_ORDER:
        rule = aliases[alias]
        rule.parent_id = player_section.pk
        rule.show_in_toc = False
        rule.is_public = True
        rule.save(update_fields=['parent', 'show_in_toc', 'is_public'])
        _set_translation(RuleTranslation, rule, CLAUSES[key])

    for key, alias in CARD_ORDER:
        rule = aliases[alias]
        rule.parent_id = card_section.pk
        rule.show_in_toc = False
        rule.is_public = True
        rule.save(update_fields=['parent', 'show_in_toc', 'is_public'])
        _set_translation(RuleTranslation, rule, CLAUSES[key])

    for index, (_key, alias) in enumerate(PLAYER_ORDER, start=1):
        Rule.objects.filter(pk=aliases[alias].pk).update(priority=index * 10)
    for index, (_key, alias) in enumerate(CARD_ORDER, start=1):
        Rule.objects.filter(pk=aliases[alias].pk).update(priority=index * 10)

    _set_translation(RuleTranslation, deck_clause, CLAUSES['deck'])
    setup_children = list(
        Rule.objects
        .filter(rulebook_id=book.pk, parent_id=setup_deck_section.pk)
        .exclude(pk=deck_clause.pk)
        .order_by('priority', 'pk')
    )
    for index, rule in enumerate([deck_clause, *setup_children], start=1):
        Rule.objects.filter(pk=rule.pk).update(priority=index * 10)

    other_object_children = list(
        Rule.objects
        .filter(rulebook_id=book.pk, parent_id=object_root.pk)
        .exclude(pk__in=[player_section.pk, card_section.pk])
        .order_by('priority', 'pk')
    )
    for section in other_object_children:
        _merge_section(Rule, RuleTranslation, RuleVisualGuide, section, card_section)
    Rule.objects.filter(pk=player_section.pk).update(priority=10)
    Rule.objects.filter(pk=card_section.pk).update(priority=20)

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
            _set_section(
                RuleTranslation,
                revision,
                {'ko': '개정 이력', 'en': 'Revision History', 'ja': '改訂履歴'},
                REVISION_CONTENT,
            )

    _update_judgment_map(RuleVisualGuideTranslation, book)
    book.version = '0.5-web'
    book.updated_on = date(2026, 9, 1)
    book.save(update_fields=['version', 'updated_on'])


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0018_expand_game_area_definitions'),
    ]

    operations = [
        migrations.RunPython(restructure_game_objects, migrations.RunPython.noop),
    ]
