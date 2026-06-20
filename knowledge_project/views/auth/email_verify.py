"""Compatibility module alias for accounts.auth.email_verify."""
import sys

from accounts.auth import email_verify as _module

sys.modules[__name__] = _module
