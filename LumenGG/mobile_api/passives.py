"""Translate existing passive panels into data, without shipping executable code."""
import copy
from battlelog.services import _passive_ui, _passive_cards, initial_passive_state_for_character


def native_passive(character, language='ko'):
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
            for k, v in initial_passive_state_for_character(character).items() if isinstance(v, dict)
        ]
        if not options['controls']:
            options['controls'] = [{'type': 'counter', 'key': str(card['id']), 'label': card['name']} for card in _passive_cards(character, language)]
    options['schema_version'] = 1
    return options
