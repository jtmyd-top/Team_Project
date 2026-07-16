"""quick_search_api 测试

覆盖:
- 空查询返回空分组
- 命中当前用户的笔记 + 协作笔记，跳过他人笔记
- 跳过保密/回收站笔记
- 命中当前用户所属群组（按名称），不返回未加入群组
- 未登录重定向/拒绝
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from messaging.models import MessageGroup, MessageGroupMember
from notes.models import Note, NoteCollaborator

from ._helpers import login, make_user, parse


@override_settings(
    SESSION_ENGINE='django.contrib.sessions.backends.db',
    SECURE_SSL_REDIRECT=False,
)
class QuickSearchApiTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_empty_query_returns_empty_groups(self):
        user = make_user('qs01')
        login(self.client, user)
        response = self.client.get(reverse('api_quick_search'))
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertEqual(body['notes'], [])
        self.assertEqual(body['groups'], [])

    def test_requires_login(self):
        response = self.client.get(reverse('api_quick_search') + '?q=x')
        self.assertIn(response.status_code, (302, 401, 403))

    def test_matches_own_notes_only(self):
        user = make_user('qs02')
        other = make_user('qsother02')
        Note.objects.create(author=user, title='RoadmapQ2', content='')
        Note.objects.create(author=other, title='RoadmapQ2', content='')
        login(self.client, user)
        body = parse(self.client.get(reverse('api_quick_search') + '?q=Roadmap'))
        self.assertEqual(len(body['notes']), 1)
        self.assertEqual(body['notes'][0]['title'], 'RoadmapQ2')

    def test_matches_collaborator_notes(self):
        owner = make_user('qsowner03')
        collaborator = make_user('qscollab03')
        note = Note.objects.create(author=owner, title='SharedPlan', content='')
        NoteCollaborator.objects.create(
            note=note, user=collaborator, role=NoteCollaborator.ROLE_EDITOR,
        )
        login(self.client, collaborator)
        body = parse(self.client.get(reverse('api_quick_search') + '?q=SharedPlan'))
        self.assertEqual({n['title'] for n in body['notes']}, {'SharedPlan'})

    def test_excludes_secret_and_trashed(self):
        user = make_user('qs04')
        Note.objects.create(author=user, title='SecretMatch', content='', is_secret=True)
        Note.objects.create(author=user, title='TrashMatch', content='', is_trashed=True)
        Note.objects.create(author=user, title='OpenMatch', content='')
        login(self.client, user)
        body = parse(self.client.get(reverse('api_quick_search') + '?q=Match'))
        self.assertEqual({n['title'] for n in body['notes']}, {'OpenMatch'})

    def test_matches_joined_groups_only(self):
        user = make_user('qs05')
        stranger = make_user('qsstranger05')
        joined = MessageGroup.objects.create(name='DesignSquad', owner=user, created_by=user)
        MessageGroupMember.objects.create(group=joined, user=user, role='owner')
        other = MessageGroup.objects.create(name='DesignOutsiders', owner=stranger, created_by=stranger)
        MessageGroupMember.objects.create(group=other, user=stranger, role='owner')
        login(self.client, user)
        body = parse(self.client.get(reverse('api_quick_search') + '?q=Design'))
        self.assertEqual({g['name'] for g in body['groups']}, {'DesignSquad'})
        self.assertEqual(body['groups'][0]['role'], 'owner')

    def test_left_group_excluded(self):
        from django.utils import timezone
        user = make_user('qs06')
        group = MessageGroup.objects.create(name='GhostGroup', owner=user, created_by=user)
        MessageGroupMember.objects.create(
            group=group, user=user, role='owner', left_at=timezone.now(),
        )
        login(self.client, user)
        body = parse(self.client.get(reverse('api_quick_search') + '?q=Ghost'))
        self.assertEqual(body['groups'], [])
