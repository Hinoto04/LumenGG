"""Reviewed-first localization batch prepared on 2026-08-17.

Keep this module immutable after the corresponding data migration ships.  The
migration imports these values so a fresh database receives the same catalog
content as the database on which the batch was prepared.
"""


SEMANTIC_REFERENCES = {
    'ST2-PS1': {
        'kind': 'state', 'slug': 'charge',
        'ko': '차지', 'en': 'Charge', 'ja': 'チャージ',
    },
    'ST3-PS1': {
        'kind': 'state', 'slug': 'down_stance',
        'ko': '다운 스탠스', 'en': 'Down Stance', 'ja': 'ダウンスタンス',
    },
    'ST5-PS1': {
        'kind': 'state', 'slug': 'intimidation',
        'ko': '위압', 'en': 'Intimidation', 'ja': '威圧',
    },
    'CB03-PS-001': {
        'kind': 'state', 'slug': 'high_tension',
        'ko': '하이텐션', 'en': 'High Tension', 'ja': 'ハイテンション',
    },
    'LMI-AT-056': {
        'kind': 'state', 'slug': 'guardian',
        'ko': '가디언', 'en': 'Guardian', 'ja': 'ガーディアン',
    },
    'LMI-AT-057': {
        'kind': 'state', 'slug': 'assassin',
        'ko': '어쌔신', 'en': 'Assassin', 'ja': 'アサシン',
    },
    'LMI-AT-058': {
        'kind': 'state', 'slug': 'paladin',
        'ko': '팔라딘', 'en': 'Paladin', 'ja': 'パラディン',
    },
    'CRS-AT-057': {
        'kind': 'token', 'slug': 'ember',
        'ko': '불씨', 'en': 'Ember', 'ja': '火種',
    },
    'DFR-TK-001': {
        'kind': 'token', 'slug': 'new_single',
        'ko': '뉴 싱글', 'en': 'New Single', 'ja': 'ニューシングル',
    },
    'LMI-AT-059': {
        'kind': 'token', 'slug': 'dagger',
        'ko': '단검', 'en': 'Dagger', 'ja': '短剣',
    },
    'PMP-AT-053': {
        'kind': 'token', 'slug': 'spider',
        'ko': '거미', 'en': 'Spider', 'ja': '蜘蛛',
    },
    'PMP-CS-009': {
        'kind': 'token', 'slug': 'foresight',
        'ko': '예지', 'en': 'Foresight', 'ja': '予知',
    },
}


def semantic_token_for_card(code):
    reference = SEMANTIC_REFERENCES.get(str(code or ''))
    if reference is None:
        return ''
    return f'[[{reference["kind"]}:{reference["slug"]}]]'


def normalize_semantic_card_tokens(text):
    """Normalize only references that explicitly describe state/token roles."""
    result = str(text or '')
    for code in SEMANTIC_REFERENCES:
        replacement = semantic_token_for_card(code)
        for kind in ('state-card', 'token-card', 'counter-card'):
            result = result.replace(f'[[{kind}:{code}]]', replacement)
    return result


# TranslationSource key -> language -> final catalog value.
TRANSLATIONS = {
    'card.CB03-AT-020.keyword': {
        'en': 'Rakshasa/Catch Shift/Gain Ember/',
        'ja': '羅刹/キャッチ変速/火種獲得/',
    },
    'card.CB03-AT-020.name': {
        'en': 'Rakshasa Crimson Lotus Wave',
        'ja': '羅刹紅蓮波',
    },
    'card.CB03-AT-020.search': {
        'en': 'Rakshasa/Inferno Orb/',
        'ja': '羅刹/極炎玉/',
    },
    'card.CB03-AT-020.text': {
        'en': '①On catch, this Technique can be used at <Speed 4>. If so, gain 1 [[token:ember]] Counter and return the used Technique to your hand.\n②On combo, if there are 3 [[card:CRS-AT-002]] in the Break Zone, gain 1 Technique with [[keyword:rakshasa]] in its name from the List or Break Zone.',
        'ja': '①キャッチ時、この技を〈速度4〉として使用できる。その場合、[[token:ember]]カウンターを1個得て、使用したこの技を手札に戻す。\n②コンボ時、ブレイクゾーンに[[card:CRS-AT-002]]が3枚ある場合、リストまたはブレイクゾーンからカード名に[[keyword:rakshasa]]を含む技1枚を獲得する。',
    },
    'card.CB03-AT-024.hiddenKeyword': {
        'en': 'SpiderlingBrood/spiderlingbrood/',
        'ja': 'スパイダーリングブルード/',
    },
    'card.CB03-AT-024.keyword': {
        'en': 'Grab/HP Recovery/',
        'ja': '投げ/HP回復/',
    },
    'card.CB03-AT-024.name': {
        'en': 'Spiderling Brood',
        'ja': 'スパイダーリング・ブルード',
    },
    'card.CB03-AT-024.search': {
        'en': 'Grab/',
        'ja': '投げ/',
    },
    'card.CB03-AT-024.text': {
        'en': '①On hit/counter/combo, place 2 [[token:spider]] Tokens in your opponent\'s List. (Max 4)\nIf they cannot be placed, recover 400 HP instead.\n②If this Technique\'s Grab is negated, place 1 [[token:spider]] Token in your opponent\'s List.',
        'ja': '①ヒット/カウンター/コンボ時、相手のリストに[[token:spider]]トークンを2個配置する。（最大4個）\n配置できない場合、代わりに体力を400回復する。\n②この技の投げが無効になった場合、相手のリストに[[token:spider]]トークンを1個配置する。',
    },
    'card.CB03-AT-029.hiddenKeyword': {
        'en': 'DoppelSchwerterZwei/doppelschwerterzwei/TwinBladesTwo/TwinBlades2/',
        'ja': 'ドッペルシュヴェルターツヴァイ/双剣ツヴァイ/双剣2/',
    },
    'card.CB03-AT-029.keyword': {
        'en': 'Effect Damage/Break/Gain Technique/',
        'ja': '効果ダメージ/ブレイク/技獲得/',
    },
    'card.CB03-AT-029.name': {
        'en': 'Doppel Schwerter Zwei',
        'ja': 'ドッペルシュヴェルター・ツヴァイ',
    },
    'card.CB03-AT-029.search': {'en': 'ARM/', 'ja': 'ARM/'},
    'card.CB03-AT-029.text': {
        'en': '①On hit or counter, if there are 2 Techniques with "ARM" in their names in the Lumen Zone, deal 300 damage to your opponent.\n②On combo, gain 1 [[character:pinp]] Technique from the List and break this Technique.',
        'ja': '①ヒットまたはカウンター時、ルーメンゾーンにカード名に「ARM」を含む技が2枚ある場合、相手に300ダメージを与える。\n②コンボ時、リストから[[character:pinp]]の技1枚を獲得し、この技をブレイクする。',
    },
    'card.CB03-AT-030.hiddenKeyword': {
        'en': 'TechBlaster/techblaster/', 'ja': 'テックブラスター/',
    },
    'card.CB03-AT-030.keyword': {
        'en': 'Effect Damage/Gain Technique/',
        'ja': '効果ダメージ/技獲得/',
    },
    'card.CB03-AT-030.name': {
        'en': 'Tech Blaster', 'ja': 'テックブラスター',
    },
    'card.CB03-AT-030.text': {
        'en': '①On hit or counter, discard 1 card from your hand and deal 100 damage to your opponent twice.\n②On combo, if this is after the 3rd Combo, gain 1 Technique from the List.',
        'ja': '①ヒットまたはカウンター時、手札を1枚捨て、相手に100ダメージを2回与える。\n②コンボ時、3コンボ後なら、リストから技1枚を獲得する。',
    },
    'card.CB03-AT-032.hiddenKeyword': {
        'en': 'SlapAndCrash/Slap&Crash/slapandcrash/',
        'ja': 'スラップアンドクラッシュ/スラップ＆クラッシュ/',
    },
    'card.CB03-AT-032.keyword': {
        'en': 'Bass/Speed Change/New Single/',
        'ja': 'ベース/速度変更/ニューシングル/',
    },
    'card.CB03-AT-032.name': {
        'en': 'Slap & Crash', 'ja': 'スラップ＆クラッシュ',
    },
    'card.CB03-AT-032.search': {
        'en': 'Drum/New Single/', 'ja': 'ドラム/ニューシングル/',
    },
    'card.CB03-AT-032.text': {
        'en': '①[[token:bass]]: (If set to a [[character:cmyk]] Technique, gain 1 FP on hit or counter. This effect does not stack.)\n②Before judgment, if one of the set Techniques has a [[token:drum]] effect, this Technique becomes 2 Speed faster.\n③On combo, you may set 1 [[character:cmyk]] Technique from your hand or List to a [[character:cmyk]] Technique in the Battle Zone. If you do, you may gain up to 2 [[token:new_single]] Tokens from the List.',
        'ja': '①[[token:bass]]：（[[character:cmyk]]の技にセットされている場合、ヒットまたはカウンター時に1FPを得る。この効果は重複しない。）\n②判定前、セットされた技の中に[[token:drum]]効果がある場合、この技の速度は2速くなる。\n③コンボ時、手札またはリストの[[character:cmyk]]の技1枚を、バトルゾーンの[[character:cmyk]]の技にセットできる。その場合、リストから[[token:new_single]]トークンを2個まで獲得できる。',
    },
    'card.DFR-AT-001.hiddenKeyword': {
        'en': 'Climax!/Climax/climax/',
        'ja': 'クライマックス!/クライマックス/',
    },
    'card.DFR-AT-007.hiddenKeyword': {
        'en': 'CDominant/cdominant/', 'ja': 'Cドミナント/',
    },
    'card.AWL-AT-013.detail_text': {
        'en': '①Effect: This is a mandatory effect that activates at the "On Combo" timing if this Technique is the 1st Combo Technique. Apply all of the following effects.\n-"On combo, break this Technique": Break this Technique at its "On Combo" timing.\n-"This turn, you can chain only up to the 3rd Combo": This turn, you cannot use a Technique as the 4th Combo or later.\n②Effect: This effect applies at the "On Combo" timing of the Nth Combo Technique and enables use of the following N+1 Combo Technique. [Lefi! Screw!] can be chained after a card with [[keyword:rai]] in its name, regardless of Speed.',
        'ja': '①効果：この技が1コンボ目の技である場合、「コンボ時」のタイミングに発動する強制効果です。以下の効果をすべて適用します。\n-「コンボ時、この技をブレイクする」：「コンボ時」のタイミングにこの技をブレイクします。\n-「このターン、3コンボまでしかつなげられない」：このターン、自分は4コンボ目以降の技を使用できません。\n②効果：Nコンボ目の技の「コンボ時」に適用され、次に続くN+1コンボ目の技を使用可能にする効果です。[レピ！スクリュー！]は速度に関係なく、カード名に[[keyword:rai]]を含むカードの後につなげて使用できます。',
    },
    'card.AWL-AT-015.detail_text': {
        'en': '"This Technique can be used only if there are at least 6 Attack and Defense Techniques in the Lumen Zone.": This is a continuous restriction on using this Technique and has no trigger timing.\n"Your opponent cannot clash this Technique.": This is a continuous effect with no trigger timing. Refer to it during the "Clash Check" of the "Battle Judgment" step.\n①Effect: This is a mandatory effect that activates when this Technique successfully hits or counters. Return all Neutral Techniques in your Lumen Zone to your List.',
        'ja': '「この技は、ルーメンゾーンに攻撃・防御技が6枚以上ある場合のみ使用できる。」：発動タイミングを持たず、常時適用される技の使用制限です。\n「相手はこの技を相殺できない。」：発動タイミングを持たず、常時適用される効果です。「戦闘判定」段階の「相殺確認」時に参照します。\n①効果：この技がヒットまたはカウンターに成功した時に発動する強制効果です。自分のルーメンゾーンにあるニュートラル技をすべて自分のリストに送ります。',
    },
    'card.AWL-AT-016.detail_text': {
        'en': '"This Technique dodges only Techniques with Speed 10 or higher.": This is a continuous effect with no trigger timing. Refer to it during the "Dodge Check" and "Clash Check" of the "Battle Judgment" step.\n①Effect: This is a mandatory effect that activates at the "Before Judgment" timing if the Speeds of your readied Technique and your opponent\'s readied Technique differ by 2. Neither Technique is affected by FP during the FP Adjustment step, and neither is affected by Speed-changing effects until the "After Use" timing.\n②Effect: This is a mandatory effect that activates when you successfully counter. If there is no Technique in the Battle Zone or Lumen Zone, the effect activates but does not apply anything.',
        'ja': '「この技は速度10以上の技のみ回避する」：発動タイミングを持たず、常時適用される効果です。「戦闘判定」段階の「回避確認」および「相殺確認」時に参照します。\n①効果：「判定前」のタイミングに、自分がレディした技と相手がレディした技の速度差が2である場合に発動する強制効果です。お互いの技はFP補正段階でFPの影響を受けず、「使用後」のタイミングまで速度変更効果を受けません。\n②効果：自分がカウンターに成功した場合に発動する強制効果です。バトルゾーンにもルーメンゾーンにも技がない場合、効果は発動しますが何も適用しません。',
    },
    'card.AWL-AT-017.detail_text': {
        'en': '①Effect: This is a mandatory effect that activates when you successfully catch. Send 1 Technique from your Lumen Zone to the List.\n(The caught Technique\'s "On Catch" timing is resolved after "On Use" and before "On Hit.")\n②Effect: This is a mandatory effect that activates at this Technique\'s "On Use" timing if you are in [[state:over_limit]].',
        'ja': '①効果：自分がキャッチに成功した場合に発動する強制効果です。自分のルーメンゾーンから技1枚をリストに送ります。\n（キャッチした技の「キャッチ時」は「使用時」の後、「ヒット時」の前に処理します。）\n②効果：自分が[[state:over_limit]]状態である場合、この技の「使用時」のタイミングに発動する強制効果です。',
    },
    'card.CB01-AT-006.detail_text': {
        'en': '"This Technique\'s effects can be used only if your HP is 3000 or less.": This is a continuous restriction with no trigger timing. You can use this Technique\'s effects only while you satisfy the condition of having 3000 HP or less.\n①Effect: This effect can be activated at your "On Combo" timing if you are in [[state:over_limit]].\nAfter resolving "You may break this Technique," if that action was completed, resolve the effect after "If you do."\n"This turn, you may use 1 <[[character:nya]]> Technique from the Side Deck in a combo, and break it after use.": You may use 1 <[[character:nya]]> Technique from the Side Deck that satisfies the condition for the next combo. Break that Technique after it is used.\n②Effect: This effect can be activated when [[state:over_limit]] is removed. Reduce by 500 the damage you take when [[state:over_limit]] is removed by its own effect.',
        'ja': '「この技の効果は、自分の体力が3000以下の場合のみ使用できる。」：発動タイミングを持たず、常時適用される制限です。自分の体力が3000以下という条件を満たしている場合のみ、この技の効果を使用できます。\n①効果：自分が[[state:over_limit]]状態である場合、自分の「コンボ時」のタイミングに発動できる効果です。\n「この技をブレイクできる。」を処理し、その処理が完了した場合、「その場合、」以降の効果を処理します。\n「このターン、サイドデッキから〈[[character:nya]]〉技1枚をコンボに使用でき、その技は使用後にブレイクする。」：次のコンボ条件を満たす〈[[character:nya]]〉技1枚をサイドデッキからコンボに使用でき、その技の使用後にブレイクします。\n②効果：[[state:over_limit]]状態が解除された場合に発動できる効果です。[[state:over_limit]]自身の効果によって状態が解除される時に受けるダメージを500軽減します。',
    },
    'card.CB01-AT-007.detail_text': {
        'en': '"If this Technique\'s Grab is negated, send this Technique to the Side Deck.": This applies when your opponent declares and resolves Grab Negation after this Technique\'s hit and counter results are determined during the "Battle Judgment" step. This effect is mandatory.\n①Effect: This is a continuous effect with no trigger timing while you are in [[state:over_limit]]. Refer to it during the "Guard Check" of the "Battle Judgment" step.\n②Effect: This is a mandatory effect that activates when you successfully hit.',
        'ja': '「この技の投げが無効になった場合、この技をサイドデッキに送る。」：「戦闘判定」段階でこの技のヒットおよびカウンターが決定した後、相手が投げ無効を宣言して処理した時に適用されます。適用は強制です。\n①効果：自分が[[state:over_limit]]状態である場合、発動タイミングを持たず常時適用される効果です。「戦闘判定」段階の「ガード確認」時に参照します。\n②効果：自分がヒットに成功した場合に発動する強制効果です。',
    },
    'card.CB01-AT-008.detail_text': {
        'en': '①Effect: This effect can be activated at this Technique\'s "On Use" timing if you are not in [[state:over_limit]]. Choose up to 3 Techniques from your List and send them to the Lumen Zone. If you sent 3, increase this Technique\'s damage by 100.\n②Effect: This effect can be activated when you successfully hit or counter if you are in [[state:over_limit]]. You must designate exactly 3 cards to send; if you cannot, this effect cannot be activated.\nIf the part before "If you do" was completed, apply the part after it.\nBreak this Technique at its "After Use" timing.',
        'ja': '①効果：自分が[[state:over_limit]]状態でない場合、この技の「使用時」のタイミングに発動できる効果です。自分のリストから技を3枚まで選び、ルーメンゾーンに送ります。3枚送った場合、この技のダメージを100上げます。\n②効果：自分が[[state:over_limit]]状態で、ヒットまたはカウンターに成功した場合に発動できる効果です。送るカードを必ず3枚指定する必要があり、指定できない場合は発動できません。\n「その場合、」より前の処理を完了した場合、「その場合、」以降の効果を適用します。\nこの技の「使用後」のタイミングに、この技をブレイクします。',
    },
    'card.CRS-AT-021.detail_text': {
        'en': '"You can include up to 2 copies of this Technique in your deck.": Refer to this restriction when building a deck.\n"This Technique cannot be readied.": This is a continuous restriction with no trigger timing. This Technique cannot be readied face down during the Ready Phase.\n"You can use only one effect of cards with this name per turn.": This is a continuous restriction with no trigger timing. You can activate only one of effects ① and ② per turn, and a second [Plus Ultra!] cannot activate either effect.\n①Effect: This is a mandatory effect that activates when this Technique is sent to the Lumen Zone. It activates after the effect that sent it there finishes resolving.\n②Effect: This effect can be activated at the "On Combo" timing of a Technique that satisfies <Speed 12 or higher [[character:nya]] Technique>. Take 200 damage and increase that Technique\'s damage by 100.',
        'ja': '「この技はデッキに2枚まで入れられる。」：デッキ構築時に参照する制限です。\n「この技はレディできない。」：発動タイミングを持たず、常時適用される制限です。この技はレディフェイズに裏向きでレディできません。\n「このカード名の効果はいずれかをターンに1回しか使用できない。」：発動タイミングを持たず、常時適用される制限です。この技の①②のうち1つだけを1ターンに発動でき、2枚目の[プルス・ウルトラ！]はいずれの効果も発動できません。\n①効果：この技がルーメンゾーンに送られた場合に発動する強制効果です。ルーメンゾーンへ送る効果の処理終了後に発動します。\n②効果：〈速度12以上 [[character:nya]]の技〉という条件を満たす技の「コンボ時」に発動できる効果です。自分は200ダメージを受け、その技のダメージを100上げます。',
    },
    'card.LMI-AT-011.detail_text': {
        'en': '"This card is unaffected by other Techniques.": This is a continuous effect with no trigger timing.\n①Effect: This effect can be activated at the end of the Battle Phase of the first turn in which you enter [[state:over_limit]]. Afterward, apply all of the following effects while this Technique is in the Lumen Zone.\n-"The removal condition for [[state:over_limit]] changes from 8 or more cards to 11 or more cards.": This is a continuous effect with no trigger timing. When checking the condition for removing [[state:over_limit]] during the Lumen Phase by its effect ②, change the condition so it activates at 11 cards rather than 8.\n-"<[[character:nya]]> Techniques in the Lumen Zone cannot be broken.": This is a continuous effect with no trigger timing. You cannot break <[[character:nya]]> Techniques under any circumstances, including by the effect of [[state:over_limit]]. Even mandatory effects such as [[card:ST1-005]] do not break them.\n-"During the Get Phase, you may gain 1 <[[character:nya]]> Technique from the Lumen Zone.": This effect can be activated during the Get Phase, after both players have completed their Get Phase actions.\n-"On combo, you may use up to 1 <[[character:nya]]> Technique from the Lumen Zone in the combo. If you do, break that Technique after use.": This effect applies at the "On Combo" timing of the Nth Combo Technique and enables use of the following N+1 Combo Technique. You may use 1 <[[character:nya]]> Technique from the Lumen Zone that satisfies the combo condition, then break it after use.\n-"When [[state:over_limit]] is removed, take 500 damage.": This is a mandatory effect that activates when [[state:over_limit]] is removed, after the removing effect finishes resolving.',
        'ja': '「このカードは他の技の影響を受けない。」：発動タイミングを持たず、常時適用される効果です。\n①効果：ゲーム中初めて[[state:over_limit]]状態になったターンのバトルフェイズ終了時に発動できる効果です。以後、この技がルーメンゾーンにある間、以下の効果をすべて適用します。\n-「[[state:over_limit]]の解除条件が8枚以上から11枚以上になる。」：発動タイミングを持たず、常時適用される効果です。[[state:over_limit]]の②効果によってルーメンフェイズ時に解除条件を確認する際、8枚ではなく11枚で発動するよう条件を変更します。\n-「ルーメンゾーンの〈[[character:nya]]〉技をブレイクできない。」：発動タイミングを持たず、常時適用される効果です。[[state:over_limit]]の効果を含め、いかなる場合も〈[[character:nya]]〉技をブレイクできません。[[card:ST1-005]]などの強制効果でブレイクする場合もブレイクしません。\n-「ゲットフェイズ時、ルーメンゾーンから〈[[character:nya]]〉技1枚を獲得できる。」：ゲットフェイズに、お互いがゲットフェイズの処理を行った後で発動できる効果です。\n-「コンボ時、ルーメンゾーンの〈[[character:nya]]〉技を1枚までコンボに使用できる。その場合、使用後にその技をブレイクする。」：Nコンボ目の技の「コンボ時」に適用され、次に続くN+1コンボ目の技を使用可能にする効果です。コンボ条件を満たす〈[[character:nya]]〉技1枚をルーメンゾーンから使用でき、その技の使用後にブレイクします。\n-「[[state:over_limit]]解除時、自分は500ダメージを受ける。」：[[state:over_limit]]が解除された場合に発動する強制効果です。解除する効果の処理後に発動します。',
    },
    'card.LMI-AT-012.detail_text': {
        'en': '"This Technique cannot be broken while in the Lumen Zone.": This is a continuous effect with no trigger timing.\n①Effect: This effect can be activated at this Technique\'s "On Use" timing. Send 1 Technique from your hand or List to your Lumen Zone.\n②Effect: This is a continuous effect while you are in [[state:over_limit]]. This Technique\'s damage increases by 100 for every 3 Techniques in your Lumen Zone. If there are 3N+1 or 3N+2 Techniques there, its damage increases only by N00.\n③Effect: This is a mandatory effect that activates at this Technique\'s "Before Judgment" timing. Gain 2 FP for every 3 Techniques in your Lumen Zone. If there are 3N+1 or 3N+2 Techniques there, gain only 2×N FP.',
        'ja': '「この技はルーメンゾーンではブレイクできない。」：発動タイミングを持たず、常時適用される効果です。\n①効果：この技の「使用時」のタイミングに発動できる効果です。自分の手札またはリストから技1枚を自分のルーメンゾーンに送ります。\n②効果：自分が[[state:over_limit]]状態である間、常時適用される効果です。自分のルーメンゾーンの技3枚につき、この技のダメージが100上がります。技が3N+1枚または3N+2枚の場合、ダメージはN00だけ上がります。\n③効果：この技の「判定前」のタイミングに発動する強制効果です。自分のルーメンゾーンの技3枚につき2FPを得ます。技が3N+1枚または3N+2枚の場合、2×N FPだけを得ます。',
    },
    'card.PMP-AT-013.detail_text': {
        'en': '"This Technique\'s damage +200 for every 4 cards in the Lumen Zone": This is a continuous effect with no trigger timing. Its damage increases by 200 with 4–7 Techniques in the Lumen Zone, by 400 with 8–11, and by 600 with 12–15.\n①Effect: This is a continuous effect with no trigger timing while there are at least 7 cards in your Lumen Zone. Refer to it during the "Clash Check" of the "Battle Judgment" step.\n②Effect: This effect applies at the "On Combo" timing of the Nth Combo Technique and enables use of the following N+1 Combo Technique. [Rai! Lefi! Blast!] can be chained after a card with [[keyword:rai]] or [[keyword:lefi]] in its name, regardless of Speed. If you do, at this Technique\'s "On Combo" timing, take 100 damage for each <[[character:nya]]> Technique in your Lumen Zone.',
        'ja': '「ルーメンゾーンのカード4枚につき、この技のダメージ+200」：発動タイミングを持たず、常時適用される効果です。ルーメンゾーンの技が4～7枚なら200、8～11枚なら400、12～15枚なら600上がります。\n①効果：自分のルーメンゾーンにカードが7枚以上ある間、発動タイミングを持たず常時適用される効果です。「戦闘判定」段階の「相殺確認」時に参照します。\n②効果：Nコンボ目の技の「コンボ時」に適用され、次に続くN+1コンボ目の技を使用可能にする効果です。[ライ！レピ！ブラスト！]は速度に関係なく、カード名に[[keyword:rai]]または[[keyword:lefi]]を含むカードの後につなげて使用できます。その場合、この技の「コンボ時」に、自分のルーメンゾーンの〈[[character:nya]]〉技1枚につき100ダメージを受けます。',
    },
    'card.ST1-001.detail_text': {
        'en': '①Effect: This is a mandatory effect that activates at this Technique\'s "After Use" timing.\nApply one of the following effects according to your current state.\n-If you are not in [[state:over_limit]]: Send 1 Technique from your List to the Lumen Zone.\n-If you are in [[state:over_limit]]: Send 1 face-up Technique from your Lumen Zone to your List.',
        'ja': '①効果：この技の「使用後」のタイミングに発動する強制効果です。\n自分の状態に応じて、以下の効果のいずれか1つを適用します。\n-自分が[[state:over_limit]]状態でない場合：自分のリストから技1枚をルーメンゾーンに送ります。\n-自分が[[state:over_limit]]状態の場合：自分のルーメンゾーンにある表向きの技1枚を自分のリストに送ります。',
    },
    'card.ST1-002.detail_text': {
        'en': '①Effect: This is a continuous effect with no trigger timing while you are in [[state:over_limit]].\n②Effect: This is a mandatory effect that activates at this Technique\'s "Before Judgment" timing if the opponent\'s Technique in the Battle Zone satisfies both <Speed 7 or lower> and <Hand-judgment Attack Technique>. Gain 2 FP.',
        'ja': '①効果：自分が[[state:over_limit]]状態である間、発動タイミングを持たず常時適用される効果です。\n②効果：この技の「判定前」のタイミングに、バトルゾーンの相手の技が〈速度7以下〉かつ〈手判定の攻撃技〉という条件を満たす場合に発動する強制効果です。自分は2FPを得ます。',
    },
    'card.ST1-003.detail_text': {
        'en': '"This Technique clashes only Techniques with a <Hand> judgment.": This is a continuous effect with no trigger timing. Refer to it during the "Clash Check" of the "Battle Judgment" step.\n①Effect: This is a mandatory effect that activates at this Technique\'s "On Clash" timing.\n②Effect: This effect applies at the "On Combo" timing of the Nth Combo Technique and enables use of the following N+1 Combo Technique. [Rai! Bounce!] can be chained after a card with [[keyword:lefi]] in its name, regardless of Speed.',
        'ja': '「この技は〈手〉判定の技のみ相殺する。」：発動タイミングを持たず、常時適用される効果です。「戦闘判定」段階の「相殺確認」時に参照します。\n①効果：この技の「相殺時」のタイミングに発動する強制効果です。\n②効果：Nコンボ目の技の「コンボ時」に適用され、次に続くN+1コンボ目の技を使用可能にする効果です。[ライ！バウンス！]は速度に関係なく、カード名に[[keyword:lefi]]を含むカードの後につなげて使用できます。',
    },
    'card.ST1-004.detail_text': {
        'en': '"This Technique dodges only Techniques with Speed 8 or lower.": This is a continuous effect with no trigger timing. Refer to it during the "Dodge Check" of the "Battle Judgment" step.',
        'ja': '「この技は速度8以下の技のみ回避する」：発動タイミングを持たず、常時適用される効果です。「戦闘判定」段階の「回避確認」時に参照します。',
    },
    'card.ST1-005.detail_text': {
        'en': '"This Technique clashes only Techniques with a <Foot> judgment.": This is a continuous effect with no trigger timing. Refer to it during the "Clash Check" of the "Battle Judgment" step.\n①Effect: This effect applies at the "On Combo" timing of the Nth Combo Technique and enables use of the following N+1 Combo Technique. [Rai! Chop!] can be chained after a card with [[keyword:lefi]] in its name, regardless of Speed.\n②Effect: This is a mandatory effect that activates at the "On Combo" timing if you are in [[state:over_limit]]. If you successfully resolve "Break 1 Technique in the Lumen Zone," then resolve "Gain 1 Technique from the List."',
        'ja': '「この技は〈足〉判定の技のみ相殺する。」：発動タイミングを持たず、常時適用される効果です。「戦闘判定」段階の「相殺確認」時に参照します。\n①効果：Nコンボ目の技の「コンボ時」に適用され、次に続くN+1コンボ目の技を使用可能にする効果です。[ライ！チョップ！]は速度に関係なく、カード名に[[keyword:lefi]]を含むカードの後につなげて使用できます。\n②効果：自分が[[state:over_limit]]状態である場合、「コンボ時」のタイミングに発動する強制効果です。「ルーメンゾーンにある技1枚をブレイクする」の処理に成功した場合、「リストから技1枚を獲得する」を実行します。',
    },
    'card.ST1-006.detail_text': {
        'en': '①Effect: This is a mandatory effect that activates at the "Before Judgment" timing if your opponent\'s Technique has a special judgment. Apply all of the following effects.\n-"Lock this Technique\'s Speed": This Technique is unaffected by FP during the FP Adjustment step and is unaffected by Speed-changing effects until the "After Use" timing.\n-"Your opponent cannot dodge or clash this Technique": Refer to this during the "Dodge Check" and "Clash Check" of the "Battle Judgment" step.',
        'ja': '①効果：「判定前」のタイミングに、相手の技が特殊判定を持つ場合に発動する強制効果です。以下の効果をすべて適用します。\n-「この技の速度を固定する」：この技はFP補正段階でFPの影響を受けず、「使用後」のタイミングまで速度変更効果を受けません。\n-「相手はこの技を回避および相殺できない」：「戦闘判定」段階の「回避確認」および「相殺確認」時に参照します。',
    },
    'card.ST1-007.detail_text': {
        'en': '①Effect: This effect applies at the "On Combo" timing of the Nth Combo Technique and enables use of the following N+1 Combo Technique. [Rai! Lefi! Bomber!] can be used in a combo from the List.\nIf you do, resolve "Take 200 damage for each Technique in the Lumen Zone" at this Technique\'s "On Combo" timing.\n②Effect: This is a mandatory effect that applies at this Technique\'s "On Combo" timing if you are in [[state:over_limit]].',
        'ja': '①効果：Nコンボ目の技の「コンボ時」に適用され、次に続くN+1コンボ目の技を使用可能にする効果です。[ライ！レピ！ボンバー！]はリストからコンボに使用できます。\nその場合、この技の「コンボ時」のタイミングに「ルーメンゾーンにある技1枚につき200ダメージを受ける。」を処理します。\n②効果：自分が[[state:over_limit]]状態である場合、この技の「コンボ時」のタイミングに適用される強制効果です。',
    },
    'card.ST1-008.detail_text': {
        'en': '①Effect: This is a mandatory effect that activates at the "Before Judgment" timing if you are in [[state:over_limit]]. Gain 5 FP.\n②Effect: This effect applies at the "On Combo" timing of the Nth Combo Technique and enables use of the following N+1 Combo Technique. [Lefi! Fire!] can be chained after a card with [[keyword:rai]] in its name, regardless of Speed.',
        'ja': '①効果：自分が[[state:over_limit]]状態である場合、「判定前」のタイミングに発動する強制効果です。自分は5FPを得ます。\n②効果：Nコンボ目の技の「コンボ時」に適用され、次に続くN+1コンボ目の技を使用可能にする効果です。[レピ！ファイア！]は速度に関係なく、カード名に[[keyword:rai]]を含むカードの後につなげて使用できます。',
    },
    'card.ST1-009.detail_text': {
        'en': '"Function": This is a continuous function with no trigger timing. Refer to it during the "Guard Check" and "Clash Check" of the "Battle Judgment" step.\n①Effect: This is a mandatory effect that activates when your opponent successfully counters.\n②Effect: This effect applies at the "On Combo" timing. Apply all of the following effects.\n-"Can be used after the 3rd Combo": This effect restricts use of the following N+1 Combo Technique at the "On Combo" timing of the Nth Combo Technique. [Rai! Lefi! Rocket!] cannot be used as the 2nd or 3rd Combo and can be used starting with the 4th Combo.\n-"This Technique\'s damage -400": This effect applies at this Technique\'s "On Combo" timing.\n③Effect: This is a mandatory effect that activates at the "After Use" timing if you are in [[state:over_limit]].',
        'ja': '「機能」：発動タイミングを持たず、常時適用される機能です。「戦闘判定」段階の「ガード確認」および「相殺確認」時に参照します。\n①効果：相手がカウンターに成功した場合に発動する強制効果です。\n②効果：「コンボ時」のタイミングに適用される効果です。以下の効果をすべて適用します。\n-「3コンボ後に使用できる」：Nコンボ目の技の「コンボ時」に適用され、次に続くN+1コンボ目の技の使用を制限する効果です。[ライ！レピ！ロケット！]は2・3コンボ目には使用できず、4コンボ目から使用できます。\n-「この技のダメージ-400」：この技の「コンボ時」のタイミングに適用される効果です。\n③効果：自分が[[state:over_limit]]状態である場合、「使用後」のタイミングに発動する強制効果です。',
    },
    'card.ST1-010.detail_text': {
        'en': '"You can use only one of the following effects": This is a continuous restriction with no trigger timing. During a single Battle Phase, you can use either effect ① or effect ②, but not both.\n①Effect: This effect can be activated when you successfully guard. After both Techniques\' "After Use" timings, you may declare a catch with a Technique that satisfies the condition during "Catch Time."\n②Effect: This effect can be activated at the "After Judgment" timing if you did not take damage. After both Techniques\' "After Use" timings, you may declare a catch with a Technique that satisfies the condition during "Catch Time."',
        'ja': '「以下の効果は1つしか使用できない」：発動タイミングを持たず、常時適用される制限です。1回のバトルフェイズ中、①効果か②効果のいずれか1つだけを使用できます。\n①効果：自分がガードに成功した時に発動できる効果です。お互いの技の「使用後」のタイミングの後、「キャッチタイム」に条件を満たす技でキャッチを宣言できます。\n②効果：「判定後」のタイミングに、自分がダメージを受けていない場合に発動できる効果です。お互いの技の「使用後」のタイミングの後、「キャッチタイム」に条件を満たす技でキャッチを宣言できます。',
    },
    'card.ST1-011.detail_text': {
        'en': '①\nThis is a mandatory effect that occurs at the "On Guard" timing.\nThe source dealing the damage is this card\'s user.\nThe object receiving the damage is this card\'s user.',
        'ja': '①\n「ガード時」のタイミングに発生する強制効果です。\nダメージを与える主体はこのカードの使用者です。\nダメージを受ける対象もこのカードの使用者です。',
    },
    'card.ST1-PS1.detail_text': {
        'en': '①Effect: This is a mandatory effect that activates at the "After Use" timing.\n②Effect: This is a mandatory effect that activates if there are at least 4 Attack and Defense Techniques in the Lumen Zone. Enter [[state:over_limit]], then apply all of the following effects while in [[state:over_limit]].\n-"All <[[character:nya]] Attack> Techniques\' damage +100": This is a continuous effect with no trigger timing.\n-"During the Recovery Phase, break 1 <[[character:nya]]> Technique in the Lumen Zone, or send 2 Techniques from your hand or List to the Lumen Zone.": This is a mandatory effect that activates during the Recovery Phase.\n-"During the Lumen Phase, if there are at least 8 Techniques in the Lumen Zone, take 100 damage for each of those Techniques and send all Attack and Defense Techniques to the List. Then lose 2 FP and remove [[state:over_limit]].": This is a mandatory effect that activates during the Lumen Phase if there are at least 8 face-up Techniques in the Lumen Zone. After sending all Attack and Defense Techniques to the List, lose 2 FP and leave [[state:over_limit]].',
        'ja': '①効果：「使用後」のタイミングに発動する強制効果です。\n②効果：ルーメンゾーンに攻撃・防御技が4枚以上ある場合に発動する強制効果です。自分は[[state:over_limit]]状態になり、[[state:over_limit]]状態の間、以下の効果をすべて適用します。\n-「すべての〈[[character:nya]] 攻撃〉技のダメージ+100」：発動タイミングを持たず、常時適用される効果です。\n-「リカバリーフェイズ時、ルーメンゾーンの〈[[character:nya]]〉技1枚をブレイクするか、手札またはリストから技2枚をルーメンゾーンに送る。」：リカバリーフェイズに発動する強制効果です。\n-「ルーメンフェイズ時、ルーメンゾーンの技が8枚以上ある場合、その技1枚につき100ダメージを受け、攻撃・防御技をすべてリストに送る。その後、2FPを失い[[state:over_limit]]を解除する。」：ルーメンフェイズ時、ルーメンゾーンに表向きの技が8枚以上ある場合に発動する強制効果です。すべての攻撃・防御技をリストに送った後、自分は2FPを失い、[[state:over_limit]]状態が解除されます。',
    },
    'card.UNC-AT-011.detail_text': {
        'en': '"Your opponent cannot guard or clash this Technique.": This is a continuous effect with no trigger timing. Refer to it during the "Guard Check" and "Clash Check" of the "Battle Judgment" step.\n"This Technique cannot be dodged with a special judgment.": This is a continuous effect with no trigger timing. Refer to it during the "Dodge Check" of the "Battle Judgment" step.\n①Effect: This effect activates if your opponent successfully negates this Technique\'s Grab or dodges it.\nIf your opponent successfully negates this Technique\'s Grab during the Battle Judgment step, they gain 2 FP, then the game returns to the Ready Phase.\nIf your opponent successfully dodges, they gain 2 FP at the "When Opponent Dodges" timing.\n②Effect: This effect applies at the "On Combo" timing of the Nth Combo Technique and governs use of the following N+1 Combo Technique. [Rai! Lefi! Catch!] cannot be used as the 2nd or 3rd Combo and can be used starting with the 4th Combo. It can also be chained after a card with [[keyword:rai]] or [[keyword:lefi]] in its name, regardless of Speed.\n④Effect: This effect can be activated at the "On Combo" timing if you are in [[state:over_limit]]. End Combo Time at this Technique\'s "After Use" timing, and gain 1 FP during your next Recovery Phase.',
        'ja': '「相手はこの技をガードおよび相殺できない。」：発動タイミングを持たず、常時適用される効果です。「戦闘判定」段階の「ガード確認」および「相殺確認」時に参照します。\n「この技は特殊判定で回避できない。」：発動タイミングを持たず、常時適用される効果です。「戦闘判定」段階の「回避確認」時に参照します。\n①効果：相手がこの技の投げ無効または回避に成功した場合に発動する効果です。\n戦闘判定段階で相手がこの技の「投げ無効」に成功した場合、相手は2FPを得た後、再びレディフェイズに戻ります。\n相手が回避に成功した場合、「相手回避時」のタイミングに相手は2FPを得ます。\n②効果：Nコンボ目の技の「コンボ時」に適用され、次に続くN+1コンボ目の技の使用に関する効果です。[ライ！レピ！キャッチ！]は2・3コンボ目には使用できず、4コンボ目から使用できます。また、速度に関係なく、カード名に[[keyword:rai]]または[[keyword:lefi]]を含むカードの後につなげて使用できます。\n④効果：自分が[[state:over_limit]]状態である場合、「コンボ時」のタイミングに発動できる効果です。この技の「使用後」のタイミングにコンボタイムを終了し、次のリカバリーフェイズに自分は1FPを得ます。',
    },
    'card.UNC-AT-012.detail_text': {
        'en': '①Effect: This is a mandatory effect that activates at this Technique\'s "Before Judgment" timing. This Technique\'s damage increases by 100 for each Technique in your Lumen Zone, up to +500 once there are 5 or more.\n②Effect: This effect applies at the "On Combo" timing of the Nth Combo Technique and enables use of the following N+1 Combo Technique. [Lefi! Drill!] can be chained after a card with [[keyword:rai]] in its name, regardless of Speed.\n③Effect: This is a mandatory effect that activates when your opponent successfully guards if you are in [[state:over_limit]]. Deal 100 damage to your opponent once for each of your broken Techniques, up to 300 damage.',
        'ja': '①効果：この技の「判定前」のタイミングに発動する強制効果です。自分のルーメンゾーンの技1枚につき、この技のダメージが100上がります。5枚以上の場合は最大+500です。\n②効果：Nコンボ目の技の「コンボ時」に適用され、次に続くN+1コンボ目の技を使用可能にする効果です。[レピ！ドリル！]は速度に関係なく、カード名に[[keyword:rai]]を含むカードの後につなげて使用できます。\n③効果：自分が[[state:over_limit]]状態で、相手がガードに成功した場合に発動する強制効果です。自分のブレイクされた技1枚につき100ダメージ（最大300）を、相手に1回与えます。',
    },
    'card.UNC-AT-013.detail_text': {
        'en': '"High dodges only Techniques with Speed 10 or lower.": This is a continuous effect with no trigger timing. Refer to it during the "Dodge Check" of the "Battle Judgment" step.\n"Mid dodges only Techniques with Speed 8 or lower.": This is a continuous effect with no trigger timing. Refer to it during the "Dodge Check" of the "Battle Judgment" step.\n①Effect: This is a mandatory effect that activates when you successfully dodge.\n②Effect: This is a mandatory effect that activates at the "After Judgment" timing if you took damage during this Battle Phase.',
        'ja': '「上段は速度10以下の技のみ回避する。」：発動タイミングを持たず、常時適用される効果です。「戦闘判定」段階の「回避確認」時に参照します。\n「中段は速度8以下の技のみ回避する。」：発動タイミングを持たず、常時適用される効果です。「戦闘判定」段階の「回避確認」時に参照します。\n①効果：自分が回避に成功した場合に発動する強制効果です。\n②効果：このバトルフェイズ中に自分がダメージを受けていた場合、「判定後」のタイミングに発動する強制効果です。',
    },
    'term.state.disaster_one': {
        'ja': 'ディザスター・ワン',
    },
}
