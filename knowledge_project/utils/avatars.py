import os
import hashlib
import random
import requests
from io import BytesIO
from PIL import Image, ImageDraw
from PIL import Image, ImageDraw, ImageFont
AVATAR_DIR = os.path.join("media", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

def get_gravatar_url(email, size=128):
    """Gravatar 头像 URL"""
    email_hash = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d=404"

def get_qq_avatar_url(email):
    """QQ 邮箱头像 URL (通过 QQ 邮箱 API 获取 QQ 号)"""
    if email.endswith("@qq.com"):
        qq_number = email.split("@")[0]
        return f"https://q1.qlogo.cn/g?b=qq&nk={qq_number}&s=100"
    return None

def try_download(url):
    """尝试下载头像并返回 bytes，如果失败返回 None"""
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        print(f"[⚠️] 获取头像失败: {url} -> {e}")
    return None

def generate_random_avatar(size=128, username=""):
    """生成随机颜色圆形头像，带首字母"""
    # 1. 随机背景色
    color = tuple(random.randint(64, 192) for _ in range(3))
    img = Image.new("RGB", (size, size), color)
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, size-1, size-1), fill=color)

    # 2. 画首字母
    ch = username[0].upper() if username else "?"
    try:
        font_path = os.path.join("knowledge_project", "utils", "kumo.ttf")
        font = ImageFont.truetype(font_path, size // 2)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), ch, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, (size - th) / 2), ch, font=font, fill=(255, 255, 255))

    # 3. 输出字节流
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue(), "random"

def save_user_avatar(email, username):
    """
    优先级：
    1. QQ 邮箱头像
    2. Gravatar
    3. 随机颜色头像
    返回：(文件路径, 来源标记)
    """
    # 优先尝试 QQ 头像
    qq_url = get_qq_avatar_url(email)
    if qq_url:
        data = try_download(qq_url)
        if data:
            return _save_avatar_file(username, data), "qq"

    # 尝试 Gravatar
    gravatar_url = get_gravatar_url(email)
    data = try_download(gravatar_url)
    if data:
        return _save_avatar_file(username, data), "gravatar"

    # 生成随机头像
    data, source = generate_random_avatar(username=username)
    return _save_avatar_file(username, data), source

def _save_avatar_file(username, data):
    """将头像二进制保存到本地并返回文件路径"""
    filename = f"{username}.png"
    filepath = os.path.join(AVATAR_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(data)
    return filepath
