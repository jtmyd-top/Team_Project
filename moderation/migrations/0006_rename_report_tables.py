from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('moderation', '0005_migrate_report_permissions'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='attachmentreport',
            table='moderation_attachmentreport',
        ),
        migrations.AlterModelTable(
            name='notereport',
            table='moderation_notereport',
        ),
        migrations.AlterModelTable(
            name='commentreport',
            table='moderation_commentreport',
        ),
        migrations.AlterModelTable(
            name='messagereport',
            table='moderation_messagereport',
        ),
    ]
