from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0009_sudden_death_turns'),
    ]

    operations = [
        migrations.CreateModel(
            name='LumenSimulatorSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('view_token', models.CharField(max_length=64, unique=True)),
                ('player1_token', models.CharField(max_length=64, unique=True)),
                ('player2_token', models.CharField(max_length=64, unique=True)),
                ('player1_name', models.CharField(default='플레이어1', max_length=60)),
                ('player2_name', models.CharField(default='플레이어2', max_length=60)),
                ('document', models.JSONField(blank=True, default=dict)),
                ('version', models.PositiveIntegerField(default=1)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
