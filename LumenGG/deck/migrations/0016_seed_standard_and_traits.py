import copy
from django.db import migrations, models


def seed(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    Card = apps.get_model('card', 'Card')
    Deck = apps.get_model('deck', 'Deck')
    Regulation = apps.get_model('deck', 'Regulation')
    Version = apps.get_model('deck', 'RegulationVersion')
    regulation = Regulation.objects.create(name='기본 규정')
    Version.objects.create(regulation=regulation, version='1', rules={
        'bans': [], 'combinations': [], 'reserve_limit': 0,
        'technique_swap_limit': 0, 'trait_swap_limit': 0, 'ultimate_swap_limit': 0,
        'reserve_public': False, 'swaps_public': False,
    })
    for character in Character.objects.all().iterator():
        traits = list(Card.objects.filter(character_id=character.pk).filter(
            models.Q(type='특성') | models.Q(code__icontains='PS'))[:2])
        if len(traits) != 1:
            continue
        trait = traits[0]
        config = copy.deepcopy(trait.trait_config or {})
        for key in ('battle_passive_ui', 'simulator_passive_ui', 'initial_passive_state', 'automatic_deck_rules', 'battle_calculator', 'battleCalculator', 'battle', 'simulator', 'passive_ui', 'passiveUi', 'simulatorPassiveUi', 'battlePassiveUi'):
            if key in (character.datas or {}):
                config.setdefault('deck_rules' if key == 'automatic_deck_rules' else key, copy.deepcopy(character.datas[key]))
        config.setdefault('legacy_character_actions', True)
        config.setdefault('supports_shield', character.name == '핀프')
        trait.trait_config = config
        trait.save(update_fields=['trait_config'])
        Deck.objects.filter(character_id=character.pk, trait_card__isnull=True).update(trait_card_id=trait.pk)


class Migration(migrations.Migration):
    dependencies = [('deck', '0015_deck_schema_version_deck_trait_card_regulation_and_more')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
