from django.db import migrations


ROOT_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/root.html',
    'css': 'battlelog/passive_ui/root.css',
    'js': 'battlelog/passive_ui/root.js',
}


def apply_root_passive_ui(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='루트'):
        datas = dict(character.datas or {})
        datas['battle_passive_ui'] = ROOT_PASSIVE_UI
        character.datas = datas
        character.save(update_fields=['datas'])


def remove_root_passive_ui(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for character in Character.objects.filter(name='루트'):
        datas = dict(character.datas or {})
        if datas.get('battle_passive_ui') == ROOT_PASSIVE_UI:
            datas.pop('battle_passive_ui')
            character.datas = datas
            character.save(update_fields=['datas'])


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(apply_root_passive_ui, remove_root_passive_ui),
    ]
