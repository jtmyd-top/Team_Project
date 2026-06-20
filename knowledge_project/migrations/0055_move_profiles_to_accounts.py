from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_move_profiles_to_accounts_state'),
        ('knowledge_project', '0054_move_login_devices_to_accounts'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterUniqueTogether(
                    name='profilelike',
                    unique_together=None,
                ),
                migrations.RemoveField(
                    model_name='profilelike',
                    name='liker',
                ),
                migrations.RemoveField(
                    model_name='profilelike',
                    name='profile',
                ),
                migrations.RemoveField(
                    model_name='profilevisit',
                    name='profile',
                ),
                migrations.RemoveField(
                    model_name='profilevisit',
                    name='viewer',
                ),
                migrations.DeleteModel(name='Profile'),
                migrations.DeleteModel(name='ProfileLike'),
                migrations.DeleteModel(name='ProfileVisit'),
            ],
        ),
    ]
