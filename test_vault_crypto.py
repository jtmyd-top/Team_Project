#!/usr/bin/env python
"""
测试保险柜加密工具
"""
import os
import sys

# 设置环境变量
os.environ['VAULT_KEK'] = 'TkGduAY/6e1skN+ZvWY7RoLzAsOE6W9E2LPxj7hB/no='

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入测试
from knowledge_project.utils.vault_crypto import test_encryption

if __name__ == '__main__':
    success = test_encryption()
    sys.exit(0 if success else 1)
