from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0008_tao_latched_harmony'),
    ]

    operations = [
        migrations.AddField(
            model_name='battlesession',
            name='sudden_death_turns_remaining',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
