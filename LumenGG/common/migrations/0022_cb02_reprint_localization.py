from django.db import migrations

from common.localization_batches.batch_cb02_reprints_20261023 import restore_missing_pack_translations


def forwards(apps, schema_editor):
    restore_missing_pack_translations(apps, using=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [
        ('common', '0021_cb02_localization'),
        ('collection', '0010_collectioncard_character_item_type'),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
