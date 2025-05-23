# Generated by Django 5.1.4 on 2025-04-20 05:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('card', '0018_remove_character_hp_hand'),
    ]

    operations = [
        migrations.AddField(
            model_name='character',
            name='icon_img',
            field=models.URLField(blank=True, default='', null=True),
        ),
        migrations.AlterField(
            model_name='cardcomment',
            name='score',
            field=models.SmallIntegerField(default=5),
        ),
    ]
