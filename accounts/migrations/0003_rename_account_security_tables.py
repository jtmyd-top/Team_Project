from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_migrate_account_security_permissions'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='passwordresettoken',
            table='accounts_passwordresettoken',
        ),
        migrations.AlterModelTable(
            name='passwordresetattempt',
            table='accounts_passwordresetattempt',
        ),
        migrations.AlterModelTable(
            name='securityauditlog',
            table='accounts_securityauditlog',
        ),
        migrations.AlterModelTable(
            name='accesslog',
            table='accounts_accesslog',
        ),
    ]
