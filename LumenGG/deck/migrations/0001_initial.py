# Generated by Django 5.1.4 on 2024-12-30 11:02

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('card', '0010_alter_card_body'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CardInDeck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('count', models.SmallIntegerField(default=1)),
                ('card', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='card.card')),
            ],
        ),
        migrations.CreateModel(
            name='Deck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=25)),
                ('version', models.CharField(default='LMI', max_length=5)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('card', models.ManyToManyField(through='deck.CardInDeck', to='card.card')),
                ('character', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='card.character')),
            ],
        ),
        migrations.AddField(
            model_name='cardindeck',
            name='deck',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='deck.deck'),
        ),
    ]
