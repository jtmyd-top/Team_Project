from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge_project', '0050_alter_messagegroupannouncementhistory_options_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='UserNotification',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('kind', models.CharField(choices=[
                            ('report_received', '举报已收到'),
                            ('report_resolved', '举报已处理'),
                            ('sanction_applied', '用户处置'),
                            ('sanction_revoked', '处置解除'),
                            ('appeal_submitted', '申诉已提交'),
                            ('appeal_resolved', '申诉已处理'),
                            ('new_comment', 'New comment'),
                            ('comment_reply', 'Comment reply'),
                            ('profile_liked', 'Profile liked'),
                            ('new_follower', 'New follower'),
                            ('new_message', 'New message'),
                            ('note_copied', 'Note copied'),
                        ], max_length=40, verbose_name='通知类型')),
                        ('title', models.CharField(max_length=120, verbose_name='标题')),
                        ('body', models.TextField(blank=True, verbose_name='内容')),
                        ('data', models.JSONField(blank=True, default=dict, verbose_name='附加数据')),
                        ('is_read', models.BooleanField(default=False, verbose_name='是否已读')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                        ('user', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='notifications',
                            to=settings.AUTH_USER_MODEL,
                            verbose_name='接收用户',
                        )),
                    ],
                    options={
                        'db_table': 'knowledge_project_usernotification',
                        'verbose_name': '用户通知',
                        'verbose_name_plural': '用户通知',
                        'ordering': ['-created_at'],
                        'indexes': [
                            models.Index(fields=['user', 'is_read', '-created_at'], name='unotify_user_read_idx'),
                        ],
                    },
                ),
            ],
        ),
    ]
