from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge_project', '0055_move_profiles_to_accounts'),
        ('moderation', '0003_rename_moderation_core_tables'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='MessageReport',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('reason', models.CharField(choices=[('spam', '垃圾广告'), ('abuse', '辱骂骚扰'), ('porn', '色情低俗'), ('scam', '诈骗欺诈'), ('privacy', '侵犯隐私'), ('illegal', '违法违规'), ('other', '其他')], max_length=20, verbose_name='原因')),
                        ('detail', models.TextField(blank=True, max_length=1000, verbose_name='补充说明')),
                        ('evidence_snapshot', models.JSONField(blank=True, default=dict, verbose_name='举报证据快照')),
                        ('status', models.CharField(choices=[('pending', '待处理'), ('resolved', '已处理'), ('dismissed', '已驳回')], default='pending', max_length=20, verbose_name='处理状态')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='举报时间')),
                        ('resolved_at', models.DateTimeField(blank=True, null=True, verbose_name='处理时间')),
                        ('resolution_note', models.TextField(blank=True, verbose_name='处理备注')),
                        ('group_message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports', to='knowledge_project.groupmessage', verbose_name='关联群组消息')),
                        ('handled_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='处理人')),
                        ('message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports', to='knowledge_project.message', verbose_name='关联消息')),
                        ('reported_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='被举报者')),
                        ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='举报者')),
                    ],
                    options={
                        'verbose_name': '私信举报',
                        'verbose_name_plural': '私信举报',
                        'db_table': 'knowledge_project_messagereport',
                        'ordering': ['-created_at'],
                        'indexes': [
                            models.Index(fields=['status', '-created_at'], name='knowledge_p_status_5b6c65_idx'),
                            models.Index(fields=['reported_user'], name='knowledge_p_reporte_e39bf0_idx'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='CommentReport',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('status', models.CharField(choices=[('pending', '待处理'), ('removed', '已删除'), ('dismissed', '已驳回')], default='pending', max_length=20, verbose_name='处理状态')),
                        ('reason', models.CharField(choices=[('spam', '垃圾广告'), ('abuse', '辱骂骚扰'), ('porn', '色情低俗'), ('scam', '诈骗欺诈'), ('privacy', '侵犯隐私'), ('illegal', '违法违规'), ('other', '其他')], default='other', max_length=120, verbose_name='举报原因')),
                        ('detail', models.TextField(blank=True, max_length=1000, verbose_name='补充说明')),
                        ('evidence_snapshot', models.JSONField(blank=True, default=dict, verbose_name='举报证据快照')),
                        ('pending_dedup_key', models.CharField(blank=True, editable=False, max_length=16, null=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='举报时间')),
                        ('handled_at', models.DateTimeField(blank=True, null=True, verbose_name='处理时间')),
                        ('resolution_note', models.TextField(blank=True, verbose_name='处理备注')),
                        ('comment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports', to='knowledge_project.notecomment', verbose_name='关联评论')),
                        ('handled_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                        ('note', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comment_reports', to='knowledge_project.note', verbose_name='关联文章')),
                        ('reported_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='被举报用户')),
                        ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='举报人')),
                    ],
                    options={
                        'verbose_name': '评论举报',
                        'verbose_name_plural': '评论举报',
                        'db_table': 'knowledge_project_commentreport',
                        'ordering': ['-created_at'],
                        'indexes': [
                            models.Index(fields=['comment', 'status'], name='knowledge_p_comment_d35317_idx'),
                            models.Index(fields=['status', '-created_at'], name='knowledge_p_status_25a0ee_idx'),
                            models.Index(fields=['reporter', '-created_at'], name='knowledge_p_reporte_17249c_idx'),
                            models.Index(fields=['reported_user'], name='knowledge_p_reporte_869c9d_idx'),
                        ],
                        'constraints': [
                            models.UniqueConstraint(fields=('comment', 'reporter', 'pending_dedup_key'), name='uniq_pending_comment_report_per_reporter'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='AttachmentReport',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('status', models.CharField(choices=[('pending', '待处理'), ('removed', '已违规删除'), ('dismissed', '已驳回误报')], default='pending', max_length=20, verbose_name='处理状态')),
                        ('reason', models.CharField(choices=[('spam', '垃圾广告'), ('abuse', '辱骂骚扰'), ('porn', '色情低俗'), ('scam', '诈骗欺诈'), ('privacy', '侵犯隐私'), ('illegal', '违法违规'), ('other', '其他')], default='other', max_length=120, verbose_name='举报原因')),
                        ('detail', models.TextField(blank=True, max_length=1000, verbose_name='补充说明')),
                        ('evidence_snapshot', models.JSONField(blank=True, default=dict, verbose_name='举报证据快照')),
                        ('pending_dedup_key', models.CharField(blank=True, editable=False, max_length=16, null=True, verbose_name='待处理去重标记')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='举报时间')),
                        ('handled_at', models.DateTimeField(blank=True, null=True, verbose_name='处理时间')),
                        ('resolution_note', models.TextField(blank=True, verbose_name='处理备注')),
                        ('attachment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='knowledge_project.messageattachment', verbose_name='关联附件')),
                        ('handled_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='处理人')),
                        ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='举报人')),
                    ],
                    options={
                        'verbose_name': '私信附件举报',
                        'verbose_name_plural': '私信附件举报',
                        'db_table': 'knowledge_project_attachmentreport',
                        'ordering': ['-created_at'],
                        'indexes': [
                            models.Index(fields=['attachment', 'status'], name='knowledge_p_attachm_58c78e_idx'),
                            models.Index(fields=['status', '-created_at'], name='knowledge_p_status_8f4cb4_idx'),
                            models.Index(fields=['reporter', '-created_at'], name='knowledge_p_reporte_46bcc1_idx'),
                        ],
                        'constraints': [
                            models.UniqueConstraint(fields=('attachment', 'reporter', 'pending_dedup_key'), name='uniq_pending_attachment_report_per_reporter'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='NoteReport',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('status', models.CharField(choices=[('pending', '待处理'), ('removed', '已下架'), ('dismissed', '已驳回')], default='pending', max_length=20, verbose_name='处理状态')),
                        ('reason', models.CharField(choices=[('spam', '垃圾广告'), ('abuse', '辱骂骚扰'), ('porn', '色情低俗'), ('scam', '诈骗欺诈'), ('privacy', '侵犯隐私'), ('illegal', '违法违规'), ('other', '其他')], default='other', max_length=120, verbose_name='举报原因')),
                        ('detail', models.TextField(blank=True, max_length=1000, verbose_name='补充说明')),
                        ('evidence_snapshot', models.JSONField(blank=True, default=dict, verbose_name='举报证据快照')),
                        ('pending_dedup_key', models.CharField(blank=True, editable=False, max_length=16, null=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='举报时间')),
                        ('handled_at', models.DateTimeField(blank=True, null=True, verbose_name='处理时间')),
                        ('resolution_note', models.TextField(blank=True, verbose_name='处理备注')),
                        ('handled_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                        ('note', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports', to='knowledge_project.note', verbose_name='关联文章')),
                        ('reported_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='被举报用户')),
                        ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='举报人')),
                    ],
                    options={
                        'verbose_name': '文章举报',
                        'verbose_name_plural': '文章举报',
                        'db_table': 'knowledge_project_notereport',
                        'ordering': ['-created_at'],
                        'indexes': [
                            models.Index(fields=['note', 'status'], name='knowledge_p_note_id_5b63af_idx'),
                            models.Index(fields=['status', '-created_at'], name='knowledge_p_status_fa622a_idx'),
                            models.Index(fields=['reporter', '-created_at'], name='knowledge_p_reporte_b322f9_idx'),
                            models.Index(fields=['reported_user'], name='knowledge_p_reporte_45dc07_idx'),
                        ],
                        'constraints': [
                            models.UniqueConstraint(fields=('note', 'reporter', 'pending_dedup_key'), name='uniq_pending_note_report_per_reporter'),
                        ],
                    },
                ),
            ],
        ),
    ]
