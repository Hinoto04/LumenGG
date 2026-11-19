from django.db import migrations

from common.localization_batches.batch_cb04_markup_20261119 import apply_markup


def forwards(apps, schema_editor):
    apply_markup(apps, using=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [
        ('common', '0027_cb04_fifth_localization'),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
