#!/usr/bin/env python
"""
测试并发限流的原子性
这个脚本将模拟多个并发请求来验证限流是否真正工作
"""

import os
import sys
import django
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Team_Project.settings')
django.setup()

from knowledge_project.utils.redis_rate_limiter import check_redis_rate_limit, reset_rate_limit
from knowledge_project.utils.request_utils import check_rate_limit_atomic


def test_single_rate_limit():
    """测试单个请求的限流"""
    print("=== 单个请求限流测试 ===")

    key = "test_single_limit"
    reset_rate_limit(key)

    for i in range(5):
        allowed, count = check_rate_limit_atomic(key, 3, 60)
        print(f"请求 {i+1}: 允许={allowed}, 计数={count}")
        time.sleep(0.1)


def test_concurrent_requests():
    """测试并发请求的限流"""
    print("\n=== 并发请求限流测试 ===")

    key = "test_concurrent_limit"
    reset_rate_limit(key)

    results = []

    def make_request(request_id):
        """模拟单个请求"""
        allowed, count = check_rate_limit_atomic(key, 3, 60)
        return request_id, allowed, count

    # 启动10个并发请求
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request, i) for i in range(10)]

        for future in as_completed(futures):
            request_id, allowed, count = future.result()
            results.append((request_id, allowed, count))
            print(f"请求 {request_id}: 允许={allowed}, 计数={count}")

    # 统计结果
    allowed_count = sum(1 for _, allowed, _ in results if allowed)
    max_count = max(count for _, _, count in results) if results else 0

    print(f"\n统计结果:")
    print(f"总请求数: {len(results)}")
    print(f"允许的请求数: {allowed_count}")
    print(f"最大计数: {max_count}")

    # 验证限流是否有效
    if allowed_count <= 3 and max_count <= 3:
        print("✅ 限流工作正常")
    else:
        print("❌ 限流失效！允许的请求数超过限制")


def test_different_keys():
    """测试不同键的独立性"""
    print("\n=== 不同键独立性测试 ===")

    keys = ["test_key_1", "test_key_2", "test_key_3"]

    for key in keys:
        reset_rate_limit(key)
        allowed, count = check_rate_limit_atomic(key, 2, 60)
        print(f"键 {key}: 允许={allowed}, 计数={count}")

    print("不同键应该互不影响")


def stress_test():
    """压力测试 - 大量并发请求"""
    print("\n=== 压力测试 ===")

    key = "test_stress_limit"
    reset_rate_limit(key)

    results = []

    def make_request(request_id):
        """模拟单个请求"""
        try:
            allowed, count = check_rate_limit_atomic(key, 5, 60)
            return request_id, allowed, count, None
        except Exception as e:
            return request_id, False, 0, str(e)

    # 启动50个并发请求
    print("启动50个并发请求...")
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(make_request, i) for i in range(50)]

        for future in as_completed(futures):
            request_id, allowed, count, error = future.result()
            results.append((request_id, allowed, count, error))
            if error:
                print(f"请求 {request_id}: 错误={error}")

    # 统计结果
    successful_requests = [r for r in results if r[3] is None]
    allowed_count = sum(1 for _, allowed, _, _ in successful_requests if allowed)
    max_count = max(count for _, _, count, _ in successful_requests) if successful_requests else 0
    error_count = len(results) - len(successful_requests)

    print(f"\n压力测试统计:")
    print(f"总请求数: {len(results)}")
    print(f"成功请求数: {len(successful_requests)}")
    print(f"错误请求数: {error_count}")
    print(f"允许的请求数: {allowed_count}")
    print(f"最大计数: {max_count}")

    if error_count == 0 and allowed_count <= 5 and max_count <= 5:
        print("✅ 压力测试通过")
    else:
        print("❌ 压力测试失败")


def main():
    """主测试函数"""
    print("开始并发限流测试...")

    try:
        test_single_rate_limit()
        test_concurrent_requests()
        test_different_keys()
        stress_test()

        print("\n=== 测试完成 ===")
        print("如果看到限流失效，请检查:")
        print("1. Redis服务是否正常运行")
        print("2. Django cache配置是否正确")
        print("3. 网络连接是否稳定")

    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()