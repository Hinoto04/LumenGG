from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0015_battlesession_version'),
    ]

    operations = [
        migrations.CreateModel(
            name='RealtimePresence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scope', models.CharField(choices=[('battle', '계산기'), ('simulator', '시뮬레이터')], max_length=16)),
                ('view_token', models.CharField(db_index=True, max_length=64)),
                ('role', models.CharField(max_length=16)),
                ('channel_name', models.CharField(max_length=255, unique=True)),
                ('connected_at', models.DateTimeField(auto_now_add=True)),
                ('last_seen_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name='realtimepresence',
            index=models.Index(fields=['scope', 'view_token', 'role'], name='battlelog_r_scope_9af048_idx'),
        ),
        migrations.AddIndex(
            model_name='realtimepresence',
            index=models.Index(fields=['last_seen_at'], name='battlelog_r_last_se_f30c9f_idx'),
        ),
    ]
