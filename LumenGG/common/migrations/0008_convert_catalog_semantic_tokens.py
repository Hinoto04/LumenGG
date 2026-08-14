import importlib

from django.db import migrations


def forwards(apps, schema_editor):
    semantic_migration = importlib.import_module(
        'common.migrations.0007_semantic_state_and_token_terms'
    )
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationValue = apps.get_model('common', 'TranslationValue')
    aliases = semantic_migration.aliases_by_language(apps)

    sources = TranslationSource.objects.filter(
        category='card',
        field_name__in=('text', 'detail_text'),
    ).order_by('id')
    for source in sources:
        old = source.source_text or ''
        new = semantic_migration.replace_semantic_text(old, 'ko', aliases)
        if new != old:
            source.source_text = new
            source.save(update_fields=['source_text'])

        for value in TranslationValue.objects.filter(source_id=source.id).order_by('id'):
            old = value.text or ''
            new = semantic_migration.replace_semantic_text(old, value.language, aliases)
            if new != old:
                value.text = new
                value.save(update_fields=['text', 'updated_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0007_semantic_state_and_token_terms'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
