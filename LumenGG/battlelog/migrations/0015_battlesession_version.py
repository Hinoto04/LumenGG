from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0014_tao_simulator_compact_css'),
    ]

    operations = [
        migrations.AddField(
            model_name='battlesession',
            name='version',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
