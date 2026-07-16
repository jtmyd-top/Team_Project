"""note_links_api / wiki-link resolution 测试

覆盖:
- extract_wiki_link_titles：解析、去重、忽略空、剥离 HTML
- 出链解析：命中唯一笔记 / 未命中 / 歧义（同名多篇）
- 反链：正确识别引用当前笔记标题的其它笔记
- 权限：登录校验、读权限校验、保密笔记拒绝
- 隔离：不泄露他人私有笔记、不越权
"""

from __future__ import annotations

from django.test import TestCase, override_settings
from django.urls import reverse

from notes.models import Note
from notes.views.note.wiki_links import extract_wiki_link_titles

from ._helpers import get_json, login, make_user, parse


class ExtractWikiLinkTitlesTests(TestCase):
    def test_basic_extraction(self):
        titles = extract_wiki_link_titles('<p>see [[Alpha]] and [[Beta]]</p>')
        self.assertEqual(titles, ['Alpha', 'Beta'])

    def test_dedupes_case_insensitively(self):
        titles = extract_wiki_link_titles('<p>[[Alpha]] [[alpha]] [[ALPHA]]</p>')
        self.assertEqual(titles, ['Alpha'])

    def test_ignores_empty_and_whitespace(self):
        titles = extract_wiki_link_titles('<p>[[]] [[   ]] [[Real]]</p>')
        self.assertEqual(titles, ['Real'])

    def test_strips_html_tags(self):
        titles = extract_wiki_link_titles('<p>[[Foo]]</p><blockquote>[[Bar]]</blockquote>')
        self.assertEqual(titles, ['Foo', 'Bar'])

    def test_empty_content(self):
        self.assertEqual(extract_wiki_link_titles(''), [])
        self.assertEqual(extract_wiki_link_titles(None), [])


@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    SECURE_SSL_REDIRECT=False,
)
class NoteLinksApiTests(TestCase):
    def test_requires_login(self):
        user = make_user('wl00')
        note = Note.objects.create(author=user, title='Root', content='<p>x</p>')
        response = get_json(self.client, reverse('api_note_links', args=[note.id]))
        self.assertIn(response.status_code, (302, 403))

    def test_resolves_outgoing_link(self):
        user = make_user('wl01')
        target = Note.objects.create(author=user, title='Roadmap', content='<p>plans</p>')
        source = Note.objects.create(author=user, title='Index', content='<p>see [[Roadmap]]</p>')
        login(self.client, user)
        response = get_json(self.client, reverse('api_note_links', args=[source.id]))
        self.assertEqual(response.status_code, 200)
        data = parse(response)
        resolved = data['outgoing']['resolved']
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]['id'], target.id)
        self.assertEqual(resolved[0]['title'], 'Roadmap')
        self.assertEqual(data['outgoing']['unresolved'], [])

    def test_unresolved_link_when_missing(self):
        user = make_user('wl02')
        source = Note.objects.create(author=user, title='Index', content='<p>[[Ghost]]</p>')
        login(self.client, user)
        response = get_json(self.client, reverse('api_note_links', args=[source.id]))
        self.assertEqual(response.status_code, 200)
        data = parse(response)
        self.assertEqual(data['outgoing']['resolved'], [])
        self.assertEqual(data['outgoing']['unresolved'], ['Ghost'])

    def test_ambiguous_title_is_unresolved(self):
        user = make_user('wl03')
        Note.objects.create(author=user, title='Dup', content='<p>a</p>')
        Note.objects.create(author=user, title='Dup', content='<p>b</p>')
        source = Note.objects.create(author=user, title='Index', content='<p>[[Dup]]</p>')
        login(self.client, user)
        response = get_json(self.client, reverse('api_note_links', args=[source.id]))
        self.assertEqual(response.status_code, 200)
        data = parse(response)
        self.assertEqual(data['outgoing']['resolved'], [])
        self.assertEqual(data['outgoing']['unresolved'], ['Dup'])

    def test_backlinks_found(self):
        user = make_user('wl04')
        target = Note.objects.create(author=user, title='Hub', content='<p>center</p>')
        referrer = Note.objects.create(author=user, title='Spoke', content='<p>links to [[Hub]]</p>')
        login(self.client, user)
        response = get_json(self.client, reverse('api_note_links', args=[target.id]))
        self.assertEqual(response.status_code, 200)
        data = parse(response)
        ids = [b['id'] for b in data['backlinks']]
        self.assertIn(referrer.id, ids)

    def test_backlink_substring_not_false_positive(self):
        user = make_user('wl05')
        target = Note.objects.create(author=user, title='Road', content='<p>x</p>')
        # References "Roadmap", not "Road" — must NOT be a backlink of "Road".
        Note.objects.create(author=user, title='Other', content='<p>[[Roadmap]]</p>')
        login(self.client, user)
        response = get_json(self.client, reverse('api_note_links', args=[target.id]))
        self.assertEqual(response.status_code, 200)
        data = parse(response)
        self.assertEqual(data['backlinks'], [])

    def test_secret_note_rejected(self):
        user = make_user('wl06')
        note = Note.objects.create(author=user, title='Sec', content='cipher', is_secret=True)
        login(self.client, user)
        response = get_json(self.client, reverse('api_note_links', args=[note.id]))
        self.assertEqual(response.status_code, 400)

    def test_cross_user_denied(self):
        owner = make_user('wl07')
        other = make_user('wl07b')
        note = Note.objects.create(author=owner, title='Priv', content='<p>[[x]]</p>')
        login(self.client, other)
        response = get_json(self.client, reverse('api_note_links', args=[note.id]))
        self.assertEqual(response.status_code, 403)

    def test_does_not_leak_other_users_notes_as_links(self):
        owner = make_user('wl08')
        other = make_user('wl08b')
        # Another user has a note titled "Confidential".
        Note.objects.create(author=other, title='Confidential', content='<p>secret</p>')
        source = Note.objects.create(author=owner, title='Mine', content='<p>[[Confidential]]</p>')
        login(self.client, owner)
        response = get_json(self.client, reverse('api_note_links', args=[source.id]))
        self.assertEqual(response.status_code, 200)
        data = parse(response)
        # Must not resolve to the other user's note.
        self.assertEqual(data['outgoing']['resolved'], [])
        self.assertEqual(data['outgoing']['unresolved'], ['Confidential'])
