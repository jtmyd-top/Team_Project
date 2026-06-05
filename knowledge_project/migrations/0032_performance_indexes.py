# Generated manually for performance optimization
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_project', '0031_noteasset_session_throttle'),
    ]

    operations = [
        # 为 Note 模型添加复合索引，优化公开笔记查询
        migrations.AddIndex(
            model_name='note',
            index=models.Index(
                fields=['is_public', '-updated_at'],
                name='note_public_updated_idx',
                condition=models.Q(is_public=True),
            ),
        ),
        # 为 NoteComment 添加索引，优化评论计数查询
        migrations.AddIndex(
            model_name='notecomment',
            index=models.Index(
                fields=['note', 'created_at'],
                name='notecomment_note_created_idx',
            ),
        ),
        # 为 NoteHistory 添加索引，优化用户历史查询
        migrations.AddIndex(
            model_name='notehistory',
            index=models.Index(
                fields=['user', '-viewed_at'],
                name='notehistory_user_viewed_idx',
            ),
        ),
        # 为 ProfileLike 添加索引，优化点赞查询
        migrations.AddIndex(
            model_name='profilelike',
            index=models.Index(
                fields=['liker', 'profile'],
                name='profilelike_liker_profile_idx',
            ),
        ),
    ]
