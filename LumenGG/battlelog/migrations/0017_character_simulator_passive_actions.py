from django.db import migrations


YOHAN_SIMULATOR_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/yohan_simulator.html',
    'css': 'battlelog/passive_ui/character_simulator.css',
    'js': 'battlelog/passive_ui/yohan_simulator.js',
}

NIA_SIMULATOR_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/nia_simulator.html',
    'css': 'battlelog/passive_ui/character_simulator.css',
    'js': 'battlelog/passive_ui/nia_simulator.js',
}

PASSIVE_UI_BY_NAME = {
    '요한': YOHAN_SIMULATOR_PASSIVE_UI,
    '니아': NIA_SIMULATOR_PASSIVE_UI,
}


def apply_character_simulator_passive_actions(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for name, passive_ui in PASSIVE_UI_BY_NAME.items():
        for character in Character.objects.filter(name__icontains=name):
            datas = dict(character.datas or {})
            datas['simulator_passive_ui'] = passive_ui
            character.datas = datas
            character.save(update_fields=['datas'])


def remove_character_simulator_passive_actions(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for name, passive_ui in PASSIVE_UI_BY_NAME.items():
        for character in Character.objects.filter(name__icontains=name):
            datas = dict(character.datas or {})
            if datas.get('simulator_passive_ui') == passive_ui:
                datas.pop('simulator_passive_ui')
                character.datas = datas
                character.save(update_fields=['datas'])


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0016_realtimepresence'),
    ]

    operations = [
        migrations.RunPython(
            apply_character_simulator_passive_actions,
            remove_character_simulator_passive_actions,
        ),
    ]
