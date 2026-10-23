from django.db import migrations


def unrestrict_basic_regulation_decks(apps, schema_editor):
    Deck = apps.get_model('deck', 'Deck')
    Deck.objects.filter(
        regulation_version__regulation__name='기본 규정',
    ).update(regulation_version=None)


class Migration(migrations.Migration):
    dependencies = [('deck', '0016_seed_standard_and_traits')]
    operations = [
        migrations.RunPython(unrestrict_basic_regulation_decks, migrations.RunPython.noop),
    ]
