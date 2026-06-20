from django.conf import settings
from django.db import migrations, models
import django.core.serializers.json
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge_project', '0052_move_moderation_core_to_moderation'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='PasswordResetToken',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('token', models.CharField(max_length=64, unique=True)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('expires_at', models.DateTimeField()),
                        ('is_used', models.BooleanField(default=False)),
                        ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='password_reset_token', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'knowledge_project_passwordresettoken',
                        'verbose_name': '密码重置令牌',
                        'verbose_name_plural': '密码重置令牌',
                        'indexes': [
                            models.Index(fields=['token'], name='knowledge_p_token_b56c5f_idx'),
                            models.Index(fields=['expires_at'], name='knowledge_p_expires_e8717b_idx'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='PasswordResetAttempt',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('email', models.EmailField(db_index=True, max_length=254, verbose_name='邮箱')),
                        ('ip_address', models.GenericIPAddressField(db_index=True, verbose_name='IP地址')),
                        ('fingerprint', models.CharField(db_index=True, max_length=64, verbose_name='客户端指纹')),
                        ('attempted_at', models.DateTimeField(auto_now_add=True, verbose_name='尝试时间')),
                        ('is_successful', models.BooleanField(default=False, verbose_name='是否成功')),
                        ('user_agent', models.TextField(blank=True, verbose_name='用户代理')),
                    ],
                    options={
                        'db_table': 'knowledge_project_passwordresetattempt',
                        'verbose_name': '密码重置尝试',
                        'verbose_name_plural': '密码重置尝试',
                        'indexes': [
                            models.Index(fields=['email', 'attempted_at'], name='knowledge_p_email_704833_idx'),
                            models.Index(fields=['ip_address', 'attempted_at'], name='knowledge_p_ip_addr_48fcac_idx'),
                            models.Index(fields=['fingerprint', 'attempted_at'], name='knowledge_p_fingerp_113a05_idx'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='SecurityAuditLog',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('action', models.CharField(choices=[('email_changed', 'Email changed'), ('device_revoked', 'Login device revoked')], db_index=True, max_length=64)),
                        ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                        ('user_agent', models.TextField(blank=True, default='')),
                        ('metadata', models.JSONField(blank=True, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder)),
                        ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                        ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='security_audit_actions', to=settings.AUTH_USER_MODEL)),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='security_audit_logs', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'knowledge_project_securityauditlog',
                        'verbose_name': 'Security audit log',
                        'verbose_name_plural': 'Security audit logs',
                        'ordering': ['-created_at'],
                        'indexes': [
                            models.Index(fields=['user', '-created_at'], name='knowledge_p_user_id_b62207_idx'),
                            models.Index(fields=['actor', '-created_at'], name='knowledge_p_actor_i_30257b_idx'),
                            models.Index(fields=['action', '-created_at'], name='knowledge_p_action_1a1904_idx'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='AccessLog',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('user_identifier', models.CharField(db_index=True, max_length=150, verbose_name='用户/账号')),
                        ('ip_address', models.GenericIPAddressField(db_index=True, verbose_name='来源IP')),
                        ('action', models.CharField(choices=[('vault_fail', '保险柜失败'), ('login_fail', '登录失败'), ('ip_banned', 'IP封禁'), ('device_revoked', '设备信任撤销')], db_index=True, default='vault_fail', max_length=20, verbose_name='行为')),
                        ('count', models.IntegerField(default=1, verbose_name='聚合频次')),
                        ('details', models.TextField(blank=True, verbose_name='详细信息')),
                        ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='发生时间')),
                        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='最后更新')),
                    ],
                    options={
                        'db_table': 'knowledge_project_accesslog',
                        'verbose_name': '安全访问日志',
                        'verbose_name_plural': '安全访问日志',
                        'indexes': [
                            models.Index(fields=['user_identifier', 'ip_address', 'action'], name='knowledge_p_user_id_1113d0_idx'),
                            models.Index(fields=['created_at'], name='knowledge_p_created_78d3e5_idx'),
                        ],
                    },
                ),
            ],
        ),
    ]
