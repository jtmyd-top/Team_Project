"""Helpers for serving local media through Django or X-Accel-Redirect."""
import os
import posixpath
import mimetypes

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.utils.encoding import iri_to_uri


def resolve_media_path(relative_path):
    """Return (normalized_relative_path, full_path) under MEDIA_ROOT."""
    raw_path = str(relative_path or '').replace('\\', '/')
    normalized = posixpath.normpath(raw_path).lstrip('/')
    if normalized in ('', '.') or normalized.startswith('../'):
        raise Http404

    media_root = os.path.normpath(settings.MEDIA_ROOT)
    full_path = os.path.normpath(os.path.join(media_root, *normalized.split('/')))
    if full_path != media_root and not full_path.startswith(media_root + os.sep):
        raise Http404
    return normalized, full_path


def media_file_response(relative_path, content_type=None, content_disposition=None):
    """Serve a MEDIA_ROOT file directly or hand it to Nginx via X-Accel."""
    normalized, full_path = resolve_media_path(relative_path)
    if not os.path.isfile(full_path):
        raise Http404

    if content_type is None:
        content_type = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'

    if getattr(settings, 'USE_X_ACCEL_REDIRECT', False):
        prefix = getattr(settings, 'X_ACCEL_REDIRECT_PREFIX', '/internal-media/')
        prefix = '/' + str(prefix).strip('/') + '/'
        response = HttpResponse(content_type=content_type)
        response['X-Accel-Redirect'] = iri_to_uri(f'{prefix}{normalized}')
        if content_disposition:
            response['Content-Disposition'] = content_disposition
        return response

    response = FileResponse(open(full_path, 'rb'), content_type=content_type)
    if content_disposition:
        response['Content-Disposition'] = content_disposition
    return response
