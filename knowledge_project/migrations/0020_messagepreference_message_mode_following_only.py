from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_project', '0019_messagepreference_last_email_notified_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messagepreference',
            name='message_mode',
            field=models.CharField(
                choices=[
                    ('all', '所有已登录用户'),
                    ('followers_only', '仅关注者'),
                    ('following_only', '仅我关注的人'),
                    ('disabled', '禁用私信'),
                ],
                default='all',
                max_length=20,
                verbose_name='私信模式',
            ),
        ),
    ]

