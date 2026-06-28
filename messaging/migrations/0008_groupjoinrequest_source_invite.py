from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('messaging', '0007_messagegroup_allow_new_members_view_history'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupjoinrequest',
            name='source_invite',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='join_requests',
                to='messaging.messagegroupinvitelink',
                verbose_name='来源邀请链接',
            ),
        ),
        migrations.AddField(
            model_name='groupjoinrequest',
            name='source_invite_use',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='join_requests',
                to='messaging.messagegroupinviteuse',
                verbose_name='来源邀请使用记录',
            ),
        ),
    ]
