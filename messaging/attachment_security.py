"""Content-aware validation for direct and group message attachments."""

from __future__ import annotations

import os
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path


MAX_ARCHIVE_UNCOMPRESSED_BYTES = 250 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 100

_OLE_COMPOUND_HEADER = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
_IMAGE_SIGNATURES = {
    '.jpg': (b'\xff\xd8\xff', 'image/jpeg'),
    '.jpeg': (b'\xff\xd8\xff', 'image/jpeg'),
    '.png': (b'\x89PNG\r\n\x1a\n', 'image/png'),
    '.gif': ((b'GIF87a', b'GIF89a'), 'image/gif'),
}
_EXPECTED_MIME_TYPES = {
    '.jpg': {'image/jpeg'},
    '.jpeg': {'image/jpeg'},
    '.png': {'image/png'},
    '.gif': {'image/gif'},
    '.webp': {'image/webp'},
    '.webm': {'audio/webm', 'video/webm'},
    '.ogg': {'audio/ogg'},
    '.mp3': {'audio/mpeg'},
    '.mp4': {'audio/mp4', 'video/mp4'},
    '.wav': {'audio/wav', 'audio/x-wav'},
    '.mov': {'video/quicktime'},
    '.pdf': {'application/pdf'},
    '.zip': {'application/zip', 'application/x-zip-compressed'},
    '.doc': {'application/msword'},
    '.docx': {'application/vnd.openxmlformats-officedocument.wordprocessingml.document'},
    '.xls': {'application/vnd.ms-excel'},
    '.xlsx': {'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},
    '.ppt': {'application/vnd.ms-powerpoint'},
    '.pptx': {'application/vnd.openxmlformats-officedocument.presentationml.presentation'},
    '.txt': {'text/plain'},
    '.md': {'text/markdown'},
}


@dataclass(frozen=True)
class AttachmentInspection:
    original_name: str
    mime_type: str
    attachment_type: str


def _read_header(uploaded, size=8192):
    position = uploaded.tell()
    try:
        uploaded.seek(0)
        return uploaded.read(size)
    finally:
        uploaded.seek(position)


def _normalized_filename(raw_name):
    name = unicodedata.normalize('NFC', os.path.basename(raw_name or 'attachment'))
    name = ''.join(char for char in name if char >= ' ' and char not in '\x7f')
    name = name.strip(' .')
    return (name or 'attachment')[:255]


def _is_zip_container(header):
    return header.startswith((b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'))


def _validate_zip_container(uploaded):
    position = uploaded.tell()
    try:
        uploaded.seek(0)
        with zipfile.ZipFile(uploaded) as archive:
            total_uncompressed = 0
            total_compressed = 0
            for entry in archive.infolist():
                normalized = entry.filename.replace('\\', '/')
                if entry.flag_bits & 0x1:
                    return '不允许上传加密压缩包。'
                if normalized.startswith('/') or '..' in Path(normalized).parts:
                    return '压缩包包含不安全的文件路径。'
                total_uncompressed += entry.file_size
                total_compressed += entry.compress_size
                if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    return '压缩包解压后的内容过大。'
            if total_compressed and total_uncompressed / total_compressed > MAX_ARCHIVE_COMPRESSION_RATIO:
                return '压缩包压缩比异常。'
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile):
        return '压缩包内容无效。'
    finally:
        uploaded.seek(position)
    return ''


def _is_valid_content(extension, header, uploaded):
    if extension in _IMAGE_SIGNATURES:
        signatures, _mime = _IMAGE_SIGNATURES[extension]
        if isinstance(signatures, bytes):
            signatures = (signatures,)
        return any(header.startswith(signature) for signature in signatures), ''
    if extension == '.webp':
        return header.startswith(b'RIFF') and header[8:12] == b'WEBP', ''
    if extension == '.pdf':
        return header.startswith(b'%PDF-'), ''
    if extension in {'.zip', '.docx', '.xlsx', '.pptx'}:
        if not _is_zip_container(header):
            return False, ''
        return True, _validate_zip_container(uploaded)
    if extension in {'.doc', '.xls', '.ppt'}:
        return header.startswith(_OLE_COMPOUND_HEADER), ''
    if extension == '.ogg':
        return header.startswith(b'OggS'), ''
    if extension == '.mp3':
        return header.startswith(b'ID3') or (len(header) >= 2 and header[0] == 0xff and header[1] & 0xe0 == 0xe0), ''
    if extension == '.wav':
        return header.startswith(b'RIFF') and header[8:12] == b'WAVE', ''
    if extension in {'.mp4', '.mov'}:
        return len(header) >= 12 and header[4:8] == b'ftyp', ''
    if extension == '.webm':
        return header.startswith(b'\x1a\x45\xdf\xa3'), ''
    if extension in {'.txt', '.md'}:
        return b'\x00' not in header, ''
    return False, ''


def inspect_message_attachment(uploaded) -> tuple[AttachmentInspection | None, str]:
    """Return canonical metadata, or a user-facing validation error."""
    if not uploaded:
        return None, '没有找到上传的文件。'
    if not getattr(uploaded, 'size', 0):
        return None, '上传文件不能为空。'

    original_name = _normalized_filename(getattr(uploaded, 'name', ''))
    extension = Path(original_name).suffix.lower()
    expected_mime_types = _EXPECTED_MIME_TYPES.get(extension)
    if not expected_mime_types:
        return None, '文件扩展名不受支持。'

    declared_mime = (getattr(uploaded, 'content_type', '') or '').lower().split(';', 1)[0].strip()
    if declared_mime not in expected_mime_types:
        return None, '文件类型与扩展名不匹配。'

    valid, archive_error = _is_valid_content(extension, _read_header(uploaded), uploaded)
    if archive_error:
        return None, archive_error
    if not valid:
        return None, '文件内容与声明的格式不匹配。'

    if extension in {'.jpg', '.jpeg', '.png', '.gif', '.webp'}:
        attachment_type = 'image'
    elif extension in {'.ogg', '.mp3', '.wav'} or declared_mime == 'audio/mp4' or declared_mime == 'audio/webm':
        attachment_type = 'audio'
    elif extension in {'.webm', '.mp4', '.mov'}:
        attachment_type = 'video'
    else:
        attachment_type = 'file'
    canonical_mime = 'application/zip' if extension == '.zip' else declared_mime
    return AttachmentInspection(original_name, canonical_mime, attachment_type), ''
