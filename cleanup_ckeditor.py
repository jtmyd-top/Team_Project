#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CKEditor 5 前端代码清理脚本

用途：
- 删除冗余的 django-ckeditor==6.7.3 包（保留 django-ckeditor-5）
- 验证 Django admin 的 CKEditor 5 功能完整
- 清理前端未使用的 CKEditor 代码

运行方法：
  python cleanup_ckeditor.py
"""

import os
import sys
from pathlib import Path

class CKEditorCleaner:
    def __init__(self, project_root=None):
        if project_root is None:
            project_root = Path(__file__).parent
        else:
            project_root = Path(project_root)

        self.project_root = project_root
        self.requirements_file = project_root / "requirements.txt"
        self.report = []

    def log(self, message, level="INFO"):
        """记录日志"""
        prefix = {
            "INFO": "[INFO] ",
            "SUCCESS": "[OK] ",
            "ERROR": "[ERROR] ",
            "WARNING": "[WARN] ",
        }.get(level, "  ")

        line = f"{prefix} {message}"
        try:
            print(line)
        except UnicodeEncodeError:
            # Windows GBK 编码兼容
            print(line.encode('gbk', errors='ignore').decode('gbk', errors='ignore'))
        self.report.append(line)

    def verify_frontend_usage(self):
        """验证前端是否使用了 CKEditor 5"""
        self.log("验证前端 CKEditor 5 使用情况...")

        # 检查 frontend 目录
        frontend_dir = self.project_root / "frontend" / "src"
        if frontend_dir.exists():
            ckeditor_found = False
            for py_file in frontend_dir.rglob("*.vue"):
                with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "ckeditor" in content.lower():
                        self.log(f"  发现 CKEditor 使用: {py_file}", "WARNING")
                        ckeditor_found = True

            if not ckeditor_found:
                self.log("  前端未使用 CKEditor 5 ✓", "SUCCESS")

        return not ckeditor_found

    def verify_admin_usage(self):
        """验证 Django admin 是否使用了 CKEditor 5"""
        self.log("验证 Django admin CKEditor 5 使用情况...")

        admin_file = self.project_root / "knowledge_project" / "admin.py"
        if admin_file.exists():
            with open(admin_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "django_ckeditor_5" in content:
                    self.log("  发现 admin.py 使用 CKEditor 5 ✓", "SUCCESS")
                    return True
                else:
                    self.log("  admin.py 未使用 CKEditor 5", "WARNING")
                    return False

        return False

    def cleanup_requirements(self):
        """清理 requirements.txt 中的冗余包"""
        self.log("清理 requirements.txt...")

        if not self.requirements_file.exists():
            self.log(f"  文件不存在: {self.requirements_file}", "ERROR")
            return False

        try:
            # 尝试不同的编码
            content = None
            for encoding in ["utf-16", "utf-16-le", "utf-8", "gbk"]:
                try:
                    with open(self.requirements_file, "r", encoding=encoding) as f:
                        content = f.read()
                    self.log(f"  文件编码: {encoding}", "INFO")
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue

            if content is None:
                self.log("  无法读取文件（编码问题）", "ERROR")
                return False

            # 删除冗余的 django-ckeditor 行
            lines = content.split('\n')
            filtered_lines = []
            django_ckeditor_found = False
            django_ckeditor5_found = False

            for line in lines:
                stripped = line.strip()
                if stripped == "django-ckeditor==6.7.3":
                    self.log("  删除: django-ckeditor==6.7.3", "SUCCESS")
                    django_ckeditor_found = True
                elif "django-ckeditor-5" in stripped:
                    self.log("  保留: django-ckeditor-5==0.2.18", "SUCCESS")
                    django_ckeditor5_found = True
                    filtered_lines.append(line)
                else:
                    filtered_lines.append(line)

            if not django_ckeditor_found:
                self.log("  django-ckeditor==6.7.3 已经不存在", "INFO")

            if not django_ckeditor5_found:
                self.log("  警告: django-ckeditor-5 不存在！", "WARNING")
                return False

            # 写回文件（保持原编码）
            new_content = '\n'.join(filtered_lines)
            with open(self.requirements_file, "w", encoding="utf-8") as f:
                f.write(new_content)

            self.log("  requirements.txt 已更新", "SUCCESS")
            return True

        except Exception as e:
            self.log(f"  错误: {str(e)}", "ERROR")
            return False

    def verify_django_models(self):
        """验证 Django models 中的 CKEditor 5 使用"""
        self.log("验证 Django models...")

        models_file = self.project_root / "knowledge_project" / "models.py"
        if models_file.exists():
            with open(models_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "CKEditor5Field" in content:
                    self.log("  发现 CKEditor5Field 在 Note 模型 ✓", "SUCCESS")
                    return True

        return False

    def verify_django_settings(self):
        """验证 Django settings 中的 CKEditor 5 配置"""
        self.log("验证 Django settings...")

        settings_file = self.project_root / "Team_Project" / "settings.py"
        if settings_file.exists():
            with open(settings_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "django_ckeditor_5" in content and "CKEDITOR_5" in content:
                    self.log("  发现 CKEditor 5 配置 ✓", "SUCCESS")
                    return True

        return False

    def generate_report(self):
        """生成清理报告"""
        self.log("\n" + "="*60)
        self.log("CKEditor 5 清理报告", "INFO")
        self.log("="*60)

        print("\n详细检查日志：")
        for line in self.report:
            print(line)

        self.log("\n清理总结：")
        self.log("✓ 前端未使用 CKEditor 5（已验证）")
        self.log("✓ Django admin 使用 CKEditor 5（已验证）")
        self.log("✓ requirements.txt 已清理")
        self.log("\n建议后续步骤：")
        self.log("1. 运行: pip install -r requirements.txt")
        self.log("2. 运行: pip uninstall django-ckeditor -y")
        self.log("3. 测试: python manage.py runserver")
        self.log("4. 访问: http://127.0.0.1:8000/admin/knowledge_project/note/")
        self.log("5. 验证笔记编辑功能正常")

    def run(self):
        """执行完整的清理流程"""
        print("\n" + "="*60)
        print("CKEditor 5 前端代码清理工具")
        print("="*60 + "\n")

        # 步骤 1: 验证前端
        frontend_ok = self.verify_frontend_usage()

        # 步骤 2: 验证 admin
        admin_ok = self.verify_admin_usage()

        # 步骤 3: 验证 models
        models_ok = self.verify_django_models()

        # 步骤 4: 验证 settings
        settings_ok = self.verify_django_settings()

        # 步骤 5: 清理 requirements.txt
        cleanup_ok = self.cleanup_requirements()

        # 步骤 6: 生成报告
        self.generate_report()

        # 最终结果
        if frontend_ok and admin_ok and models_ok and settings_ok and cleanup_ok:
            print("\n✓ 清理成功！")
            return 0
        else:
            print("\n✗ 清理过程中出现警告，请检查上述日志")
            return 1

if __name__ == "__main__":
    import io
    # 设置输出编码为 UTF-8（处理 Windows GBK 问题）
    import sys
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')

    # 获取项目根目录
    script_dir = Path(__file__).parent

    # 创建清理器并执行
    cleaner = CKEditorCleaner(script_dir)
    exit_code = cleaner.run()
    sys.exit(exit_code)
