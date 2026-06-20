"""Compatibility module alias for accounts.auth._shared."""
import sys

from accounts.auth import _shared as _module

sys.modules[__name__] = _module
