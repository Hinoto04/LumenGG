from django.db import migrations


TAO_SIMULATOR_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/tao.html',
    'css': 'battlelog/passive_ui/tao_simulator.css',
    'js': 'battlelog/passive_ui/tao_simulator.js',
}


def apply_tao_simulator_custom_passive_ui(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='타오'):
        datas = dict(character.datas or {})
        datas['simulator_passive_ui'] = TAO_SIMULATOR_PASSIVE_UI
        character.datas = datas
        character.save(update_fields=['datas'])


def remove_tao_simulator_custom_passive_ui(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='타오'):
        datas = dict(character.datas or {})
        if datas.get('simulator_passive_ui') == TAO_SIMULATOR_PASSIVE_UI:
            datas.pop('simulator_passive_ui')
            character.datas = datas
            character.save(update_fields=['datas'])


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0012_tao_custom_passive_ui'),
    ]

    operations = [
        migrations.RunPython(
            apply_tao_simulator_custom_passive_ui,
            remove_tao_simulator_custom_passive_ui,
        ),
    ]
