from django.db import migrations


CMYK_SIMULATOR_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/cmyk_simulator.html',
    'css': 'battlelog/passive_ui/character_simulator.css',
    'js': 'battlelog/passive_ui/cmyk_simulator.js',
}


def apply_cmyk_simulator_passive_ui(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name__icontains='CMYK'):
        datas = dict(character.datas or {})
        datas['simulator_passive_ui'] = CMYK_SIMULATOR_PASSIVE_UI
        character.datas = datas
        character.save(update_fields=['datas'])


def remove_cmyk_simulator_passive_ui(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name__icontains='CMYK'):
        datas = dict(character.datas or {})
        if datas.get('simulator_passive_ui') == CMYK_SIMULATOR_PASSIVE_UI:
            datas.pop('simulator_passive_ui')
            character.datas = datas
            character.save(update_fields=['datas'])


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0017_character_simulator_passive_actions'),
    ]

    operations = [
        migrations.RunPython(
            apply_cmyk_simulator_passive_ui,
            remove_cmyk_simulator_passive_ui,
        ),
    ]
