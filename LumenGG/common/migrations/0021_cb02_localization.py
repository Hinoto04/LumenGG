from django.db import migrations

from common.localization_batches.batch_cb02_20261023 import restore_missing_translations


def forwards(apps, schema_editor):
    restore_missing_translations(apps, using=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [
        ('common', '0020_rule_contract_references'),
        ('card', '0026_card_effect_definition'),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
