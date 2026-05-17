"""upload 模块测试

覆盖:
- image_upload_view (TinyMCE): 鉴权 / 缺字段 / 上传成功 / 去重
- ckeditor_image_upload_view: 鉴权 / 缺字段 / 上传成功 / 去重
- protected_media_view: 上传者可访问 / 公开笔记引用可匿名访问 /
  无权访问 403 / 不存在 404 / 路径穿越拒绝
"""

from __future__ import annotations

import os
import tempfile

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from knowledge_project.models import Asset, Note

from ._helpers import login, make_user, parse


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class _UploadTestBase(TestCase):
    def setUp(self):
        cache.clear()


PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
    b'\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
)


# =========================================================================
# image_upload_view (TinyMCE)
# =========================================================================
class ImageUploadViewTests(_UploadTestBase):
    def test_requires_login(self):
        response = self.client.post(reverse('image_upload_view'))
        self.assertIn(response.status_code, (302, 401, 403))

    def test_missing_file_returns_400(self):
        user = make_user('iu01')
        login(self.client, user)
        response = self.client.post(reverse('image_upload_view'))
        self.assertEqual(response.status_code, 400)

    def test_upload_success_returns_location(self):
        user = make_user('iu02')
        login(self.client, user)
        upload = SimpleUploadedFile('test.png', PNG_BYTES, content_type='image/png')
        response = self.client.post(reverse('image_upload_view'), {'file': upload})
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertIn('location', body)
        self.assertTrue(body['location'].startswith('/protected_uploads/'))
        # Asset 已落库
        self.assertTrue(Asset.objects.filter(uploader=user).exists())

    def test_upload_dedupe_by_hash(self):
        user = make_user('iu03')
        login(self.client, user)
        upload1 = SimpleUploadedFile('a.png', PNG_BYTES, content_type='image/png')
        first = parse(self.client.post(reverse('image_upload_view'), {'file': upload1}))
        upload2 = SimpleUploadedFile('b.png', PNG_BYTES, content_type='image/png')
        second = parse(self.client.post(reverse('image_upload_view'), {'file': upload2}))
        # 同一哈希返回的 URL 应该相同
        self.assertEqual(first['location'], second['location'])
        # 数据库只有一条 Asset
        self.assertEqual(Asset.objects.filter(uploader=user).count(), 1)


# =========================================================================
# ckeditor_image_upload_view
# =========================================================================
class CKEditorUploadViewTests(_UploadTestBase):
    def test_requires_login(self):
        response = self.client.post(reverse('ckeditor_image_upload_view'))
        self.assertIn(response.status_code, (302, 401, 403))

    def test_missing_upload_field_returns_400(self):
        user = make_user('ck01')
        login(self.client, user)
        response = self.client.post(reverse('ckeditor_image_upload_view'))
        self.assertEqual(response.status_code, 400)

    def test_upload_success_returns_url(self):
        user = make_user('ck02')
        login(self.client, user)
        upload = SimpleUploadedFile('ck.png', PNG_BYTES, content_type='image/png')
        response = self.client.post(reverse('ckeditor_image_upload_view'), {'upload': upload})
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertIn('url', body)
        self.assertTrue(body['url'].startswith('/protected_uploads/'))

    def test_upload_dedupe(self):
        user = make_user('ck03')
        login(self.client, user)
        first = parse(self.client.post(
            reverse('ckeditor_image_upload_view'),
            {'upload': SimpleUploadedFile('a.png', PNG_BYTES, content_type='image/png')},
        ))
        second = parse(self.client.post(
            reverse('ckeditor_image_upload_view'),
            {'upload': SimpleUploadedFile('b.png', PNG_BYTES, content_type='image/png')},
        ))
        self.assertEqual(first['url'], second['url'])
        self.assertEqual(Asset.objects.filter(uploader=user).count(), 1)


# =========================================================================
# protected_media_view
# =========================================================================
class ProtectedMediaViewTests(_UploadTestBase):
    def _upload_as(self, user) -> str:
        """返回 file_path(相对 MEDIA_ROOT)"""
        login(self.client, user)
        upload = SimpleUploadedFile('share.png', PNG_BYTES, content_type='image/png')
        body = parse(self.client.post(reverse('image_upload_view'), {'file': upload}))
        # body['location'] = '/protected_uploads/user_X/share.png'
        file_path = body['location'][len('/protected_uploads/'):]
        # 切换回未登录
        self.client.logout()
        return file_path

    def test_uploader_can_access(self):
        user = make_user('pm01')
        file_path = self._upload_as(user)
        login(self.client, user)
        response = self.client.get(reverse('protected_media_view', args=[file_path]))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_cannot_access_private(self):
        user = make_user('pm02')
        file_path = self._upload_as(user)
        # 不登录 + 资源没被任何公开笔记引用 -> 403
        response = self.client.get(reverse('protected_media_view', args=[file_path]))
        self.assertEqual(response.status_code, 403)

    def test_other_user_cannot_access_private(self):
        owner = make_user('pm03_o')
        file_path = self._upload_as(owner)
        intruder = make_user('pm03_i')
        login(self.client, intruder)
        response = self.client.get(reverse('protected_media_view', args=[file_path]))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_can_access_if_referenced_by_public_note(self):
        author = make_user('pm04')
        file_path = self._upload_as(author)
        # 用公开笔记引用 protected_url
        protected_url = f'/protected_uploads/{file_path}'
        Note.objects.create(
            author=author, title='公开笔记', is_public=True, is_trashed=False,
            content=f'<img src="{protected_url}">',
        )
        # 不登录访问
        response = self.client.get(reverse('protected_media_view', args=[file_path]))
        self.assertEqual(response.status_code, 200)

    def test_trashed_public_note_does_not_grant_access(self):
        author = make_user('pm05')
        file_path = self._upload_as(author)
        protected_url = f'/protected_uploads/{file_path}'
        # 注意 is_trashed=True 不应授权
        Note.objects.create(
            author=author, title='已删除笔记', is_public=True, is_trashed=True,
            content=f'<img src="{protected_url}">',
        )
        response = self.client.get(reverse('protected_media_view', args=[file_path]))
        self.assertEqual(response.status_code, 403)

    def test_private_note_does_not_grant_anonymous_access(self):
        author = make_user('pm06')
        file_path = self._upload_as(author)
        protected_url = f'/protected_uploads/{file_path}'
        Note.objects.create(
            author=author, title='私密笔记', is_public=False, is_trashed=False,
            content=f'<img src="{protected_url}">',
        )
        response = self.client.get(reverse('protected_media_view', args=[file_path]))
        self.assertEqual(response.status_code, 403)

    def test_nonexistent_file_returns_404(self):
        user = make_user('pm07')
        login(self.client, user)
        response = self.client.get(reverse('protected_media_view', args=['user_999/ghost.png']))
        self.assertEqual(response.status_code, 404)

    def test_path_traversal_rejected(self):
        author = make_user('pm08')
        file_path = self._upload_as(author)
        # 上传一个真实资源,然后用上传者身份请求 ../etc/passwd 之类的
        # 由于上传的 file 字段是 'user_X/share.png',Asset.objects.get(file='../...') 找不到 -> 404
        login(self.client, author)
        response = self.client.get(reverse('protected_media_view', args=['../etc/passwd']))
        self.assertEqual(response.status_code, 404)
