from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0004_message_unread_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='messagegroup',
            name='members_visible',
            field=models.BooleanField(default=True, verbose_name='成员列表对普通成员可见'),
        ),
    ]
