from django.db import migrations

from common.localization_batches.batch_cb04_20261110 import restore_missing_translations


def forwards(apps, schema_editor):
    restore_missing_translations(apps, using=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [
        ('common', '0022_cb02_reprint_localization'),
        ('card', '0030_card_trait_config'),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
