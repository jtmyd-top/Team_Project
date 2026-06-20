import accounts.models
from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0006_rename_login_device_tables'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name='Profile',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('activation_code', models.CharField(blank=True, max_length=8, null=True, unique=True, verbose_name='激活码')),
                        ('code_created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                        ('avatar', models.ImageField(blank=True, null=True, upload_to=accounts.models.user_avatar_path, verbose_name='头像')),
                        ('avatar_source', models.CharField(blank=True, max_length=32, verbose_name='头像来源')),
                        ('bio', models.TextField(blank=True, max_length=160, validators=[django.core.validators.MaxLengthValidator(160)], verbose_name='个人简介')),
                        ('banner_image', models.FileField(blank=True, null=True, upload_to=accounts.models.user_avatar_path, verbose_name='主页横幅')),
                        ('theme', models.JSONField(default=accounts.models.default_theme_settings, help_text='存储用户界面主题配置', verbose_name='主题设置')),
                        ('layout_mode', models.CharField(choices=[('default', '默认布局'), ('compact', '紧凑布局'), ('wide', '宽屏布局')], default='default', max_length=20, verbose_name='界面布局')),
                        ('last_theme_update', models.DateTimeField(auto_now=True, help_text='记录用户最后修改主题的时间', verbose_name='最后主题更新时间')),
                        ('allow_rich_bio', models.BooleanField(default=False, verbose_name='允许富文本简介')),
                        ('email_last_changed_at', models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='Last email change time')),
                        ('likes_count', models.IntegerField(default=0, verbose_name='获赞数')),
                        ('last_updated', models.DateTimeField(auto_now=True, verbose_name='最后更新时间')),
                        ('two_fa_enabled', models.BooleanField(default=False, verbose_name='启用两因素认证')),
                        ('two_fa_method', models.CharField(blank=True, choices=[('totp', 'TOTP验证器'), ('email', '邮箱验证')], default='totp', max_length=10, verbose_name='2FA验证方式')),
                        ('totp_secret', models.CharField(blank=True, help_text='用于 Google Authenticator 等 TOTP 应用的密钥', max_length=32, verbose_name='TOTP密钥')),
                        ('backup_codes', models.JSONField(blank=True, default=list, help_text='用于 TOTP 设备丢失时的一次性备用码', verbose_name='备用验证码')),
                        ('notify_login', models.BooleanField(default=True, help_text='账户登录时发送邮件通知', verbose_name='登录通知')),
                        ('notify_password_change', models.BooleanField(default=True, help_text='密码修改时发送邮件通知', verbose_name='密码修改通知')),
                        ('notify_password_reset', models.BooleanField(default=True, help_text='密码重置时发送邮件通知', verbose_name='密码重置通知')),
                        ('notify_note_activities', models.BooleanField(default=False, help_text='笔记创建/修改/删除时发送邮件通知', verbose_name='笔记活动通知')),
                        ('notify_profile_likes', models.BooleanField(default=True, help_text='个人空间或作品被点赞时发送邮件通知', verbose_name='点赞通知')),
                        ('discoverable_by_username', models.BooleanField(default=False, help_text='关闭后即使输入完整用户名也无法被搜索到', verbose_name='允许通过用户名搜索到我')),
                        ('discoverable_by_email', models.BooleanField(default=False, help_text='关闭后即使输入完整邮箱也无法被搜索到', verbose_name='允许通过邮箱搜索到我')),
                        ('search_code', models.CharField(blank=True, db_index=True, help_text='8 位随机字符串，用户可主动分享给朋友用于添加', max_length=12, null=True, unique=True, verbose_name='公开搜索短码')),
                        ('encrypted_vault_key', models.TextField(blank=True, help_text='Base64编码的AES加密DEK，用KEK加密', null=True, verbose_name='加密保险柜密钥')),
                        ('vault_key_iv', models.TextField(blank=True, help_text='加密DEK时的初始化向量（Base64编码）', null=True, verbose_name='保险柜密钥IV')),
                        ('vault_initialized', models.BooleanField(default=False, help_text='用户是否已初始化保险柜', verbose_name='保险柜已初始化')),
                        ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='关联用户')),
                    ],
                    options={
                        'verbose_name': '用户资料',
                        'verbose_name_plural': '用户资料',
                        'db_table': 'knowledge_project_profile',
                    },
                ),
                migrations.CreateModel(
                    name='ProfileVisit',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('session_key', models.CharField(blank=True, db_index=True, max_length=40)),
                        ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                        ('user_agent', models.CharField(blank=True, max_length=255)),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profile_visits', to='accounts.profile')),
                        ('viewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='profile_visits_made', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'verbose_name': 'Profile visit',
                        'verbose_name_plural': 'Profile visits',
                        'db_table': 'knowledge_project_profilevisit',
                        'ordering': ['-created_at'],
                        'indexes': [
                            models.Index(fields=['profile', '-created_at'], name='profilevisit_profile_idx'),
                            models.Index(fields=['viewer', '-created_at'], name='profilevisit_viewer_idx'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='ProfileLike',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='点赞时间')),
                        ('liker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='given_likes', to=settings.AUTH_USER_MODEL, verbose_name='点赞者')),
                        ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_likes', to='accounts.profile', verbose_name='被点赞的用户资料')),
                    ],
                    options={
                        'verbose_name': '点赞记录',
                        'verbose_name_plural': '点赞记录',
                        'db_table': 'knowledge_project_profilelike',
                        'indexes': [
                            models.Index(fields=['liker', 'profile'], name='knowledge_p_liker_i_ea4deb_idx'),
                            models.Index(fields=['liker', 'profile'], name='profilelike_liker_profile_idx'),
                        ],
                        'unique_together': {('liker', 'profile')},
                    },
                ),
            ],
        ),
    ]
