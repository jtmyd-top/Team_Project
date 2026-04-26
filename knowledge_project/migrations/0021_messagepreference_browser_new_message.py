from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_project', '0020_messagepreference_message_mode_following_only'),
    ]

    operations = [
        migrations.AddField(
            model_name='messagepreference',
            name='browser_new_message',
            field=models.BooleanField(default=False, verbose_name='浏览器通知新私信'),
        ),
    ]
