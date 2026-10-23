"""Upgrade the bundled offline seed using its existing, frozen source text.

Run from the repository root with .venv/Scripts/python.exe. No server database
or published releases are touched. Re-running an already upgraded seed is safe.
"""
import copy
import json
import os
from pathlib import Path
import sqlite3
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'LumenGG'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LumenGG.test_settings')
import django
django.setup()
from battlelog.game.drafts import build_effect_draft

path = root / 'mobile/assets/catalog.sqlite'
with sqlite3.connect(path) as db:
    schema = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0]
    if schema == '2' and '--refresh' not in sys.argv:
        print('Bundled catalog is already schema 2.')
        raise SystemExit(0)
    rows = [(kind, pk, json.loads(raw)) for kind, pk, raw in db.execute('SELECT kind,id,data FROM entries')]
    cards = {pk: data for kind, pk, data in rows if kind == 'card'}
    definitions = {}
    for pk, card in cards.items():
        source = card.get('localized', {}).get('ko', {})
        definition = build_effect_draft(card.get('code') or '', source.get('text') or '', detail_text=source.get('detail_text') or '')
        definitions[pk] = definition
        card.update(original_name=source.get('name', ''), setup_rules=definition.get('deck_rules_when_included', {}), deck_limit=definition.get('deck_limit'), token_key=definition.get('token_key'))
    # The legacy seed stores display markup. Reconstruct semantic references
    # from its own card identities before compiling printed deck exceptions.
    references = {}
    for kind, pk, character in rows:
        if kind == 'character':
            name = character['localized']['ko']['name']
            key = (character.get('calculator_ui') or {}).get('theme_key') or f'character_{pk}'
            references[f'[{name}]'] = f'[[character:{key}]]'
    for pk, card in cards.items():
        name = card['localized']['ko']['name']
        token = definitions[pk].get('token_key')
        reference = f'[[token:{token}]]' if token else f'[[card:{card["code"]}]]'
        for wrapper in ('[{}]', '【{}】'):
            references.setdefault(wrapper.format(name), reference)
    for pk, card in cards.items():
        source = card['localized']['ko']
        text = source.get('text') or ''
        for visible, semantic in sorted(references.items(), key=lambda row: -len(row[0])):
            text = text.replace(visible, semantic)
        definition = build_effect_draft(card.get('code') or '', text, detail_text=source.get('detail_text') or '')
        definitions[pk] = definition
        card.update(setup_rules=definition.get('deck_rules_when_included', {}), deck_limit=definition.get('deck_limit'), token_key=definition.get('token_key'))
    for kind, pk, character in rows:
        if kind != 'character':
            continue
        traits = [card for card in cards.values() if card['character_id'] == pk and card['type'] == '특성']
        character['base_deck_rules'] = {}
        character['traits'] = []
        for trait in traits:
            # The old seed contains exactly one trait per playable character.
            # Ambiguous future seeds must be published with explicit profiles.
            if len(traits) != 1:
                raise ValueError('Cannot infer an ambiguous legacy trait profile.')
            config = {'legacy_character_actions': True, 'supports_shield': pk == 17,
                      'initial_passive_state': copy.deepcopy(character['initial_passive_state']),
                      'battle_passive_ui': {'options': copy.deepcopy(character['localized']['ko'].get('passive', {}))}}
            character['traits'].append({
                'id': trait['id'], 'name': trait['localized']['ko']['name'], 'code': trait['code'], 'img': trait['img_sm'] or trait['img'],
                'trait_config': config, 'deck_rules': definitions[trait['id']].get('deck_rules', {}),
                'initial_hp': character['initial_hp'], 'hand_table': copy.deepcopy(character['hand_table']),
                'initial_passive_state': copy.deepcopy(character['initial_passive_state']),
                'localized': {lang: {'name': trait['localized'][lang]['name'], 'passive': copy.deepcopy(value.get('passive', {}))} for lang, value in character['localized'].items()},
            })
    for kind, pk, data in rows:
        if kind == 'rules':
            data.update(schema_version=2, regulations=[])
        db.execute('UPDATE entries SET data=? WHERE kind=? AND id=?', (json.dumps(data, ensure_ascii=False, separators=(',', ':')), kind, pk))
    db.execute("UPDATE metadata SET value='2' WHERE key='schema_version'")
    db.execute("UPDATE metadata SET value='seed-20261023-traits-v2' WHERE key='release_version'")
    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise ValueError('Invalid seed catalog.')
print('Upgraded bundled catalog to schema 2 without contacting the server.')
