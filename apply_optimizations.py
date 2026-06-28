#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能优化执行脚本
用于应用数据库迁移和验证优化效果
"""
import os
import sys
import django

# 设置Django环境
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Team_Project.settings')
django.setup()

from django.core.management import call_command
from django.core.cache import cache
from django.db import connection

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def check_redis_connection():
    """检查Redis连接"""
    print_section("检查Redis连接")
    try:
        cache.set('test_key', 'test_value', 10)
        value = cache.get('test_key')
        if value == 'test_value':
            print("[OK] Redis连接正常")
            return True
        else:
            print("[ERROR] Redis连接异常：值不匹配")
            return False
    except Exception as e:
        print(f"[ERROR] Redis连接失败: {e}")
        return False

def check_database_connection():
    """检查数据库连接"""
    print_section("检查数据库连接")
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result[0] == 1:
                print("[OK] 数据库连接正常")
                return True
    except Exception as e:
        print(f"[ERROR] 数据库连接失败: {e}")
        return False

def apply_migrations():
    """应用数据库迁移"""
    print_section("应用数据库迁移")
    try:
        print("正在检查待应用的迁移...")
        call_command('showmigrations', '--plan')

        print("\n正在应用迁移...")
        call_command('migrate', '--noinput')
        print("[OK] 数据库迁移完成")
        return True
    except Exception as e:
        print(f"[ERROR] 迁移失败: {e}")
        return False

def check_indexes():
    """检查索引是否创建成功"""
    print_section("检查数据库索引")
    try:
        with connection.cursor() as cursor:
            # 检查MySQL索引
            cursor.execute("""
                SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME IN ('knowledge_project_note', 'knowledge_project_notecomment',
                                   'knowledge_project_notehistory', 'knowledge_project_profilelike')
                AND INDEX_NAME LIKE '%_idx'
                ORDER BY TABLE_NAME, INDEX_NAME
            """)
            indexes = cursor.fetchall()

            if indexes:
                print("[OK] 找到以下性能索引：")
                for table, index, column in indexes:
                    print(f"   - {table}.{index} ({column})")
            else:
                print("[WARNING] 未找到性能索引，可能迁移尚未应用")

            return len(indexes) > 0
    except Exception as e:
        print(f"[ERROR] 检查索引失败: {e}")
        return False

def collect_static():
    """收集静态文件"""
    print_section("收集静态文件")
    try:
        print("正在收集静态文件...")
        call_command('collectstatic', '--noinput', '--clear')
        print("[OK] 静态文件收集完成")
        return True
    except Exception as e:
        print(f"[ERROR] 收集静态文件失败: {e}")
        return False

def clear_cache():
    """清除缓存"""
    print_section("清除缓存")
    try:
        cache.clear()
        print("[OK] 缓存已清除")
        return True
    except Exception as e:
        print(f"[ERROR] 清除缓存失败: {e}")
        return False

def performance_test():
    """简单的性能测试"""
    print_section("性能测试")
    try:
        from notes.models import Note
        from django.db.models import Count
        import time

        # 测试1：查询公开笔记（优化后）
        start = time.time()
        notes = list(
            Note.objects
            .filter(is_public=True)
            .select_related('author', 'author__profile')
            .prefetch_related('tags')
            .annotate(comments_count_cached=Count('comments'))
            .order_by('-updated_at')[:10]
        )
        elapsed = time.time() - start
        print(f"[OK] 查询10条公开笔记耗时: {elapsed*1000:.2f}ms")

        # 测试2：缓存读写
        start = time.time()
        cache.set('perf_test', 'test_data', 300)
        cache.get('perf_test')
        elapsed = time.time() - start
        print(f"[OK] Redis缓存读写耗时: {elapsed*1000:.2f}ms")

        return True
    except Exception as e:
        print(f"[ERROR] 性能测试失败: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("   网站性能优化执行脚本")
    print("="*60)

    results = {
        'Redis连接': check_redis_connection(),
        '数据库连接': check_database_connection(),
        '应用迁移': apply_migrations(),
        '检查索引': check_indexes(),
        '收集静态文件': collect_static(),
        '清除缓存': clear_cache(),
        '性能测试': performance_test(),
    }

    print_section("执行结果汇总")
    success_count = sum(results.values())
    total_count = len(results)

    for task, success in results.items():
        status = "[OK]" if success else "[FAIL]"
        print(f"{status} {task}")

    print(f"\n总计: {success_count}/{total_count} 项任务成功")

    if success_count == total_count:
        print("\n[SUCCESS] 所有优化任务执行成功！")
        print("\n[TODO] 后续步骤：")
        print("1. 修改 .env 文件，设置 DEBUG=False")
        print("2. 配置Nginx（参考 NGINX_OPTIMIZATION.md）")
        print("3. 重启Django服务")
        print("4. 监控网站性能指标")
    else:
        print("\n[WARNING] 部分任务失败，请检查错误信息")
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
