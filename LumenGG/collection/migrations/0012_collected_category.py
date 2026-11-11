from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('collection', '0011_collectedduplicatearchive_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='collected',
            name='category',
            field=models.PositiveSmallIntegerField(choices=[(0, '분류 없음'), (1, '분류 1'), (2, '분류 2'), (3, '분류 3'), (4, '분류 4'), (5, '분류 5')], default=0),
        ),
    ]
