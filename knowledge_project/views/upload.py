import sys

from notes.views import upload as _upload

sys.modules[__name__] = _upload
