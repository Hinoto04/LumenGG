"""Translate the automatic engine's Korean UI strings for the play client.

The engine writes action labels (``레디 · 하이 잽``), decision prompts and option
labels in Korean. For English/Japanese viewers the session payload is passed
through :func:`localize_engine_text_fields` just before it is sent:

* fixed engine words use the exact table below (no substring guessing —
  ``ui_text``'s term fallback turns ``발동하지 않음`` into nonsense);
* effect labels and prompts written in the card DSL use the reviewed
  translation table ``play_effect_text.json`` (Korean -> English/Japanese);
* card names are swapped for the card's translated name;
* ``(5속도)`` speed suffixes are rewritten;
* what is left goes through the shared translation catalog part by part, but
  only when that leaves no Korean behind: word-by-word substitution of a
  sentence (``Lumen 존에 1 cards만``) reads worse than the original.

Only display fields are touched. ``legal_actions[].payload`` and option ids are
echoed back to the engine and stay as they are.
"""
import json
import re
import time
from pathlib import Path

from card.models import Card, Character
from common.language import (
    DEFAULT_LANGUAGE,
    normalize_language,
    translated_card_field,
    translated_character_field,
)
from common.localization import render_visible_markup, translate_text_by_parts

# 카드 이름 번역은 거의 바뀌지 않는다. 이벤트마다 DB를 묻지 않도록 잠시 담아 둔다.
NAME_CACHE_SECONDS = 600
_NAME_CACHE = {'at': 0.0, 'rows': {}}
HANGUL = re.compile('[가-힣]')
SPEED_SUFFIX = re.compile(r'\((\d+)속도\)')
PART_SEPARATORS = re.compile(r'(\s*(?:·|→|,)\s*)')

# Korean -> (English, Japanese). Engine labels and the common decision options.
ENGINE_TEXT = {
    '획득하지 않음': ('Take nothing', '獲得しない'),
    '페이즈 종료': ('End phase', 'フェイズ終了'),
    '타이머 재개': ('Resume timer', 'タイマー再開'),
    '콤보 종료': ('End combo', 'コンボ終了'),
    '캐치 종료': ('End catch', 'キャッチ終了'),
    '첫 카드 다시 선택': ('Choose the first card again', '最初のカードを選び直す'),
    '직전 명령 되감기 요청': ('Ask to rewind the last command', '直前のコマンドの巻き戻しを要請'),
    '선택 타이머 일시정지': ('Pause choice timer', '選択タイマー一時停止'),
    '레디 타이머 일시정지': ('Pause Ready timer', 'レディタイマー一時停止'),
    '상대 시작 패 확인 완료': ("Done reviewing opponent's hand", '相手の初期手札の確認完了'),
    '사용 가능한 카드 없음': ('No usable card', '使用可能なカードなし'),
    '무작위 뒷면 카드로 캐치': ('Catch with a random face-down card', 'ランダムな裏向きカードでキャッチ'),
    '되감기 수락': ('Accept rewind', '巻き戻しを承諾'),
    '되감기 거절': ('Decline rewind', '巻き戻しを拒否'),
    '기권': ('Concede', '投了'),
    '레디': ('Ready', 'レディ'),
    '획득': ('Take', '獲得'),
    '캐치': ('Catch', 'キャッチ'),
    '콤보': ('Combo', 'コンボ'),
    '히트': ('Hit', 'ヒット'),
    '카운터': ('Counter', 'カウンター'),
    '가드': ('Guard', 'ガード'),
    '회피': ('Dodge', '回避'),
    '상쇄': ('Clash', '相殺'),
    '비용을 지불하지 않음': ("Don't pay the cost", 'コストを支払わない'),
    '보충하지 않음': ("Don't refill", '補充しない'),
    '뒷면 카드': ('Face-down card', '裏向きのカード'),
    '패의 카드': ('Card in hand', '手札のカード'),
    '사이드 카드': ('Side card', 'サイドのカード'),
    '그랩 기술': ('Grab technique', 'グラブ技'),
    '카드': ('Card', 'カード'),
    '발동': ('Activate', '発動'),
    '발동하지 않음': ("Don't activate", '発動しない'),
    '사용': ('Use', '使用'),
    '사용하지 않음': ("Don't use", '使用しない'),
    '보정 없음': ('no modifier', '補正なし'),
    '예': ('Yes', 'はい'),
    '아니오': ('No', 'いいえ'),
    '하나를 고르세요': ('Choose one', '1つ選んでください'),
    # 엔진(engine.py·effects.py)이 직접 쓰는 결정 문구와 선택지
    '먼저 해결할 효과를 선택하세요.': ('Choose the effect to resolve first.', '先に解決する効果を選んでください。'),
    '무응답 기술에 대한 판정을 선택하세요.': (
        'Choose the judgment for the unanswered Technique.', '無応答の技に対する判定を選んでください。',
    ),
    '사이드 덱에서 리스트로 보충할 카드를 선택할 수 있습니다.': (
        'You may choose a card from your Side Deck to refill your List.', 'サイドデッキからリストに補充するカードを選べます。',
    ),
    '상대 손패에서 강제 레디할 카드를 선택하세요.': (
        "Choose a card in your opponent's hand to force Ready.", '相手の手札から強制レディするカードを選んでください。',
    ),
    '상대가 획득할 리스트의 기술을 선택하세요.': (
        'Choose a Technique in the List for your opponent to take.', '相手が獲得するリストの技を選んでください。',
    ),
    '선택한 카드의 종류를 선언하세요.': ('Declare the type of the chosen card.', '選んだカードの種類を宣言してください。'),
    '종류를 추측할 상대 패 1장을 선택하세요.': (
        "Choose 1 card in your opponent's hand to guess its type.", '種類を推測する相手の手札を1枚選んでください。',
    ),
    '추측 효과를 다시 사용하시겠습니까?': ('Use the guessing effect again?', '推測効果をもう一度使用しますか?'),
    '카드 사용 비용을 지불할 대상을 선택하세요.': (
        "Choose what to pay the card's cost with.", 'カードの使用コストを支払う対象を選んでください。',
    ),
    '콤보 속도 예외 비용으로 버릴 카드를 선택하세요.': (
        'Choose a card to discard for the combo speed exception cost.', 'コンボ速度の例外コストとして捨てるカードを選んでください。',
    ),
    '패의 그랩을 브레이크해 상대 그랩을 무효로 할 수 있습니다.': (
        "You may break a Grab in your hand to negate your opponent's Grab.", '手札のグラブをブレイクして相手のグラブを無効にできます。',
    ),
    '공개된 기술의 사용 조건으로 버릴 카드를 선택하세요.': (
        "Choose a card to discard for the revealed Technique's use condition.", '公開された技の使用条件として捨てるカードを選んでください。',
    ),
    '효과 대상 선택': ('Choose a target', '効果の対象を選択'),
    '효과 선택': ('Choose an effect', '効果を選択'),
    '효과 발동 여부를 선택': ('Choose whether to activate the effect', '効果を発動するか選択'),
    '수치를 선택하세요.': ('Choose a value.', '数値を選んでください。'),
    '적용할 효과를 선택하세요.': ('Choose an effect to apply.', '適用する効果を選んでください。'),
    '상대가 선택 중입니다.': ('Your opponent is choosing.', '相手が選択中です。'),
    '다시 사용': ('Use again', 'もう一度使用'),
    '종료': ('End', '終了'),
    '조건에 맞는 카드가 없습니다.': ('No card meets the condition.', '条件に合うカードがありません。'),
}

# 카드 DSL의 능력 라벨·결정 문구·선택지(카드 효과문 조각) 번역표. 키는 정의에 적힌 한국어 원문이고
# 값에는 [[kind:slug]] 표기가 그대로 남아 있어 언어별로 렌더링해 쓴다.
# 새 카드의 문구가 빠졌는지는 `manage.py audit_play_effect_text`로 확인한다.
EFFECT_TEXT_PATH = Path(__file__).with_name('play_effect_text.json')
_EFFECT_TEXT = {'source': None, 'at': 0.0, 'tables': {}}


def _effect_key(text):
    return ' '.join(str(text).split())


def effect_text_source():
    """Normalized Korean -> [English, Japanese] from ``play_effect_text.json``."""
    if _EFFECT_TEXT['source'] is None:
        try:
            rows = json.loads(EFFECT_TEXT_PATH.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            rows = {}
        _EFFECT_TEXT['source'] = {
            _effect_key(ko): values for ko, values in rows.items()
            if isinstance(values, (list, tuple)) and len(values) == 2
        }
    return _EFFECT_TEXT['source']


def _effect_table(language):
    """Raw and rendered Korean keys -> the translation rendered in ``language``.

    Session payloads render ``[[kind:slug]]`` in the viewer's language before
    they reach this module, so each key is stored both raw and rendered.
    """
    now = time.monotonic()
    if now - _EFFECT_TEXT['at'] > NAME_CACHE_SECONDS:
        _EFFECT_TEXT.update(at=now, tables={})
    table = _EFFECT_TEXT['tables'].get(language)
    if table is None:
        index = 0 if language == 'en' else 1
        table = {}
        for ko, values in effect_text_source().items():
            translated = values[index]
            if not translated:
                continue
            value = render_visible_markup(translated, language) if '[[' in translated else translated
            table[ko] = value
            if '[[' in ko:
                table.setdefault(_effect_key(render_visible_markup(ko, language)), value)
        _EFFECT_TEXT['tables'][language] = table
    return table


def _effect_text(text, language):
    if not isinstance(text, str) or not text.strip():
        return None
    return _effect_table(language).get(_effect_key(text))


def _exact(text, language):
    row = ENGINE_TEXT.get(text)
    if not row:
        return None
    return row[0] if language == 'en' else row[1]


def _card_names(payload, language):
    """Korean card name -> translated name for every card the payload shows."""
    ids = set()

    def walk(value):
        if isinstance(value, dict):
            card_id = value.get('card_id')
            if isinstance(card_id, int):
                ids.add(card_id)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload.get('state'))
    walk(payload.get('pending_decision'))
    for action in payload.get('legal_actions') or []:
        if isinstance(action, dict):
            walk(action.get('options'))
    if not ids:
        return {}
    now = time.monotonic()
    if now - _NAME_CACHE['at'] > NAME_CACHE_SECONDS:
        _NAME_CACHE.update(at=now, rows={})
    rows = _NAME_CACHE['rows']
    missing = [card_id for card_id in ids if (card_id, language) not in rows]
    if missing:
        for card in Card.objects.prefetch_related('translations').filter(id__in=missing):
            rows[(card.id, language)] = (card.name, translated_card_field(card, language, 'name'))
        for card_id in missing:
            rows.setdefault((card_id, language), (None, None))
    names = {}
    for card_id in ids:
        source, translated = rows[(card_id, language)]
        if source and translated and translated != source:
            names[source] = translated
    return names


def localize_engine_text(text, language, card_names=None):
    """One engine string in ``language``; returns ``text`` unchanged for Korean."""
    if not isinstance(text, str) or not HANGUL.search(text):
        return text
    exact = _exact(text, language)
    if exact is None:
        exact = _effect_text(text, language)
    if exact is not None:
        return exact
    result = text
    for name in sorted(card_names or {}, key=len, reverse=True):
        result = result.replace(name, card_names[name])
    speed = 'speed {n}' if language == 'en' else '速度{n}'
    result = SPEED_SUFFIX.sub(lambda match: f' ({speed.format(n=match.group(1))})' if language == 'en'
                              else f'({speed.format(n=match.group(1))})', result)
    parts = PART_SEPARATORS.split(result)
    result = ''.join(_exact(part, language) or _effect_text(part, language) or part for part in parts)
    if HANGUL.search(result):
        # 용어 단위 치환은 짧은 용어(상단 회피 등)에만 맞는다. 문장에 쓰면 한국어와 영어가 뒤섞인
        # 문장이 되므로, 남김없이 옮겨질 때만 쓴다.
        by_terms = translate_text_by_parts(result, language)
        if not HANGUL.search(by_terms):
            result = by_terms
    return result


UNAVAILABLE_VERBS = {
    # 한국어 동사 -> (English past participle, 日本語「〜ません」, 日本語「〜ないカードしかありません」)
    '브레이크할': ('broken', 'ブレイクできません', 'ブレイクできないカードしかありません'),
    '옮길': ('moved', '移動できません', '移動できないカードしかありません'),
    '버릴': ('discarded', '捨てられません', '捨てられないカードしかありません'),
}
SHORTAGE_REASON = re.compile(r'^조건에 맞는 카드가 부족합니다\((\d+)/(\d+)\)\.$')
ONLY_BLOCKED_REASON = re.compile(r'^효과로 (\S+) 수 없는 카드뿐입니다\.$')
BLOCKED_BY_REASON = re.compile(r'^(.+) 효과로 (\S+) 수 없습니다\.$')
QUOTED_NAME = re.compile(r'「([^」]+)」')


def localize_unavailable_reason(reason, language, card_names=None):
    """Why an option cannot be chosen (engine ``selector_unavailable_reason``)."""
    if not isinstance(reason, str) or not HANGUL.search(reason):
        return reason
    en = language == 'en'
    match = SHORTAGE_REASON.match(reason)
    if match:
        count = f'{match.group(1)}/{match.group(2)}'
        return (f'Not enough cards meet the condition ({count}).' if en
                else f'条件に合うカードが足りません({count})。')
    match = ONLY_BLOCKED_REASON.match(reason)
    if match and match.group(1) in UNAVAILABLE_VERBS:
        verb = UNAVAILABLE_VERBS[match.group(1)]
        return f'Every candidate is protected from being {verb[0]} by an effect.' if en else f'効果で{verb[2]}。'
    match = BLOCKED_BY_REASON.match(reason)
    if match and match.group(2) in UNAVAILABLE_VERBS:
        verb = UNAVAILABLE_VERBS[match.group(2)]
        names = QUOTED_NAME.sub(
            lambda found: f'「{(card_names or {}).get(found.group(1), found.group(1))}」', match.group(1),
        )
        return f"Can't be {verb[0]} because of {names}." if en else f'{names}の効果で{verb[1]}。'
    return localize_engine_text(reason, language, card_names)


GENERIC_PROMPTS = {
    # (English, Japanese). {card} is the source card's translated name.
    'optional_effect': ("Activate {card}'s effect?", '{card}の効果を発動しますか?'),
    None: ('{card}: make a choice', '{card}:選択してください'),
}
NO_SOURCE_PROMPT = ('Make a choice', '選択してください')


def _source_card_name(source, language):
    code = (source or {}).get('card_code') if isinstance(source, dict) else None
    if not code:
        return ''
    card = Card.objects.prefetch_related('translations').filter(code=code).first()
    return translated_card_field(card, language, 'name') if card else ''


def localize_prompt(prompt, language, card_names=None, *, kind=None, source=None):
    """A decision prompt. Effect prompts are fragments of card text; when they
    cannot be translated whole, a generic prompt naming the card is clearer than
    a half-Korean sentence (the full card text is one tap away)."""
    translated = localize_engine_text(prompt, language, card_names)
    if not isinstance(translated, str) or not HANGUL.search(translated):
        return translated
    index = 0 if language == 'en' else 1
    name = _source_card_name(source, language)
    if not name:
        return NO_SOURCE_PROMPT[index]
    template = GENERIC_PROMPTS.get(kind) or GENERIC_PROMPTS[None]
    return template[index].format(card=name)


CARD_NAME_FIELDS = ('card_label', 'name', 'source_card_label')
EFFECT_FALLBACK = ('Effect activated', '効果発動')


def _translate_card_fields(value, language, names):
    """Card names inside an event payload (``card_label``/``name`` next to a ``card_id``)."""
    if isinstance(value, dict):
        for key in CARD_NAME_FIELDS:
            text = value.get(key)
            if isinstance(text, str) and HANGUL.search(text):
                value[key] = localize_engine_text(text, language, names)
        for item in value.values():
            if isinstance(item, (dict, list)):
                _translate_card_fields(item, language, names)
    elif isinstance(value, list):
        for item in value:
            _translate_card_fields(item, language, names)


def localize_event_payload(event_type, payload, language):
    """Event payload for the log/animations: card names, decision prompts and
    choices, and effect descriptions."""
    language = normalize_language(language)
    if language == DEFAULT_LANGUAGE or not isinstance(payload, dict):
        return payload
    names = _card_names({'state': payload}, language)
    if names:
        _translate_card_fields(payload, language, names)
    effect = payload.get('effect_label')
    if isinstance(effect, str) and HANGUL.search(effect):
        # 효과 설명은 카드 효과문 조각이다. 통째로 옮기지 못하면 반쯤 한국어인 문장 대신
        # "효과 발동"으로 보여 준다(카드 이름은 card_label로 함께 보인다).
        translated = localize_engine_text(effect, language, names)
        payload['effect_label'] = translated if not HANGUL.search(translated) else EFFECT_FALLBACK[0 if language == 'en' else 1]
    if event_type not in ('decision_resolved', 'decision_requested'):
        return payload
    if 'prompt' in payload:
        payload['prompt'] = localize_prompt(
            payload['prompt'], language, names, kind=payload.get('kind'), source=payload.get('source'),
        )
    for option in payload.get('selected_options') or []:
        if isinstance(option, dict) and 'label' in option:
            option['label'] = localize_engine_text(option['label'], language, names)
    return payload


PLAYER_NAME = re.compile(r'^플레이어\s*(\d)\s*(?:\((.+)\))?$')


def _localize_players(state, language):
    """Character names (and the default ``플레이어1(캐릭터)`` seat names).

    Automatic sessions rebuild the player block from the engine state after the
    usual localization step, so the character name arrives in Korean.
    """
    players = (state or {}).get('players') if isinstance(state, dict) else None
    if not isinstance(players, dict):
        return
    characters = {}
    ids = {
        (player.get('character') or {}).get('id')
        for player in players.values() if isinstance(player, dict) and isinstance(player.get('character'), dict)
    }
    ids.discard(None)
    if ids:
        for character in Character.objects.filter(id__in=ids):
            characters[character.id] = (character.name, translated_character_field(character, language, 'name'))
    player_word = 'Player ' if language == 'en' else 'プレイヤー'
    for player in players.values():
        if not isinstance(player, dict):
            continue
        character = player.get('character')
        names = characters.get((character or {}).get('id')) if isinstance(character, dict) else None
        if names and names[1]:
            character['name'] = names[1]
        match = PLAYER_NAME.match(str(player.get('name') or ''))
        if match:
            inner = match.group(2) or ''
            if names and inner == names[0]:
                inner = names[1]
            player['name'] = f'{player_word}{match.group(1)}' + (f' ({inner})' if inner else '')


CATALOG_FIELDS = ('name', 'text_label', 'detail_text_label', 'type_label', 'pos_label')


def _localize_preparation_catalogs(preparation, language):
    """Deck-prep card catalogs carry Korean names/text; use the localized metadata."""
    catalogs = []

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == 'catalog' and isinstance(item, dict):
                    catalogs.append(item)
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(preparation)
    ids = {card_id for catalog in catalogs for card_id in catalog}
    if not ids:
        return
    from .simulator_services import serialize_simulator_card_metadata

    metadata = serialize_simulator_card_metadata(ids, language)
    for catalog in catalogs:
        for card_id, card in catalog.items():
            localized = metadata.get(str(card_id))
            if not isinstance(card, dict) or not localized:
                continue
            for field in CATALOG_FIELDS:
                if localized.get(field):
                    card[field] = localized[field]


def localize_engine_text_fields(payload, language):
    """Translate engine labels/prompts in a serialized session (in place)."""
    language = normalize_language(language)
    if language == DEFAULT_LANGUAGE or not isinstance(payload, dict):
        return payload
    names = _card_names(payload, language)

    def options(items):
        for option in items or []:
            if isinstance(option, dict) and 'label' in option:
                option['label'] = localize_engine_text(option['label'], language, names)

    pending = payload.get('pending_decision') if isinstance(payload.get('pending_decision'), dict) else {}
    for action in payload.get('legal_actions') or []:
        if not isinstance(action, dict):
            continue
        for key in ('label', 'prompt'):
            if key not in action:
                continue
            if key == 'prompt' or action.get('type') == 'submit_decision':
                # 결정 행동의 label은 결정 문구(prompt)를 그대로 쓴다.
                action[key] = localize_prompt(
                    action[key], language, names, kind=pending.get('kind'), source=pending.get('source'),
                )
            else:
                action[key] = localize_engine_text(action[key], language, names)
        options(action.get('options'))
    _localize_players(payload.get('state'), language)
    if isinstance(payload.get('preparation'), dict):
        _localize_preparation_catalogs(payload['preparation'], language)
    decision = payload.get('pending_decision')
    if isinstance(decision, dict):
        if 'prompt' in decision:
            decision['prompt'] = localize_prompt(
                decision['prompt'], language, names, kind=decision.get('kind'), source=decision.get('source'),
            )
        options(decision.get('options'))
        for option in decision.get('unavailable_options') or []:
            if not isinstance(option, dict):
                continue
            if 'label' in option:
                option['label'] = localize_engine_text(option['label'], language, names)
            if 'reason' in option:
                option['reason'] = localize_unavailable_reason(option['reason'], language, names)
    return payload
