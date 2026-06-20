from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('moderation', '0001_initial'),
        ('knowledge_project', '0051_move_usernotification_to_notifications'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name='ModerationAppeal'),
                migrations.DeleteModel(name='ModerationTemplate'),
                migrations.DeleteModel(name='ModerationLog'),
                migrations.DeleteModel(name='UserSanction'),
            ],
        ),
    ]
