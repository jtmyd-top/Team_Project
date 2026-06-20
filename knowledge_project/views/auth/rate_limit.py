"""Compatibility module alias for accounts.auth.rate_limit."""
import sys

from accounts.auth import rate_limit as _module

sys.modules[__name__] = _module
