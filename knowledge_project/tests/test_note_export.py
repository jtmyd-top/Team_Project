"""export_note_api 测试

覆盖:
- Markdown 导出：标题 + 常见块级元素转换
- HTML 导出：独立文档 + 附件头
- 保密笔记拒绝导出
- 越权访问拒绝
- 不支持的格式返回 400
"""

from __future__ import annotations

from django.test import TestCase, override_settings
from django.urls import reverse

from notes.models import Note
from notes.views.note.export import html_to_markdown

from ._helpers import login, make_user


@override_settings(SECURE_SSL_REDIRECT=False)
class HtmlToMarkdownTests(TestCase):
    def test_headings_and_paragraph(self):
        md = html_to_markdown('<h1>Title</h1><p>Body text</p>', title='')
        self.assertIn('# Title', md)
        self.assertIn('Body text', md)

    def test_inline_formatting(self):
        md = html_to_markdown('<p><strong>bold</strong> and <em>italic</em> and <code>x</code></p>')
        self.assertIn('**bold**', md)
        self.assertIn('*italic*', md)
        self.assertIn('`x`', md)

    def test_link_and_image(self):
        md = html_to_markdown('<p><a href="https://e.com">link</a></p><p><img src="/a.png" alt="pic"></p>')
        self.assertIn('[link](https://e.com)', md)
        self.assertIn('![pic](/a.png)', md)

    def test_unordered_list(self):
        md = html_to_markdown('<ul><li>one</li><li>two</li></ul>')
        self.assertIn('- one', md)
        self.assertIn('- two', md)

    def test_ordered_list(self):
        md = html_to_markdown('<ol><li>first</li><li>second</li></ol>')
        self.assertIn('1. first', md)
        self.assertIn('2. second', md)

    def test_title_prepended(self):
        md = html_to_markdown('<p>content</p>', title='My Note')
        self.assertTrue(md.startswith('# My Note'))


@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    SECURE_SSL_REDIRECT=False,
)
class ExportNoteApiTests(TestCase):
    def test_markdown_export_download(self):
        user = make_user('exp01')
        note = Note.objects.create(author=user, title='Roadmap', content='<h2>Q1</h2><p>Ship it</p>')
        login(self.client, user)
        response = self.client.get(reverse('api_export_note', args=[note.id]) + '?format=md')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/markdown', response['Content-Type'])
        self.assertIn('attachment', response['Content-Disposition'])
        body = response.content.decode('utf-8')
        self.assertIn('# Roadmap', body)
        self.assertIn('## Q1', body)

    def test_html_export_download(self):
        user = make_user('exp02')
        note = Note.objects.create(author=user, title='Doc', content='<p>hi</p>')
        login(self.client, user)
        response = self.client.get(reverse('api_export_note', args=[note.id]) + '?format=html')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response['Content-Type'])
        body = response.content.decode('utf-8')
        self.assertIn('<!DOCTYPE html>', body)
        self.assertIn('<h1>Doc</h1>', body)

    def test_secret_note_export_denied(self):
        user = make_user('exp03')
        note = Note.objects.create(author=user, title='Secret', content='cipher', is_secret=True)
        login(self.client, user)
        response = self.client.get(reverse('api_export_note', args=[note.id]) + '?format=md')
        self.assertEqual(response.status_code, 400)

    def test_cross_user_export_denied(self):
        owner = make_user('exp04')
        other = make_user('exp04b')
        note = Note.objects.create(author=owner, title='Private', content='<p>x</p>')
        login(self.client, other)
        response = self.client.get(reverse('api_export_note', args=[note.id]) + '?format=md')
        self.assertEqual(response.status_code, 403)

    def test_public_note_exportable_by_others(self):
        owner = make_user('exp05')
        other = make_user('exp05b')
        note = Note.objects.create(author=owner, title='Open', content='<p>public</p>', is_public=True)
        login(self.client, other)
        response = self.client.get(reverse('api_export_note', args=[note.id]) + '?format=md')
        self.assertEqual(response.status_code, 200)

    def test_unsupported_format(self):
        user = make_user('exp06')
        note = Note.objects.create(author=user, title='X', content='<p>y</p>')
        login(self.client, user)
        response = self.client.get(reverse('api_export_note', args=[note.id]) + '?format=pdf')
        self.assertEqual(response.status_code, 400)
