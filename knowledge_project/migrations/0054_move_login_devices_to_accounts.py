from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_move_login_devices_to_accounts_state'),
        ('knowledge_project', '0053_move_account_security_to_accounts'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name='loginnotification',
                    name='device',
                ),
                migrations.RemoveField(
                    model_name='loginnotification',
                    name='user',
                ),
                migrations.RemoveField(
                    model_name='trusteddevice',
                    name='user',
                ),
                migrations.DeleteModel(name='LoginDevice'),
                migrations.DeleteModel(name='LoginNotification'),
                migrations.DeleteModel(name='TrustedDevice'),
            ],
        ),
    ]
