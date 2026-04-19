# Generated migration for Message, MessagePreference, and UserBlocklist models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_project', '0015_notehistory'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(max_length=5000, verbose_name='消息内容')),
                ('is_read', models.BooleanField(default=False, verbose_name='已读')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='发送时间')),
                ('read_at', models.DateTimeField(blank=True, null=True, verbose_name='读取时间')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_messages', to=settings.AUTH_USER_MODEL, verbose_name='接收者')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_messages', to=settings.AUTH_USER_MODEL, verbose_name='发送者')),
            ],
            options={
                'verbose_name': '私信',
                'verbose_name_plural': '私信',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='UserBlocklist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(blank=True, max_length=500, verbose_name='屏蔽原因')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='屏蔽时间')),
                ('blocked_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocked_by', to=settings.AUTH_USER_MODEL, verbose_name='被屏蔽用户')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocked_users', to=settings.AUTH_USER_MODEL, verbose_name='屏蔽者')),
            ],
            options={
                'verbose_name': '用户屏蔽',
                'verbose_name_plural': '用户屏蔽',
                'unique_together': {('user', 'blocked_user')},
            },
        ),
        migrations.CreateModel(
            name='MessagePreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('allow_messages', models.BooleanField(default=True, verbose_name='允许接收私信')),
                ('message_mode', models.CharField(choices=[('all', '所有已登录用户'), ('followers_only', '仅关注者'), ('disabled', '禁用私信')], default='all', max_length=20, verbose_name='私信模式')),
                ('show_read_status', models.BooleanField(default=True, verbose_name='显示已读状态')),
                ('auto_reply_enabled', models.BooleanField(default=False, verbose_name='启用自动回复')),
                ('auto_reply_text', models.TextField(blank=True, default='', max_length=500, verbose_name='自动回复内容')),
                ('notify_new_message', models.BooleanField(default=True, verbose_name='邮件通知新私信')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='message_preference', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '私信偏好设置',
                'verbose_name_plural': '私信偏好设置',
            },
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['sender', 'recipient', '-created_at'], name='knowledge_p_sender__idx'),
        ),
        migrations.AddIndex(
            model_name='message',
            index=models.Index(fields=['recipient', 'is_read'], name='knowledge_p_recipie_idx'),
        ),
        migrations.AddIndex(
            model_name='userblocklist',
            index=models.Index(fields=['user', 'blocked_user'], name='knowledge_p_user_id_idx'),
        ),
    ]
