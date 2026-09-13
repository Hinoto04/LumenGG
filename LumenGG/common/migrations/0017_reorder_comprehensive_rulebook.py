import re
from datetime import date

from django.db import migrations


LANGUAGES = ('ko', 'en', 'ja')

ROOT_TITLES = {
    0: {
        'ko': '규칙서를 읽기 전 알아야 할 내용',
        'en': 'Before Reading This Rulebook',
        'ja': 'ルールブックを読む前に',
    },
    1: {
        'ko': '게임 내 객체의 정의',
        'en': 'Definitions of Game Objects',
        'ja': 'ゲーム内オブジェクトの定義',
    },
    2: {
        'ko': '게임 내 영역의 정의',
        'en': 'Definitions of Game Areas',
        'ja': 'ゲーム内領域の定義',
    },
    3: {
        'ko': '게임 준비',
        'en': 'Game Setup',
        'ja': 'ゲームの準備',
    },
    4: {
        'ko': '게임 진행',
        'en': 'Game Progression',
        'ja': 'ゲームの進行',
    },
    5: {
        'ko': '게임 종료',
        'en': 'Game End',
        'ja': 'ゲームの終了',
    },
    6: {
        'ko': '카드의 효과와 우선권',
        'en': 'Card Effects and Priority',
        'ja': 'カードの効果と優先権',
    },
    7: {'ko': '배틀', 'en': 'Battle', 'ja': 'バトル'},
    8: {
        'ko': '콤보와 캐치',
        'en': 'Combos and Catches',
        'ja': 'コンボとキャッチ',
    },
    9: {
        'ko': '규칙에 의한 효과',
        'en': 'Rule-Based Effects',
        'ja': 'ルールによる効果',
    },
}

ROOT_SEMANTIC_ALIASES = {
    0: 'rule-before-reading-this-rulebook',
    1: 'rule-definitions-of-game-objects',
    2: 'rule-definitions-of-game-areas',
    3: 'rule-game-setup',
    4: 'rule-game-progression',
    5: 'rule-game-end',
    6: 'rule-card-effects-and-priority',
    7: 'rule-battle',
    8: 'rule-combos-and-catches',
    9: 'rule-rule-based-effects',
}

SECTION_TITLES = {
    'object-character': {
        'ko': '플레이어와 캐릭터 카드',
        'en': 'Players and Character Cards',
        'ja': 'プレイヤーとキャラクターカード',
    },
    'object-deck': {'ko': '덱', 'en': 'Decks', 'ja': 'デッキ'},
    'object-trait': {'ko': '특성 카드', 'en': 'Trait Cards', 'ja': '特性カード'},
    'object-technique': {
        'ko': '공격·수비 기술',
        'en': 'Attack and Defense Techniques',
        'ja': '攻撃・防御技',
    },
    'object-special': {'ko': '특수 기술', 'en': 'Special Techniques', 'ja': '特殊技'},
    'object-ultimate': {
        'ko': '얼티밋 기술',
        'en': 'Ultimate Techniques',
        'ja': 'アルティメット技',
    },
    'area-zone': {'ko': '존의 정의', 'en': 'Definition of Zones', 'ja': 'ゾーンの定義'},
    'area-public': {
        'ko': '존별 공개 정보',
        'en': 'Public Information by Zone',
        'ja': 'ゾーン別公開情報',
    },
    'setup-deck': {
        'ko': '덱 구성 규칙',
        'en': 'Deck Construction Rules',
        'ja': 'デッキ構築ルール',
    },
    'setup-game': {
        'ko': '게임 준비 절차',
        'en': 'Game Setup Procedure',
        'ja': 'ゲーム準備手順',
    },
    'end-win': {'ko': '승리와 패배', 'en': 'Victory and Defeat', 'ja': '勝利と敗北'},
    'end-sudden': {'ko': '서든 데스', 'en': 'Sudden Death', 'ja': 'サドンデス'},
    'effect-grammar': {
        'ko': '기능·효과·생략 문법',
        'en': 'Function, Effect, and Omission Grammar',
        'ja': '機能・効果・省略文法',
    },
    'effect-unit': {
        'ko': '처리 단위와 상태 확인',
        'en': 'Processing Units and State Checks',
        'ja': '処理単位と状態確認',
    },
    'rule-movement': {
        'ko': '존 이동과 버리기',
        'en': 'Zone Movement and Discarding',
        'ja': 'ゾーン移動と捨てる',
    },
    'rule-break': {
        'ko': '브레이크와 보충',
        'en': 'Break and Replenishment',
        'ja': 'ブレイクと補充',
    },
    'rule-illegal': {
        'ko': '특수 기술의 불법 이동',
        'en': 'Illegal Movement of Special Techniques',
        'ja': '特殊技の不正な移動',
    },
    'rule-defense-over': {
        'ko': '디펜스 오버',
        'en': 'Defense Over',
        'ja': 'ディフェンスオーバー',
    },
    'combo-group': {'ko': '콤보', 'en': 'Combos', 'ja': 'コンボ'},
    'catch-group': {'ko': '캐치', 'en': 'Catches', 'ja': 'キャッチ'},
}

INTRO_CONTENT = {
    'ko': '<p>이 장은 게임의 개요와 이 문서의 지위, 규칙 간 우선순위와 읽기 전 주의사항을 설명합니다.</p>',
    'en': '<p>This chapter explains the game overview, the status of this document, the priority among rules, and the cautions to know before reading.</p>',
    'ja': '<p>この章では、ゲームの概要、この文書の位置づけ、ルール間の優先順位、読む前の注意事項を説明します。</p>',
}

JUDGMENT_MAP_TITLES = {
    'ko': '판정 지도',
    'en': 'Judgment Map',
    'ja': '判定マップ',
}

JUDGMENT_MAP_CONTENT = {
    'ko': "<div class=\"v2-rulebook-visual-stage\"><div class=\"v2-rulebook-phase-track\"><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"게임 내 객체의 정의\" data-text=\"플레이어, 캐릭터·특성·기술 카드, 덱과 얼티밋 기술의 정의를 확인합니다.\" data-hint=\"플레이어 · 카드 · 덱\" data-href=\"#rule-definitions-of-game-objects\" type=\"button\"><span>1</span><strong>객체</strong><em>플레이어 · 카드 · 덱</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"게임 내 영역의 정의\" data-text=\"각 존에 놓을 수 있는 카드, 공개 여부, 순서와 이동 결과를 확인합니다.\" data-hint=\"존 · 공개 · 순서\" data-href=\"#rule-definitions-of-game-areas\" type=\"button\"><span>2</span><strong>영역</strong><em>존 · 공개 · 순서</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"게임 준비\" data-text=\"덱 구성 규칙과 초기 패·리스트·사이드 덱의 준비 절차를 확인합니다.\" data-hint=\"덱 구성 · 초기 배치\" data-href=\"#rule-game-setup\" type=\"button\"><span>3</span><strong>준비</strong><em>덱 구성 · 초기 배치</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"게임 진행\" data-text=\"루멘, 레디, 배틀, 겟, 리커버리 페이즈의 순서를 확인합니다.\" data-hint=\"턴 순서\" data-href=\"#rule-game-progression\" type=\"button\"><span>4</span><strong>턴</strong><em>턴 순서</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"게임 종료\" data-text=\"게임의 승리와 패배, 동시 체력 0과 서든 데스 절차를 확인합니다.\" data-hint=\"승패 · 서든 데스\" data-href=\"#rule-game-end\" type=\"button\"><span>5</span><strong>종료</strong><em>승패 · 서든 데스</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"카드의 효과와 우선권\" data-text=\"동시에 처리할 효과, 강제/임의 효과, 텍스트 충돌과 대기 효과를 확인합니다.\" data-hint=\"동시 처리\" data-href=\"#rule-card-effects-and-priority\" type=\"button\"><span>6</span><strong>우선권</strong><em>동시 처리</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"배틀\" data-text=\"속도, FP, 공격 대 공격, 공격 대 수비, 무승부와 상쇄 판정을 확인합니다.\" data-hint=\"속도 · FP · 데미지\" data-href=\"#rule-battle\" type=\"button\"><span>7</span><strong>배틀</strong><em>속도 · FP · 데미지</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"콤보와 캐치\" data-text=\"콤보의 연결과 데미지 보정, 캐치의 조건과 연속 처리를 확인합니다.\" data-hint=\"연속 공격 · 반격\" data-href=\"#rule-combos-and-catches\" type=\"button\"><span>8</span><strong>콤보·캐치</strong><em>연속 공격 · 반격</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"규칙에 의한 효과\" data-text=\"존 이동에 따른 브레이크와 보충, 특수 기술의 불법 이동, 디펜스 오버를 확인합니다.\" data-hint=\"브레이크 · 디펜스 오버\" data-href=\"#rule-rule-based-effects\" type=\"button\"><span>9</span><strong>규칙 효과</strong><em>브레이크 · 디펜스 오버</em></button></div></div><aside class=\"v2-rulebook-visual-info\"><span>판정 지도</span><strong data-rulebook-visual-title>판정 지도</strong><small data-rulebook-visual-hint></small><p data-rulebook-visual-text>지금 확인하려는 판정이 어느 장에 있는지 먼저 고르고, 해당 규칙 장으로 이동합니다.</p><a class=\"v2-button v2-button-primary\" data-rulebook-visual-link href=\"#rule-to-use-this-document\">본문으로 이동</a></aside>",
    'en': "<div class=\"v2-rulebook-visual-stage\"><div class=\"v2-rulebook-phase-track\"><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"Definitions of Game Objects\" data-text=\"Review the definitions of players, Character, Trait, and Technique Cards, decks, and Ultimate Techniques.\" data-hint=\"Players · Cards · Decks\" data-href=\"#rule-definitions-of-game-objects\" type=\"button\"><span>1</span><strong>Objects</strong><em>Players · Cards · Decks</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"Definitions of Game Areas\" data-text=\"Check the cards that can be placed in each zone, whether they are revealed, the order, and the results of the moves.\" data-hint=\"Zones · Visibility · Order\" data-href=\"#rule-definitions-of-game-areas\" type=\"button\"><span>2</span><strong>Areas</strong><em>Zones · Visibility · Order</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"Game Setup\" data-text=\"Review deck construction and how to prepare the initial hand, List, and Side Deck.\" data-hint=\"Deck Construction · Initial Setup\" data-href=\"#rule-game-setup\" type=\"button\"><span>3</span><strong>Setup</strong><em>Deck Construction · Initial Setup</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"Game Progression\" data-text=\"Check the order of Lumen, Ready, Battle, Get, Recovery Phase.\" data-hint=\"turn order\" data-href=\"#rule-game-progression\" type=\"button\"><span>4</span><strong>turn</strong><em>turn order</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"Game End\" data-text=\"Review victory and defeat, simultaneous zero HP, and the Sudden Death procedure.\" data-hint=\"Win/Loss · Sudden Death\" data-href=\"#rule-game-end\" type=\"button\"><span>5</span><strong>end</strong><em>Win/Loss · Sudden Death</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"Card Effects and Priority\" data-text=\"Check which effects to process simultaneously, forced/random effects, text collisions and atmospheric effects.\" data-hint=\"concurrent processing\" data-href=\"#rule-card-effects-and-priority\" type=\"button\"><span>6</span><strong>Priority</strong><em>concurrent processing</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"Battle\" data-text=\"Check speed, FP, attack vs. attack, attack vs. defense, draw, and Clash decisions.\" data-hint=\"Speed · FP · Damage\" data-href=\"#rule-battle\" type=\"button\"><span>7</span><strong>Battle</strong><em>Speed · FP · Damage</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"Combos and Catches\" data-text=\"Review combo connections and damage adjustments, plus Catch conditions and consecutive processing.\" data-hint=\"Attack Chains · Counterattack\" data-href=\"#rule-combos-and-catches\" type=\"button\"><span>8</span><strong>Combo · Catch</strong><em>Attack Chains · Counterattack</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"Rule-Based Effects\" data-text=\"Review Break and replenishment caused by zone movement, illegal movement of Special Techniques, and Defense Over.\" data-hint=\"Break · Defense Over\" data-href=\"#rule-rule-based-effects\" type=\"button\"><span>9</span><strong>Rule Effects</strong><em>Break · Defense Over</em></button></div></div><aside class=\"v2-rulebook-visual-info\"><span>Judgment Map</span><strong data-rulebook-visual-title>Judgment Map</strong><small data-rulebook-visual-hint></small><p data-rulebook-visual-text>First select which chapter the decision you want to check is in, and then move to the corresponding rules chapter.</p><a class=\"v2-button v2-button-primary\" data-rulebook-visual-link href=\"#rule-to-use-this-document\">Go to Section</a></aside>",
    'ja': "<div class=\"v2-rulebook-visual-stage\"><div class=\"v2-rulebook-phase-track\"><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"ゲーム内オブジェクトの定義\" data-text=\"プレイヤー、キャラクター・特性・技カード、デッキ、アルティメット技の定義を確認します。\" data-hint=\"プレイヤー · カード · デッキ\" data-href=\"#rule-definitions-of-game-objects\" type=\"button\"><span>1</span><strong>オブジェクト</strong><em>プレイヤー · カード · デッキ</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"ゲーム内領域の定義\" data-text=\"各ゾーンに置くことができるカード、公開されているかどうか、順序と移動の結果を確認します。\" data-hint=\"ゾーン · 公開 · 順序\" data-href=\"#rule-definitions-of-game-areas\" type=\"button\"><span>2</span><strong>領域</strong><em>ゾーン · 公開 · 順序</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"ゲームの準備\" data-text=\"デッキ構築ルールと初期手札・リスト・サイドデッキの準備手順を確認します。\" data-hint=\"デッキ構築 · 初期配置\" data-href=\"#rule-game-setup\" type=\"button\"><span>3</span><strong>準備</strong><em>デッキ構築 · 初期配置</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"ゲームの進行\" data-text=\"ルーメン、レディ、バトル、ゲット、リカバリーフェイズの順番を確認します。\" data-hint=\"ターン順\" data-href=\"#rule-game-progression\" type=\"button\"><span>4</span><strong>ターン</strong><em>ターン順</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"ゲームの終了\" data-text=\"ゲームの勝利と敗北、同時に体力が0になった場合、サドンデスの手順を確認します。\" data-hint=\"勝敗・サドンデス\" data-href=\"#rule-game-end\" type=\"button\"><span>5</span><strong>終了</strong><em>勝敗・サドンデス</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"カードの効果と優先権\" data-text=\"同時に処理する効果、強制/ランダム効果、テキストの衝突と待機効果を確認します。\" data-hint=\"同時処理\" data-href=\"#rule-card-effects-and-priority\" type=\"button\"><span>6</span><strong>優先権</strong><em>同時処理</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"バトル\" data-text=\"速度、FP、攻撃対攻撃、攻撃対守備、引き分けと相殺判定を確認します。\" data-hint=\"スピード・FP・ダメージ\" data-href=\"#rule-battle\" type=\"button\"><span>7</span><strong>バトル</strong><em>スピード・FP・ダメージ</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"コンボとキャッチ\" data-text=\"コンボの接続とダメージ補正、キャッチの条件と連続処理を確認します。\" data-hint=\"連続攻撃 · 反撃\" data-href=\"#rule-combos-and-catches\" type=\"button\"><span>8</span><strong>コンボ · キャッチ</strong><em>連続攻撃 · 反撃</em></button><button class=\"v2-rulebook-phase\" data-rulebook-hotspot data-title=\"ルールによる効果\" data-text=\"ゾーン移動によるブレイクと補充、特殊技の不正な移動、ディフェンスオーバーを確認します。\" data-hint=\"ブレイク · ディフェンスオーバー\" data-href=\"#rule-rule-based-effects\" type=\"button\"><span>9</span><strong>ルール効果</strong><em>ブレイク · ディフェンスオーバー</em></button></div></div><aside class=\"v2-rulebook-visual-info\"><span>判定マップ</span><strong data-rulebook-visual-title>判定マップ</strong><small data-rulebook-visual-hint></small><p data-rulebook-visual-text>今確認したい判定がどの章にあるのかをまず選び、該当する規則章に移動します。</p><a class=\"v2-button v2-button-primary\" data-rulebook-visual-link href=\"#rule-to-use-this-document\">本文へ移動</a></aside>",
}



def _ordered(rules):
    return sorted(rules, key=lambda rule: (rule.priority, rule.pk))


def _add_alias(rule, alias):
    aliases = list(rule.reference_aliases or [])
    if alias and alias != rule.reference_name and alias not in aliases:
        aliases.append(alias)
    rule.reference_aliases = aliases


def _set_translations(RuleTranslation, rule, titles, *, contents=None):
    contents = contents or {}
    for language in LANGUAGES:
        translation, _created = RuleTranslation.objects.get_or_create(
            rule_id=rule.pk,
            language=language,
            defaults={
                'title': titles.get(language, titles.get('ko', '')),
                'content': contents.get(language, ''),
            },
        )
        translation.title = titles.get(language, titles.get('ko', translation.title))
        if language in contents:
            translation.content = contents[language]
        translation.save(update_fields=['title', 'content'])


def _translation_contents(RuleTranslation, rule):
    return {
        translation.language: translation.content
        for translation in RuleTranslation.objects.filter(rule_id=rule.pk)
    }

def _update_judgment_map(
    RuleVisualGuide,
    RuleVisualGuideTranslation,
    book,
):
    korean = (
        RuleVisualGuideTranslation.objects
        .filter(
            guide__rulebook_id=book.pk,
            guide__rule_id=None,
            language='ko',
            title='판정 지도',
        )
        .order_by('guide_id')
        .first()
    )
    if korean is None:
        return
    guide = RuleVisualGuide.objects.get(pk=korean.guide_id)
    guide.style_key = 'rules'
    guide.is_public = True
    guide.save(update_fields=['style_key', 'is_public'])
    for language in LANGUAGES:
        RuleVisualGuideTranslation.objects.update_or_create(
            guide_id=guide.pk,
            language=language,
            defaults={
                'title': JUDGMENT_MAP_TITLES[language],
                'content': JUDGMENT_MAP_CONTENT[language],
            },
        )



def _merge_rule(
    Rule,
    RuleTranslation,
    RuleVisualGuide,
    source,
    target,
):
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
        if not source_content:
            continue
        target_translation = target_translations.get(source_translation.language)
        if target_translation is None:
            source_translation.rule_id = target.pk
            source_translation.save(update_fields=['rule'])
            target_translations[source_translation.language] = source_translation
            continue
        if source_content not in (target_translation.content or ''):
            target_translation.content = ''.join((target_translation.content or '', source_translation.content))
            target_translation.save(update_fields=['content'])

    for alias in [source.reference_name, *(source.reference_aliases or [])]:
        _add_alias(target, alias)
    target.save(update_fields=['reference_aliases'])
    source.delete()


def _apply_child_order(Rule, rulebook_id, parent, preferred):
    current = _ordered(Rule.objects.filter(rulebook_id=rulebook_id, parent_id=parent.pk))
    preferred_ids = [rule.pk for rule in preferred if rule is not None]
    ordered = []
    seen = set()
    for rule in [*preferred, *current]:
        if rule is None or rule.pk in seen or not Rule.objects.filter(pk=rule.pk).exists():
            continue
        seen.add(rule.pk)
        ordered.append(rule)
    for index, rule in enumerate(ordered, start=1):
        Rule.objects.filter(pk=rule.pk).update(priority=index * 10)


def reorder_comprehensive_rules(apps, schema_editor):
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

    aliases = {}
    by_id = {rule.pk: rule for rule in rules}
    for rule in rules:
        for alias in [rule.reference_name, *(rule.reference_aliases or [])]:
            aliases.setdefault(alias, rule)

    old_roots = [aliases.get(f'chapter-{index}') for index in range(13)]
    found_chapter_count = sum(rule is not None for rule in old_roots)
    if found_chapter_count == 0:
        # The comprehensive book has not been imported with the standard source anchors.
        return
    if any(rule is None for rule in old_roots):
        possible_new_roots = old_roots[:10]
        is_new_layout = (
            all(rule is not None for rule in possible_new_roots)
            and all(rule is None for rule in old_roots[10:])
            and all(
                RuleTranslation.objects.filter(
                    rule_id=rule.pk,
                    language='ko',
                    title=ROOT_TITLES[index]['ko'],
                ).exists()
                for index, rule in enumerate(possible_new_roots)
            )
        )
        if is_new_layout:
            return
        raise RuntimeError(
            '종합 규칙서의 기존 0~12장 앵커가 일부 누락되어 '
            'v0.3 배치 마이그레이션을 안전하게 적용할 수 없습니다.'
        )

    def section_for(clause_alias):
        clause = aliases.get(clause_alias)
        return by_id.get(clause.parent_id) if clause and clause.parent_id else None

    sections = {
        '0.1': section_for('rule-0-1-1'),
        '0.2': section_for('rule-0-2-1'),
        '0.3': section_for('rule-0-3-1'),
        '1.1': section_for('rule-1-1-1'),
        '1.2': section_for('rule-1-2-1'),
        '1.3': section_for('rule-1-3-1'),
        '2.1': section_for('rule-2-1-1'),
        '2.2': section_for('rule-2-2-1'),
        '3.1': section_for('rule-3-1-1'),
        '3.2': section_for('rule-3-2-1'),
        '3.3': section_for('rule-3-3-1'),
        '3.4': section_for('rule-3-4-1'),
        '3.5': section_for('rule-3-5-1'),
        '4.1': section_for('rule-4-1-1'),
        '10.1': section_for('rule-10-1-1'),
        '10.2': section_for('rule-10-2-1'),
        '10.3': section_for('rule-10-3-1'),
        '11.1': section_for('rule-11-1-1'),
        '11.2': section_for('rule-11-2-1'),
        '12.1': section_for('rule-12-1-1'),
        '12.2': section_for('rule-12-2-1'),
    }
    if any(rule is None for rule in sections.values()):
        raise RuntimeError(
            '종합 규칙서의 필수 세부 조항 앵커가 누락되어 '
            'v0.3 배치 마이그레이션을 안전하게 적용할 수 없습니다.'
        )

    root0, old_basic, root2, root3, root4, root5, root6, root7, root8, root9, root10, root11, root12 = old_roots
    original_children = {
        root.pk: _ordered(rule for rule in rules if rule.parent_id == root.pk)
        for root in old_roots
    }

    new_roots = [root0, root3, root2, root4, root5, root12, root6, root7, root8, root10]
    combo_group = old_basic
    catch_group = root9

    moves = {
        sections['0.3'].pk: root6.pk,
        sections['1.1'].pk: root12.pk,
        sections['1.3'].pk: root6.pk,
        sections['3.1'].pk: root3.pk,
        sections['3.2'].pk: root3.pk,
        sections['3.3'].pk: root3.pk,
        sections['3.4'].pk: root3.pk,
        sections['3.5'].pk: root4.pk,
        sections['4.1'].pk: root4.pk,
        sections['11.1'].pk: root3.pk,
        sections['11.2'].pk: root3.pk,
        sections['12.1'].pk: root10.pk,
        sections['12.2'].pk: root12.pk,
        combo_group.pk: root8.pk,
        catch_group.pk: root8.pk,
    }
    for child in original_children[root9.pk]:
        moves[child.pk] = root8.pk
    for child in original_children[root11.pk]:
        moves[child.pk] = root3.pk
    for rule_id, parent_id in moves.items():
        Rule.objects.filter(pk=rule_id).update(parent_id=parent_id)
        by_id[rule_id].parent_id = parent_id

    # Merge the old public-information wrapper into the existing zone-public section.
    old_public = sections['1.2']
    zone_public = sections['2.2']
    Rule.objects.filter(parent_id=old_public.pk).update(parent_id=zone_public.pk)
    for child in rules:
        if child.parent_id == old_public.pk:
            child.parent_id = zone_public.pk
    _merge_rule(Rule, RuleTranslation, RuleVisualGuide, old_public, zone_public)

    # The former special/ultimate chapter becomes part of the object-definition chapter.
    _merge_rule(Rule, RuleTranslation, RuleVisualGuide, root11, root3)

    combo_contents = _translation_contents(RuleTranslation, root8)
    _set_translations(
        RuleTranslation,
        combo_group,
        SECTION_TITLES['combo-group'],
        contents=combo_contents,
    )
    _set_translations(
        RuleTranslation,
        root8,
        ROOT_TITLES[8],
        contents={language: '' for language in LANGUAGES},
    )
    _set_translations(RuleTranslation, catch_group, SECTION_TITLES['catch-group'])
    _set_translations(RuleTranslation, root0, ROOT_TITLES[0], contents=INTRO_CONTENT)

    for index, root in enumerate(new_roots):
        _set_translations(RuleTranslation, root, ROOT_TITLES[index])
        root.reference_aliases = [
            alias
            for alias in (root.reference_aliases or [])
            if not re.fullmatch(r'chapter-\d+', alias)
        ]
        _add_alias(root, f'chapter-{index}')
        _add_alias(root, ROOT_SEMANTIC_ALIASES[index])
        root.show_in_toc = True
        root.is_public = True
        root.save(update_fields=['reference_aliases', 'show_in_toc', 'is_public'])

    for group, semantic_alias in (
        (combo_group, 'rule-combos'),
        (catch_group, 'rule-catches'),
    ):
        group.reference_aliases = [
            alias
            for alias in (group.reference_aliases or [])
            if not re.fullmatch(r'chapter-\d+', alias)
        ]
        _add_alias(group, semantic_alias)
        group.show_in_toc = True
        group.is_public = True
        group.save(update_fields=['reference_aliases', 'show_in_toc', 'is_public'])

    section_title_rules = {
        'object-character': sections['3.2'],
        'object-deck': sections['3.1'],
        'object-trait': sections['3.3'],
        'object-technique': sections['3.4'],
        'object-special': sections['11.1'],
        'object-ultimate': sections['11.2'],
        'area-zone': sections['2.1'],
        'area-public': zone_public,
        'setup-deck': sections['3.5'],
        'setup-game': sections['4.1'],
        'end-win': sections['1.1'],
        'end-sudden': sections['12.2'],
        'effect-grammar': sections['1.3'],
        'effect-unit': sections['0.3'],
        'rule-movement': sections['10.1'],
        'rule-break': sections['10.2'],
        'rule-illegal': sections['10.3'],
        'rule-defense-over': sections['12.1'],
    }
    for key, rule in section_title_rules.items():
        _set_translations(RuleTranslation, rule, SECTION_TITLES[key])

    # Root order keeps the document preface ahead of chapter 0 and appendices after chapter 9.
    current_roots = _ordered(Rule.objects.filter(rulebook_id=book.pk, parent_id=None))
    chapter_root_ids = {root.pk for root in new_roots}
    before = [
        rule for rule in current_roots
        if rule.pk not in chapter_root_ids and rule.priority < root0.priority
    ]
    after = [
        rule for rule in current_roots
        if rule.pk not in chapter_root_ids and rule.priority >= root0.priority
    ]
    for index, rule in enumerate([*before, *new_roots, *after], start=1):
        Rule.objects.filter(pk=rule.pk).update(priority=index * 10)

    _apply_child_order(Rule, book.pk, root0, [sections['0.1'], sections['0.2']])
    _apply_child_order(
        Rule,
        book.pk,
        root3,
        [
            sections['3.2'], sections['3.1'], sections['3.3'],
            sections['3.4'], sections['11.1'], sections['11.2'],
        ],
    )
    _apply_child_order(Rule, book.pk, root4, [sections['3.5'], sections['4.1']])
    _apply_child_order(Rule, book.pk, root12, [sections['1.1'], sections['12.2']])
    _apply_child_order(
        Rule,
        book.pk,
        root6,
        [sections['1.3'], sections['0.3'], *original_children[root6.pk]],
    )
    _apply_child_order(
        Rule,
        book.pk,
        root8,
        [
            combo_group,
            *original_children[root8.pk],
            catch_group,
            *original_children[root9.pk],
        ],
    )
    _apply_child_order(
        Rule,
        book.pk,
        root10,
        [*original_children[root10.pk], sections['12.1']],
    )

    public_clauses = _ordered(Rule.objects.filter(rulebook_id=book.pk, parent_id=zone_public.pk))
    public_basic = aliases.get('rule-1-2-1')
    zone_property = aliases.get('rule-2-2-1')
    ordered_public_clauses = []
    seen_public_clause_ids = set()
    for rule in [public_basic, zone_property, *public_clauses]:
        if rule is None or rule.pk in seen_public_clause_ids:
            continue
        seen_public_clause_ids.add(rule.pk)
        ordered_public_clauses.append(rule)
    for index, rule in enumerate(ordered_public_clauses, start=1):
        Rule.objects.filter(pk=rule.pk).update(priority=index * 10)

    book.version = '0.3-web'
    book.updated_on = date(2026, 9, 1)
    book.save(update_fields=['version', 'updated_on'])
    _update_judgment_map(
        RuleVisualGuide,
        RuleVisualGuideTranslation,
        book,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0016_rulebook_visual_assets'),
    ]

    operations = [
        migrations.RunPython(reorder_comprehensive_rules, migrations.RunPython.noop),
    ]
