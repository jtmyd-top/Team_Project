"""Compatibility module alias for accounts.auth.password_reset."""
import sys

from accounts.auth import password_reset as _module

sys.modules[__name__] = _module
