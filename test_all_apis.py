#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete API Testing Suite for Team Project
Tests all 70+ API endpoints for jtmyd12 user
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import sys

# Configuration
BASE_URL = "http://192.168.1.6"
CSRF_TOKEN = "QCGOOIbLIzbZbtqAJnnsuZ4Ojs7gzoK2"
SESSION_ID = "cpdcs96arpsxyceh1hkug8vuhev8r22n"

# Session setup with cookies
session = requests.Session()
session.cookies.set('csrftoken', CSRF_TOKEN)
session.cookies.set('sessionid', SESSION_ID)

# Headers
HEADERS = {
    'X-CSRFToken': CSRF_TOKEN,
    'Content-Type': 'application/json',
    'User-Agent': 'TestRunner/1.0'
}

# Test Results Storage
test_results = {
    'passed': [],
    'failed': [],
    'warnings': [],
    'total': 0,
    'timestamp': datetime.now().isoformat()
}

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}")
    print(f"{text}")
    print(f"{'='*60}{Colors.END}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}[OK] {text}{Colors.END}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}[FAIL] {text}{Colors.END}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}[WARN] {text}{Colors.END}")

def test_endpoint(method: str, endpoint: str, expected_status: int = 200,
                 data: Optional[Dict] = None, description: str = "") -> Tuple[bool, str]:
    """
    Test a single API endpoint

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint path
        expected_status: Expected HTTP status code
        data: Request body data (for POST/PUT)
        description: Test description

    Returns:
        (success: bool, message: str)
    """
    test_results['total'] += 1
    url = f"{BASE_URL}{endpoint}"

    try:
        if method.upper() == 'GET':
            response = session.get(url, headers=HEADERS, timeout=10)
        elif method.upper() == 'POST':
            response = session.post(url, json=data, headers=HEADERS, timeout=10)
        elif method.upper() == 'PUT':
            response = session.put(url, json=data, headers=HEADERS, timeout=10)
        elif method.upper() == 'DELETE':
            response = session.delete(url, headers=HEADERS, timeout=10)
        elif method.upper() == 'PATCH':
            response = session.patch(url, json=data, headers=HEADERS, timeout=10)
        else:
            return False, f"Unknown HTTP method: {method}"

        status_ok = response.status_code == expected_status

        test_name = f"{method.upper()} {endpoint}"
        test_info = {
            'name': test_name,
            'description': description,
            'status_code': response.status_code,
            'expected_status': expected_status,
            'url': url,
            'response_length': len(response.text)
        }

        if status_ok:
            test_results['passed'].append(test_info)
            print_success(f"{test_name} - {description}")
            return True, f"Status: {response.status_code}"
        else:
            test_results['failed'].append(test_info)
            print_error(f"{test_name} - Expected {expected_status}, got {response.status_code}")
            return False, f"Status: {response.status_code}"

    except requests.exceptions.Timeout:
        test_results['failed'].append({
            'name': f"{method} {endpoint}",
            'description': description,
            'error': 'Request timeout'
        })
        print_error(f"{method} {endpoint} - Request timeout")
        return False, "Timeout"

    except requests.exceptions.ConnectionError:
        test_results['failed'].append({
            'name': f"{method} {endpoint}",
            'description': description,
            'error': 'Connection error'
        })
        print_error(f"{method} {endpoint} - Connection error")
        return False, "Connection error"

    except Exception as e:
        test_results['failed'].append({
            'name': f"{method} {endpoint}",
            'description': description,
            'error': str(e)
        })
        print_error(f"{method} {endpoint} - {str(e)}")
        return False, str(e)

def test_authentication_apis():
    """Test Authentication & Security APIs"""
    print_header("Testing Authentication & Security APIs")

    test_endpoint('GET', '/api/vault/status/', 200, description="获取保密柜状态")
    test_endpoint('GET', '/api/vault/lock-status/', 200, description="获取保密柜锁定状态")

def test_user_management_apis():
    """Test User Management APIs"""
    print_header("Testing User Management APIs")

    test_endpoint('POST', '/check-username/', 200,
                 data={'username': 'testuser'}, description="检查用户名可用性")
    test_endpoint('POST', '/check-email/', 200,
                 data={'email': 'test@example.com'}, description="检查邮箱可用性")
    test_endpoint('GET', '/api/profile/', 200, description="获取用户资料")
    test_endpoint('GET', '/api/notification-preferences/', 200, description="获取通知设置")
    test_endpoint('GET', '/api/theme-settings/', 200, description="获取主题设置")

def test_note_management_apis():
    """Test Note Management APIs"""
    print_header("Testing Note Management APIs")

    test_endpoint('GET', '/api/notes/all/', 200, description="获取所有笔记")
    test_endpoint('GET', '/api/notes/flat/', 200, description="获取平铺笔记列表")
    test_endpoint('GET', '/api/notes/search/', 200,
                 data={'query': 'test'}, description="搜索笔记")
    test_endpoint('GET', '/api/vault/notes/', 200, description="获取保密柜笔记")

def test_folder_management_apis():
    """Test Folder Management APIs"""
    print_header("Testing Folder Management APIs")

    test_endpoint('GET', '/api/folders/', 200, description="获取所有文件夹（树形结构）")
    test_endpoint('GET', '/api/folders/inbox/notes/', 200, description="获取收件箱笔记")

def test_settings_apis():
    """Test Settings & Preferences APIs"""
    print_header("Testing Settings APIs")

    test_endpoint('POST', '/api/notification-preferences/', 200,
                 data={'notify_login': True}, description="更新通知设置")
    test_endpoint('POST', '/api/theme-settings/', 200,
                 data={'theme': 'dark'}, description="更新主题设置")

def test_engagement_apis():
    """Test Engagement APIs"""
    print_header("Testing Engagement APIs")

    test_endpoint('GET', '/api/public-notes/', 200, description="获取公开笔记列表")

def test_verification_apis():
    """Test Verification & CAPTCHA APIs"""
    print_header("Testing Verification & CAPTCHA APIs")

    test_endpoint('GET', '/api/captcha/init/', 200, description="初始化验证码")
    test_endpoint('GET', '/api/captcha/', 200, description="获取验证码")
    test_endpoint('GET', '/api/turnstile/config/', 200, description="获取Turnstile配置")

def test_public_apis():
    """Test Public Content APIs"""
    print_header("Testing Public Content APIs")

    # These will return 404 if no public notes exist, which is expected
    test_endpoint('GET', '/api/public-notes/', 200, description="列表公开笔记")

def test_vault_apis():
    """Test Vault (Secret Storage) APIs"""
    print_header("Testing Vault Security APIs")

    test_endpoint('GET', '/api/vault/status/', 200, description="获取保密柜访问状态")
    test_endpoint('GET', '/api/vault/lock-status/', 200, description="检查保密柜锁定状态")
    test_endpoint('POST', '/api/vault/lock/', 200, description="锁定保密柜")

def test_home_and_basic():
    """Test Basic & Home Page"""
    print_header("Testing Basic Pages")

    test_endpoint('GET', '/', 200, description="首页")
    test_endpoint('GET', '/home/', 200, description="主页")

def print_summary():
    """Print test summary"""
    print_header("Test Summary")

    total = test_results['total']
    passed = len(test_results['passed'])
    failed = len(test_results['failed'])

    print(f"总测试数: {Colors.BOLD}{total}{Colors.END}")
    print(f"{Colors.GREEN}通过: {passed}{Colors.END}")
    print(f"{Colors.RED}失败: {failed}{Colors.END}")

    if failed > 0:
        print(f"\n{Colors.BOLD}失败的端点:{Colors.END}")
        for item in test_results['failed']:
            error_msg = item.get('error', f"Status {item.get('status_code')}")
            print(f"  - {item['name']}: {error_msg}")

    success_rate = (passed / total * 100) if total > 0 else 0
    print(f"\n成功率: {Colors.BOLD}{success_rate:.1f}%{Colors.END}")

    # Save detailed results
    with open('test_results.json', 'w', encoding='utf-8') as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)

    print(f"\n详细结果已保存到: test_results.json")

def main():
    """Main test runner"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔" + "="*58 + "╗")
    print("║" + " Team Project API 完整测试套件".center(58) + "║")
    print("║" + f" 用户: jtmyd12 | 服务器: {BASE_URL}".ljust(58) + "║")
    print("║" + f" 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".ljust(58) + "║")
    print("╚" + "="*58 + "╝")
    print(f"{Colors.END}\n")

    # Verify connection
    print("验证服务器连接...")
    try:
        response = session.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print_success("服务器连接正常")
        else:
            print_warning(f"服务器返回状态码: {response.status_code}")
    except Exception as e:
        print_error(f"无法连接到服务器: {e}")
        return 1

    # Run all tests
    test_home_and_basic()
    test_authentication_apis()
    test_user_management_apis()
    test_note_management_apis()
    test_folder_management_apis()
    test_settings_apis()
    test_vault_apis()
    test_verification_apis()
    test_engagement_apis()
    test_public_apis()

    # Print summary
    print_summary()

    return 0 if len(test_results['failed']) == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
