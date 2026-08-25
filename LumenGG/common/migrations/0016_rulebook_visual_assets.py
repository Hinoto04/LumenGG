from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0015_rule_visual_guide_owners'),
    ]

    operations = [
        migrations.AddField(
            model_name='rulebook',
            name='visual_css',
            field=models.TextField(
                blank=True,
                help_text='룰북 상단 비주얼 가이드들이 공통으로 사용하는 CSS입니다.',
            ),
        ),
        migrations.AddField(
            model_name='rulebook',
            name='visual_javascript',
            field=models.TextField(
                blank=True,
                help_text='룰북 상단 비주얼 가이드들이 공통으로 사용하는 JavaScript입니다.',
            ),
        ),
    ]
