from django.db import migrations

from common.localization_batches.batch_cb04_20261125 import restore_missing_translations


def forwards(apps, schema_editor):
    restore_missing_translations(apps, using=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [
        ('common', '0029_cb04_sixth_localization'),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
