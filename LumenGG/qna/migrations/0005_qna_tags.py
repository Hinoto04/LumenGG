# Generated by Django 5.1.4 on 2025-04-08 15:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qna', '0004_alter_qna_answer_alter_qna_question'),
    ]

    operations = [
        migrations.AddField(
            model_name='qna',
            name='tags',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
