# Generated by Django 5.1.4 on 2025-03-04 11:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('card', '0005_card_hiddenkeyword'),
    ]

    operations = [
        migrations.AlterField(
            model_name='card',
            name='body',
            field=models.CharField(blank=True, default='', max_length=10, null=True),
        ),
        migrations.AlterField(
            model_name='card',
            name='character',
            field=models.ForeignKey(blank=True, on_delete=django.db.models.deletion.PROTECT, related_name='cards', to='card.character'),
        ),
        migrations.AlterField(
            model_name='card',
            name='code',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AlterField(
            model_name='card',
            name='counter',
            field=models.CharField(blank=True, default=0, max_length=4, null=True),
        ),
        migrations.AlterField(
            model_name='card',
            name='damage',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='card',
            name='frame',
            field=models.SmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='card',
            name='guard',
            field=models.CharField(blank=True, default=0, max_length=4, null=True),
        ),
        migrations.AlterField(
            model_name='card',
            name='hit',
            field=models.CharField(blank=True, default=0, max_length=4, null=True),
        ),
        migrations.AlterField(
            model_name='card',
            name='img',
            field=models.URLField(blank=True),
        ),
        migrations.AlterField(
            model_name='card',
            name='name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='card',
            name='pos',
            field=models.CharField(blank=True, max_length=3, null=True),
        ),
        migrations.AlterField(
            model_name='card',
            name='type',
            field=models.CharField(blank=True, default='공격', max_length=10),
        ),
    ]
