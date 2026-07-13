from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('notifications', '0003_rename_usernotification_table'),
    ]

    operations = [
        migrations.CreateModel(
            name='BrowserPushSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.URLField(max_length=255, unique=True, verbose_name='推送地址')),
                ('p256dh', models.CharField(max_length=255, verbose_name='P-256 DH 密钥')),
                ('auth', models.CharField(max_length=255, verbose_name='认证密钥')),
                ('expiration_time', models.DateTimeField(blank=True, null=True, verbose_name='订阅到期时间')),
                ('user_agent', models.CharField(blank=True, default='', max_length=512, verbose_name='浏览器标识')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='browser_push_subscriptions',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='订阅用户',
                    ),
                ),
            ],
            options={
                'db_table': 'notifications_browserpushsubscription',
                'verbose_name': '浏览器推送订阅',
                'verbose_name_plural': '浏览器推送订阅',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddIndex(
            model_name='browserpushsubscription',
            index=models.Index(fields=['user', '-updated_at'], name='bpush_user_updated_idx'),
        ),
    ]
