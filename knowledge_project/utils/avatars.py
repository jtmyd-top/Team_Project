import os
import hashlib
import random
from io import BytesIO
from PIL import Image, ImageDraw
import requests

# 头像保存目录
AVATAR_DIR = os.path.join("media", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

def get_gravatar_url(email, size=128):
    """
    根据邮箱生成 Gravatar 头像 URL
    """
    email_hash = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d=404"

def download_avatar(email):
    """
    优先尝试下载 Gravatar 头像，如果没有，则返回 None
    """
    url = get_gravatar_url(email)
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        print(f"[⚠️] 获取 Gravatar 失败: {e}")
    return None

def generate_random_avatar(size=128):
    """
    生成随机颜色的圆形头像
    """
    # 随机颜色
    color = tuple(random.randint(64, 192) for _ in range(3))
    img = Image.new("RGB", (size, size), color)

    # 可选：画上用户首字母或简单图案
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, size-1, size-1), fill=color)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()

def save_user_avatar(email, username):
    """
    综合逻辑：
    1. 尝试从 Gravatar 获取
    2. 若失败，生成随机颜色头像
    3. 保存到本地并返回路径
    """
    avatar_bytes = download_avatar(email)
    if avatar_bytes is None:
        avatar_bytes = generate_random_avatar()

    filename = f"{username}.png"
    filepath = os.path.join(AVATAR_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(avatar_bytes)

    return filepath
