# Generated by Django 5.1.4 on 2025-01-01 08:33

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('deck', '0003_cardindeck_description_deck_description_deck_keyword'),
    ]

    operations = [
        migrations.AddField(
            model_name='deck',
            name='created',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
