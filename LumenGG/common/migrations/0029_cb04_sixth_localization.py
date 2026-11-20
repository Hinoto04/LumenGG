from django.db import migrations

from common.localization_batches.batch_cb04_20261121 import convert_source_markup, restore_missing_translations


def forwards(apps, schema_editor):
    restore_missing_translations(apps, using=schema_editor.connection.alias)
    convert_source_markup(apps, using=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [
        ('common', '0028_cb04_localized_markup'),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
