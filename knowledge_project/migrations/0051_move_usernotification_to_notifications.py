from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0001_initial'),
        ('knowledge_project', '0050_alter_messagegroupannouncementhistory_options_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name='UserNotification'),
            ],
        ),
    ]
