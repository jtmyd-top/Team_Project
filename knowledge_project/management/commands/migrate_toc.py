"""
为现有笔记生成目录的管理命令

用法:
    python manage.py migrate_toc                    # 处理所有笔记
    python manage.py migrate_toc --note-id 123      # 只处理指定笔记
    python manage.py migrate_toc --author-id 1      # 只处理指定作者的笔记
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from knowledge_project.models import Note
from knowledge_project.utils.toc_extractor import extract_toc_from_html


class Command(BaseCommand):
    help = '为现有笔记生成目录结构并注入标题 ID'

    def add_arguments(self, parser):
        parser.add_argument(
            '--note-id',
            type=int,
            help='只处理指定的笔记 ID',
        )
        parser.add_argument(
            '--author-id',
            type=int,
            help='只处理指定作者的笔记',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='预览模式，不实际保存',
        )

    def handle(self, *args, **options):
        note_id = options.get('note_id')
        author_id = options.get('author_id')
        dry_run = options.get('dry_run')

        # 获取要处理的笔记
        queryset = Note.objects.all()

        if note_id:
            queryset = queryset.filter(id=note_id)
            self.stdout.write(f"只处理笔记 ID: {note_id}")
        elif author_id:
            queryset = queryset.filter(author_id=author_id)
            self.stdout.write(f"只处理作者 ID: {author_id} 的笔记")
        else:
            self.stdout.write("处理所有笔记")

        total = queryset.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("没有找到要处理的笔记"))
            return

        self.stdout.write(f"共找到 {total} 篇笔记需要处理")

        # 统计
        updated_count = 0
        skipped_count = 0
        error_count = 0

        for note in queryset:
            try:
                if not note.content:
                    skipped_count += 1
                    continue

                # 提取目录
                toc_list, updated_html = extract_toc_from_html(note.content)

                # 检查是否有变化
                has_changes = (
                    note.toc != toc_list or
                    note.content != updated_html
                )

                if not has_changes:
                    skipped_count += 1
                    continue

                if dry_run:
                    self.stdout.write(f"[Preview] Note: '{note.title}' ({note.id}):")
                    self.stdout.write(f"  - TOC items: {len(toc_list)}")
                    for item in toc_list[:5]:  # Only show first 5 items
                        self.stdout.write(f"    {'  ' * (item['level'] - 1)}- {item['text']}")
                    if len(toc_list) > 5:
                        self.stdout.write(f"    ... and {len(toc_list) - 5} more items")
                else:
                    # 保存更新
                    note.toc = toc_list
                    note.content = updated_html
                    note.save(update_fields=['toc', 'content'])
                    updated_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(f"[OK] Note '{note.title}' ({note.id}) - {len(toc_list)} TOC items")
                    )

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"[FAIL] Note '{note.title}' ({note.id}) Error: {str(e)}")
                )

        # 输出总结
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("处理完成:")
        self.stdout.write(f"  - 成功更新: {updated_count} 篇")
        self.stdout.write(f"  - 跳过: {skipped_count} 篇")
        self.stdout.write(f"  - 失败: {error_count} 篇")

        if dry_run:
            self.stdout.write("\n这是预览模式，使用 --no-dry-run 来实际保存")
