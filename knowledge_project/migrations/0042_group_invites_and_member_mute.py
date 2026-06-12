from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import knowledge_project.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge_project', '0041_profilevisit_notification_kinds'),
    ]

    operations = [
        migrations.AddField(
            model_name='messagegroupmember',
            name='muted_until',
            field=models.DateTimeField(blank=True, null=True, verbose_name='群内禁言到期时间'),
        ),
        migrations.CreateModel(
            name='MessageGroupInviteLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(default=knowledge_project.models.generate_group_invite_token, max_length=64, unique=True, verbose_name='邀请令牌')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('expires_at', models.DateTimeField(blank=True, null=True, verbose_name='过期时间')),
                ('max_uses', models.PositiveIntegerField(blank=True, null=True, verbose_name='最大使用次数')),
                ('uses_count', models.PositiveIntegerField(default=0, verbose_name='已使用次数')),
                ('revoked_at', models.DateTimeField(blank=True, null=True, verbose_name='撤销时间')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='创建者')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='invite_links', to='knowledge_project.messagegroup', verbose_name='群组')),
            ],
            options={
                'verbose_name': '群组邀请链接',
                'verbose_name_plural': '群组邀请链接',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='messagegroupinvitelink',
            index=models.Index(fields=['group', 'revoked_at'], name='knowledge_p_group_i_6ccecf_idx'),
        ),
        migrations.AddIndex(
            model_name='messagegroupinvitelink',
            index=models.Index(fields=['token'], name='knowledge_p_token_50ec98_idx'),
        ),
    ]
