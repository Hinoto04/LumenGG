from django.db import migrations, models
import django.db.models.deletion


def populate_visual_rulebooks(apps, schema_editor):
    RuleVisualGuide = apps.get_model('common', 'RuleVisualGuide')
    for guide in RuleVisualGuide.objects.select_related('rule').all():
        guide.rulebook_id = guide.rule.rulebook_id
        guide.save(update_fields=['rulebook'])


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0014_rule_visual_guides'),
    ]

    operations = [
        migrations.AddField(
            model_name='rulevisualguide',
            name='rulebook',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='visual_guides',
                to='common.rulebook',
            ),
        ),
        migrations.AddField(
            model_name='rulevisualguide',
            name='style_key',
            field=models.SlugField(
                blank=True,
                help_text='비주얼 가이드에 적용할 CSS 식별자입니다. 예: field, cards, phases',
                max_length=40,
            ),
        ),
        migrations.RunPython(populate_visual_rulebooks, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='rulevisualguide',
            name='rulebook',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='visual_guides',
                to='common.rulebook',
            ),
        ),
        migrations.AlterField(
            model_name='rulevisualguide',
            name='rule',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='visual_guides',
                to='common.rule',
            ),
        ),
        migrations.RemoveIndex(
            model_name='rulevisualguide',
            name='common_visual_rule_public_idx',
        ),
        migrations.AddIndex(
            model_name='rulevisualguide',
            index=models.Index(
                fields=['rulebook', 'rule', 'is_public', 'priority'],
                name='common_visual_owner_public_idx',
            ),
        ),
    ]
