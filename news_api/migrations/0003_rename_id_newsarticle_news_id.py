# Generated by Django 4.2.20 on 2025-05-09 04:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('news_api', '0002_newsarticle_full_text'),
    ]

    operations = [
        migrations.RenameField(
            model_name='newsarticle',
            old_name='id',
            new_name='news_id',
        ),
    ]
