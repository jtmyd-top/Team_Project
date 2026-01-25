#!/usr/bin/env python
"""
测试限流功能的简单脚本
用于验证修复后的并发安全性
"""

import os
import sys
import django
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import json
import time

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Team_Project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from knowledge_project.views import SendEmailCodeView
from knowledge_project.utils.request_utils import get_client_ip, check_rate_limit_atomic


def test_ip_extraction():
    """测试IP获取功能"""
    print("=== 测试IP获取功能 ===")

    factory = RequestFactory()

    # 测试直接连接
    request = factory.post('/')
    print(f"直接连接IP: {get_client_ip(request)}")

    # 测试代理连接
    request = factory.post('/', HTTP_X_FORWARDED_FOR='203.0.113.1, 10.0.0.1')
    print(f"代理连接IP: {get_client_ip(request)}")

    # 测试真实IP头部
    request = factory.post('/', HTTP_X_REAL_IP='203.0.113.2')
    print(f"真实IP头部: {get_client_ip(request)}")


def test_rate_limit_atomic():
    """测试原子限流功能"""
    print("\n=== 测试原子限流功能 ===")

    # 清理之前的测试数据
    from django.core.cache import cache
    cache.delete('test_rate_limit_key')

    # 测试正常限流
    print("测试基本限流功能...")
    for i in range(5):
        allowed, attempts = check_rate_limit_atomic('test_rate_limit_key', 3, 60)
        print(f"尝试 {i+1}: 允许={allowed}, 次数={attempts}")
        time.sleep(0.1)

    # 清理
    cache.delete('test_rate_limit_key')


def test_concurrent_requests():
    """测试并发请求"""
    print("\n=== 测试并发请求 ===")

    # 注意：这个测试需要运行的服务器环境
    print("并发测试需要在服务器运行时进行")
    print("建议使用ab、wrk或JMeter等工具进行压力测试")

    # 示例ab命令：
    print("ab -n 100 -c 10 http://localhost:8000/api/send-email-code/")


def main():
    """主测试函数"""
    print("开始测试验证码限流修复...")

    test_ip_extraction()
    test_rate_limit_atomic()
    test_concurrent_requests()

    print("\n=== 测试完成 ===")
    print("建议的后续测试：")
    print("1. 启动开发服务器")
    print("2. 使用浏览器测试正常流程")
    print("3. 使用ab/wrk工具进行并发测试")
    print("4. 检查Redis中的缓存键是否正确设置和递增")


if __name__ == '__main__':
    main()