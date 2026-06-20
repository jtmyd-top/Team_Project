"""Compatibility module alias for asset upload/media views."""
import sys

from assets.views import upload as _upload

sys.modules[__name__] = _upload
