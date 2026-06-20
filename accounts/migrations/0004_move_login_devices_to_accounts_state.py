from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0003_rename_account_security_tables'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='LoginDevice',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('device_fingerprint', models.CharField(db_index=True, max_length=64, verbose_name='设备指纹')),
                        ('ip_address', models.GenericIPAddressField(db_index=True, verbose_name='IP地址')),
                        ('ip_location', models.CharField(blank=True, max_length=200, verbose_name='IP归属地')),
                        ('user_agent', models.TextField(verbose_name='用户代理')),
                        ('device_info', models.CharField(max_length=200, verbose_name='设备信息')),
                        ('first_login_at', models.DateTimeField(auto_now_add=True, verbose_name='首次登录时间')),
                        ('last_login_at', models.DateTimeField(auto_now=True, verbose_name='最后登录时间')),
                        ('login_count', models.IntegerField(default=1, verbose_name='登录次数')),
                        ('is_trusted', models.BooleanField(default=False, verbose_name='是否信任')),
                        ('trusted_at', models.DateTimeField(blank=True, null=True, verbose_name='信任时间')),
                        ('session_key', models.CharField(blank=True, db_index=True, max_length=40, verbose_name='Session key')),
                        ('is_active', models.BooleanField(db_index=True, default=True, verbose_name='Active session')),
                        ('revoked_at', models.DateTimeField(blank=True, null=True, verbose_name='Revoked at')),
                        ('revoked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revoked_login_devices', to=settings.AUTH_USER_MODEL, verbose_name='Revoked by')),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='login_devices', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
                    ],
                    options={
                        'db_table': 'knowledge_project_logindevice',
                        'verbose_name': '登录设备',
                        'verbose_name_plural': '登录设备',
                        'indexes': [
                            models.Index(fields=['user', 'device_fingerprint'], name='knowledge_p_user_id_7475e1_idx'),
                            models.Index(fields=['user', 'last_login_at'], name='knowledge_p_user_id_967b54_idx'),
                            models.Index(fields=['user', 'is_active'], name='knowledge_p_user_id_4c985c_idx'),
                        ],
                        'unique_together': {('user', 'device_fingerprint')},
                    },
                ),
                migrations.CreateModel(
                    name='TrustedDevice',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('device_token', models.CharField(db_index=True, max_length=128, unique=True, verbose_name='加密令牌')),
                        ('user_agent', models.CharField(max_length=500, verbose_name='UA标识')),
                        ('ip_address', models.GenericIPAddressField(verbose_name='首次IP')),
                        ('last_login_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='最近IP')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                        ('last_used_at', models.DateTimeField(auto_now=True, verbose_name='最后使用')),
                        ('expires_at', models.DateTimeField(db_index=True, verbose_name='过期时间')),
                        ('fail_count', models.IntegerField(default=0, verbose_name='设备级失败计数')),
                        ('is_revoked', models.BooleanField(db_index=True, default=False, verbose_name='已撤销')),
                        ('revoked_reason', models.CharField(blank=True, max_length=100, verbose_name='撤销原因')),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='trusted_devices', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
                    ],
                    options={
                        'db_table': 'knowledge_project_trusteddevice',
                        'verbose_name': '信任设备',
                        'verbose_name_plural': '信任设备',
                        'indexes': [
                            models.Index(fields=['user', 'is_revoked'], name='knowledge_p_user_id_91fd9a_idx'),
                            models.Index(fields=['expires_at'], name='knowledge_p_expires_503a0e_idx'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='LoginNotification',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('ip_address', models.GenericIPAddressField(verbose_name='IP地址')),
                        ('reason', models.CharField(choices=[('new_device', '新设备'), ('new_location', '新位置'), ('suspicious', '可疑登录'), ('first_login', '首次登录')], max_length=20, verbose_name='通知原因')),
                        ('sent_at', models.DateTimeField(auto_now_add=True, verbose_name='发送时间')),
                        ('email_sent', models.BooleanField(default=False, verbose_name='邮件已发送')),
                        ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='accounts.logindevice', verbose_name='设备')),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='login_notifications', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
                    ],
                    options={
                        'db_table': 'knowledge_project_loginnotification',
                        'verbose_name': '登录通知记录',
                        'verbose_name_plural': '登录通知记录',
                        'indexes': [
                            models.Index(fields=['user', 'sent_at'], name='knowledge_p_user_id_a9bb4b_idx'),
                            models.Index(fields=['device', 'sent_at'], name='knowledge_p_device__6b0641_idx'),
                        ],
                    },
                ),
            ],
        ),
    ]
