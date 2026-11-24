"""Translate the automatic engine's Korean UI strings for the play client.

The engine writes action labels (``레디 · 하이 잽``), decision prompts and option
labels in Korean. For English/Japanese viewers the session payload is passed
through :func:`localize_engine_text_fields` just before it is sent:

* fixed engine words use the exact table below (no substring guessing —
  ``ui_text``'s term fallback turns ``발동하지 않음`` into nonsense);
* card names are swapped for the card's translated name;
* ``(5속도)`` speed suffixes are rewritten;
* what is left goes through the shared translation catalog part by part.

Only display fields are touched. ``legal_actions[].payload`` and option ids are
echoed back to the engine and stay as they are.
"""
import re
import time

from card.models import Card, Character
from common.language import (
    DEFAULT_LANGUAGE,
    normalize_language,
    translated_card_field,
    translated_character_field,
)
from common.localization import translate_text_by_parts

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
}


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
    if exact is not None:
        return exact
    result = text
    for name in sorted(card_names or {}, key=len, reverse=True):
        result = result.replace(name, card_names[name])
    speed = 'speed {n}' if language == 'en' else '速度{n}'
    result = SPEED_SUFFIX.sub(lambda match: f' ({speed.format(n=match.group(1))})' if language == 'en'
                              else f'({speed.format(n=match.group(1))})', result)
    parts = PART_SEPARATORS.split(result)
    result = ''.join(_exact(part, language) or part for part in parts)
    if HANGUL.search(result):
        result = translate_text_by_parts(result, language)
    return result


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
    return payload
