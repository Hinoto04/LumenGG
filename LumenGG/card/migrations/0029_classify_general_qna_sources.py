from django.db import migrations
from django.utils import timezone


GENERAL_QNA_IDS = {645, 679}


def classify_general_qna_sources(apps, schema_editor):
    Card = apps.get_model('card', 'Card')
    card = Card.objects.filter(code='CB03-AT-001').first()
    if not card or not isinstance(card.effect_definition, dict):
        return
    definition = dict(card.effect_definition)
    changed = False
    abilities = []
    for ability in definition.get('abilities') or []:
        if not isinstance(ability, dict) or ability.get('id') != 'cb03-at-001-n1':
            abilities.append(ability)
            continue
        normalized = dict(ability)
        sources = dict(normalized.get('source_refs') or {})
        linked = list(sources.get('qna_ids') or [])
        general = set(sources.get('general_qna_ids') or [])
        moved = GENERAL_QNA_IDS.intersection(linked)
        if moved:
            sources['qna_ids'] = [item for item in linked if item not in moved]
            general.update(moved)
            sources['general_qna_ids'] = sorted(general)
            normalized['source_refs'] = sources
            changed = True
        abilities.append(normalized)
    if not changed:
        return
    definition['abilities'] = abilities
    card.effect_definition = definition
    card.effect_revision = int(card.effect_revision or 0) + 1
    card.effect_updated_at = timezone.now()
    card.save(update_fields=[
        'effect_definition', 'effect_revision', 'effect_updated_at',
    ])


class Migration(migrations.Migration):
    dependencies = [('card', '0028_normalize_reviewed_effect_drafts')]

    operations = [
        migrations.RunPython(
            classify_general_qna_sources,
            migrations.RunPython.noop,
        ),
    ]
