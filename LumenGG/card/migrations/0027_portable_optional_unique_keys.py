from django.db import migrations, models


def blank_keys_to_null(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    Card = apps.get_model('card', 'Card')
    Character.objects.filter(localization_key='').update(localization_key=None)
    Card.objects.filter(code='').update(code=None)


def null_keys_to_blank(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    Card = apps.get_model('card', 'Card')
    Character.objects.filter(localization_key__isnull=True).update(localization_key='')
    Card.objects.filter(code__isnull=True).update(code='')


class Migration(migrations.Migration):

    dependencies = [('card', '0026_card_effect_definition')]

    operations = [
        migrations.RemoveConstraint(
            model_name='character',
            name='unique_character_localization_key',
        ),
        migrations.RemoveConstraint(
            model_name='card',
            name='unique_nonblank_card_code',
        ),
        migrations.AlterField(
            model_name='character',
            name='localization_key',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='card',
            name='code',
            field=models.CharField(blank=True, max_length=25, null=True),
        ),
        migrations.RunPython(blank_keys_to_null, null_keys_to_blank),
        migrations.AlterField(
            model_name='character',
            name='localization_key',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='card',
            name='code',
            field=models.CharField(blank=True, max_length=25, null=True, unique=True),
        ),
    ]
