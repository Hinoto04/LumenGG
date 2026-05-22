from django.db import migrations


FORESIGHT_INITIAL_STATE = {
    'count': 2,
    'label': '예지 카운터',
}


def _update_foresight_control(datas, add_default):
    battle_ui = datas.get('battle_passive_ui') or {}
    if not isinstance(battle_ui, dict):
        return
    options = battle_ui.get('options') or {}
    controls = options.get('controls') or []
    for control in controls:
        if not isinstance(control, dict):
            continue
        if control.get('key') != 'foresight_counter':
            continue
        if add_default:
            control['default'] = 2
        elif control.get('default') == 2:
            control.pop('default', None)


def apply_yohan_initial_passive(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name__icontains='요한'):
        datas = dict(character.datas or {})
        initial_state = dict(datas.get('initial_passive_state') or {})
        initial_state['foresight_counter'] = dict(FORESIGHT_INITIAL_STATE)
        datas['initial_passive_state'] = initial_state
        _update_foresight_control(datas, add_default=True)
        character.datas = datas
        character.save(update_fields=['datas'])


def restore_yohan_initial_passive(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name__icontains='요한'):
        datas = dict(character.datas or {})
        initial_state = dict(datas.get('initial_passive_state') or {})
        if initial_state.get('foresight_counter') == FORESIGHT_INITIAL_STATE:
            initial_state.pop('foresight_counter', None)
            if initial_state:
                datas['initial_passive_state'] = initial_state
            else:
                datas.pop('initial_passive_state', None)
        _update_foresight_control(datas, add_default=False)
        character.datas = datas
        character.save(update_fields=['datas'])


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0020_battle_passive_yohan_cmyk'),
    ]

    operations = [
        migrations.RunPython(
            apply_yohan_initial_passive,
            restore_yohan_initial_passive,
        ),
    ]
