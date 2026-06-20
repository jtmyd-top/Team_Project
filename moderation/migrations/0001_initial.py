from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge_project', '0051_move_usernotification_to_notifications'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='UserSanction',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('sanction_type', models.CharField(choices=[('mute_messages', '禁言私信'), ('ban_comments', '禁止评论'), ('ban_public_notes', '禁止发布公开文章'), ('ban_login', '封禁登录')], max_length=20, verbose_name='处置类型')),
                        ('expires_at', models.DateTimeField(blank=True, help_text='留空表示永久', null=True, verbose_name='到期时间')),
                        ('reason', models.TextField(blank=True, verbose_name='处置原因 / 备注')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='处置时间')),
                        ('is_active', models.BooleanField(default=True, verbose_name='是否生效')),
                        ('revoked_at', models.DateTimeField(blank=True, null=True, verbose_name='解除时间')),
                        ('source_report_type', models.CharField(blank=True, choices=[('message', '私信举报'), ('attachment', '附件举报'), ('note', '文章举报'), ('comment', '评论举报')], max_length=20, verbose_name='来源工单类型')),
                        ('source_report_id', models.IntegerField(blank=True, null=True, verbose_name='来源工单 ID')),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='操作管理员')),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sanctions', to=settings.AUTH_USER_MODEL, verbose_name='被处置用户')),
                    ],
                    options={
                        'db_table': 'knowledge_project_usersanction',
                        'verbose_name': '用户处置',
                        'verbose_name_plural': '用户处置',
                        'ordering': ['-created_at'],
                        'indexes': [
                            models.Index(fields=['user', 'sanction_type', 'is_active'], name='usanction_user_type_act_idx'),
                            models.Index(fields=['is_active', 'expires_at'], name='usanction_active_exp_idx'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='ModerationLog',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('report_type', models.CharField(choices=[('message', '私信举报'), ('attachment', '附件举报'), ('note', '文章举报'), ('comment', '评论举报')], max_length=20, verbose_name='工单类型')),
                        ('report_id', models.IntegerField(verbose_name='工单 ID')),
                        ('action', models.CharField(max_length=40, verbose_name='处置动作')),
                        ('note', models.TextField(blank=True, verbose_name='备注')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='处置时间')),
                        ('moderator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='处置人')),
                        ('target_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='被处置对象')),
                    ],
                    options={
                        'db_table': 'knowledge_project_moderationlog',
                        'verbose_name': '处置日志',
                        'verbose_name_plural': '处置日志',
                        'ordering': ['-created_at'],
                        'indexes': [
                            models.Index(fields=['report_type', 'report_id'], name='modlog_report_idx'),
                            models.Index(fields=['-created_at'], name='modlog_created_idx'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='ModerationAppeal',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('reason', models.TextField(max_length=2000, verbose_name='申诉理由')),
                        ('status', models.CharField(choices=[('pending', '待处理'), ('accepted', '申诉通过'), ('rejected', '申诉驳回')], default='pending', max_length=20, verbose_name='处理状态')),
                        ('resolution_note', models.TextField(blank=True, verbose_name='处理备注')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='提交时间')),
                        ('handled_at', models.DateTimeField(blank=True, null=True, verbose_name='处理时间')),
                        ('handled_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='处理人')),
                        ('sanction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='appeals', to='moderation.usersanction', verbose_name='关联处置')),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='moderation_appeals', to=settings.AUTH_USER_MODEL, verbose_name='申诉用户')),
                    ],
                    options={
                        'db_table': 'knowledge_project_moderationappeal',
                        'verbose_name': '处置申诉',
                        'verbose_name_plural': '处置申诉',
                        'ordering': ['-created_at'],
                        'indexes': [
                            models.Index(fields=['status', '-created_at'], name='mappeal_status_idx'),
                            models.Index(fields=['user', '-created_at'], name='mappeal_user_idx'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='ModerationTemplate',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('title', models.CharField(max_length=80, verbose_name='模板名称')),
                        ('report_type', models.CharField(blank=True, choices=[('message', '私信举报'), ('attachment', '附件举报'), ('note', '文章举报'), ('comment', '评论举报')], max_length=20, verbose_name='适用举报类型')),
                        ('decision', models.CharField(blank=True, choices=[('uphold', '举报成立'), ('dismiss', '驳回举报'), ('manual', '重新处置'), ('appeal', '申诉处理')], max_length=20, verbose_name='适用场景')),
                        ('content', models.TextField(max_length=2000, verbose_name='模板内容')),
                        ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                    ],
                    options={
                        'db_table': 'knowledge_project_moderationtemplate',
                        'verbose_name': '处置模板',
                        'verbose_name_plural': '处置模板',
                        'ordering': ['report_type', 'decision', 'title'],
                        'indexes': [
                            models.Index(fields=['is_active', 'report_type', 'decision'], name='mtemplate_lookup_idx'),
                        ],
                    },
                ),
            ],
        ),
    ]
