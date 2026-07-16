"""insights_api / 个人数据洞察测试

覆盖:
- 登录校验（页面与 API）
- 概览统计：总数、公开、收藏、保密、浏览量、字符数（保密/回收站排除规则）
- 热力图与连续活跃天数（基于 NoteRevision）
- 热门笔记榜单：排序、保密笔记不出现
- 文件夹分布与标签统计
- 消息趋势与 30 天收发计数
- 用户隔离：不统计他人数据
"""

from __future__ import annotations

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from messaging.models import Message
from notes.models import Folder, Note, NoteRevision, Tag

from ._helpers import get_json, login, make_user, parse


@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    SECURE_SSL_REDIRECT=False,
)
class InsightsApiTests(TestCase):
    def test_api_requires_login(self):
        response = get_json(self.client, reverse('api_insights'))
        self.assertIn(response.status_code, (302, 403))

    def test_page_requires_login(self):
        response = self.client.get(reverse('insights'))
        self.assertIn(response.status_code, (302, 403))

    def test_page_renders_for_authenticated_user(self):
        user = make_user('ins00')
        login(self.client, user)
        response = self.client.get(reverse('insights'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'insights-app')

    def test_summary_counts(self):
        user = make_user('ins01')
        Note.objects.create(author=user, title='普通', content='<p>hello</p>')
        Note.objects.create(
            author=user, title='公开', content='<p>world</p>',
            is_public=True, views=7,
        )
        Note.objects.create(
            author=user, title='收藏', content='<p>fav</p>', is_favorited=True,
        )
        Note.objects.create(author=user, title='保密', content='encrypted-blob', is_secret=True)
        Note.objects.create(author=user, title='回收站', content='<p>gone</p>', is_trashed=True)

        login(self.client, user)
        response = get_json(self.client, reverse('api_insights'))
        self.assertEqual(response.status_code, 200)
        summary = parse(response)['summary']

        self.assertEqual(summary['note_count'], 4)  # 不含回收站
        self.assertEqual(summary['public_count'], 1)
        self.assertEqual(summary['favorited_count'], 1)
        self.assertEqual(summary['vault_count'], 1)
        self.assertEqual(summary['total_views'], 7)
        # 字符数只统计非保密笔记：len('<p>hello</p>')+len('<p>world</p>')+len('<p>fav</p>')
        self.assertEqual(summary['content_chars'], 12 + 12 + 10)

    def test_secret_note_never_in_top_notes(self):
        user = make_user('ins02')
        Note.objects.create(
            author=user, title='秘密', content='blob', is_secret=True, views=99,
        )
        visible = Note.objects.create(
            author=user, title='普通', content='<p>x</p>', views=3,
        )
        login(self.client, user)
        data = parse(get_json(self.client, reverse('api_insights')))
        top_ids = [item['id'] for item in data['top_notes']]
        self.assertEqual(top_ids, [visible.id])

    def test_top_notes_ordered_by_views(self):
        user = make_user('ins03')
        low = Note.objects.create(author=user, title='低', content='<p>a</p>', views=1)
        high = Note.objects.create(author=user, title='高', content='<p>b</p>', views=10)
        Note.objects.create(author=user, title='零', content='<p>c</p>', views=0)
        login(self.client, user)
        data = parse(get_json(self.client, reverse('api_insights')))
        self.assertEqual(
            [item['id'] for item in data['top_notes']],
            [high.id, low.id],
        )

    def test_heatmap_counts_revisions_and_streak(self):
        user = make_user('ins04')
        note = Note.objects.create(author=user, title='笔记', content='<p>x</p>')
        NoteRevision.objects.create(
            note=note, version_number=1, title='笔记', content='<p>x</p>',
            created_by=user,
        )
        NoteRevision.objects.create(
            note=note, version_number=2, title='笔记', content='<p>xx</p>',
            created_by=user,
        )
        login(self.client, user)
        data = parse(get_json(self.client, reverse('api_insights')))

        today = timezone.localtime(timezone.now()).date().isoformat()
        today_cell = next(cell for cell in data['heatmap'] if cell['date'] == today)
        self.assertEqual(today_cell['count'], 2)
        self.assertGreaterEqual(data['streak']['current'], 1)
        self.assertGreaterEqual(data['streak']['longest'], 1)

    def test_folder_distribution_and_tags(self):
        user = make_user('ins05')
        folder = Folder.objects.create(owner=user, name='工作')
        tag = Tag.objects.create(name='ins05-python')
        in_folder = Note.objects.create(
            author=user, title='A', content='<p>a</p>', folder=folder,
        )
        in_folder.tags.add(tag)
        Note.objects.create(author=user, title='B', content='<p>b</p>')

        login(self.client, user)
        data = parse(get_json(self.client, reverse('api_insights')))

        dist = {row['name']: row['count'] for row in data['folder_distribution']}
        self.assertEqual(dist.get('工作'), 1)
        self.assertEqual(dist.get('未分类'), 1)

        tags = {row['name']: row['count'] for row in data['top_tags']}
        self.assertEqual(tags.get('ins05-python'), 1)

    def test_message_stats(self):
        user = make_user('ins06')
        peer = make_user('ins06peer')
        Message.objects.create(sender=user, recipient=peer, content='hi')
        Message.objects.create(sender=peer, recipient=user, content='yo')
        Message.objects.create(sender=peer, recipient=user, content='again')

        login(self.client, user)
        data = parse(get_json(self.client, reverse('api_insights')))

        self.assertEqual(data['summary']['messages_sent_30d'], 1)
        self.assertEqual(data['summary']['messages_received_30d'], 2)

        today = timezone.localtime(timezone.now()).date().isoformat()
        today_trend = next(row for row in data['message_trend'] if row['date'] == today)
        self.assertEqual(today_trend['sent'], 1)
        self.assertEqual(today_trend['received'], 2)

    def test_does_not_count_other_users_data(self):
        user = make_user('ins07')
        other = make_user('ins07other')
        Note.objects.create(author=other, title='别人的', content='<p>y</p>', views=50)
        other_note = Note.objects.create(author=other, title='别人的2', content='<p>z</p>')
        NoteRevision.objects.create(
            note=other_note, version_number=1, title='别人的2', content='<p>z</p>',
            created_by=other,
        )

        login(self.client, user)
        data = parse(get_json(self.client, reverse('api_insights')))

        self.assertEqual(data['summary']['note_count'], 0)
        self.assertEqual(data['summary']['total_views'], 0)
        self.assertEqual(data['top_notes'], [])
        self.assertEqual(sum(cell['count'] for cell in data['heatmap']), 0)
