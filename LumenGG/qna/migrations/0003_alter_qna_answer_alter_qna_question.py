# Generated by Django 5.1.4 on 2025-03-16 17:58

import martor.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('qna', '0002_alter_qna_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='qna',
            name='answer',
            field=martor.models.MartorField(),
        ),
        migrations.AlterField(
            model_name='qna',
            name='question',
            field=martor.models.MartorField(),
        ),
    ]
