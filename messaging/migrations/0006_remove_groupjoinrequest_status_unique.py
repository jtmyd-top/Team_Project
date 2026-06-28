from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0005_messagegroup_members_visible'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='groupjoinrequest',
            unique_together=set(),
        ),
    ]
