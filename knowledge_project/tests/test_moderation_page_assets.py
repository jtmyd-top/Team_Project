"""举报处置页面静态资源回归测试

element-plus 的组件样式在构建时被拆分为独立 chunk CSS（el-select.css 等），
页面必须链接 manifest 中入口的全部 css，否则组件（下拉框图标、输入框）裸奔。
"""

from __future__ import annotations

from django.test import TestCase, override_settings
from django.urls import reverse

from knowledge_project.templatetags.static_files import vite_entry_css

from ._helpers import login, make_user


@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    SECURE_SSL_REDIRECT=False,
)
class ModerationPageAssetsTests(TestCase):
    def _superuser(self):
        user = make_user('mod01')
        user.is_superuser = True
        user.save(update_fields=['is_superuser'])
        return user

    def test_page_links_all_entry_css(self):
        user = self._superuser()
        login(self.client, user)
        response = self.client.get(reverse('moderation_reports'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'assets/moderation.css')
        # element-plus 拆分出的组件样式必须一并链接
        self.assertContains(response, 'assets/el-select.css')
        self.assertContains(response, 'assets/el-input.css')
        self.assertContains(response, 'assets/el-overlay.css')

    def test_non_superuser_redirected(self):
        user = make_user('mod02')
        login(self.client, user)
        response = self.client.get(reverse('moderation_reports'))
        self.assertEqual(response.status_code, 302)

    def test_tag_falls_back_without_manifest_entry(self):
        html = vite_entry_css('nonexistent-entry')
        self.assertIn('assets/nonexistent-entry.css', html)


@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    SECURE_SSL_REDIRECT=False,
)
class KnowledgePageAssetsTests(TestCase):
    def test_page_links_all_entry_css(self):
        user = make_user('mod03')
        login(self.client, user)
        response = self.client.get(reverse('knowledge_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'assets/knowledge.css')
        # 分享管理的 el-switch/el-dialog 等组件样式在拆分的 chunk CSS 里
        self.assertContains(response, 'assets/el-select.css')
        self.assertContains(response, 'assets/el-overlay.css')
