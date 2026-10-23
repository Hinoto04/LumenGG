"""Resolve selected trait setup without mixing another trait's abilities."""
import copy
from types import SimpleNamespace
from django.db.models import Q
from battlelog.game.card_identity import is_passive_card
from card.models import Card

TRAIT_SETUP_KEYS = ('battle_passive_ui', 'simulator_passive_ui', 'initial_passive_state', 'automatic_deck_rules')


def trait_choices(character_id):
    return Card.objects.filter(Q(character_id=character_id), Q(type='특성') | Q(code__icontains='PS')).order_by('id')


def selected_trait(character_id, trait_id=None, *, required=False):
    if trait_id:
        card = Card.objects.filter(pk=trait_id, character_id=character_id).first()
        if not card or not is_passive_card(card):
            raise ValueError('선택한 캐릭터의 특성을 선택해주세요.')
        return card
    choices = list(trait_choices(character_id)[:2])
    if len(choices) == 1:
        return choices[0]
    if required:
        raise ValueError('사용할 특성을 선택해주세요.')
    return None


def setup_character(character, trait):
    if not trait:
        return character
    data = copy.deepcopy(character.datas or {})
    for key in TRAIT_SETUP_KEYS:
        data.pop(key, None)
    # Remove historical aliases which otherwise select a different trait's UI.
    for key in ('battle_calculator', 'battleCalculator', 'battle', 'simulator', 'passive_ui', 'passiveUi', 'simulatorPassiveUi', 'battlePassiveUi'):
        data.pop(key, None)
    config = copy.deepcopy(getattr(trait, 'trait_config', None) or {})
    data.update(config)
    if 'deck_rules' in config:
        data['automatic_deck_rules'] = config['deck_rules']
    return SimpleNamespace(id=character.id, pk=character.id, name=character.name,
                           datas=data, trait_card_id=trait.id, trait_config=config,
                           localization_key=getattr(character, 'localization_key', None),
                           **{key: getattr(character, key, '') for key in ('img', 'sd_img', 'icon_img', 'body_img', 'color')})


def allowed_passive_keys(character):
    from mobile_api.passives import native_passive
    from battlelog.services import initial_passive_state_for_character, PASSIVE_UI_SEMANTIC_SLUG_ALIASES, _passive_ui
    definition = native_passive(character)
    keys = {'memo', str(character.trait_card_id), *initial_passive_state_for_character(character)}
    for group in ('controls', 'badges', 'latchedStatuses'):
        for control in definition.get(group, []):
            if control.get('key'):
                keys.add(control['key'])
            keys.update(control.get('resetKeys') or [])
    keys.update(_passive_ui(character).get('managed_keys') or [])
    for alias, canonical in PASSIVE_UI_SEMANTIC_SLUG_ALIASES.items():
        if alias in keys or canonical in keys:
            keys.update((alias, canonical))
    return keys
