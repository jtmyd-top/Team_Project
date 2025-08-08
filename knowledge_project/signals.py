# In: knowledge_project/signals.py (Refactored Version)

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
# 【核心修改】导入新的模型
from .models import Project, ProjectMembership

@receiver(post_save, sender=User)
def create_personal_project_for_new_user(sender, instance, created, **kwargs):
    """
    当一个新用户被创建时，自动为他创建一个个人项目，
    并将他自己设为该项目的所有者。
    """
    if created:
        # 1. 创建一个新的个人项目
        personal_project = Project.objects.create(
            # 项目的标题可以直接使用用户名，或者更友好一些
            title=f"{instance.username}",
            # 将新注册的用户设为这个项目的所有者
            is_personal_inbox=True,
            owner=instance
        )

        # 2. 在 ProjectMembership 中创建一条记录，明确该用户是所有者
        #    这是必需的，因为 'owner' 字段只定义了所有权，
        #    而 'members' 字段（通过ProjectMembership管理）才真正定义了谁可以访问。
        ProjectMembership.objects.create(
            user=instance,
            project=personal_project,
            role='owner' # 将用户在此项目中的角色设为 'owner'
        )