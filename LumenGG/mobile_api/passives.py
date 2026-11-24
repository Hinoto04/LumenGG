"""Translate existing passive panels into data, without shipping executable code."""
import copy
import re
from battlelog.services import _passive_ui, _passive_cards, initial_passive_state_for_character
from battlelog.shields import SHIELD_KEY


def native_passive(character, language='ko', with_tokens=True):
    ui = _passive_ui(character, language)
    options = copy.deepcopy(ui.get('options') or {})
    if not isinstance(options, dict):
        options = {}
    script = ui.get('js', '')
    if 'root_charge' in script and not options.get('controls'):
        options['controls'] = [{'type': 'toggle', 'key': 'root_charge', 'label': {'ko': '차지', 'en': 'Charge', 'ja': 'チャージ'}[language]}]
    elif 'yang_counter' in script and 'yin_counter' in script and not options.get('controls'):
        labels = {'ko': ['양', '음', '조화', '조화 효과'], 'en': ['Yang', 'Yin', 'Harmony', 'Harmony effect'], 'ja': ['陽', '陰', '調和', '調和効果']}[language]
        options['controls'] = [
            {'type': 'counter', 'key': 'yang_counter', 'label': labels[0], 'max': 4},
            {'type': 'counter', 'key': 'yin_counter', 'label': labels[1], 'max': 4},
            {'type': 'latchedStatus', 'key': 'harmony', 'label': labels[2],
             'activateWhen': {'type': 'allEquals', 'keys':['yang_counter','yin_counter'], 'value':4},
             'keepWhile': {'type': 'allAtLeast', 'keys':['yang_counter','yin_counter'], 'value':3}},
            {'type': 'choice', 'key': 'harmony_effect', 'label': labels[3],
             'enableWhen': {'type': 'active', 'key': 'harmony'},
             'choices': [{'value': 'damage_100', 'label': '+100DMG'}, {'value': 'fp_1', 'label': '+1FP'}]},
        ]
        options['adapter'] = 'tao'
    # All configurable controls are already declarative. Unsupported custom
    # panels retain named editable state instead of executing HTML/JS.
    if not options.get('controls'):
        options['controls'] = [
            {'type': 'toggle' if isinstance(v.get('value'), bool) else 'counter' if 'count' in v else 'text',
             'key': k, 'label': v.get('label', k)}
            for k, v in initial_passive_state_for_character(character).items() if isinstance(v, dict) and k != SHIELD_KEY
        ]
        if not options['controls']:
            options['controls'] = [{'type': 'counter', 'key': str(card['id']), 'label': card['name']} for card in _passive_cards(character, language)]
    for control in options.get('controls') or []:
        if isinstance(control, dict) and control.get('key') in COUNTER_MAX_OVERRIDES:
            control['max'] = COUNTER_MAX_OVERRIDES[control['key']]
    if with_tokens:
        _attach_token_cards(options, character, language)
    options['schema_version'] = 1
    return options


# 계산기에서 다루기 쉬운 최대 개수(불빛 수). 실제 값은 ± 버튼으로 이 안에서 조정한다.
COUNTER_MAX_OVERRIDES = {'foresight_counter': 5}
_TOKEN_NAME_NOISE = re.compile(r'[「」『』【】\[\]()\s]|토큰')


def _token_name(text):
    return _TOKEN_NAME_NOISE.sub('', str(text or ''))


def _attach_token_cards(options, character, language):
    """카운터 이름에 그 캐릭터의 토큰 카드 이름이 들어 있으면 카드 그림을 붙인다(예: 개러지 토큰 ↔ 「개러지」)."""
    controls = [control for control in options.get('controls') or [] if isinstance(control, dict) and control.get('type') == 'counter']
    character_id = getattr(character, 'id', None)
    if not controls or not character_id:
        return
    from card.models import Card
    tokens = [(_token_name(card.name), card) for card in Card.objects.filter(character_id=character_id, type__contains='토큰').order_by('id')]
    tokens = [(name, card) for name, card in tokens if name]
    if not tokens:
        return
    # 이름 비교는 한국어 원문으로 한다. 다른 언어 화면이면 한국어 정의의 이름을 키로 찾는다.
    korean = {control.get('key'): control.get('label') for control in (options if language == 'ko' else native_passive(character, 'ko', with_tokens=False)).get('controls') or [] if isinstance(control, dict)}
    for control in controls:
        label = _token_name(korean.get(control.get('key')) or control.get('label'))
        # 가장 긴 이름부터 맞춰 짧은 이름이 먼저 걸리지 않게 한다.
        match = next((card for name, card in sorted(tokens, key=lambda pair: -len(pair[0])) if name in label), None)
        if match and match.img:
            control['token'] = {'id': match.id, 'code': match.code, 'img': match.img}
