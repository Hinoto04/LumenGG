from django.db import migrations


TAO_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/tao.html',
    'css': 'battlelog/passive_ui/tao.css',
    'js': 'battlelog/passive_ui/tao.js',
}


CONFIGURABLE_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/configurable.html',
    'css': 'battlelog/passive_ui/configurable.css',
    'js': 'battlelog/passive_ui/configurable.js',
    'options': {
        'title': '양과 음',
        'controls': [
            {
                'type': 'counter',
                'key': 'yang_counter',
                'label': '양 카운터',
                'max': 4,
                'reset': True,
                'resetText': '0',
                'highlightHighestWith': ['yang_counter', 'yin_counter'],
            },
            {
                'type': 'counter',
                'key': 'yin_counter',
                'label': '음 카운터',
                'max': 4,
                'reset': True,
                'resetText': '0',
                'highlightHighestWith': ['yang_counter', 'yin_counter'],
            },
            {
                'type': 'latchedStatus',
                'key': 'harmony',
                'label': '조화',
                'activateWhen': {'type': 'allEquals', 'keys': ['yang_counter', 'yin_counter'], 'value': 4},
                'keepWhile': {'type': 'allAtLeast', 'keys': ['yang_counter', 'yin_counter'], 'value': 3},
                'activeText': '조화',
                'inactiveText': '대기',
            },
            {
                'type': 'choice',
                'key': 'harmony_effect',
                'label': '조화 효과',
                'visibleWhen': {'type': 'keyActive', 'key': 'harmony'},
                'enableWhen': {'type': 'keyActive', 'key': 'harmony'},
                'choices': [
                    {'value': 'damage_100', 'label': '+100DMG'},
                    {'value': 'fp_1', 'label': '+1FP'},
                ],
            },
        ],
        'latchedStatuses': [
            {
                'key': 'harmony',
                'label': '조화',
                'activateWhen': {'type': 'allEquals', 'keys': ['yang_counter', 'yin_counter'], 'value': 4},
                'keepWhile': {'type': 'allAtLeast', 'keys': ['yang_counter', 'yin_counter'], 'value': 3},
            },
        ],
    },
}


def apply_tao_custom_passive_ui(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='타오'):
        datas = dict(character.datas or {})
        datas['battle_passive_ui'] = TAO_PASSIVE_UI
        character.datas = datas
        character.save(update_fields=['datas'])


def restore_tao_configurable_passive_ui(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='타오'):
        datas = dict(character.datas or {})
        datas['battle_passive_ui'] = CONFIGURABLE_PASSIVE_UI
        character.datas = datas
        character.save(update_fields=['datas'])


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0011_tao_harmony_effect_choice'),
    ]

    operations = [
        migrations.RunPython(apply_tao_custom_passive_ui, restore_tao_configurable_passive_ui),
    ]
