from django.db import migrations


OLD_ROOT_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/root.html',
    'css': 'battlelog/passive_ui/root.css',
    'js': 'battlelog/passive_ui/root.js',
}

ROOT_CONFIGURABLE_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/configurable.html',
    'css': 'battlelog/passive_ui/configurable.css',
    'js': 'battlelog/passive_ui/configurable.js',
    'options': {
        'title': '차지',
        'controls': [
            {
                'type': 'toggle',
                'key': 'root_charge',
                'label': '차지',
            },
        ],
    },
}


def apply_root_configurable_passive_ui(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='루트'):
        datas = character.datas or {}
        datas['battle_passive_ui'] = ROOT_CONFIGURABLE_PASSIVE_UI
        character.datas = datas
        character.save(update_fields=['datas'])


def restore_root_custom_passive_ui(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='루트'):
        datas = character.datas or {}
        if datas.get('battle_passive_ui') == ROOT_CONFIGURABLE_PASSIVE_UI:
            datas['battle_passive_ui'] = OLD_ROOT_PASSIVE_UI
            character.datas = datas
            character.save(update_fields=['datas'])


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0003_configurable_passive_ui'),
    ]

    operations = [
        migrations.RunPython(
            apply_root_configurable_passive_ui,
            restore_root_custom_passive_ui,
        ),
    ]
