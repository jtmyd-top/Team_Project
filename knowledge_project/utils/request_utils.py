import ipaddress
import logging

from django.conf import settings


logger = logging.getLogger(__name__)


def _parse_ip(value):
    if not value:
        return None
    try:
        return ipaddress.ip_address(str(value).strip())
    except ValueError:
        return None


def _parse_forwarded_chain(header_value):
    if not header_value:
        return []

    chain = []
    for part in str(header_value).split(','):
        parsed = _parse_ip(part)
        if parsed is not None:
            chain.append(str(parsed))
    return chain


def _trusted_proxy_networks():
    raw_values = getattr(settings, 'TRUSTED_PROXY_CIDRS', [])
    networks = []

    for raw_value in raw_values:
        try:
            networks.append(ipaddress.ip_network(raw_value, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid TRUSTED_PROXY_CIDRS entry: %s", raw_value)

    return networks


def _is_trusted_proxy(ip_value, trusted_networks):
    parsed_ip = _parse_ip(ip_value)
    if parsed_ip is None:
        return False
    return any(parsed_ip in network for network in trusted_networks)


def get_client_ip(request):
    """
    Return the client IP while only trusting proxy headers from known proxies.
    """
    remote_addr = request.META.get('REMOTE_ADDR')
    if not remote_addr:
        return '0.0.0.0'

    trusted_networks = _trusted_proxy_networks()
    if not _is_trusted_proxy(remote_addr, trusted_networks):
        return remote_addr

    forwarded_chain = _parse_forwarded_chain(request.META.get('HTTP_X_FORWARDED_FOR'))
    if forwarded_chain:
        for candidate in reversed(forwarded_chain + [remote_addr]):
            if not _is_trusted_proxy(candidate, trusted_networks):
                return candidate
        return forwarded_chain[0]

    x_real_ip = _parse_ip(request.META.get('HTTP_X_REAL_IP'))
    if x_real_ip is not None:
        return str(x_real_ip)

    return remote_addr


def check_rate_limit_atomic(key, limit, timeout):
    """
    Atomic rate-limit check with a Redis implementation when available.
    """
    try:
        from knowledge_project.utils.redis_rate_limiter import check_redis_rate_limit
        return check_redis_rate_limit(key, limit, timeout)
    except ImportError:
        from django.core.cache import cache

        logger.warning("Redis rate limiter unavailable, falling back to cache ops")

        try:
            current_count = cache.get(key, 0)
            if current_count >= limit:
                return False, current_count

            new_count = cache.incr(key)
            if new_count == 1:
                cache.expire(key, timeout)
            return new_count <= limit, new_count
        except Exception as exc:
            logger.error("Fallback rate limiter failed: %s", exc)
            return True, 0
