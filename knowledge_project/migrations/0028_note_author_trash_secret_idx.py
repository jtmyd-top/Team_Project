from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_project', '0027_backfill_merged_forward_searchable_text'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='note',
            index=models.Index(fields=['author', 'is_trashed', 'is_secret'], name='note_author_trash_secret_idx'),
        ),
    ]
