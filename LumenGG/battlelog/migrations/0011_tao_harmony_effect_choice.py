from django.db import migrations


CONFIGURABLE_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/configurable.html',
    'css': 'battlelog/passive_ui/configurable.css',
    'js': 'battlelog/passive_ui/configurable.js',
}


OLD_TAO_OPTIONS = {
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
    ],
    'latchedStatuses': [
        {
            'key': 'harmony',
            'label': '조화',
            'activateWhen': {'type': 'allEquals', 'keys': ['yang_counter', 'yin_counter'], 'value': 4},
            'keepWhile': {'type': 'allAtLeast', 'keys': ['yang_counter', 'yin_counter'], 'value': 3},
        },
    ],
}


NEW_TAO_OPTIONS = {
    **OLD_TAO_OPTIONS,
    'controls': [
        *OLD_TAO_OPTIONS['controls'],
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


def apply_tao_harmony_effect_choice(apps, schema_editor):
    set_tao_options(apps, NEW_TAO_OPTIONS)


def restore_tao_latched_harmony(apps, schema_editor):
    set_tao_options(apps, OLD_TAO_OPTIONS)


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0010_lumensimulatorsession'),
    ]

    operations = [
        migrations.RunPython(apply_tao_harmony_effect_choice, restore_tao_latched_harmony),
    ]
