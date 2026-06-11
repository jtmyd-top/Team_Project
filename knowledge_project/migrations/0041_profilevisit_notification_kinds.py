from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge_project', '0040_seed_moderation_templates'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProfileVisit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_key', models.CharField(blank=True, db_index=True, max_length=40)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profile_visits', to='knowledge_project.profile')),
                ('viewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='profile_visits_made', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Profile visit',
                'verbose_name_plural': 'Profile visits',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AlterField(
            model_name='usernotification',
            name='kind',
            field=models.CharField(choices=[
                ('report_received', '举报已收到'),
                ('report_resolved', '举报已处理'),
                ('sanction_applied', '用户处置'),
                ('sanction_revoked', '处置解除'),
                ('appeal_submitted', '申诉已提交'),
                ('appeal_resolved', '申诉已处理'),
                ('new_comment', 'New comment'),
                ('comment_reply', 'Comment reply'),
                ('profile_liked', 'Profile liked'),
                ('new_follower', 'New follower'),
                ('new_message', 'New message'),
                ('note_copied', 'Note copied'),
            ], max_length=40, verbose_name='通知类型'),
        ),
        migrations.AddIndex(
            model_name='profilevisit',
            index=models.Index(fields=['profile', '-created_at'], name='profilevisit_profile_idx'),
        ),
        migrations.AddIndex(
            model_name='profilevisit',
            index=models.Index(fields=['viewer', '-created_at'], name='profilevisit_viewer_idx'),
        ),
    ]
