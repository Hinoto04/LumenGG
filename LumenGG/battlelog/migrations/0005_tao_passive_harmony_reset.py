from django.db import migrations


CONFIGURABLE_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/configurable.html',
    'css': 'battlelog/passive_ui/configurable.css',
    'js': 'battlelog/passive_ui/configurable.js',
}

OLD_TAO_OPTIONS = {
    'title': '양과 음',
    'controls': [
        {'type': 'counter', 'key': 'yang_counter', 'label': '양 카운터', 'max': 4},
        {'type': 'counter', 'key': 'yin_counter', 'label': '음 카운터', 'max': 4},
        {
            'type': 'status',
            'key': 'harmony',
            'label': '조화',
            'condition': {'type': 'allEquals', 'keys': ['yang_counter', 'yin_counter'], 'value': 4},
            'activeText': '조화',
            'inactiveText': '대기',
        },
    ],
}

NEW_TAO_OPTIONS = {
    'title': '양과 음',
    'controls': [
        {
            'type': 'counter',
            'key': 'yang_counter',
            'label': '양 카운터',
            'max': 4,
            'reset': True,
            'resetText': '0',
        },
        {
            'type': 'counter',
            'key': 'yin_counter',
            'label': '음 카운터',
            'max': 4,
            'reset': True,
            'resetText': '0',
        },
        {
            'type': 'status',
            'key': 'harmony',
            'label': '조화',
            'condition': {'type': 'allAtLeast', 'keys': ['yang_counter', 'yin_counter'], 'value': 3},
            'activeText': '조화',
            'inactiveText': '대기',
        },
    ],
}


def set_tao_options(apps, options):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='타오'):
        datas = dict(character.datas or {})
        datas['battle_passive_ui'] = {
            **CONFIGURABLE_PASSIVE_UI,
            'options': options,
        }
        character.datas = datas
        character.save(update_fields=['datas'])


def apply_tao_harmony_reset(apps, schema_editor):
    set_tao_options(apps, NEW_TAO_OPTIONS)


def restore_tao_harmony_reset(apps, schema_editor):
    set_tao_options(apps, OLD_TAO_OPTIONS)


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0004_root_configurable_passive_ui'),
    ]

    operations = [
        migrations.RunPython(apply_tao_harmony_reset, restore_tao_harmony_reset),
    ]
