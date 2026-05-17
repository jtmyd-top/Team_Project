"""follow 模块测试

覆盖:
- follow_user_api: 关注 / 自己 / 双向屏蔽 / 缺参数 / 幂等
- unfollow_user_api: 取消关注 / 不存在的关系 / 缺参数
- follow_status_api: 已关注 / 未关注 / 匿名 / 自己 / 计数
"""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from knowledge_project.models import UserBlocklist, UserFollow

from ._helpers import login, make_user, parse, post_json


@override_settings(SESSION_ENGINE='django.contrib.sessions.backends.db')
class _FollowTestBase(TestCase):
    def setUp(self):
        cache.clear()


# =========================================================================
# follow_user_api
# =========================================================================
class FollowUserApiTests(_FollowTestBase):
    def test_follow_success(self):
        a = make_user('fl01_a')
        b = make_user('fl01_b')
        login(self.client, a)
        response = post_json(self.client, reverse('follow_user_api'), {'user_id': b.id})
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertTrue(body['is_following'])
        self.assertTrue(body['created'])
        self.assertEqual(body['followers_count'], 1)
        self.assertTrue(UserFollow.objects.filter(follower=a, following=b).exists())

    def test_follow_self_rejected(self):
        user = make_user('fl02')
        login(self.client, user)
        response = post_json(self.client, reverse('follow_user_api'), {'user_id': user.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn('自己', parse(response)['error'])

    def test_follow_blocked_relationship_rejected(self):
        a = make_user('fl03_a')
        b = make_user('fl03_b')
        # b 屏蔽了 a
        UserBlocklist.objects.create(user=b, blocked_user=a)
        login(self.client, a)
        response = post_json(self.client, reverse('follow_user_api'), {'user_id': b.id})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(UserFollow.objects.filter(follower=a, following=b).exists())

    def test_follow_self_blocking_target_rejected(self):
        a = make_user('fl04_a')
        b = make_user('fl04_b')
        # a 屏蔽了 b,a 也不能关注 b
        UserBlocklist.objects.create(user=a, blocked_user=b)
        login(self.client, a)
        response = post_json(self.client, reverse('follow_user_api'), {'user_id': b.id})
        self.assertEqual(response.status_code, 403)

    def test_follow_missing_user_id(self):
        user = make_user('fl05')
        login(self.client, user)
        response = post_json(self.client, reverse('follow_user_api'), {})
        self.assertEqual(response.status_code, 400)

    def test_follow_is_idempotent(self):
        a = make_user('fl06_a')
        b = make_user('fl06_b')
        UserFollow.objects.create(follower=a, following=b)
        login(self.client, a)
        response = post_json(self.client, reverse('follow_user_api'), {'user_id': b.id})
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertTrue(body['is_following'])
        self.assertFalse(body['created'])  # 已存在,不会再 create
        # 仍然只有一条记录
        self.assertEqual(UserFollow.objects.filter(follower=a, following=b).count(), 1)

    def test_follow_returns_404_for_nonexistent_user(self):
        user = make_user('fl07')
        login(self.client, user)
        response = post_json(self.client, reverse('follow_user_api'), {'user_id': 9999999})
        self.assertEqual(response.status_code, 404)

    def test_follow_requires_login(self):
        b = make_user('fl08_b')
        response = post_json(self.client, reverse('follow_user_api'), {'user_id': b.id})
        # @login_required 默认重定向
        self.assertIn(response.status_code, (302, 401, 403))


# =========================================================================
# unfollow_user_api
# =========================================================================
class UnfollowUserApiTests(_FollowTestBase):
    def test_unfollow_success(self):
        a = make_user('uf01_a')
        b = make_user('uf01_b')
        UserFollow.objects.create(follower=a, following=b)
        login(self.client, a)
        response = post_json(self.client, reverse('unfollow_user_api'), {'user_id': b.id})
        self.assertEqual(response.status_code, 200)
        body = parse(response)
        self.assertFalse(body['is_following'])
        self.assertEqual(body['followers_count'], 0)
        self.assertFalse(UserFollow.objects.filter(follower=a, following=b).exists())

    def test_unfollow_nonexistent_relationship(self):
        # 取消一个本来不存在的关注关系应当幂等返回成功
        a = make_user('uf02_a')
        b = make_user('uf02_b')
        login(self.client, a)
        response = post_json(self.client, reverse('unfollow_user_api'), {'user_id': b.id})
        self.assertEqual(response.status_code, 200)

    def test_unfollow_missing_user_id(self):
        user = make_user('uf03')
        login(self.client, user)
        response = post_json(self.client, reverse('unfollow_user_api'), {})
        self.assertEqual(response.status_code, 400)


# =========================================================================
# follow_status_api
# =========================================================================
class FollowStatusApiTests(_FollowTestBase):
    def test_status_when_following(self):
        a = make_user('fs01_a')
        b = make_user('fs01_b')
        UserFollow.objects.create(follower=a, following=b)
        login(self.client, a)
        body = parse(self.client.get(reverse('follow_status_api', args=[b.id])))
        self.assertTrue(body['is_following'])
        self.assertEqual(body['followers_count'], 1)
        self.assertEqual(body['following_count'], 0)
        self.assertFalse(body['is_self'])

    def test_status_when_not_following(self):
        a = make_user('fs02_a')
        b = make_user('fs02_b')
        login(self.client, a)
        body = parse(self.client.get(reverse('follow_status_api', args=[b.id])))
        self.assertFalse(body['is_following'])
        self.assertEqual(body['followers_count'], 0)

    def test_status_for_self(self):
        user = make_user('fs03')
        login(self.client, user)
        body = parse(self.client.get(reverse('follow_status_api', args=[user.id])))
        self.assertTrue(body['is_self'])
        self.assertFalse(body['is_following'])

    def test_status_anonymous_returns_counts_only(self):
        target = make_user('fs04')
        # 另外两个用户关注 target
        f1 = make_user('fs04_f1')
        f2 = make_user('fs04_f2')
        UserFollow.objects.create(follower=f1, following=target)
        UserFollow.objects.create(follower=f2, following=target)
        # 不 login
        body = parse(self.client.get(reverse('follow_status_api', args=[target.id])))
        self.assertFalse(body['is_following'])
        self.assertEqual(body['followers_count'], 2)
        self.assertFalse(body['is_self'])

    def test_status_returns_404_for_nonexistent_user(self):
        response = self.client.get(reverse('follow_status_api', args=[9999999]))
        self.assertEqual(response.status_code, 404)

    def test_status_counts_following(self):
        # following_count = 该用户关注了多少人
        a = make_user('fs06_a')
        b = make_user('fs06_b')
        c = make_user('fs06_c')
        UserFollow.objects.create(follower=a, following=b)
        UserFollow.objects.create(follower=a, following=c)
        body = parse(self.client.get(reverse('follow_status_api', args=[a.id])))
        self.assertEqual(body['following_count'], 2)
        self.assertEqual(body['followers_count'], 0)
