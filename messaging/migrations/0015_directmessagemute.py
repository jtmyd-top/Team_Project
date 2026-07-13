from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('messaging', '0014_rename_messaging_d_share_i_58ee7d_idx_messaging_d_share_i_b17ba1_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DirectMessageMute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(blank=True, max_length=500, verbose_name='禁言原因')),
                (
                    'expires_at',
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        help_text='留空表示永久禁言',
                        null=True,
                        verbose_name='禁言到期时间',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='禁言时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                (
                    'muted_user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='muted_in_direct_messages',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='被禁言用户',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='direct_message_mutes',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='禁言发起人',
                    ),
                ),
            ],
            options={
                'verbose_name': '私信禁言',
                'verbose_name_plural': '私信禁言',
                'indexes': [
                    models.Index(fields=['user', 'muted_user'], name='messaging_d_user_id_a03bb7_idx'),
                    models.Index(fields=['user', 'expires_at'], name='messaging_d_user_id_9e08dc_idx'),
                ],
                'unique_together': {('user', 'muted_user')},
            },
        ),
    ]
