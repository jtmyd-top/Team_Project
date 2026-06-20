from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_migrate_profile_permissions'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='profile',
            table='accounts_profile',
        ),
        migrations.AlterModelTable(
            name='profilevisit',
            table='accounts_profilevisit',
        ),
        migrations.AlterModelTable(
            name='profilelike',
            table='accounts_profilelike',
        ),
    ]
