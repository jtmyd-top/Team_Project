"""Compatibility module alias for accounts.auth.two_factor."""
import sys

from accounts.auth import two_factor as _module

sys.modules[__name__] = _module
