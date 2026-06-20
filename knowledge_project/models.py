import random as pyrandom
import logging
import secrets
import threading

from bs4 import BeautifulSoup
import jieba.analyse
from django.db import models, transaction
import uuid
from django.contrib.auth.models import User
from django_ckeditor_5.fields import CKEditor5Field
from django.db.models.signals import post_save
from django.dispatch import receiver
import nh3
import os
import hashlib, io, re, requests, colorsys
from urllib.parse import unquote, urlparse
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.core.validators import MaxLengthValidator
from io import BytesIO
from django.core.serializers.json import DjangoJSONEncoder
from knowledge_project.utils.request_utils import get_client_ip

logger = logging.getLogger(__name__)
# ---------------- Notes / folders / assets ----------------
from notes.models import (  # Backward-compatible import path.
    Asset,
    Folder,
    Note,
    NoteAsset,
    NoteComment,
    NoteHistory,
    Tag,
    auto_generate_tags_for_note,
    extract_protected_upload_paths,
    sync_note_asset_links,
    user_directory_path,
)


# ---------------- 用户资料 + 头像 ----------------
def user_avatar_path(instance, filename):
    return f'user_{instance.user.id}/avatar/{filename}'

def default_theme_settings():
    """为 JSONField 提供默认主题设置的可调用函数"""
    return {
        'mode': 'light',
        'primary_color': '#409EFF',
        'font_size': 14,
        'compact_mode': False,
        'animations': True,
        'dark_mode': False  # 保留兼容性
    }

from accounts.models import (  # Backward-compatible import path.
    Profile,
    ProfileLike,
    ProfileVisit,
)


from accounts.models import (  # Backward-compatible import path.
    AccessLog,
    LoginDevice,
    LoginNotification,
    PasswordResetAttempt,
    PasswordResetToken,
    SecurityAuditLog,
    TrustedDevice,
)

# ---------------- 头像抓取逻辑 ----------------
def _http_get(url):
    try:
        r = requests.get(url, timeout=4, stream=True)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
            return r.content
    except requests.RequestException:
        return None

def _md5(email): return hashlib.md5(email.strip().lower().encode()).hexdigest()

def fetch_avatar(user):
    email = (user.email or "").strip().lower()
    img_bytes, source = None, "default"

    if email:
        # 1. Libravatar
        url = f"https://seccdn.libravatar.org/avatar/{_md5(email)}?s=256&d=404"
        img_bytes = _http_get(url)
        if img_bytes: source = "libravatar"

        # 2. Gravatar
        if not img_bytes:
            url = f"https://www.gravatar.com/avatar/{_md5(email)}?s=256&d=404"
            img_bytes = _http_get(url)
            if img_bytes: source = "gravatar"

        # 3. QQ 邮箱头像
        if not img_bytes and email.endswith("@qq.com"):
            qq = email.split("@")[0]
            url = f"https://q1.qlogo.cn/g?b=qq&nk={qq}&s=100"
            img_bytes = _http_get(url)
            if img_bytes: source = "qq"

    # 4. 兜底：纯色首字母
    if not img_bytes:
        img_bytes = generate_initial_avatar(user.username or email)
        source = "default"

    if img_bytes:
        filename = f"avatar_{source}.png"
        user.profile.avatar.save(filename, ContentFile(img_bytes), save=True)
        user.profile.avatar_source = source
        user.profile.save(update_fields=["avatar", "avatar_source"])


def fetch_avatar_async(user_id):
    def _runner():
        try:
            user = User.objects.select_related("profile").get(id=user_id)
            fetch_avatar(user)
        except User.DoesNotExist:
            logger.warning("Skipping async avatar fetch for missing user %s", user_id)
        except Exception:
            logger.exception("Failed to fetch avatar asynchronously for user %s", user_id)

    threading.Thread(target=_runner, daemon=True).start()

from io import BytesIO

def generate_initial_avatar(text, size=128):
    img = Image.new("RGB", (size, size),
                    (pyrandom.randint(64, 192),
                     pyrandom.randint(64, 192),
                     pyrandom.randint(64, 192)))
    draw = ImageDraw.Draw(img)
    font_path = os.path.join(settings.BASE_DIR, "knowledge_project", "utils", "kumo.ttf")
    font = ImageFont.truetype(font_path, size // 2)

    ch = text[0].upper() if text else "?"
    bbox = draw.textbbox((0, 0), ch, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, (size - th) / 2), ch, font=font, fill=(255, 255, 255))

    # 返回字节流而不是 Image 对象，避免 ContentFile 出错
    from io import BytesIO
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


# ---------------- Compatibility signal implementation ----------------
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile = Profile.objects.create(user=instance)
        transaction.on_commit(lambda: fetch_avatar_async(instance.id))

        # 生成 8 位搜索短码（若未生成）
        try:
            import secrets, string
            if not profile.search_code:
                alphabet = string.ascii_uppercase + string.digits
                for _ in range(5):
                    code = ''.join(secrets.choice(alphabet) for _ in range(8))
                    if not Profile.objects.filter(search_code=code).exists():
                        profile.search_code = code
                        break
        except Exception as e:
            logger.error(f"[Profile] 生成 search_code 失败: {e}")

        # ==================== 【新增】自动初始化保密柜 ====================
        try:
            from vault.crypto import VaultEncryption

            # 生成随机 DEK（数据加密密钥）
            dek = VaultEncryption.generate_dek()

            # 用 KEK（密钥加密密钥）加密 DEK
            encrypted_dek_b64, iv_b64 = VaultEncryption.encrypt_dek(dek)

            # 保存到 Profile
            profile.encrypted_vault_key = encrypted_dek_b64
            profile.vault_key_iv = iv_b64
            profile.vault_initialized = True
            profile.save(update_fields=['encrypted_vault_key', 'vault_key_iv', 'vault_initialized'])

            logger.info(f"[Vault] Auto-initialized vault for new user: {instance.username}")
        except Exception as e:
            logger.error(f"[Vault] Failed to auto-initialize vault for user {instance.username}: {e}")
            # 继续执行，vault 初始化失败不应该阻止用户创建


from accounts import avatar as _accounts_avatar

fetch_avatar = _accounts_avatar.fetch_avatar
fetch_avatar_async = _accounts_avatar.fetch_avatar_async
generate_initial_avatar = _accounts_avatar.generate_initial_avatar


# ============ ?????? ============
from messaging.models import (  # Backward-compatible import path.
    ConversationSettings,
    GroupJoinRequest,
    GroupMessage,
    GroupMessageDeletion,
    GroupMessageMention,
    GroupMessageReaction,
    GroupTag,
    GroupTagRelation,
    Message,
    MessageAttachment,
    MessageGroup,
    MessageGroupAnnouncementHistory,
    MessageGroupAnnouncementRead,
    MessageGroupAuditLog,
    MessageGroupBan,
    MessageGroupInviteLink,
    MessageGroupInviteUse,
    MessageGroupMember,
    MessageGroupPolicy,
    MessagePreference,
    NewConversationQuotaLog,
    UserBlocklist,
    UserFollow,
    generate_group_invite_token,
    message_attachment_path,
)

from moderation.models import (  # Backward-compatible import path.
    AttachmentReport,
    CommentReport,
    NoteReport,
)


from moderation.models import MessageReport  # Backward-compatible import path.


from moderation.models import (  # Backward-compatible import path.
    ModerationAppeal,
    ModerationLog,
    ModerationTemplate,
    UserSanction,
)
from notifications.models import UserNotification  # Backward-compatible import path.


