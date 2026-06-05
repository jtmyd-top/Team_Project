from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge_project', '0032_performance_indexes'),
    ]

    operations = [
        # ---- 现有举报工单补字段 ----
        migrations.AddField(
            model_name='messagereport',
            name='handled_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to=settings.AUTH_USER_MODEL,
                verbose_name='处理人',
            ),
        ),
        migrations.AddField(
            model_name='messagereport',
            name='resolution_note',
            field=models.TextField(blank=True, verbose_name='处理备注'),
        ),
        migrations.AddField(
            model_name='attachmentreport',
            name='resolution_note',
            field=models.TextField(blank=True, verbose_name='处理备注'),
        ),
        # ---- 用户处置 / 制裁记录 ----
        migrations.CreateModel(
            name='UserSanction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sanction_type', models.CharField(choices=[('mute_messages', '禁言私信'), ('ban_login', '封禁登录')], max_length=20, verbose_name='处置类型')),
                ('expires_at', models.DateTimeField(blank=True, help_text='留空表示永久', null=True, verbose_name='到期时间')),
                ('reason', models.TextField(blank=True, verbose_name='处置原因 / 备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='处置时间')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否生效')),
                ('revoked_at', models.DateTimeField(blank=True, null=True, verbose_name='解除时间')),
                ('source_report_type', models.CharField(blank=True, choices=[('message', '私信举报'), ('attachment', '附件举报')], max_length=20, verbose_name='来源工单类型')),
                ('source_report_id', models.IntegerField(blank=True, null=True, verbose_name='来源工单 ID')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='操作管理员')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sanctions', to=settings.AUTH_USER_MODEL, verbose_name='被处置用户')),
            ],
            options={
                'verbose_name': '用户处置',
                'verbose_name_plural': '用户处置',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='usersanction',
            index=models.Index(fields=['user', 'sanction_type', 'is_active'], name='usanction_user_type_act_idx'),
        ),
        migrations.AddIndex(
            model_name='usersanction',
            index=models.Index(fields=['is_active', 'expires_at'], name='usanction_active_exp_idx'),
        ),
        # ---- 处置审计日志 ----
        migrations.CreateModel(
            name='ModerationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_type', models.CharField(choices=[('message', '私信举报'), ('attachment', '附件举报')], max_length=20, verbose_name='工单类型')),
                ('report_id', models.IntegerField(verbose_name='工单 ID')),
                ('action', models.CharField(max_length=40, verbose_name='处置动作')),
                ('note', models.TextField(blank=True, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='处置时间')),
                ('moderator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='处置人')),
                ('target_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='被处置对象')),
            ],
            options={
                'verbose_name': '处置日志',
                'verbose_name_plural': '处置日志',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='moderationlog',
            index=models.Index(fields=['report_type', 'report_id'], name='modlog_report_idx'),
        ),
        migrations.AddIndex(
            model_name='moderationlog',
            index=models.Index(fields=['-created_at'], name='modlog_created_idx'),
        ),
    ]
