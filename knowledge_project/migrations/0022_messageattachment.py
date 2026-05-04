from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import knowledge_project.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge_project', '0021_messagepreference_browser_new_message'),
    ]

    operations = [
        migrations.CreateModel(
            name='MessageAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to=knowledge_project.models.message_attachment_path, verbose_name='附件文件')),
                ('original_name', models.CharField(max_length=255, verbose_name='原始文件名')),
                ('attachment_type', models.CharField(choices=[('image', '图片'), ('file', '文件')], default='file', max_length=10, verbose_name='附件类型')),
                ('mime_type', models.CharField(blank=True, max_length=120, verbose_name='MIME 类型')),
                ('size', models.PositiveIntegerField(default=0, verbose_name='文件大小')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='上传时间')),
                ('message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='knowledge_project.message', verbose_name='关联私信')),
                ('uploader', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='message_attachments', to=settings.AUTH_USER_MODEL, verbose_name='上传者')),
            ],
            options={
                'verbose_name': '私信附件',
                'verbose_name_plural': '私信附件',
                'ordering': ['created_at'],
                'indexes': [
                    models.Index(fields=['uploader', 'message'], name='knowledge_p_uploade_dc88e7_idx'),
                    models.Index(fields=['message', 'created_at'], name='knowledge_p_message_9b22f9_idx'),
                ],
            },
        ),
    ]
