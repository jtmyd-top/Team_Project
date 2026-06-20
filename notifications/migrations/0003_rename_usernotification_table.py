from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('notifications', '0002_migrate_usernotification_permissions'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='usernotification',
            table='notifications_usernotification',
        ),
    ]
