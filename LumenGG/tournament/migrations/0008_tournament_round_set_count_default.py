from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tournament', '0007_tournament_tags'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tournament',
            name='round_set_count',
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
