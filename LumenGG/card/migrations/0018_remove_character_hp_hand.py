# Generated by Django 5.1.4 on 2025-04-18 21:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('card', '0017_character_datas'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='character',
            name='hp_hand',
        ),
    ]
