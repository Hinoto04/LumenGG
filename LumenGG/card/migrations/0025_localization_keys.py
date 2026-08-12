import re
import unicodedata

from django.db import migrations, models


CHARACTER_KEY_OVERRIDES = {
    '세츠메이': 'setsumei',
    '니아': 'nya',
    '루트': 'route',
    '델피': 'delphi',
    '키스': 'kiss',
    '울프': 'wolf',
    '비올라': 'viola',
    '타오': 'tao',
    '리타': 'lita',
    '레브': 'reve',
    '린': 'rin',
    '요한': 'yohann',
    '이제벨': 'ezebel',
    '이오몽': 'eomong',
    '키메라': 'chimera',
    '무영': 'muyoung',
    '핀프': 'pinp',
    'CMYK': 'cmyk',
    '미녕이': 'minyeongi',
}


def slugify_key(value, fallback):
    normalized = unicodedata.normalize('NFKD', str(value or ''))
    ascii_value = normalized.encode('ascii', 'ignore').decode('ascii').lower()
    slug = re.sub(r'[^a-z0-9]+', '_', ascii_value).strip('_')
    return slug or fallback


def backfill_character_keys(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    CharacterTranslation = apps.get_model('card', 'CharacterTranslation')
    used = set()

    for character in Character.objects.order_by('id'):
        key = CHARACTER_KEY_OVERRIDES.get(character.name)
        if not key:
            english_name = (
                CharacterTranslation.objects
                .filter(character_id=character.id, language='en')
                .values_list('name', flat=True)
                .first()
            )
            key = slugify_key(english_name or character.name, f'character_{character.id}')

        base = key
        index = 2
        while key in used:
            key = f'{base}_{index}'
            index += 1
        used.add(key)
        character.localization_key = key
        character.save(update_fields=['localization_key'])


def clear_character_keys(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    Character.objects.update(localization_key='')


class Migration(migrations.Migration):

    dependencies = [
        ('card', '0024_cardtranslation_charactertranslation'),
    ]

    operations = [
        migrations.AddField(
            model_name='character',
            name='localization_key',
            field=models.CharField(blank=True, db_index=True, max_length=50),
        ),
        migrations.RunPython(backfill_character_keys, clear_character_keys),
        migrations.AddConstraint(
            model_name='character',
            constraint=models.UniqueConstraint(
                fields=('localization_key',),
                condition=~models.Q(localization_key=''),
                name='unique_character_localization_key',
            ),
        ),
        migrations.AddConstraint(
            model_name='card',
            constraint=models.UniqueConstraint(
                fields=('code',),
                condition=~models.Q(code=''),
                name='unique_nonblank_card_code',
            ),
        ),
    ]
