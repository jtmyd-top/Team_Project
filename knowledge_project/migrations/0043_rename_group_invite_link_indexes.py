from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_project', '0042_group_invites_and_member_mute'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='messagegroupinvitelink',
            new_name='knowledge_p_group_i_6012d6_idx',
            old_name='knowledge_p_group_i_6ccecf_idx',
        ),
        migrations.RenameIndex(
            model_name='messagegroupinvitelink',
            new_name='knowledge_p_token_cf0d54_idx',
            old_name='knowledge_p_token_50ec98_idx',
        ),
    ]
