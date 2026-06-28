from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0006_remove_groupjoinrequest_status_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='messagegroup',
            name='allow_new_members_view_history',
            field=models.BooleanField(default=False, verbose_name='新成员可见群历史消息'),
        ),
    ]
