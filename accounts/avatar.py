import hashlib
import logging
import os
import random as pyrandom
import threading
from io import BytesIO

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont


logger = logging.getLogger(__name__)


def _http_get(url):
    try:
        response = requests.get(url, timeout=4, stream=True)
        if response.status_code == 200 and response.headers.get("content-type", "").startswith("image/"):
            return response.content
    except requests.RequestException:
        return None
    return None


def _md5(email):
    return hashlib.md5(email.strip().lower().encode()).hexdigest()


def generate_initial_avatar(text, size=128):
    img = Image.new(
        "RGB",
        (size, size),
        (
            pyrandom.randint(64, 192),
            pyrandom.randint(64, 192),
            pyrandom.randint(64, 192),
        ),
    )
    draw = ImageDraw.Draw(img)
    font_path = os.path.join(settings.BASE_DIR, "knowledge_project", "utils", "kumo.ttf")
    font = ImageFont.truetype(font_path, size // 2)

    ch = text[0].upper() if text else "?"
    bbox = draw.textbbox((0, 0), ch, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, (size - th) / 2), ch, font=font, fill=(255, 255, 255))

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def fetch_avatar(user):
    email = (user.email or "").strip().lower()
    img_bytes, source = None, "default"

    if email:
        url = f"https://seccdn.libravatar.org/avatar/{_md5(email)}?s=256&d=404"
        img_bytes = _http_get(url)
        if img_bytes:
            source = "libravatar"

        if not img_bytes:
            url = f"https://www.gravatar.com/avatar/{_md5(email)}?s=256&d=404"
            img_bytes = _http_get(url)
            if img_bytes:
                source = "gravatar"

        if not img_bytes and email.endswith("@qq.com"):
            qq = email.split("@")[0]
            url = f"https://q1.qlogo.cn/g?b=qq&nk={qq}&s=100"
            img_bytes = _http_get(url)
            if img_bytes:
                source = "qq"

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
