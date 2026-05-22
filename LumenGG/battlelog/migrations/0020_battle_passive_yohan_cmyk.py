from django.db import migrations


CONFIGURABLE_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/configurable.html',
    'css': 'battlelog/passive_ui/configurable.css',
    'js': 'battlelog/passive_ui/configurable.js',
}

YOHAN_BATTLE_PASSIVE_UI = {
    **CONFIGURABLE_PASSIVE_UI,
    'options': {
        'title': '예지',
        'controls': [
            {'type': 'counter', 'key': 'foresight_counter', 'label': '예지 카운터', 'max': 10},
            {'type': 'toggle', 'key': 'disaster_one', 'label': '디제스터 원'},
        ],
    },
}

CMYK_DISABLED_BATTLE_PASSIVE_UI = {
    'disabled': True,
}


def apply_battle_passive_changes(apps, schema_editor):
    Character = apps.get_model('card', 'Character')

    for character in Character.objects.filter(name__icontains='요한'):
        datas = dict(character.datas or {})
        datas['battle_passive_ui'] = YOHAN_BATTLE_PASSIVE_UI
        character.datas = datas
        character.save(update_fields=['datas'])

    for character in Character.objects.filter(name__icontains='CMYK'):
        datas = dict(character.datas or {})
        datas['battle_passive_ui'] = CMYK_DISABLED_BATTLE_PASSIVE_UI
        character.datas = datas
        character.save(update_fields=['datas'])


def restore_battle_passive_changes(apps, schema_editor):
    Character = apps.get_model('card', 'Character')

    for character in Character.objects.filter(name__icontains='요한'):
        datas = dict(character.datas or {})
        if datas.get('battle_passive_ui') == YOHAN_BATTLE_PASSIVE_UI:
            datas['battle_passive_ui'] = {
                **CONFIGURABLE_PASSIVE_UI,
                'options': {
                    'title': '예지',
                    'controls': [
                        {'type': 'counter', 'key': 'foresight_counter', 'label': '예지 카운터', 'max': 10},
                    ],
                },
            }
            character.datas = datas
            character.save(update_fields=['datas'])

    for character in Character.objects.filter(name__icontains='CMYK'):
        datas = dict(character.datas or {})
        if datas.get('battle_passive_ui') == CMYK_DISABLED_BATTLE_PASSIVE_UI:
            datas.pop('battle_passive_ui')
            character.datas = datas
            character.save(update_fields=['datas'])


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0019_restore_cmyk_simulator_passive_ui'),
    ]

    operations = [
        migrations.RunPython(
            apply_battle_passive_changes,
            restore_battle_passive_changes,
        ),
    ]
