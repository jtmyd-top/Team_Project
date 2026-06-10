from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_project', '0034_commentreport_notereport_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usersanction',
            name='sanction_type',
            field=models.CharField(
                choices=[
                    ('mute_messages', '禁言私信'),
                    ('ban_comments', '禁止评论'),
                    ('ban_public_notes', '禁止发布公开文章'),
                    ('ban_login', '封禁登录'),
                ],
                max_length=20,
                verbose_name='处置类型',
            ),
        ),
    ]
