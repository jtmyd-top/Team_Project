"""Compatibility module alias for accounts.captcha."""
import sys

from accounts import captcha as _module

sys.modules[__name__] = _module
