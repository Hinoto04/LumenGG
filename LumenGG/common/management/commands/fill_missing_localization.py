import copy
import re
import unicodedata

from django.core.management.base import BaseCommand
from django.db import transaction

from card.models import Card, CardTranslation, Character, CharacterTranslation
from common.localization import SUPPORTED_TRANSLATION_LANGUAGES, render_localized_markup
from common.models import TranslationSource, TranslationValue
from common.localization_batches.batch_20260817 import (
    TRANSLATIONS as REVIEW_BATCH_TRANSLATIONS,
    normalize_semantic_card_tokens,
)


HANGUL_RE = re.compile(r'[가-힣]')

STATUS_TRANSLATED = TranslationValue.STATUS_TRANSLATED
STATUS_REVIEW = TranslationValue.STATUS_NEEDS_REVIEW
CARD_TRANSLATION_FIELDS = {
    'name', 'ruby', 'text', 'detail_text', 'keyword', 'hiddenKeyword', 'search',
}

MANUAL_TEXTS = {
    'ui.tournament': {
        'ja': ('トーナメント', STATUS_TRANSLATED),
    },
    'ui.ui_11600c9ada': {
        'en': (' item(s)', STATUS_TRANSLATED),
    },
    'character.minyeongi.name': {
        'en': ('MINYEONGI', STATUS_TRANSLATED),
        'ja': ('ミニョンイ', STATUS_TRANSLATED),
    },
    'character.minyeongi.group': {
        'en': ('Neutral', STATUS_TRANSLATED),
        'ja': ('ニュートラル', STATUS_TRANSLATED),
    },
}
for _source_key, _translations in REVIEW_BATCH_TRANSLATIONS.items():
    for _language, _text in _translations.items():
        MANUAL_TEXTS.setdefault(_source_key, {})[_language] = (_text, STATUS_TRANSLATED)

CHARACTER_DESCRIPTIONS = {
    'setsumei': {
        'en': 'Neutral character',
        'ja': 'ニュートラルキャラクター',
    },
    'nya': {
        'en': 'A hidden cat who broke free with late-blooming knowledge',
        'ja': '晩学の知識とともに抜け出した隠れた猫',
    },
    'route': {
        'en': 'A path that seeks to illuminate a world lost to Nox',
        'ja': 'ノクスに敗れた世界を照らそうとする道',
    },
    'delphi': {
        'en': 'Leave it to me! Perfect mechanic girl',
        'ja': '誰でも任せて！完璧整備少女',
    },
    'kiss': {
        'en': 'The elusive phantom thief appears!',
        'ja': '神出鬼没な怪盗登場！',
    },
    'wolf': {
        'en': 'The Empire’s loyal, brutal, emotionless wolf',
        'ja': '帝国に忠実で残酷な、感情なき狼',
    },
    'viola': {
        'en': 'A silver-bond dancer chasing an enchanting dance',
        'ja': '魅惑的な舞を追う銀縁の舞姫',
    },
    'tao': {
        'en': 'Disciple of all creation, Bagua yin-yang fox martial artist',
        'ja': '森羅万象の弟子、八卦陰陽の狐拳士',
    },
    'lita': {
        'en': 'Saintess of pure starlight',
        'ja': '純粋な星光の聖女',
    },
    'reve': {
        'en': 'A veil of night where even the wind falls silent',
        'ja': '風さえ沈黙する夜の帳',
    },
    'rin': {
        'en': 'Indomitable fighting princess, striker of blazing fire',
        'ja': '不屈の闘姫、炎華のストライカー',
    },
    'yohann': {
        'en': 'Perfect Double-O, secret agent',
        'ja': 'パーフェクト・ダブルオー、シークレットエージェント',
    },
    'ezebel': {
        'en': 'Red dress of vanity, queen of screams',
        'ja': '虚飾の赤いドレス、悲鳴の女王',
    },
    'eomong': {
        'en': 'From spring in full bloom...',
        'ja': '花咲き誇る春の盛りから...',
    },
    'chimera': {
        'en': 'Failed work of profane madness, a rag of torn souls',
        'ja': '冒涜的な狂気の失敗作、裂かれた魂のぼろ布',
    },
    'muyoung': {
        'en': 'Nameless omen, swordsman of deep blue',
        'ja': '名もなき凶兆、紺碧の剣客',
    },
    'pinp': {
        'en': 'Cockpit-bound spirit, enhanced pilot No. 5',
        'ja': 'コックピットの地縛霊、強化パイロット5号',
    },
    'cmyk': {
        'en': 'A rhythm found beyond formula\nA vivid melody crossing silence\nA beat quietly burning in ash\nA bass note echoing after gunfire',
        'ja': '公式を外れて見つけた音律\n沈黙を横切る鮮やかなメロディ\n灰の中で静かに燃えるビート\n銃声の後に響く低音',
    },
    'minyeongi': {
        'en': 'Moon goddess who grants wishes',
        'ja': '願いを叶える月の女神',
    },
}

RUBY_TRANSLATIONS = {
    'card.CB01-AT-025.ruby': {'en': 'Unlimited', 'ja': 'アンリミテッド'},
    'card.CB01-AT-026.ruby': {'en': 'Skyfall', 'ja': 'スカイフォール'},
    'card.CB01-AT-027.ruby': {'en': 'Meteor Storm Kick: 03', 'ja': 'メテオストームキック：03'},
    'card.CB02-AT-032.ruby': {'en': 'Sky Split Kick', 'ja': 'スカイスプリットキック'},
    'card.CB02-AT-033.ruby': {'en': 'Halo Arts', 'ja': 'ヘイローアーツ'},
    'card.CRS-AT-043.ruby': {'en': 'Engage!', 'ja': 'エンゲージ！'},
    'card.CRS-AT-044.ruby': {'en': 'Spiral String', 'ja': 'スパイラルストリング'},
    'card.CRS-AT-045.ruby': {'en': 'Mandarising', 'ja': 'マンダライジング'},
    'card.DFR-AT-023.ruby': {'en': 'Hyper Tao!', 'ja': 'ハイパータオ！'},
    'card.LMI-AT-043.ruby': {'en': 'Caesar Scrapper', 'ja': 'シーザースクラッパー'},
    'card.LMI-AT-044.ruby': {'en': 'Wave Cannon', 'ja': 'ウェーブキャノン'},
    'card.LMI-AT-045.ruby': {'en': 'Dodge Roll', 'ja': 'ドッジロール'},
    'card.PMP-AT-036.ruby': {'en': 'Black Hole Finger!', 'ja': 'ブラックホールフィンガー！'},
    'card.PMP-AT-037.ruby': {'en': 'Shining Ray Slap', 'ja': 'シャイニングレイスラップ'},
    'card.PMP-AT-038.ruby': {'en': 'Dolphin Flow', 'ja': 'ドルフィンフロー'},
    'card.UNC-AT-001.ruby': {'en': 'Extrike', 'ja': 'エクストライク'},
    'card.UNC-AT-002.ruby': {'en': 'Rise Falcon Kick', 'ja': 'ライズファルコンキック'},
    'card.UNC-AT-003.ruby': {'en': 'Grand Sweeper', 'ja': 'グランスイーパー'},
    'card.UNC-AT-004.ruby': {'en': 'Tiger Fist', 'ja': 'タイガーフィスト'},
    'card.UNC-AT-005.ruby': {'en': 'Dragon Drive', 'ja': 'ドラゴンドライブ'},
    'card.UNC-AT-006.ruby': {'en': 'Machine Gun Rush', 'ja': 'マシンガンラッシュ'},
    'card.UNC-AT-007.ruby': {'en': 'Activate!', 'ja': 'アクティベート！'},
    'card.UNC-AT-008.ruby': {'en': 'Downforce', 'ja': 'ダウンフォース'},
    'card.UNC-AT-009.ruby': {'en': 'Divergent Kick', 'ja': 'ダイバージェントキック'},
    'card.UNC-AT-010.ruby': {'en': 'Overwhelming Charge', 'ja': 'オーバーウェルミングチャージ'},
    'card.UNC-PS-001.ruby': {'en': 'Super Generator', 'ja': 'スーパージェネレーター'},
}

CB03_CARD_TRANSLATIONS = {
    'CB03-PS-001': {
        'name': {'en': 'High Tension', 'ja': 'ハイテンション'},
        'text': {
            'en': '①During the Lumen Phase, if your FP is 5 or higher, you gain [[state-card:CB03-PS-001]] until end of turn. During this turn, your opponent cannot dodge Techniques with special judgments.\n②[[state-card:CB03-PS-001]]: When your opponent guards, you lose 1 FP and take 100 damage.',
            'ja': '①ルーメンフェイズ時、自分のFPが5以上の場合、このターン終了時まで自分は[[state-card:CB03-PS-001]]状態になる。このターン中、相手は技を特殊判定で回避できない。\n②[[state-card:CB03-PS-001]]：相手がガードした時、自分は1FPを失い100ダメージを受ける。',
        },
    },
    'CB03-AT-001': {
        'name': {'en': 'Authority of the Moon', 'ja': '月の権能'},
        'text': {
            'en': 'This Technique can only be used if your HP is 2000 or less.\n①[[state-card:CB03-PS-001]]: Before judgment, negate 1 Attack Technique in your opponent’s Battle Zone and return it to their hand.\n②On combo, this can be used after the 3rd Combo.\n③After use, break this Technique. Then, you cannot catch this turn.',
            'ja': 'この技は自分の体力が2000以下の場合のみ使用できる。\n①[[state-card:CB03-PS-001]]：判定前、相手のバトルゾーンの攻撃技1枚を無効にして相手の手札に戻す。\n②コンボ時、3コンボ後に使用できる。\n③使用後、この技をブレイクする。その後、このターン自分はキャッチできない。',
        },
    },
    'CB03-AT-002': {
        'name': {'en': 'I’ve Got My Eye on You', 'ja': '君に目をつけた'},
        'text': {
            'en': '①On hit or counter, you may send this Technique to your opponent’s Lumen Zone. If you do, gain 5 FP and you cannot catch this turn.\n②While this Technique is in a Lumen Zone, if you take damage, take 200 damage and send this Technique to its original owner’s List.',
            'ja': '①ヒットまたはカウンター時、この技を相手のルーメンゾーンに送ってもよい。その場合、自分は5FPを得て、このターンキャッチできない。\n②この技がルーメンゾーンにある間、自分がダメージを受けた場合、200ダメージを受け、この技を元の持ち主のリストに送る。',
        },
    },
    'CB03-AT-003': {
        'name': {'en': 'Moonlight Punch', 'ja': '月光パンチ'},
        'text': {
            'en': '①[[state-card:CB03-PS-001]]: On hit or counter, you may catch with a <Speed 5 [[character:minyeongi]]> Technique from your hand or List.',
            'ja': '①[[state-card:CB03-PS-001]]：ヒットまたはカウンター時、手札またはリストの〈速度5 [[character:minyeongi]]〉技でキャッチできる。',
        },
    },
    'CB03-AT-004': {
        'name': {'en': 'Moonlight Kick', 'ja': '月光キック'},
        'text': {
            'en': '①On counter, if your opponent’s Technique is a <Hand> or <Foot> judgment Technique, change this Technique’s counter judgment to <+5>.',
            'ja': '①カウンター時、相手の技が〈手〉または〈足〉判定の技である場合、この技のカウンター判定を〈+5〉に変更する。',
        },
    },
    'CB03-AT-005': {
        'name': {'en': 'Triple Barrage', 'ja': 'トリプルバラージ'},
        'text': {
            'en': '①[[state-card:CB03-PS-001]]: Before judgment, add the <Speed 5 or lower High/Mid/Low Dodge> special judgment and change this Technique’s counter judgment to <+5>.',
            'ja': '①[[state-card:CB03-PS-001]]：判定前、〈速度5以下 上段/中段/下段回避〉特殊判定を追加し、この技のカウンター判定を〈+5〉に変更する。',
        },
    },
    'CB03-AT-006': {
        'name': {'en': 'Moonlight Arrow', 'ja': '月光の矢'},
        'text': {
            'en': '①[[state-card:CB03-PS-001]]: On hit/counter/combo, gain 1 Technique from the List.\n②On catch, this can be used at <Speed 5>. If so, this Technique’s damage -400.',
            'ja': '①[[state-card:CB03-PS-001]]：ヒット/カウンター/コンボ時、リストから技1枚を獲得する。\n②キャッチ時、〈速度5〉として使用できる。その場合、この技のダメージ-400。',
        },
    },
    'CB03-AT-007': {
        'name': {'en': 'Nemesis', 'ja': 'ネメシス'},
        'text': {
            'en': '①[[state-card:CB03-PS-001]]: Before judgment, your opponent cannot guard or clash this Technique. Then, this Technique’s damage +200.\n②Before judgment, lock both Techniques’ Speeds.',
            'ja': '①[[state-card:CB03-PS-001]]：判定前、相手はこの技をガードおよび相殺できない。その後、この技のダメージ+200。\n②判定前、お互いの技の速度を固定する。',
        },
    },
    'CB03-AT-008': {
        'name': {'en': 'Moonlight Armbar', 'ja': '月光アームバー'},
        'text': {
            'en': 'This Technique can only dodge Techniques with Speed 6 or lower.\n①On combo, end Combo Time after use.',
            'ja': 'この技は速度6以下の技のみ回避できる。\n①コンボ時、使用後にコンボタイムを終了する。',
        },
    },
    'CB03-AT-009': {
        'name': {'en': 'Hop-Hop Rush', 'ja': 'ぴょんぴょんラッシュ'},
        'text': {
            'en': '①Before judgment, if your opponent’s Technique is a Defense Technique, change this Technique’s position judgment to <Mid>.\n②On catch, this can be used at <Speed 8>. If so, change this Technique’s hit judgment to <Combo>.',
            'ja': '①判定前、相手の技が防御技の場合、この技の位置判定を〈中段〉に変更する。\n②キャッチ時、〈速度8〉として使用できる。その場合、この技のヒット判定を〈コンボ〉に変更する。',
        },
    },
    'CB03-AT-010': {
        'name': {'en': 'Dropkick!', 'ja': 'ドロップキック！'},
        'text': {
            'en': 'This Technique can only dodge Techniques with Speed 9 or lower.\n①On counter, this Technique’s damage +200.\n②[[state-card:CB03-PS-001]]: When your opponent dodges, gain 5 FP.',
            'ja': 'この技は速度9以下の技のみ回避できる。\n①カウンター時、この技のダメージ+200。\n②[[state-card:CB03-PS-001]]：相手が回避した時、5FPを得る。',
        },
    },
    'CB03-AT-011': {
        'name': {'en': 'Moonlight Stomp', 'ja': '月光踏み'},
        'text': {
            'en': '①[[state-card:CB03-PS-001]]: On combo, ignoring Speed, this can be chained after a Technique with a [[state-card:CB03-PS-001]] effect.\nIf so, if it is after the 3rd Combo, damage scaling does not apply.',
            'ja': '①[[state-card:CB03-PS-001]]：コンボ時、速度を無視して[[state-card:CB03-PS-001]]効果を持つ技の後につなげられる。\nその場合、3コンボ後ならダメージ補正を適用しない。',
        },
    },
    'CB03-AT-012': {
        'name': {'en': 'Moonlight Radiance', 'ja': '月光輝'},
        'text': {
            'en': 'This Technique cannot be dodged.\n①[[state-card:CB03-PS-001]]: On hit/counter/combo, during this turn’s Recovery Phase, gain 5 FP.',
            'ja': 'この技は回避できない。\n①[[state-card:CB03-PS-001]]：ヒット/カウンター/コンボ時、このターンのリカバリーフェイズに5FPを得る。',
        },
    },
    'CB03-AT-013': {
        'name': {'en': 'Teabag Taunt', 'ja': 'ティーバッグ挑発'},
        'text': {
            'en': '①After judgment, if you did not take damage, return the Techniques in both players’ Battle Zones to their respective hands and perform the Ready Phase again. If you do, during this turn your opponent can ready only Attack Techniques, and before judgment increase this Technique’s damage by your opponent’s Technique’s damage.',
            'ja': '①判定後、ダメージを受けていないなら、お互いのバトルゾーンの技をそれぞれ手札に戻し、レディフェイズを再び行う。その場合、このターン中、相手は攻撃技のみレディでき、判定前に相手の技のダメージ分だけ自分の技のダメージを上げる。',
        },
    },
    'CB03-AT-019': {
        'name': {'en': 'Superflame Rakshasa Strike', 'ja': '超炎羅刹肘'},
        'text': {
            'en': '①Before judgment, if your opponent’s Technique has a <Dodge> special judgment, this Technique is locked at <Speed 6>.\n②When your opponent guards, lose 1 FP for each 【Ember】 counter. (max 8)\n③On counter, gain 1 FP for each 【Ember】 counter. (max 9)',
            'ja': '①判定前、相手の技に〈回避〉特殊判定がある場合、この技は〈速度6〉で固定される。\n②相手がガードした時、【火種】カウンター1個につき1FPを失う。（最大8）\n③カウンター時、【火種】カウンター1個につき1FPを得る。（最大9）',
        },
    },
    'CB03-AT-022': {
        'name': {'en': 'Order: Aegis', 'ja': 'オーダー：アイギス'},
        'text': {
            'en': '①Before judgment, choose 1 card in your opponent’s hand and reveal it to each other. If that Technique is a Defense Technique, gain all of its defense judgments.\n②[[state:disaster_one]]: After judgment, if you did not take damage, choose 1 card in your opponent’s hand, declare odd or even, and both players reveal the chosen card’s Speed.\n-If correct, gain 6 FP and your opponent reveals that Technique this turn.\n-If incorrect, send this Technique to the List.\n③After use, if you activated effect ②, perform the Ready Phase again.',
            'ja': '①判定前、相手の手札を1枚選び、お互いに確認する。その技が防御技なら、その技の防御判定をすべて得る。\n②[[state:disaster_one]]：判定後、ダメージを受けていないなら、相手の手札を1枚選び、奇数または偶数を宣言し、選んだカードの速度をお互いに確認する。\n-当てた場合、6FPを得て、このターン相手はその技を公開する。\n-外した場合、この技をリストに送る。\n③使用後、②効果を発動していたならレディフェイズを再び行う。',
        },
    },
    'CB03-AT-028': {
        'name': {'en': 'Wall Oni Wild Dance', 'ja': '壁鬼乱舞'},
        'text': {
            'en': '①On hit or counter, if there are 3 or more [[card:RFS-AT-002]] in the Lumen Zone, each [[card:RFS-AT-002]] used this turn gets damage +100 and its hit judgment changes to <+1>. Then, gain [[state:blue_flame]] until the end of the next turn.',
            'ja': '①ヒットまたはカウンター時、ルーメンゾーンの[[card:RFS-AT-002]]が3枚以上ある場合、このターン使用する[[card:RFS-AT-002]]のダメージ+100、ヒット判定を〈+1〉に変更する。その後、次のターン終了時まで[[state:blue_flame]]状態を得る。',
        },
    },
    'CB03-AT-031': {
        'name': {'en': 'R ARM: Revolver Launcher', 'ja': 'R ARM：リボルバーランチャー'},
        'text': {
            'en': '"R ARM" Techniques can only have 1 copy placed in the Lumen Zone.\n①During the Lumen Phase, you may discard 1 card from your hand. If you do, skip your next turn’s Lumen Phase, and this turn, each time you deal damage with a [[character:pinp]] Technique, deal 100 damage to your opponent.',
            'ja': '「R ARM」名を含む技はルーメンゾーンに1枚しか配置できない。\n①ルーメンフェイズ時、手札を1枚捨ててもよい。その場合、次のターンのルーメンフェイズをスキップし、このターン[[character:pinp]]の技でダメージを与えるたび、相手に100ダメージを与える。',
        },
    },
    'CB03-AT-033': {
        'name': {'en': 'Drum Phalanx', 'ja': 'ドラムファランクス'},
        'text': {
            'en': '①[[token:drum]] (If set to a [[character:cmyk]] Technique, gain 1 FP on use. This effect does not stack.)\n②On guard, take 200 damage. Then, you may catch with the set Technique with <Speed 8 or lower>.',
            'ja': '①[[token:drum]]（[[character:cmyk]]の技にセットされている場合、使用時に1FPを得る。この効果は重複しない。）\n②ガード時、200ダメージを受ける。その後、セットされた〈速度8以下〉の技でキャッチできる。',
        },
    },
}

REVIEW_NAME_KEYS = {
    'card.CB03-AT-002.name',
    'card.CB03-AT-009.name',
    'card.CB03-AT-013.name',
    'card.CB03-AT-019.name',
    'card.CB03-AT-028.name',
}

PHRASE_TRANSLATIONS = {
    'en': {
        '강력한 얼티밋': 'Powerful Ultimate',
        '강력한 기본기 싸움': 'Strong fundamentals',
        '강력한 방어기': 'Powerful defense Technique',
        '초반 심리전': 'Early mind games',
        '압박 주축 카드': 'Core pressure card',
        '강력한 콤보용': 'Powerful combo tool',
        '주요 견제기': 'Main poke',
        '돌파력 강한 하단': 'Strong low breakthrough',
        '강력한 전용 방어기': 'Powerful exclusive defense Technique',
        '게임 제일의 하단 시동기': 'The game’s best low starter',
        '패 컨트롤 수단': 'Hand control tool',
        '강력한 뒷심': 'Powerful late game',
        '불리 상황을 무마하는 힘': 'Power to defuse disadvantage',
        '가장 강력한 가드': 'Strongest guard',
        '토큰 공급원': 'Token source',
        '훌륭한 가드 기술': 'Excellent guard Technique',
        '큰 대미지의 역전 찬스': 'High-damage comeback chance',
        '불씨 쌓기의 중간다리': 'Bridge for building Ember',
        '토큰에 따라 강해지는 카드': 'Card empowered by tokens',
        '가드 불가 강력한 기술': 'Powerful unblockable Technique',
        '판도를 바꾸는 기술': 'Game-changing Technique',
        '강력한 콤보 마무리': 'Powerful combo finisher',
        '체력 코스트 보충': 'HP cost support',
        '강력한 콤보 시동기': 'Powerful combo starter',
        '다른 캐릭터 기술 도용': 'Uses other characters’ Techniques',
        '손패 수급': 'Hand supply',
        '무영의 핵심 자원': 'Muyoung’s core resource',
        '강력한 회피기': 'Powerful dodge Technique',
        '손패 비소모 콤보 ': 'Combo without spending hand cards',
        '데미지 누적 시스템': 'Damage stacking system',
        '안정적 방어기': 'Reliable defense Technique',
        '브레이크된 카드 수': 'Broken card count',
        '대기': 'Standby',
        '자신의 체력이 2500 이하라면 자동으로 활성화됩니다.': 'Automatically active if your HP is 2500 or less.',
    },
    'ja': {
        '강력한 얼티밋': '強力なアルティメット',
        '강력한 기본기 싸움': '強力な基本技勝負',
        '강력한 방어기': '強力な防御技',
        '초반 심리전': '序盤の読み合い',
        '압박 주축 카드': '圧力の主軸カード',
        '강력한 콤보용': '強力なコンボ用',
        '주요 견제기': '主要けん制技',
        '돌파력 강한 하단': '突破力の高い下段',
        '강력한 전용 방어기': '強力な専用防御技',
        '게임 제일의 하단 시동기': 'ゲーム屈指の下段始動技',
        '패 컨트롤 수단': '手札コントロール手段',
        '강력한 뒷심': '強力な終盤力',
        '불리 상황을 무마하는 힘': '不利状況を覆す力',
        '가장 강력한 가드': '最強のガード',
        '토큰 공급원': 'トークン供給源',
        '훌륭한 가드 기술': '優秀なガード技',
        '큰 대미지의 역전 찬스': '大ダメージの逆転チャンス',
        '불씨 쌓기의 중간다리': '火種を積む中継ぎ',
        '토큰에 따라 강해지는 카드': 'トークンに応じて強くなるカード',
        '가드 불가 강력한 기술': 'ガード不能の強力な技',
        '판도를 바꾸는 기술': '戦況を変える技',
        '강력한 콤보 마무리': '強力なコンボ締め',
        '체력 코스트 보충': '体力コスト補助',
        '강력한 콤보 시동기': '強力なコンボ始動',
        '다른 캐릭터 기술 도용': '他キャラクターの技を流用',
        '손패 수급': '手札補給',
        '무영의 핵심 자원': 'ムヨンの核心リソース',
        '강력한 회피기': '強力な回避技',
        '손패 비소모 콤보 ': '手札を消費しないコンボ',
        '데미지 누적 시스템': 'ダメージ蓄積システム',
        '안정적 방어기': '安定した防御技',
        '브레이크된 카드 수': 'ブレイクされたカード数',
        '대기': '待機',
        '자신의 체력이 2500 이하라면 자동으로 활성화됩니다.': '自分の体力が2500以下なら自動で有効になります。',
    },
}

MANUAL_TERM_SOURCES = {
    'term.tag.rebattle': {
        'category': 'tag',
        'source_text': '재전투',
        'field_name': 'tag',
        'values': {
            'en': 'Rebattle',
            'ja': '再戦闘',
        },
    },
}


class Command(BaseCommand):
    help = 'Fill currently missing translation catalog values.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        stats = {'translated': 0, 'needs_review': 0, 'skipped': 0, 'normalized': 0}

        with transaction.atomic():
            self.ensure_manual_sources()
            self.normalize_empty_sources(stats)
            lookup = self.translation_lookup()
            for source in TranslationSource.objects.filter(is_active=True).prefetch_related('values').order_by('key'):
                for language in SUPPORTED_TRANSLATION_LANGUAGES:
                    value = self.value_for(source, language)
                    if not self.should_update(source, value):
                        continue
                    text, data, status = self.translation_for(source, language, lookup)
                    if text == '' and data == {} and source.source_text and not self.is_hidden_keyword_source(source):
                        stats['skipped'] += 1
                        continue
                    if (
                        value.pk
                        and value.text == text
                        and value.data == data
                        and value.status == status
                    ):
                        continue
                    value.text = text
                    value.data = data
                    value.status = status
                    value.save()
                    stats['needs_review' if status == STATUS_REVIEW else 'translated'] += 1

            if not dry_run:
                self.sync_legacy_rows()

            if dry_run:
                transaction.set_rollback(True)

        suffix = ' (dry-run)' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'fill_missing_localization{suffix}: translated={stats["translated"]}, needs_review={stats["needs_review"]}, skipped={stats["skipped"]}, normalized={stats["normalized"]}'
        ))

    def value_for(self, source, language):
        for value in source.values.all():
            if value.language == language:
                return value
        return TranslationValue(source=source, language=language)

    def is_missing(self, value):
        return (
            value.pk is None
            or value.status == TranslationValue.STATUS_MISSING
            or (value.text == '' and value.data == {})
        )

    def should_update(self, source, value):
        if self.is_empty_source(source):
            return False
        if self.is_hidden_keyword_source(source):
            return True
        if source.key in REVIEW_BATCH_TRANSLATIONS:
            return True
        if self.is_missing(value):
            return True
        if (
            source.category == 'card'
            and source.field_name in ('keyword', 'search')
            and value.status == TranslationValue.STATUS_NEEDS_REVIEW
            and HANGUL_RE.search(value.text or '')
        ):
            return True
        return False

    def is_empty_source(self, source):
        return not source.source_text and not source.source_data

    def is_hidden_keyword_source(self, source):
        return source.category == 'card' and source.field_name == 'hiddenKeyword'

    def normalize_empty_sources(self, stats):
        values = TranslationValue.objects.filter(
            source__source_text='',
            source__source_data={},
            text='',
            data={},
        ).exclude(status=TranslationValue.STATUS_TRANSLATED)
        stats['normalized'] += values.update(status=TranslationValue.STATUS_TRANSLATED)

    def translation_for(self, source, language, lookup):
        manual = self.manual_text_for(source, language)
        if manual is not None:
            text, status = manual
            return text, {}, status

        if source.category == 'character' and source.field_name == 'description':
            character_key = source.key.split('.')[1]
            text = CHARACTER_DESCRIPTIONS.get(character_key, {}).get(language, '')
            if text:
                return text, {}, STATUS_REVIEW

        if source.category == 'character' and source.field_name == 'datas':
            data = self.translate_data(source.source_data, language, lookup)
            return '', data, self.status_for_data(data)

        if source.category == 'card' and source.field_name == 'detail_text':
            text = self.translate_plain_text(source.source_text, language, lookup)
            return text, {}, STATUS_REVIEW

        if source.category == 'card' and source.field_name in ('keyword', 'search'):
            text = self.translate_slash_text(source.source_text, language, lookup)
            return text, {}, self.status_for_text(text)

        if self.is_hidden_keyword_source(source):
            return self.hidden_keyword_for(source, language), {}, STATUS_TRANSLATED

        text = self.translate_plain_text(source.source_text, language, lookup)
        return text, {}, self.status_for_text(text)

    def manual_text_for(self, source, language):
        if source.key in MANUAL_TEXTS and language in MANUAL_TEXTS[source.key]:
            text, status = MANUAL_TEXTS[source.key][language]
            return normalize_semantic_card_tokens(text), status

        if source.key in RUBY_TRANSLATIONS and language in RUBY_TRANSLATIONS[source.key]:
            return RUBY_TRANSLATIONS[source.key][language], STATUS_TRANSLATED

        if source.key.startswith('card.'):
            parts = source.key.split('.')
            if len(parts) == 3:
                code, field_name = parts[1], parts[2]
                card_data = CB03_CARD_TRANSLATIONS.get(code, {})
                if field_name in card_data and language in card_data[field_name]:
                    status = STATUS_REVIEW if source.key in REVIEW_NAME_KEYS else STATUS_TRANSLATED
                    return normalize_semantic_card_tokens(card_data[field_name][language]), status
        return None

    def translation_lookup(self):
        lookup = {}
        for source in TranslationSource.objects.filter(is_active=True).prefetch_related('values'):
            if not source.source_text:
                continue
            for value in source.values.all():
                if value.text:
                    lookup.setdefault(value.language, {})[source.source_text] = value.text

        for code, card_data in CB03_CARD_TRANSLATIONS.items():
            Korean_source = TranslationSource.objects.filter(key=f'card.{code}.name').first()
            if not Korean_source:
                continue
            for language, text in card_data.get('name', {}).items():
                lookup.setdefault(language, {})[Korean_source.source_text] = text

        for language, phrases in PHRASE_TRANSLATIONS.items():
            lookup.setdefault(language, {}).update(phrases)
        return lookup

    def ensure_manual_sources(self):
        for key, data in MANUAL_TERM_SOURCES.items():
            source, _created = TranslationSource.objects.update_or_create(
                key=key,
                defaults={
                    'category': data['category'],
                    'source_text': data['source_text'],
                    'field_name': data['field_name'],
                    'is_active': True,
                },
            )
            for language, text in data['values'].items():
                TranslationValue.objects.update_or_create(
                    source=source,
                    language=language,
                    defaults={
                        'text': text,
                        'data': {},
                        'status': STATUS_TRANSLATED,
                    },
                )

    def translate_slash_text(self, text, language, lookup):
        if not text:
            return ''
        parts = text.split('/')
        translated = [self.translate_plain_text(part, language, lookup) if part else '' for part in parts]
        return '/'.join(translated)

    def hidden_keyword_for(self, source, language):
        keywords = []
        seen = set()
        code = self.card_code_from_source(source)

        card = Card.objects.filter(code=code).first() if code else None
        localized_name = self.localized_card_name(code, language) if code else ''
        self.add_name_variants(keywords, seen, localized_name)

        for token in self.existing_hidden_keyword_tokens(source, card, language):
            if HANGUL_RE.search(token):
                continue
            self.add_keyword(keywords, seen, token)
            self.add_name_variants(keywords, seen, token)

        return self.join_keywords(keywords)

    def card_code_from_source(self, source):
        parts = source.key.split('.')
        if len(parts) == 3 and parts[0] == 'card':
            return parts[1]
        return ''

    def localized_card_name(self, code, language):
        source = TranslationSource.objects.filter(key=f'card.{code}.name').prefetch_related('values').first()
        if source:
            for value in source.values.all():
                if value.language == language and value.text:
                    return value.text

        translation = CardTranslation.objects.filter(card__code=code, language=language).first()
        if translation and translation.name:
            return translation.name

        card = Card.objects.filter(code=code).first()
        return card.name if card else ''

    def existing_hidden_keyword_tokens(self, source, card, language):
        values = [source.source_text]
        for value in source.values.all():
            if value.language == language:
                values.append(value.text)
        if card:
            translation = CardTranslation.objects.filter(card=card, language=language).first()
            if translation:
                values.append(translation.hiddenKeyword)

        tokens = []
        for value in values:
            tokens.extend(self.split_keywords(value))
        return tokens

    def split_keywords(self, text):
        return [token.strip() for token in str(text or '').split('/') if token.strip()]

    def add_name_variants(self, keywords, seen, text):
        normalized = unicodedata.normalize('NFKC', str(text or '')).strip()
        if not normalized:
            return
        no_space = re.sub(r'\s+', '', normalized)
        alnum = ''.join(character for character in no_space if character.isalnum())
        folded = alnum.casefold()

        for variant in (no_space, alnum, folded):
            if variant:
                self.add_keyword(keywords, seen, variant)

    def add_keyword(self, keywords, seen, keyword):
        keyword = str(keyword or '').strip()
        if not keyword or keyword in seen:
            return
        seen.add(keyword)
        keywords.append(keyword)

    def join_keywords(self, keywords):
        parts = []
        length = 0
        for keyword in keywords:
            additional = len(keyword) + 1
            if length + additional > CardTranslation._meta.get_field('hiddenKeyword').max_length:
                break
            parts.append(keyword)
            length += additional
        return '/'.join(parts) + '/' if parts else ''

    def translate_plain_text(self, text, language, lookup):
        if not text:
            return ''
        result = str(text)
        for source, translated in sorted(lookup.get(language, {}).items(), key=lambda item: len(item[0]), reverse=True):
            if source and translated:
                result = result.replace(source, translated)
        result = render_localized_markup(result, language)
        return result

    def translate_data(self, data, language, lookup):
        if isinstance(data, dict):
            return {
                key: self.translate_data(value, language, lookup)
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [self.translate_data(value, language, lookup) for value in data]
        if isinstance(data, str):
            return self.translate_plain_text(data, language, lookup)
        return copy.deepcopy(data)

    def status_for_text(self, text):
        return STATUS_REVIEW if HANGUL_RE.search(text or '') else STATUS_TRANSLATED

    def status_for_data(self, data):
        return STATUS_REVIEW if HANGUL_RE.search(str(data)) else STATUS_TRANSLATED

    def sync_legacy_rows(self):
        self.sync_legacy_card_rows()
        self.sync_legacy_character_rows()

    def sync_legacy_card_rows(self):
        for code, fields in CB03_CARD_TRANSLATIONS.items():
            card = Card.objects.filter(code=code).first()
            if not card:
                continue
            for language in SUPPORTED_TRANSLATION_LANGUAGES:
                translation, _created = CardTranslation.objects.get_or_create(card=card, language=language)
                changed = []
                for field_name in ('name', 'text'):
                    text = fields.get(field_name, {}).get(language)
                    if text is not None and getattr(translation, field_name) != text:
                        setattr(translation, field_name, text)
                        changed.append(field_name)
                for field_name in ('keyword', 'hiddenKeyword', 'search'):
                    source = TranslationSource.objects.filter(key=f'card.{code}.{field_name}').first()
                    if not source:
                        continue
                    value = source.values.filter(language=language).first()
                    if value and getattr(translation, field_name) != value.text:
                        setattr(translation, field_name, value.text)
                        changed.append(field_name)
                if changed:
                    translation.save(update_fields=changed)

        for key, translations in RUBY_TRANSLATIONS.items():
            _prefix, code, _field = key.split('.')
            card = Card.objects.filter(code=code).first()
            if not card:
                continue
            for language, text in translations.items():
                translation, _created = CardTranslation.objects.get_or_create(card=card, language=language)
                if translation.ruby != text:
                    translation.ruby = text
                    translation.save(update_fields=['ruby'])

        self.sync_review_batch_card_rows()
        self.sync_legacy_hidden_keywords()

    def sync_review_batch_card_rows(self):
        fields_by_card = {}
        for source_key, translations in REVIEW_BATCH_TRANSLATIONS.items():
            parts = source_key.split('.')
            if len(parts) != 3 or parts[0] != 'card':
                continue
            _prefix, code, field_name = parts
            fields_by_card.setdefault(code, {})[field_name] = translations

        for code, fields in fields_by_card.items():
            card = Card.objects.filter(code=code).first()
            if card is None:
                continue
            for language in SUPPORTED_TRANSLATION_LANGUAGES:
                translation, _created = CardTranslation.objects.get_or_create(
                    card=card,
                    language=language,
                )
                changed = []
                for field_name, values in fields.items():
                    if field_name not in CARD_TRANSLATION_FIELDS:
                        continue
                    text = values.get(language)
                    if text is None:
                        continue
                    text = normalize_semantic_card_tokens(text)
                    if getattr(translation, field_name) != text:
                        setattr(translation, field_name, text)
                        changed.append(field_name)
                if changed:
                    translation.save(update_fields=changed)

    def sync_legacy_hidden_keywords(self):
        sources = list(TranslationSource.objects.filter(
            category='card',
            field_name='hiddenKeyword',
            is_active=True,
        ).prefetch_related('values'))
        codes = [self.card_code_from_source(source) for source in sources]
        cards = {card.code: card for card in Card.objects.filter(code__in=codes)}
        translations = {
            (translation.card_id, translation.language): translation
            for translation in CardTranslation.objects.filter(
                card_id__in=[card.id for card in cards.values()],
                language__in=SUPPORTED_TRANSLATION_LANGUAGES,
            )
        }
        to_create = []
        to_update = []

        for source in sources:
            card = cards.get(self.card_code_from_source(source))
            if not card:
                continue
            for value in source.values.all():
                if value.language not in SUPPORTED_TRANSLATION_LANGUAGES:
                    continue
                key = (card.id, value.language)
                translation = translations.get(key)
                if translation is None:
                    to_create.append(CardTranslation(
                        card=card,
                        language=value.language,
                        hiddenKeyword=value.text,
                    ))
                    continue
                if translation.hiddenKeyword != value.text:
                    translation.hiddenKeyword = value.text
                    to_update.append(translation)

        if to_create:
            CardTranslation.objects.bulk_create(to_create, ignore_conflicts=True)
        if to_update:
            CardTranslation.objects.bulk_update(to_update, ['hiddenKeyword'])

    def sync_legacy_character_rows(self):
        for character in Character.objects.exclude(localization_key=''):
            for language in SUPPORTED_TRANSLATION_LANGUAGES:
                translation, _created = CharacterTranslation.objects.get_or_create(character=character, language=language)
                changed = []
                for field_name in ('name', 'description', 'group'):
                    source = TranslationSource.objects.filter(key=f'character.{character.localization_key}.{field_name}').first()
                    if source is None:
                        continue
                    value = source.values.filter(language=language).first()
                    if value and value.text and getattr(translation, field_name) != value.text:
                        setattr(translation, field_name, value.text)
                        changed.append(field_name)
                source = TranslationSource.objects.filter(key=f'character.{character.localization_key}.datas').first()
                value = source.values.filter(language=language).first() if source else None
                if value and value.data and translation.datas != value.data:
                    translation.datas = value.data
                    changed.append('datas')
                if changed:
                    translation.save(update_fields=changed)
