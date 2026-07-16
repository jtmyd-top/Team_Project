"""Content-aware validation for user-uploaded profile and group images."""

from __future__ import annotations

import warnings

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_PIXELS = 40_000_000
_FORMAT_TO_MIME = {
    'JPEG': 'image/jpeg',
    'PNG': 'image/png',
    'WEBP': 'image/webp',
    'GIF': 'image/gif',
}


def validate_image_upload(uploaded, *, allowed_mime_types: set[str]) -> str:
    """Return an empty string for a safe image upload, otherwise an error."""
    declared_mime = (getattr(uploaded, 'content_type', '') or '').lower().split(';', 1)[0]
    if declared_mime not in allowed_mime_types:
        return '\u4e0d\u652f\u6301\u8be5\u56fe\u7247\u683c\u5f0f\u3002'

    try:
        uploaded.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(uploaded) as image:
                image.verify()
            uploaded.seek(0)
            with Image.open(uploaded) as image:
                actual_mime = _FORMAT_TO_MIME.get(image.format)
                width, height = image.size
                image.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return '\u56fe\u7247\u50cf\u7d20\u8fc7\u5927\uff0c\u65e0\u6cd5\u5b89\u5168\u5904\u7406\u3002'
    except (OSError, UnidentifiedImageError, ValueError):
        return '\u56fe\u7247\u5185\u5bb9\u65e0\u6548\u6216\u4e0e\u58f0\u660e\u683c\u5f0f\u4e0d\u5339\u914d\u3002'
    finally:
        uploaded.seek(0)

    if actual_mime not in allowed_mime_types or actual_mime != declared_mime:
        return '\u56fe\u7247\u5185\u5bb9\u4e0e\u58f0\u660e\u683c\u5f0f\u4e0d\u5339\u914d\u3002'
    if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
        return '\u56fe\u7247\u50cf\u7d20\u8fc7\u5927\uff0c\u65e0\u6cd5\u5b89\u5168\u5904\u7406\u3002'
    return ''
