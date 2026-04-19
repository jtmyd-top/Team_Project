# knowledge_project/captcha_views.py
"""验证码相关视图: Turnstile / 图形验证码 / 统一验证入口

原属于 views.py 3785-4141 段。抽出后 views.py 底部通过 from ... import *
方式 re-export,保持 urls.py 与 admin_auth.py 的外部引用不变。
"""
import hashlib
import json
import logging
import secrets
import time
from io import BytesIO

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..utils.code import check_code
from ..utils.turnstile import (
    get_site_key,
    is_turnstile_enabled,
    verify_turnstile_token,
)

logger = logging.getLogger(__name__)


# 验证码安全配置
CAPTCHA_CONFIG = {
    'init_token_ttl': 30,           # init令牌有效期（秒）
    'generate_delay': 0.5,          # 生成延迟（秒），防止CPU耗尽攻击
    'ip_rate_limit': 10,            # 单IP每分钟最多请求次数
    'ip_rate_window': 60,           # 限流窗口（秒）
    'global_rate_limit': 100,       # 全局每分钟最多请求次数（熔断阈值）
    'global_rate_window': 60,       # 全局限流窗口（秒）
}


@require_http_methods(["GET"])
def turnstile_config(request):
    """
    获取Turnstile配置信息，包含是否启用状态
    前端可根据 enabled 字段决定是否加载 Turnstile
    """
    try:
        enabled = is_turnstile_enabled()
        site_key = get_site_key() if enabled else None
        return JsonResponse({
            'status': 'success',
            'enabled': enabled,
            'site_key': site_key
        })
    except Exception as e:
        logger.error(f"获取Turnstile配置失败: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '配置获取失败'}, status=500)


# ==================== 图形验证码 API（纵深防御版本） ====================


@csrf_exempt
def captcha_init(request):
    """
    验证码初始化接口 - 采用 Proof of Work 机制防止脚本滥用

    流程：
    1. GET  请求：返回 challenge（prefix + difficulty），前端需计算 PoW
    2. POST 请求：验证 PoW solution，通过后返回 init_token

    安全机制：
    - PoW 难度设置为 4（SHA256 前 4 位为 0），前端需计算约 6.5 万次哈希
    - challenge 绑定 IP 和时间戳，30 秒过期
    - 一个 challenge 只能使用一次
    - 普通 Python 脚本需要 1-3 秒才能计算出 solution，浏览器 JS 约 0.3-1 秒
    """
    from knowledge_project.utils.request_utils import get_client_ip

    client_ip = get_client_ip(request)

    if request.method == 'GET':
        # ========== 第一步：生成 PoW challenge ==========
        try:
            # 生成随机前缀（16 字符）
            pow_prefix = secrets.token_hex(8)
            # 难度：SHA256 结果前 N 位必须是 0（十六进制）
            # 难度 4 表示前 4 个十六进制字符为 0，概率 1/65536
            pow_difficulty = 4

            # 存入 session
            request.session['pow_challenge'] = pow_prefix
            request.session['pow_difficulty'] = pow_difficulty
            request.session['pow_challenge_ip'] = client_ip
            request.session['pow_challenge_time'] = time.time()
            # 标记 challenge 未被使用
            request.session['pow_challenge_used'] = False

            logger.debug(f"[PoW] 生成 challenge (IP: {client_ip}, prefix: {pow_prefix[:8]}...)")

            return JsonResponse({
                'status': 'challenge',
                'prefix': pow_prefix,
                'difficulty': pow_difficulty,
                'expires_in': 30
            })

        except Exception as e:
            logger.error(f"PoW challenge 生成失败: {str(e)}")
            return JsonResponse({'error': '初始化失败'}, status=500)

    elif request.method == 'POST':
        # ========== 第二步：验证 PoW solution ==========
        try:
            data = json.loads(request.body)
            nonce = data.get('nonce', '')

            # 获取 session 中的 challenge
            stored_prefix = request.session.get('pow_challenge')
            stored_difficulty = request.session.get('pow_difficulty', 4)
            stored_ip = request.session.get('pow_challenge_ip')
            stored_time = request.session.get('pow_challenge_time', 0)
            challenge_used = request.session.get('pow_challenge_used', True)

            # 验证 challenge 存在
            if not stored_prefix:
                return JsonResponse({'error': '请先获取 challenge'}, status=400)

            # 验证 challenge 未被使用
            if challenge_used:
                return JsonResponse({'error': 'Challenge 已被使用，请重新获取'}, status=400)

            # 验证是否过期（30 秒）
            if time.time() - stored_time > 30:
                # 清除过期 challenge
                for key in ['pow_challenge', 'pow_difficulty', 'pow_challenge_ip', 'pow_challenge_time', 'pow_challenge_used']:
                    request.session.pop(key, None)
                return JsonResponse({'error': 'Challenge 已过期，请刷新重试'}, status=400)

            # 验证 IP（记录警告但不拒绝，移动端 IP 可能变化）
            if stored_ip != client_ip:
                logger.warning(f"[PoW] IP 不匹配: stored={stored_ip}, current={client_ip}")

            # 验证 nonce
            if not nonce:
                return JsonResponse({'error': '缺少 nonce'}, status=400)

            # 计算 SHA256(prefix + nonce)
            hash_input = f"{stored_prefix}{nonce}"
            hash_result = hashlib.sha256(hash_input.encode()).hexdigest()

            # 检查前 N 位是否为 0
            expected_prefix = '0' * stored_difficulty

            # 调试日志
            logger.info(f"[PoW DEBUG] prefix={stored_prefix}, nonce={nonce}, input={hash_input}")
            logger.info(f"[PoW DEBUG] hash={hash_result}, expected_prefix={expected_prefix}, match={hash_result.startswith(expected_prefix)}")

            if not hash_result.startswith(expected_prefix):
                logger.warning(f"[PoW] 验证失败 (IP: {client_ip}): hash={hash_result[:16]}...")
                return JsonResponse({'error': 'PoW 验证失败'}, status=400)

            # PoW 验证通过，标记 challenge 已使用
            request.session['pow_challenge_used'] = True

            # 生成 init_token
            init_token = secrets.token_urlsafe(32)

            # 存储 init_token（用于后续验证码生成）
            request.session['captcha_init_token'] = init_token
            request.session['captcha_init_ip'] = client_ip
            request.session['captcha_init_time'] = time.time()

            # 清除 PoW challenge（已完成使命）
            for key in ['pow_challenge', 'pow_difficulty', 'pow_challenge_ip', 'pow_challenge_time', 'pow_challenge_used']:
                request.session.pop(key, None)

            logger.debug(f"[PoW] 验证通过 (IP: {client_ip}, nonce: {nonce[:16]}..., hash: {hash_result[:8]}...)")

            return JsonResponse({
                'status': 'success',
                'init_token': init_token,
                'expires_in': CAPTCHA_CONFIG['init_token_ttl']
            })

        except json.JSONDecodeError:
            return JsonResponse({'error': '无效的 JSON 数据'}, status=400)
        except Exception as e:
            logger.error(f"PoW 验证失败: {str(e)}")
            return JsonResponse({'error': '验证失败'}, status=500)

    else:
        return JsonResponse({'error': '只支持 GET/POST 请求'}, status=405)


def _verify_captcha_init_token(request, init_token):
    """
    验证 init_token 的有效性
    返回: (bool, str) - (是否有效, 错误信息)
    """
    from knowledge_project.utils.request_utils import get_client_ip

    if not init_token:
        return False, '缺少初始化令牌'

    stored_token = request.session.get('captcha_init_token')
    stored_ip = request.session.get('captcha_init_ip')
    stored_time = request.session.get('captcha_init_time', 0)

    if not stored_token:
        return False, '请先初始化验证码'

    if init_token != stored_token:
        return False, '令牌无效'

    # 验证 IP 是否匹配（记录警告但不拒绝，避免影响移动端用户）
    client_ip = get_client_ip(request)
    if stored_ip != client_ip:
        logger.warning(f"[验证码] IP不匹配: stored={stored_ip}, current={client_ip}")

    # 验证是否过期
    if time.time() - stored_time > CAPTCHA_CONFIG['init_token_ttl']:
        request.session.pop('captcha_init_token', None)
        request.session.pop('captcha_init_ip', None)
        request.session.pop('captcha_init_time', None)
        return False, '令牌已过期，请刷新页面'

    return True, None


def _check_captcha_rate_limits(request):
    """
    检查验证码请求的限流和熔断
    返回: (bool, str) - (是否允许, 错误信息)
    """
    from knowledge_project.utils.request_utils import get_client_ip, check_rate_limit_atomic

    client_ip = get_client_ip(request)

    # 1. 单 IP 限流检查
    ip_key = f"captcha_ip_limit_{client_ip}"
    ip_allowed, ip_count = check_rate_limit_atomic(
        ip_key,
        CAPTCHA_CONFIG['ip_rate_limit'],
        CAPTCHA_CONFIG['ip_rate_window']
    )

    if not ip_allowed:
        logger.warning(f"[验证码限流] IP {client_ip} 超过限制 ({ip_count}/{CAPTCHA_CONFIG['ip_rate_limit']})")
        return False, '请求过于频繁，请稍后再试'

    # 2. 全局熔断检查
    global_key = "captcha_global_limit"
    global_allowed, global_count = check_rate_limit_atomic(
        global_key,
        CAPTCHA_CONFIG['global_rate_limit'],
        CAPTCHA_CONFIG['global_rate_window']
    )

    if not global_allowed:
        logger.critical(f"[验证码熔断] 全局请求量超过阈值 ({global_count}/{CAPTCHA_CONFIG['global_rate_limit']}), IP: {client_ip}")
        return False, '系统繁忙，请稍后再试'

    return True, None


@csrf_exempt
def captcha_generate(request):
    """
    生成图形验证码（纵深防御版本）

    安全措施：
    1. 必须携带有效的 init_token（防止直接调用）
    2. 单 IP 限流（每分钟最多 10 次）
    3. 全局熔断（每分钟最多 100 次，防止分布式攻击）
    4. 生成延迟（500ms，防止 CPU 耗尽攻击）
    """
    if request.method != 'GET':
        return JsonResponse({'error': '只支持GET请求'}, status=405)

    try:
        from knowledge_project.utils.request_utils import get_client_ip

        client_ip = get_client_ip(request)

        # 1. 验证 init_token
        init_token = request.GET.get('token', '')
        token_valid, token_error = _verify_captcha_init_token(request, init_token)
        if not token_valid:
            logger.warning(f"[验证码] 令牌验证失败 (IP: {client_ip}): {token_error}")
            return JsonResponse({'error': token_error}, status=403)

        # 2. 限流和熔断检查
        rate_allowed, rate_error = _check_captcha_rate_limits(request)
        if not rate_allowed:
            return JsonResponse({'error': rate_error}, status=429)

        # 3. 延迟生成（防止 CPU 耗尽攻击）
        time.sleep(CAPTCHA_CONFIG['generate_delay'])

        # 4. 生成验证码
        img, code = check_code()

        # 将验证码存入 session
        request.session['image_captcha'] = code.upper()
        request.session['image_captcha_time'] = time.time()

        # 5. 使 init_token 失效（一次性使用）
        request.session.pop('captcha_init_token', None)
        request.session.pop('captcha_init_ip', None)
        request.session.pop('captcha_init_time', None)

        # 将图片转为二进制流返回
        buf = BytesIO()
        img.save(buf, 'PNG')
        buf.seek(0)

        logger.debug(f"[验证码] 生成成功 (IP: {client_ip})")

        return HttpResponse(buf.getvalue(), content_type='image/png')

    except Exception as e:
        logger.error(f"生成验证码失败: {str(e)}")
        return JsonResponse({'error': '验证码生成失败'}, status=500)


def verify_image_captcha(request, user_input):
    """
    验证图形验证码
    :param request: Django request 对象
    :param user_input: 用户输入的验证码
    :return: (bool, str) - (是否验证通过, 错误信息)
    """
    if not user_input:
        return False, '请输入验证码'

    stored_code = request.session.get('image_captcha')
    captcha_time = request.session.get('image_captcha_time', 0)

    if not stored_code:
        return False, '验证码已过期，请刷新'

    # 验证码有效期 5 分钟
    if time.time() - captcha_time > 300:
        # 清除过期验证码
        request.session.pop('image_captcha', None)
        request.session.pop('image_captcha_time', None)
        return False, '验证码已过期，请刷新'

    # 不区分大小写比较
    if user_input.upper() != stored_code.upper():
        return False, '验证码错误'

    # 验证成功后清除验证码（一次性使用）
    request.session.pop('image_captcha', None)
    request.session.pop('image_captcha_time', None)

    return True, None


def verify_captcha_unified(request, turnstile_token=None, image_captcha=None, captcha_type='turnstile'):
    """
    统一的验证码验证函数，支持 Turnstile 和图形验证码
    :param request: Django request 对象
    :param turnstile_token: Turnstile token
    :param image_captcha: 图形验证码
    :param captcha_type: 验证类型 'turnstile' 或 'image'
    :return: (bool, str) - (是否验证通过, 错误信息)
    """
    from knowledge_project.utils.request_utils import get_client_ip

    # 统一使用工具函数获取真实 IP
    client_ip = get_client_ip(request)

    if captcha_type == 'turnstile':
        if not turnstile_token:
            return False, '请完成人机验证'
        if not verify_turnstile_token(turnstile_token, client_ip):
            return False, '人机验证失败，请重试'
        return True, None

    elif captcha_type == 'image':
        return verify_image_captcha(request, image_captcha)

    else:
        return False, '未知的验证类型'
