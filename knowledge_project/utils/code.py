import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageTransform
from io import BytesIO
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
font_path = os.path.join(BASE_DIR, "kumo.ttf")


def check_code(width=120, height=30, char_length=5, font_file=font_path, font_size=28):
    """
    生成一个验证码图片（带干扰元素）
    :param width: 宽度
    :param height: 高度
    :param char_length: 字符长度
    :param font_file: 字体文件路径
    :param font_size: 字体大小
    :return: (image object, random_code)
    """

    def rndChar():
        """生成随机大写字母 A-Z"""
        return chr(random.randint(65, 90))  # 修改为从A到Z的范围

    def rndColor():
        """生成随机颜色"""
        return (random.randint(0, 255), random.randint(10, 255), random.randint(64, 255))

    def apply_distortion(img):
        """应用轻微扭曲效果，使 OCR 更难解析"""
        img = img.transform(
            (img.width, img.height),
            ImageTransform.AffineTransform(
                (1 + random.uniform(-0.02, 0.02),
                 random.uniform(-0.01, 0.01),
                 0,
                 random.uniform(-0.01, 0.01),
                 1 + random.uniform(-0.02, 0.02),
                 0)
            ),
            resample=Image.BILINEAR
        )
        return img

    # 创建验证码画布
    code = []
    img = Image.new('RGB', (width, height), '#f0f3f8')  # 背景色
    draw = ImageDraw.Draw(img)

    # 绘制验证码字符
    font = ImageFont.truetype(font_file, font_size)
    for i in range(char_length):
        char = rndChar()
        code.append(char)

        # 字符垂直方向轻微偏移，模拟手写
        h_offset = random.randint(-2, 2)
        x_pos = i * width / char_length
        draw.text((x_pos, h_offset), char, font=font, fill=rndColor())

    # 写干扰点
    for _ in range(30):  # 减少数量，避免过度干扰
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill=rndColor())

    # 写干扰圆圈和弧线
    for _ in range(20):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill=rndColor())
        draw.arc((x, y, x + 4, y + 4), 0, 90, fill=rndColor())

    # 写干扰线（与背景融合）
    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line((x1, y1, x2, y2), fill='#f0f3f8')

    # 应用轻微扭曲和锐化滤镜
    img = apply_distortion(img)
    img = img.filter(ImageFilter.SHARPEN)  # 锐化
    img = img.filter(ImageFilter.GaussianBlur(radius=0.3))  # 轻微模糊

    return img, ''.join(code)


# 示例调用函数 - 可用于测试或保存图片
def save_captcha_image(path='./captcha.png'):
    """
    生成验证码图片并保存到指定路径
    """
    img, random_code = check_code()

    # 保存到本地
    try:
        img.save(path, 'PNG')
        print(f"[✅] 验证码已保存至：{path}")
        print(f"[💡] 正确验证码为：{random_code}")
    except Exception as e:
        print(f"[❌] 保存失败：{e}")



