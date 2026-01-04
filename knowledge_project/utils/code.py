import random
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# 尝试获取当前目录下的 kumo.ttf，如果没有则需要你确保路径正确
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FONT_PATH = os.path.join(BASE_DIR, "kumo.ttf")

def check_code(width=130, height=45, char_length=4, font_file=DEFAULT_FONT_PATH, font_size=32):
    """
    生成高强度验证码
    :return: (PIL.Image对象, 验证码字符串)
    """
    
    # 1. 准备工作：排除易混淆字符 (去掉了 I, 1, l, 0, O, o, Z, 2 等容易看错的)
    # 只保留清晰的大写字母和数字
    safe_chars = 'ABCDEFGHJKLMNPQRSTUVWXY3456789'
    
    def rnd_color(start=0, end=255):
        """生成随机颜色"""
        return (random.randint(start, end), random.randint(start, end), random.randint(start, end))

    # 2. 创建画布 (背景色设为浅灰或浅白，避免纯白被轻易二值化)
    bg_color = (random.randint(230, 255), random.randint(230, 255), random.randint(230, 255))
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # 3. 加载字体 (带容错处理)
    try:
        font = ImageFont.truetype(font_file, font_size)
    except IOError:
        # 如果找不到自定义字体，使用默认字体（虽然丑一点但不会报错）
        print(f"警告: 找不到字体文件 {font_file}，使用默认字体。")
        font = ImageFont.load_default()

    # 4. 生成随机码
    code_list = []
    
    # 5. 核心逻辑：逐个字符旋转绘制
    for i in range(char_length):
        char = random.choice(safe_chars)
        code_list.append(char)
        
        # 创建一个临时的透明图层来画单个字符
        # 尺寸要稍大一点以容纳旋转后的边角
        char_image = Image.new('RGBA', (font_size * 2, font_size * 2), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_image)
        
        # 字符颜色：使用较深颜色，保证对比度
        text_color = rnd_color(30, 120)
        
        # 在临时图层中心画字
        char_draw.text((font_size//2, font_size//2), char, font=font, fill=text_color)
        
        # 随机旋转 (-30度 到 +30度)
        angle = random.randint(-30, 30)
        char_image = char_image.rotate(angle, expand=False, resample=Image.BILINEAR)
        
        # 计算粘贴位置
        # x_pos: 根据字符数量平分宽度，并加一点随机偏移
        step = width // char_length
        x_pos = 10 + i * step + random.randint(-5, 5) # 基础位置
        
        # y_pos: 垂直方向居中并随机抖动
        y_pos = (height - font_size) // 2 + random.randint(-5, 5)
        
        # 粘贴回主图 (注意要扣掉为了旋转而扩大的偏移量)
        offset_correction = font_size // 2
        img.paste(char_image, (x_pos - offset_correction, y_pos - offset_correction), char_image)

    # 6. 添加干扰元素
    
    # 干扰线：随机画 3-5 条干扰线
    for _ in range(random.randint(3, 5)):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill=rnd_color(150, 220), width=2)

    # 干扰点/噪点：画 40 个
    for _ in range(40):
        draw.point(
            (random.randint(0, width), random.randint(0, height)), 
            fill=rnd_color(100, 200)
        )

    # 7. 滤镜处理 (增加 OCR 难度)
    # 稍微模糊一点点，让像素粘连，防止简单的切割算法
    img = img.filter(ImageFilter.SMOOTH)
    
    full_code = ''.join(code_list)
    
    return img, full_code

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



