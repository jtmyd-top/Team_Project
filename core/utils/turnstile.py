import logging

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


logger = logging.getLogger(__name__)


def _is_enabled():
    enabled = getattr(settings, "TURNSTILE_ENABLED", True)
    if isinstance(enabled, str):
        return enabled.lower() not in {"false", "0", "no"}
    return bool(enabled)


TURNSTILE_ENABLED = _is_enabled()


class TurnstileValidator:
    def __init__(self):
        self.site_key = getattr(settings, "CLOUDFLARE_TURNSTILE_SITE_KEY", None)
        self.secret_key = getattr(settings, "CLOUDFLARE_TURNSTILE_SECRET_KEY", None)
        self.verify_url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

        if not self.site_key or not self.secret_key:
            raise ImproperlyConfigured(
                "CLOUDFLARE_TURNSTILE_SITE_KEY and "
                "CLOUDFLARE_TURNSTILE_SECRET_KEY must be set in settings"
            )

    def verify_token(self, token, remote_ip=None):
        if not token:
            return {
                "success": False,
                "error_codes": ["missing-input-response"],
                "message": "Missing turnstile token.",
            }

        data = {
            "secret": self.secret_key,
            "response": token,
        }
        if remote_ip:
            data["remoteip"] = remote_ip

        try:
            response = requests.post(self.verify_url, data=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            if result.get("success"):
                return {
                    "success": True,
                    "message": "Verification passed.",
                }
            return {
                "success": False,
                "error_codes": result.get("error-codes", []),
                "message": self._get_error_message(result.get("error-codes", [])),
            }
        except requests.RequestException as exc:
            logger.error("Turnstile verification request failed: %s", exc)
            return {
                "success": False,
                "error_codes": ["network-error"],
                "message": "Verification service is temporarily unavailable.",
            }
        except Exception as exc:
            logger.error("Turnstile verification failed unexpectedly: %s", exc)
            return {
                "success": False,
                "error_codes": ["internal-error"],
                "message": "Verification failed.",
            }

    @staticmethod
    def _get_error_message(error_codes):
        error_messages = {
            "missing-input-secret": "Server verification secret is missing.",
            "invalid-input-secret": "Server verification secret is invalid.",
            "missing-input-response": "Please complete the human verification.",
            "invalid-input-response": "Verification failed. Please try again.",
            "bad-request": "Invalid verification request.",
            "timeout-or-duplicate": "Verification expired or was already used.",
            "internal-error": "Verification service returned an internal error.",
        }
        for code in error_codes:
            if code in error_messages:
                return error_messages[code]
        return "Verification failed. Please try again."


try:
    turnstile_validator = TurnstileValidator()
except ImproperlyConfigured:
    logger.warning("Turnstile settings are missing; falling back to bypass mode.")
    turnstile_validator = None


def verify_turnstile_token(token, remote_ip=None):
    if not TURNSTILE_ENABLED:
        logger.warning("Turnstile disabled; skipping verification.")
        return True
    if not turnstile_validator:
        logger.warning("Turnstile validator unavailable; skipping verification.")
        return True
    result = turnstile_validator.verify_token(token, remote_ip)
    return result["success"]


def get_turnstile_verification_detail(token, remote_ip=None):
    if not TURNSTILE_ENABLED:
        return {"success": True, "message": "Turnstile disabled."}
    if not turnstile_validator:
        return {"success": True, "message": "Turnstile bypass enabled."}
    return turnstile_validator.verify_token(token, remote_ip)


def get_site_key():
    if not TURNSTILE_ENABLED or not turnstile_validator:
        return None
    return turnstile_validator.site_key


def is_turnstile_enabled():
    return TURNSTILE_ENABLED and turnstile_validator is not None
