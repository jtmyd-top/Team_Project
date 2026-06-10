from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge_project', '0035_extend_user_sanction_types'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageGroupPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enabled', models.BooleanField(default=True, verbose_name='允许用户创建群组')),
                ('min_public_notes', models.PositiveIntegerField(default=10, verbose_name='公开文章数门槛')),
                ('min_followers', models.PositiveIntegerField(default=50, verbose_name='关注者数门槛')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '私信群组创建策略',
                'verbose_name_plural': '私信群组创建策略',
            },
        ),
        migrations.CreateModel(
            name='MessageGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, verbose_name='群组名称')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='创建者')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='owned_message_groups', to=settings.AUTH_USER_MODEL, verbose_name='群主')),
            ],
            options={
                'verbose_name': '私信群组',
                'verbose_name_plural': '私信群组',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='GroupMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(verbose_name='消息内容')),
                ('searchable_text', models.TextField(blank=True, default='', verbose_name='搜索文本')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='发送时间')),
                ('is_recalled', models.BooleanField(default=False, verbose_name='已撤回')),
                ('recalled_at', models.DateTimeField(blank=True, null=True, verbose_name='撤回时间')),
                ('was_reported', models.BooleanField(default=False, verbose_name='是否曾被举报')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='knowledge_project.messagegroup', verbose_name='群组')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_group_messages', to=settings.AUTH_USER_MODEL, verbose_name='发送者')),
            ],
            options={
                'verbose_name': '群组消息',
                'verbose_name_plural': '群组消息',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MessageGroupMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('owner', '群主'), ('admin', '管理员'), ('member', '成员')], default='member', max_length=12, verbose_name='角色')),
                ('joined_at', models.DateTimeField(auto_now_add=True, verbose_name='加入时间')),
                ('left_at', models.DateTimeField(blank=True, null=True, verbose_name='退出时间')),
                ('last_read_at', models.DateTimeField(blank=True, null=True, verbose_name='最后读取时间')),
                ('is_pinned', models.BooleanField(default=False, verbose_name='置顶')),
                ('pinned_at', models.DateTimeField(blank=True, null=True, verbose_name='置顶时间')),
                ('is_muted', models.BooleanField(default=False, verbose_name='消息免打扰')),
                ('is_archived', models.BooleanField(default=False, verbose_name='已归档')),
                ('archived_at', models.DateTimeField(blank=True, null=True, verbose_name='归档时间')),
                ('force_unread', models.BooleanField(default=False, verbose_name='手动标记未读')),
                ('cleared_before', models.DateTimeField(blank=True, null=True, verbose_name='清空时间')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='knowledge_project.messagegroup', verbose_name='群组')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='message_group_memberships', to=settings.AUTH_USER_MODEL, verbose_name='成员')),
            ],
            options={
                'verbose_name': '私信群组成员',
                'verbose_name_plural': '私信群组成员',
                'unique_together': {('group', 'user')},
            },
        ),
        migrations.CreateModel(
            name='GroupMessageDeletion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='删除时间')),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='deletions', to='knowledge_project.groupmessage', verbose_name='群组消息')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '群组消息删除记录',
                'verbose_name_plural': '群组消息删除记录',
                'unique_together': {('message', 'user')},
            },
        ),
        migrations.AddField(
            model_name='messagereport',
            name='group_message',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports', to='knowledge_project.groupmessage', verbose_name='关联群组消息'),
        ),
        migrations.AddIndex(
            model_name='messagegroup',
            index=models.Index(fields=['owner', '-created_at'], name='knowledge_p_owner_i_e18715_idx'),
        ),
        migrations.AddIndex(
            model_name='messagegroup',
            index=models.Index(fields=['is_active'], name='knowledge_p_is_acti_be8860_idx'),
        ),
        migrations.AddIndex(
            model_name='groupmessage',
            index=models.Index(fields=['group', '-created_at'], name='knowledge_p_group_i_b3cef9_idx'),
        ),
        migrations.AddIndex(
            model_name='groupmessage',
            index=models.Index(fields=['sender', '-created_at'], name='knowledge_p_sender__ee5817_idx'),
        ),
        migrations.AddIndex(
            model_name='groupmessage',
            index=models.Index(fields=['was_reported'], name='knowledge_p_was_rep_3b4138_idx'),
        ),
        migrations.AddIndex(
            model_name='messagegroupmember',
            index=models.Index(fields=['user', 'is_archived'], name='knowledge_p_user_id_3305a1_idx'),
        ),
        migrations.AddIndex(
            model_name='messagegroupmember',
            index=models.Index(fields=['group', 'left_at'], name='knowledge_p_group_i_af93f4_idx'),
        ),
        migrations.AddIndex(
            model_name='groupmessagedeletion',
            index=models.Index(fields=['user', 'message'], name='knowledge_p_user_id_3d38de_idx'),
        ),
    ]
