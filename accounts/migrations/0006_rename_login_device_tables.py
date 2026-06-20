from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_migrate_login_device_permissions'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='logindevice',
            table='accounts_logindevice',
        ),
        migrations.AlterModelTable(
            name='loginnotification',
            table='accounts_loginnotification',
        ),
        migrations.AlterModelTable(
            name='trusteddevice',
            table='accounts_trusteddevice',
        ),
    ]
