from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge_project', '0042_group_invites_and_member_mute'),
    ]

    operations = [
        migrations.AddField(
            model_name='messagegroup',
            name='announcement',
            field=models.TextField(blank=True, default='', verbose_name='群公告'),
        ),
        migrations.AddField(
            model_name='messagegroup',
            name='avatar',
            field=models.ImageField(blank=True, null=True, upload_to='group_avatars/', verbose_name='群头像'),
        ),
        migrations.AddField(
            model_name='messagegroup',
            name='description',
            field=models.TextField(blank=True, default='', verbose_name='群简介'),
        ),
        migrations.AddField(
            model_name='messagegroup',
            name='mute_mode',
            field=models.CharField(choices=[('none', '不限制发言'), ('admins_only', '仅群主/管理员可发言')], default='none', max_length=32, verbose_name='发言模式'),
        ),
        migrations.CreateModel(
            name='MessageGroupAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('group_create', '创建群组'), ('group_update_profile', '更新群资料'), ('group_rename', '修改群名'), ('group_announcement_update', '更新群公告'), ('member_add', '添加成员'), ('member_remove', '移除成员'), ('member_role_change', '修改成员角色'), ('member_mute', '禁言成员'), ('member_unmute', '解除成员禁言'), ('group_mute_change', '修改全员禁言'), ('ownership_transfer', '转让群主'), ('invite_link_create', '创建邀请链接'), ('invite_link_revoke', '撤销邀请链接'), ('member_ban', '封禁成员'), ('member_unban', '解除封禁'), ('group_dissolve', '解散群组'), ('group_leave', '退出群组')], max_length=64, verbose_name='动作')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='元数据')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='message_group_audit_actions', to=settings.AUTH_USER_MODEL, verbose_name='操作者')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='knowledge_project.messagegroup', verbose_name='群组')),
                ('target_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='message_group_audit_targets', to=settings.AUTH_USER_MODEL, verbose_name='目标用户')),
            ],
            options={
                'verbose_name': '群组审计日志',
                'verbose_name_plural': '群组审计日志',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MessageGroupBan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(blank=True, default='', verbose_name='封禁原因')),
                ('expires_at', models.DateTimeField(blank=True, null=True, verbose_name='过期时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='封禁时间')),
                ('revoked_at', models.DateTimeField(blank=True, null=True, verbose_name='解封时间')),
                ('banned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='issued_message_group_bans', to=settings.AUTH_USER_MODEL, verbose_name='封禁操作者')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bans', to='knowledge_project.messagegroup', verbose_name='群组')),
                ('revoked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revoked_message_group_bans', to=settings.AUTH_USER_MODEL, verbose_name='解封操作者')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='message_group_bans', to=settings.AUTH_USER_MODEL, verbose_name='被封禁用户')),
            ],
            options={
                'verbose_name': '群组封禁记录',
                'verbose_name_plural': '群组封禁记录',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='messagegroupauditlog',
            index=models.Index(fields=['group', '-created_at'], name='knowledge_p_group_i_6b66fc_idx'),
        ),
        migrations.AddIndex(
            model_name='messagegroupauditlog',
            index=models.Index(fields=['actor'], name='knowledge_p_actor_i_d60516_idx'),
        ),
        migrations.AddIndex(
            model_name='messagegroupauditlog',
            index=models.Index(fields=['target_user'], name='knowledge_p_target__1948c8_idx'),
        ),
        migrations.AddIndex(
            model_name='messagegroupauditlog',
            index=models.Index(fields=['action'], name='knowledge_p_action_744428_idx'),
        ),
        migrations.AddIndex(
            model_name='messagegroupban',
            index=models.Index(fields=['group', 'user'], name='knowledge_p_group_i_8f9b3a_idx'),
        ),
        migrations.AddIndex(
            model_name='messagegroupban',
            index=models.Index(fields=['expires_at'], name='knowledge_p_expires_0c504e_idx'),
        ),
        migrations.AddIndex(
            model_name='messagegroupban',
            index=models.Index(fields=['revoked_at'], name='knowledge_p_revoked_3c7792_idx'),
        ),
    ]
