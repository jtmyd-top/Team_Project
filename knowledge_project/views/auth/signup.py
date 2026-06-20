"""Compatibility module alias for accounts.auth.signup."""
import sys

from accounts.auth import signup as _module

sys.modules[__name__] = _module
