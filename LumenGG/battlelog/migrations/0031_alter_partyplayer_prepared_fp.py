from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('battlelog', '0030_partyroom_alter_battlesession_session_type_and_more')]
    operations = [migrations.AlterField(model_name='partyplayer', name='prepared_fp', field=models.IntegerField(default=0))]
