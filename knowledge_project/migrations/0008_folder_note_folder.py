# Generated migration for Folder model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('knowledge_project', '0007_add_toc_to_note'),
    ]

    operations = [
        migrations.CreateModel(
            name='Folder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='文件夹名称')),
                ('order', models.IntegerField(default=0, verbose_name='排序顺序')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='folders', to=settings.AUTH_USER_MODEL, verbose_name='所有者')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='knowledge_project.folder', verbose_name='父文件夹')),
            ],
            options={
                'verbose_name': '文件夹',
                'verbose_name_plural': '文件夹',
                'ordering': ['order', 'name'],
            },
        ),
        migrations.AddField(
            model_name='note',
            name='folder',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notes_in_folder', to='knowledge_project.folder', verbose_name='所属文件夹'),
        ),
        migrations.AddField(
            model_name='note',
            name='is_trashed',
            field=models.BooleanField(default=False, verbose_name='已删除'),
        ),
        migrations.AddField(
            model_name='note',
            name='is_favorited',
            field=models.BooleanField(default=False, verbose_name='已收藏'),
        ),
        migrations.AddIndex(
            model_name='folder',
            index=models.Index(fields=['owner', 'parent'], name='knowledge_p_owner_i_folder_idx'),
        ),
        migrations.AddIndex(
            model_name='note',
            index=models.Index(fields=['folder'], name='knowledge_p_folder__note_idx'),
        ),
        migrations.AddIndex(
            model_name='note',
            index=models.Index(fields=['is_trashed'], name='knowledge_p_trashed_note_idx'),
        ),
    ]
