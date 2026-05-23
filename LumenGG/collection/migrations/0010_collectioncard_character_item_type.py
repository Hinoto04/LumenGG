from django.db import migrations, models
import django.db.models.deletion


def backfill_collection_card_character(apps, schema_editor):
    Card = apps.get_model('card', 'Card')
    Character = apps.get_model('card', 'Character')
    CollectionCard = apps.get_model('collection', 'CollectionCard')

    card_character_ids = dict(Card.objects.values_list('id', 'character_id'))
    characters = sorted(
        Character.objects.exclude(name='').values_list('id', 'name'),
        key=lambda row: len(row[1] or ''),
        reverse=True,
    )

    updates = []
    for collection_card in CollectionCard.objects.all():
        item_type = 'other'
        character_id = None

        if collection_card.card_id:
            item_type = 'card'
            character_id = card_character_ids.get(collection_card.card_id)
        else:
            name = collection_card.name or ''
            matched_character_id = None
            for candidate_id, candidate_name in characters:
                if candidate_name and candidate_name in name:
                    matched_character_id = candidate_id
                    break

            if matched_character_id:
                character_id = matched_character_id
                item_type = 'token' if '토큰' in name else 'skin'

        if collection_card.character_id != character_id or collection_card.item_type != item_type:
            collection_card.character_id = character_id
            collection_card.item_type = item_type
            updates.append(collection_card)

    if updates:
        CollectionCard.objects.bulk_update(updates, ['character', 'item_type'], batch_size=500)


def clear_backfilled_collection_card_character(apps, schema_editor):
    CollectionCard = apps.get_model('collection', 'CollectionCard')
    CollectionCard.objects.update(character=None, item_type='card')


class Migration(migrations.Migration):

    dependencies = [
        ('card', '0024_cardtranslation_charactertranslation'),
        ('collection', '0009_packtranslation'),
    ]

    operations = [
        migrations.AddField(
            model_name='collectioncard',
            name='character',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='collection_cards', to='card.character'),
        ),
        migrations.AddField(
            model_name='collectioncard',
            name='item_type',
            field=models.CharField(choices=[('card', '카드'), ('skin', '스킨'), ('token', '토큰'), ('other', '기타')], default='card', max_length=12),
        ),
        migrations.RunPython(backfill_collection_card_character, clear_backfilled_collection_card_character),
    ]
