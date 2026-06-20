# knowledge_project/views/message/_constants.py
"""私信子包共用常量"""

# 撤回时间窗口（秒）
RECALL_WINDOW_SECONDS = 120

# 每天主动发起新对话（陌生人）的免验证配额，超过后必须通过 Turnstile
NEW_CONV_DAILY_LIMIT = 5
# 同一接收者的新私信邮件节流窗口（秒）
EMAIL_NOTIFY_WINDOW_SECONDS = 30 * 60
SESSION_LAST_ACTIVITY_KEY = 'last_activity_at'
MESSAGES_PAGE_ACTIVE_AT_KEY = 'messages_page_active_at'
ONLINE_SKIP_EMAIL_WINDOW_SECONDS = 5 * 60
MESSAGES_PAGE_SKIP_EMAIL_WINDOW_SECONDS = 2 * 60
MESSAGE_PURGE_DELAY_DAYS = 7
MESSAGE_ATTACHMENT_MAX_COUNT = 6
MESSAGE_IMAGE_MAX_SIZE = 10 * 1024 * 1024
MESSAGE_AUDIO_MAX_SIZE = 12 * 1024 * 1024
MESSAGE_VIDEO_MAX_SIZE = 120 * 1024 * 1024
MESSAGE_FILE_MAX_SIZE = 25 * 1024 * 1024
MESSAGE_IMAGE_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
MESSAGE_AUDIO_MIME_TYPES = {'audio/webm', 'audio/ogg', 'audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/x-wav'}
MESSAGE_VIDEO_MIME_TYPES = {'video/mp4', 'video/webm', 'video/quicktime'}
MESSAGE_FILE_MIME_TYPES = {
    'application/pdf',
    'application/zip',
    'application/x-zip-compressed',
    'text/plain',
    'text/markdown',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
}
MESSAGE_CONTENT_MAX_LENGTH = 5000
MERGED_FORWARD_PREFIX = '__MERGED_FORWARD_V1__:'
MERGED_FORWARD_MAX_ITEMS = 99
MERGED_FORWARD_MAX_ENCODED_LENGTH = 100000
MERGED_FORWARD_MAX_DEPTH = 3
MERGED_FORWARD_MAX_SEARCHABLE_TEXT = 50000
MERGED_FORWARD_MAX_FIELD_LENGTH = 12000
