from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0013_rule_automatic_numbering'),
    ]

    operations = [
        migrations.CreateModel(
            name='RuleVisualGuide',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('priority', models.PositiveIntegerField(default=0, help_text='숫자가 낮을수록 비주얼 가이드 전환 버튼의 앞쪽에 표시됩니다.')),
                ('css', models.TextField(blank=True)),
                ('javascript', models.TextField(blank=True)),
                ('is_public', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('rule', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='visual_guides', to='common.rule')),
            ],
            options={
                'verbose_name': '규칙 비주얼 가이드',
                'verbose_name_plural': '규칙 비주얼 가이드',
                'ordering': ['priority', 'id'],
            },
        ),
        migrations.CreateModel(
            name='RuleVisualGuideTranslation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('language', models.CharField(choices=[('ko', '한국어'), ('en', 'English'), ('ja', '日本語')], max_length=5)),
                ('title', models.CharField(max_length=160)),
                ('content', models.TextField(blank=True)),
                ('guide', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='translations', to='common.rulevisualguide')),
            ],
            options={
                'verbose_name': '규칙 비주얼 가이드 번역',
                'verbose_name_plural': '규칙 비주얼 가이드 번역',
                'ordering': ['guide__priority', 'language'],
            },
        ),
        migrations.AddIndex(
            model_name='rulevisualguide',
            index=models.Index(fields=['rule', 'is_public', 'priority'], name='common_visual_rule_public_idx'),
        ),
        migrations.AddConstraint(
            model_name='rulevisualguidetranslation',
            constraint=models.UniqueConstraint(fields=('guide', 'language'), name='unique_rule_visual_translation_language'),
        ),
    ]
