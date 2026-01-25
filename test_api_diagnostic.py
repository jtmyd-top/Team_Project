#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 诊断工具 - 检查 Session 有效性和错误原因
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://192.168.1.6"
CSRF_TOKEN = "QCGOOIbLIzbZbtqAJnnsuZ4Ojs7gzoK2"
SESSION_ID = "cpdcs96arpsxyceh1hkug8vuhev8r22n"

# Session setup
session = requests.Session()
session.cookies.set('csrftoken', CSRF_TOKEN)
session.cookies.set('sessionid', SESSION_ID)

HEADERS = {
    'X-CSRFToken': CSRF_TOKEN,
    'Content-Type': 'application/json',
    'User-Agent': 'DiagnosticRunner/1.0'
}

def test_endpoint(method, endpoint, data=None):
    """Test endpoint and return full response"""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n{'='*60}")
    print(f"Testing: {method.upper()} {endpoint}")
    print(f"URL: {url}")
    print(f"{'='*60}")

    try:
        if method.upper() == 'GET':
            response = session.get(url, headers=HEADERS, timeout=10)
        elif method.upper() == 'POST':
            response = session.post(url, json=data, headers=HEADERS, timeout=10)
        else:
            return None

        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"\nResponse Content:")

        # Try to parse as JSON
        try:
            resp_json = response.json()
            print(json.dumps(resp_json, ensure_ascii=False, indent=2))
        except:
            print(f"Raw Content (first 500 chars):\n{response.text[:500]}")

        return response

    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    print("\n" + "="*60)
    print("Team Project API Diagnostic Tool")
    print(f"Server: {BASE_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*60)

    # Check basic connectivity
    print("\n[1] Checking Server Connectivity...")
    try:
        response = session.get(f"{BASE_URL}/", timeout=5)
        print(f"Server is reachable. Status: {response.status_code}")
    except Exception as e:
        print(f"Cannot reach server: {e}")
        return

    # Test different endpoints with detailed responses
    print("\n[2] Testing Key Endpoints with Response Details...")

    test_cases = [
        ('GET', '/api/vault/status/', None, "Should work - Vault status"),
        ('GET', '/api/notes/all/', None, "Likely 403 - Notes listing"),
        ('GET', '/api/profile/', None, "Likely 403 - User profile"),
        ('POST', '/check-username/', {'username': 'test'}, "Likely 403 - Username check"),
        ('POST', '/api/notification-preferences/', {'notify_login': True}, "Likely 403 - Settings update"),
    ]

    for method, endpoint, data, description in test_cases:
        print(f"\n[{description}]")
        test_endpoint(method, endpoint, data)

    # Check session info
    print("\n\n[3] Session Cookie Information:")
    print(f"Cookies in session:")
    for cookie in session.cookies:
        print(f"  - {cookie.name}: {cookie.value[:20]}..." if len(cookie.value) > 20 else f"  - {cookie.name}: {cookie.value}")

    print("\nTest completed. Review responses above for error details.")

if __name__ == '__main__':
    main()
