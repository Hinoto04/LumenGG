from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('battlelog', '0032_party_card_catalog')]

    operations = [
        migrations.AlterField(model_name='partyplayer', name='coins', field=models.PositiveIntegerField(default=0)),
    ]
