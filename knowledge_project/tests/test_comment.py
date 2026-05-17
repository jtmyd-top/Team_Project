"""comment 子模块测试

覆盖:
- note_comments_api: 公开笔记可读 / 私有 404
- note_comment_create_api: 创建评论 / 创建回复 / 私有 404 / 空内容 / 超 2000 字 / 需登录
- note_comment_delete_api: 作者可删 / 他人 403 / staff 可删任意
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from knowledge_project.models import Note, NoteComment

from ._helpers import login, make_user, parse, post_json


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class _CommentTestBase(TestCase):
    def setUp(self):
        cache.clear()


# =========================================================================
# note_comments_api (GET)
# =========================================================================
class CommentListApiTests(_CommentTestBase):
    def test_list_public_note_comments(self):
        author = make_user('cl01_a')
        commenter = make_user('cl01_c')
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        NoteComment.objects.create(note=note, author=commenter, content='hi')
        response = self.client.get(reverse('note_comments_api', args=[note.id]))
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertEqual(len(body['comments']), 1)
        self.assertEqual(body['comments'][0]['content'], 'hi')
        self.assertEqual(body['total'], 1)

    def test_list_private_note_returns_404(self):
        author = make_user('cl02_a')
        note = Note.objects.create(author=author, title='priv', content='', is_public=False)
        response = self.client.get(reverse('note_comments_api', args=[note.id]))
        self.assertEqual(response.status_code, 404)

    def test_list_includes_replies(self):
        author = make_user('cl03_a')
        u1 = make_user('cl03_u1')
        u2 = make_user('cl03_u2')
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        top = NoteComment.objects.create(note=note, author=u1, content='top')
        NoteComment.objects.create(note=note, author=u2, content='reply', parent=top)
        body = parse(self.client.get(reverse('note_comments_api', args=[note.id])))
        # 顶级评论 1 条,回复 1 条嵌在 replies 字段
        self.assertEqual(len(body['comments']), 1)
        self.assertEqual(len(body['comments'][0]['replies']), 1)
        self.assertEqual(body['total'], 2)  # total 算所有评论(含回复)


# =========================================================================
# note_comment_create_api
# =========================================================================
class CommentCreateApiTests(_CommentTestBase):
    def test_create_comment_on_public_note(self):
        author = make_user('cc01_a')
        commenter = make_user('cc01_c')
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        login(self.client, commenter)
        response = post_json(self.client, reverse('note_comment_create_api', args=[note.id]),
                             {'content': 'first comment'})
        self.assertEqual(response.status_code, 201)
        body = parse(response)
        self.assertEqual(body['content'], 'first comment')
        self.assertTrue(NoteComment.objects.filter(id=body['id'], author=commenter).exists())

    def test_create_reply(self):
        author = make_user('cc02_a')
        u1 = make_user('cc02_u1')
        u2 = make_user('cc02_u2')
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        top = NoteComment.objects.create(note=note, author=u1, content='top')
        login(self.client, u2)
        response = post_json(self.client, reverse('note_comment_create_api', args=[note.id]),
                             {'content': 'a reply', 'parent_id': top.id})
        self.assertEqual(response.status_code, 201)
        reply = NoteComment.objects.get(content='a reply')
        self.assertEqual(reply.parent_id, top.id)

    def test_create_on_private_note_returns_404(self):
        author = make_user('cc03_a')
        commenter = make_user('cc03_c')
        note = Note.objects.create(author=author, title='priv', content='', is_public=False)
        login(self.client, commenter)
        response = post_json(self.client, reverse('note_comment_create_api', args=[note.id]),
                             {'content': 'x'})
        self.assertEqual(response.status_code, 404)

    def test_create_requires_login(self):
        author = make_user('cc04_a')
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        # 不 login
        response = post_json(self.client, reverse('note_comment_create_api', args=[note.id]),
                             {'content': 'x'})
        # @login_required 默认重定向,API 调用通常 302/401/403
        self.assertIn(response.status_code, (302, 401, 403))

    def test_create_rejects_empty_content(self):
        author = make_user('cc05_a')
        commenter = make_user('cc05_c')
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        login(self.client, commenter)
        response = post_json(self.client, reverse('note_comment_create_api', args=[note.id]),
                             {'content': '   '})
        self.assertEqual(response.status_code, 400)

    def test_create_rejects_oversized_content(self):
        author = make_user('cc06_a')
        commenter = make_user('cc06_c')
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        login(self.client, commenter)
        long_text = 'x' * 2001
        response = post_json(self.client, reverse('note_comment_create_api', args=[note.id]),
                             {'content': long_text})
        self.assertEqual(response.status_code, 400)


# =========================================================================
# note_comment_delete_api
# =========================================================================
class CommentDeleteApiTests(_CommentTestBase):
    def test_author_can_delete_own_comment(self):
        author = make_user('cd01_a')
        commenter = make_user('cd01_c')
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        comment = NoteComment.objects.create(note=note, author=commenter, content='mine')
        login(self.client, commenter)
        response = self.client.delete(reverse('note_comment_delete_api', args=[comment.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(NoteComment.objects.filter(id=comment.id).exists())

    def test_other_user_cannot_delete(self):
        author = make_user('cd02_a')
        commenter = make_user('cd02_c')
        intruder = make_user('cd02_i')
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        comment = NoteComment.objects.create(note=note, author=commenter, content='mine')
        login(self.client, intruder)
        response = self.client.delete(reverse('note_comment_delete_api', args=[comment.id]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(NoteComment.objects.filter(id=comment.id).exists())

    def test_staff_can_delete_any_comment(self):
        author = make_user('cd03_a')
        commenter = make_user('cd03_c')
        staff = make_user('cd03_s', is_staff=True)
        note = Note.objects.create(author=author, title='public', content='', is_public=True)
        comment = NoteComment.objects.create(note=note, author=commenter, content='target')
        login(self.client, staff)
        response = self.client.delete(reverse('note_comment_delete_api', args=[comment.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(NoteComment.objects.filter(id=comment.id).exists())

    def test_delete_nonexistent_returns_404(self):
        user = make_user('cd04')
        login(self.client, user)
        response = self.client.delete(reverse('note_comment_delete_api', args=[999999]))
        self.assertEqual(response.status_code, 404)
