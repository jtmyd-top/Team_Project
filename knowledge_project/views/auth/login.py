"""Compatibility module alias for accounts.auth.login."""
import sys

from accounts.auth import login as _module

sys.modules[__name__] = _module
