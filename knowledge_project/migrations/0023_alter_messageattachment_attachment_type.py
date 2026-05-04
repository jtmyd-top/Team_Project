from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_project', '0022_messageattachment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='messageattachment',
            name='attachment_type',
            field=models.CharField(
                choices=[
                    ('image', '图片'),
                    ('audio', '语音'),
                    ('video', '视频'),
                    ('file', '文件'),
                ],
                default='file',
                max_length=10,
                verbose_name='附件类型',
            ),
        ),
    ]
