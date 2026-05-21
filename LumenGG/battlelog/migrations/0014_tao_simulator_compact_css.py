from django.db import migrations


OLD_TAO_SIMULATOR_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/tao.html',
    'css': 'battlelog/passive_ui/tao.css',
    'js': 'battlelog/passive_ui/tao_simulator.js',
}


NEW_TAO_SIMULATOR_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/tao.html',
    'css': 'battlelog/passive_ui/tao_simulator.css',
    'js': 'battlelog/passive_ui/tao_simulator.js',
}


def apply_compact_simulator_css(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='타오'):
        datas = dict(character.datas or {})
        current = datas.get('simulator_passive_ui')
        if current == OLD_TAO_SIMULATOR_PASSIVE_UI or current == NEW_TAO_SIMULATOR_PASSIVE_UI:
            datas['simulator_passive_ui'] = NEW_TAO_SIMULATOR_PASSIVE_UI
            character.datas = datas
            character.save(update_fields=['datas'])


def restore_shared_simulator_css(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='타오'):
        datas = dict(character.datas or {})
        if datas.get('simulator_passive_ui') == NEW_TAO_SIMULATOR_PASSIVE_UI:
            datas['simulator_passive_ui'] = OLD_TAO_SIMULATOR_PASSIVE_UI
            character.datas = datas
            character.save(update_fields=['datas'])


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0013_tao_simulator_custom_passive_ui'),
    ]

    operations = [
        migrations.RunPython(apply_compact_simulator_css, restore_shared_simulator_css),
    ]
