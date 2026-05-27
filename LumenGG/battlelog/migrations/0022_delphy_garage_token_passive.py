from django.db import migrations


CONFIGURABLE_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/configurable.html',
    'css': 'battlelog/passive_ui/configurable.css',
    'js': 'battlelog/passive_ui/configurable.js',
}

DOWN_STANCE_CONTROL = {'type': 'toggle', 'key': 'down_stance', 'label': '다운 스탠스'}
GARAGE_TOKEN_CONTROL = {'type': 'counter', 'key': 'garage_token', 'label': '개러지 토큰', 'max': 3, 'unit': '장'}


def _copy_control(control):
    return dict(control) if isinstance(control, dict) else control


def _ensure_delphy_controls(datas):
    passive_ui = datas.get('battle_passive_ui')
    if not isinstance(passive_ui, dict):
        passive_ui = {
            **CONFIGURABLE_PASSIVE_UI,
            'options': {
                'title': '다운 스탠스',
                'controls': [dict(DOWN_STANCE_CONTROL)],
            },
        }
        datas['battle_passive_ui'] = passive_ui
    else:
        for key, value in CONFIGURABLE_PASSIVE_UI.items():
            passive_ui.setdefault(key, value)

    options = passive_ui.get('options')
    if not isinstance(options, dict):
        options = {}
        passive_ui['options'] = options

    options.setdefault('title', '다운 스탠스')

    raw_controls = options.get('controls')
    controls = [_copy_control(control) for control in raw_controls] if isinstance(raw_controls, list) else []

    if not any(isinstance(control, dict) and control.get('key') == DOWN_STANCE_CONTROL['key'] for control in controls):
        controls.insert(0, dict(DOWN_STANCE_CONTROL))

    garage_index = next(
        (
            index
            for index, control in enumerate(controls)
            if isinstance(control, dict) and control.get('key') == GARAGE_TOKEN_CONTROL['key']
        ),
        None,
    )
    if garage_index is None:
        down_stance_index = next(
            (
                index
                for index, control in enumerate(controls)
                if isinstance(control, dict) and control.get('key') == DOWN_STANCE_CONTROL['key']
            ),
            len(controls) - 1,
        )
        controls.insert(down_stance_index + 1, dict(GARAGE_TOKEN_CONTROL))
    else:
        controls[garage_index].update(GARAGE_TOKEN_CONTROL)

    options['controls'] = controls


def apply_delphy_garage_token_passive(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='델피'):
        datas = dict(character.datas or {})
        _ensure_delphy_controls(datas)
        character.datas = datas
        character.save(update_fields=['datas'])


def restore_delphy_garage_token_passive(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='델피'):
        datas = dict(character.datas or {})
        passive_ui = datas.get('battle_passive_ui')
        if not isinstance(passive_ui, dict):
            continue
        options = passive_ui.get('options')
        if not isinstance(options, dict):
            continue
        controls = options.get('controls')
        if not isinstance(controls, list):
            continue
        options['controls'] = [
            control
            for control in controls
            if not (isinstance(control, dict) and control.get('key') == GARAGE_TOKEN_CONTROL['key'])
        ]
        character.datas = datas
        character.save(update_fields=['datas'])


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0021_yohan_foresight_initial'),
    ]

    operations = [
        migrations.RunPython(
            apply_delphy_garage_token_passive,
            restore_delphy_garage_token_passive,
        ),
    ]
