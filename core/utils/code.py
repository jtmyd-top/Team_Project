import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_FONT_PATH = str(BASE_DIR / "knowledge_project" / "utils" / "kumo.ttf")


def check_code(width=130, height=45, char_length=4, font_file=DEFAULT_FONT_PATH, font_size=32):
    safe_chars = "ABCDEFGHJKLMNPQRSTUVWXY3456789"

    def rnd_color(start=0, end=255):
        return (
            random.randint(start, end),
            random.randint(start, end),
            random.randint(start, end),
        )

    bg_color = (
        random.randint(230, 255),
        random.randint(230, 255),
        random.randint(230, 255),
    )
    image = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype(font_file, font_size)
    except IOError:
        print(f"Warning: font file not found, using default font: {font_file}")
        font = ImageFont.load_default()

    code_list = []
    for index in range(char_length):
        char = random.choice(safe_chars)
        code_list.append(char)

        char_image = Image.new("RGBA", (font_size * 2, font_size * 2), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_image)
        text_color = rnd_color(30, 120)
        char_draw.text((font_size // 2, font_size // 2), char, font=font, fill=text_color)

        angle = random.randint(-30, 30)
        char_image = char_image.rotate(angle, expand=False, resample=Image.BILINEAR)

        step = width // char_length
        x_pos = 10 + index * step + random.randint(-5, 5)
        y_pos = (height - font_size) // 2 + random.randint(-5, 5)
        offset_correction = font_size // 2
        image.paste(
            char_image,
            (x_pos - offset_correction, y_pos - offset_correction),
            char_image,
        )

    for _ in range(random.randint(3, 5)):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill=rnd_color(150, 220), width=2)

    for _ in range(40):
        draw.point(
            (random.randint(0, width), random.randint(0, height)),
            fill=rnd_color(100, 200),
        )

    image = image.filter(ImageFilter.SMOOTH)
    return image, "".join(code_list)


def save_captcha_image(path="./captcha.png"):
    image, random_code = check_code()
    try:
        image.save(path, "PNG")
        print(f"[OK] captcha saved to: {os.path.abspath(path)}")
        print(f"[CODE] {random_code}")
    except Exception as exc:
        print(f"[ERROR] failed to save captcha: {exc}")
