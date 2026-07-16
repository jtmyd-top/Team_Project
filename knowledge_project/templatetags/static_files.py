from django import template
import json
import os
import glob
from django.conf import settings
from django.templatetags.static import static as static_url
from django.utils.safestring import mark_safe

register = template.Library()

# Vite 开发服务器地址
VITE_DEV_SERVER = 'http://localhost:5173'

# Vite manifest 缓存（按文件 mtime 失效）
_manifest_cache = {'mtime': None, 'data': None}


def _load_vite_manifest():
    manifest_path = os.path.join(
        settings.BASE_DIR, 'static', 'dist', '.vite', 'manifest.json'
    )
    try:
        mtime = os.path.getmtime(manifest_path)
    except OSError:
        return {}
    if _manifest_cache['mtime'] != mtime:
        try:
            with open(manifest_path, encoding='utf-8') as fh:
                _manifest_cache['data'] = json.load(fh)
            _manifest_cache['mtime'] = mtime
        except (OSError, ValueError):
            return {}
    return _manifest_cache['data'] or {}


@register.simple_tag
def vite_entry_css(entry_name):
    """输出某个 Vite 入口需要的全部 CSS <link> 标签。

    element-plus 等共享依赖的样式会被拆分为独立的 chunk CSS
    （el-select.css、el-input.css 等），只链接 assets/<entry>.css
    会丢失组件样式。此标签读取构建 manifest，把入口 css 列表全部输出。

    用法: {% vite_entry_css 'moderation' %}
    """
    if is_vite_dev_mode():
        # 开发模式下 CSS 由 Vite 开发服务器注入
        return ''
    manifest = _load_vite_manifest()
    entry = manifest.get(f'src/entries/{entry_name}.js') or {}
    css_files = entry.get('css') or [f'assets/{entry_name}.css']
    version = static_mtime(f'dist/{entry_name}.js')
    links = []
    for css in css_files:
        href = static_url(f'dist/{css}')
        if version:
            href = f'{href}?v={version}'
        links.append(f'<link rel="stylesheet" href="{href}">')
    return mark_safe('\n'.join(links))



@register.simple_tag
def static_mtime(path):
    candidates = []
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root:
        candidates.append(os.path.join(static_root, path))
    for static_dir in getattr(settings, 'STATICFILES_DIRS', []):
        candidates.append(os.path.join(static_dir, path))

    for candidate in candidates:
        try:
            if os.path.exists(candidate):
                return str(int(os.path.getmtime(candidate)))
        except OSError:
            continue
    return ''

def is_vite_dev_mode():
    """
    检查是否处于 Vite 开发模式
    可以通过 settings.VITE_DEV_MODE 或 DEBUG 来控制
    """
    return getattr(settings, 'VITE_DEV_MODE', False)


@register.simple_tag
def vite_asset(entry_name, asset_type='js'):
    """
    根据开发/生产模式返回正确的资源路径

    用法:
        {% vite_asset 'login' 'js' %}  -> 返回 JS 文件路径
        {% vite_asset 'login' 'css' %} -> 返回 CSS 文件路径

    开发模式: 返回 Vite 开发服务器的 URL
    生产模式: 返回构建后的静态文件路径
    """
    if is_vite_dev_mode():
        # 开发模式：从 Vite 开发服务器加载
        if asset_type == 'js':
            return f'{VITE_DEV_SERVER}/src/entries/{entry_name}.js'
        elif asset_type == 'css':
            # 开发模式下 CSS 由 Vite 自动注入，不需要单独加载
            return ''
    else:
        # 生产模式：从构建目录加载
        if asset_type == 'js':
            return f'/static/dist/{entry_name}.js'
        elif asset_type == 'css':
            return f'/static/dist/assets/{entry_name}.css'

    return ''


@register.simple_tag
def vite_dev_client():
    """
    在开发模式下注入 Vite 客户端脚本（用于 HMR）

    用法: {% vite_dev_client %}
    """
    if is_vite_dev_mode():
        return f'<script type="module" src="{VITE_DEV_SERVER}/@vite/client"></script>'
    return ''


@register.simple_tag
def is_vite_dev():
    """
    返回是否处于 Vite 开发模式

    用法: {% is_vite_dev as vite_dev %}
    """
    return is_vite_dev_mode()


@register.simple_tag
def get_latest_static(pattern, base_path='static/dist'):
    """
    获取匹配模式的最新静态文件（CSS或JS）
    pattern: 文件名模式，如 'forgot-password*.css' 或 'login*.js'
    base_path: 基础路径，默认为 'static/JS/dist'
    """
    try:
        # 如果是相对路径，先构建绝对路径
        if not os.path.isabs(base_path):
            base_path = os.path.join(settings.BASE_DIR, base_path)

        # 构建完整的搜索路径
        search_pattern = os.path.join(base_path, pattern)

        # 获取所有匹配的文件
        files = glob.glob(search_pattern)

        if not files:
            return ''

        # 按修改时间排序，获取最新的文件
        latest_file = max(files, key=os.path.getctime)

        # 返回相对于BASE_DIR的路径
        rel_path = os.path.relpath(latest_file, settings.BASE_DIR)
        return rel_path.replace('\\', '/')  # 确保使用正斜杠

    except Exception:
        return ''

@register.inclusion_tag('auto_css.html')
def auto_css(pattern, base_path='static/dist/assets'):
    """
    自动包含最新的CSS文件
    pattern: 文件名模式，如 'forgot-password*.css'
    base_path: 基础路径，默认为 'static/JS/dist/assets'
    """
    latest_file = get_latest_static(pattern, base_path)
    return {
        'css_file': latest_file
    }

@register.inclusion_tag('auto_js.html')
def auto_js(pattern, base_path='static/dist'):
    """
    自动包含最新的JS文件
    pattern: 文件名模式，如 'forgot-password*.js'
    base_path: 基础路径，默认为 'static/JS/dist'
    """
    latest_file = get_latest_static(pattern, base_path)
    return {
        'js_file': latest_file
    }
