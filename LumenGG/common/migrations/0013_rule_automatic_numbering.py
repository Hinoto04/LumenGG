from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0012_rule_reference_aliases'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='rule',
            name='common_rule_ruleboo_52edd5_idx',
        ),
        migrations.RenameField(
            model_name='rule',
            old_name='sort_order',
            new_name='priority',
        ),
        migrations.RemoveField(
            model_name='rule',
            name='section_code',
        ),
        migrations.AlterField(
            model_name='rule',
            name='priority',
            field=models.PositiveIntegerField(
                default=0,
                help_text='같은 상위 규칙 아래에서 숫자가 낮을수록 먼저 표시됩니다.',
            ),
        ),
        migrations.AlterModelOptions(
            name='rule',
            options={
                'ordering': ['rulebook__sort_order', 'priority', 'id'],
                'verbose_name': '규칙',
                'verbose_name_plural': '규칙',
            },
        ),
        migrations.AlterModelOptions(
            name='ruletranslation',
            options={
                'ordering': ['rule__priority', 'language'],
                'verbose_name': '규칙 번역',
                'verbose_name_plural': '규칙 번역',
            },
        ),
        migrations.AddIndex(
            model_name='rule',
            index=models.Index(
                fields=['rulebook', 'parent', 'priority'],
                name='common_rule_parent_prio_idx',
            ),
        ),
    ]
