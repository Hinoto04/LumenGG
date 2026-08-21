from django.db import migrations
from django.utils import timezone


def normalize_reviewed_effect_drafts(apps, schema_editor):
    Card = apps.get_model('card', 'Card')
    updates = []
    for card in Card.objects.all().only(
        'id', 'effect_definition', 'effect_revision', 'effect_updated_at',
    ).iterator():
        definition = card.effect_definition
        if not isinstance(definition, dict) or definition.get('reviewed') is not True:
            continue
        changed = definition.get('draft') is not False
        definition = dict(definition)
        definition['draft'] = False
        abilities = []
        for ability in definition.get('abilities') or []:
            if not isinstance(ability, dict):
                abilities.append(ability)
                continue
            normalized = dict(ability)
            if normalized.get('draft') is not False:
                changed = True
            normalized['draft'] = False
            abilities.append(normalized)
        definition['abilities'] = abilities
        if not changed:
            continue
        card.effect_definition = definition
        card.effect_revision = int(card.effect_revision or 0) + 1
        card.effect_updated_at = timezone.now()
        updates.append(card)
    if updates:
        Card.objects.bulk_update(
            updates,
            ['effect_definition', 'effect_revision', 'effect_updated_at'],
            batch_size=100,
        )


class Migration(migrations.Migration):
    dependencies = [('card', '0027_portable_optional_unique_keys')]

    operations = [
        migrations.RunPython(
            normalize_reviewed_effect_drafts,
            migrations.RunPython.noop,
        ),
    ]
