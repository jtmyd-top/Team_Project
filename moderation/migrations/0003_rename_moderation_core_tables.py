from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('moderation', '0002_migrate_moderation_core_permissions'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='usersanction',
            table='moderation_usersanction',
        ),
        migrations.AlterModelTable(
            name='moderationlog',
            table='moderation_moderationlog',
        ),
        migrations.AlterModelTable(
            name='moderationappeal',
            table='moderation_moderationappeal',
        ),
        migrations.AlterModelTable(
            name='moderationtemplate',
            table='moderation_moderationtemplate',
        ),
    ]
