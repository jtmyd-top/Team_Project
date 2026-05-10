import base64
import binascii
import json

from django.db import migrations


MERGED_FORWARD_PREFIX = '__MERGED_FORWARD_V1__:'
MERGED_FORWARD_MAX_DEPTH = 3
MERGED_FORWARD_MAX_ITEMS = 99
MERGED_FORWARD_MAX_SEARCHABLE_TEXT = 50000
MESSAGE_ATTACHMENT_MAX_COUNT = 6


def parse_merged_forward(content):
    raw = (content or '').strip()
    if not raw.startswith(MERGED_FORWARD_PREFIX):
        return None
    try:
        encoded = raw[len(MERGED_FORWARD_PREFIX):].encode('ascii')
        decoded = base64.b64decode(encoded, validate=True).decode('utf-8')
        data = json.loads(decoded)
    except (UnicodeDecodeError, binascii.Error, ValueError, TypeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get('type') != 'merged_forward':
        return None
    if not isinstance(data.get('items'), list):
        return None
    return data


def merged_forward_text(data, depth=0):
    if not data or depth > MERGED_FORWARD_MAX_DEPTH:
        return ''
    parts = [
        str(data.get('title') or ''),
        str(data.get('source') or ''),
    ]
    for item in data.get('items', [])[:MERGED_FORWARD_MAX_ITEMS]:
        if not isinstance(item, dict):
            continue
        parts.append(str(item.get('sender') or ''))
        content = str(item.get('content') or '')
        nested = parse_merged_forward(content) if depth < MERGED_FORWARD_MAX_DEPTH else None
        parts.append(merged_forward_text(nested, depth + 1) if nested else content)
        parts.append(str(item.get('preview') or ''))
        attachments = item.get('attachments') if isinstance(item.get('attachments'), list) else []
        for attachment in attachments[:MESSAGE_ATTACHMENT_MAX_COUNT]:
            if isinstance(attachment, dict):
                parts.append(str(attachment.get('name') or ''))
    return '\n'.join(part for part in parts if part).strip()[:MERGED_FORWARD_MAX_SEARCHABLE_TEXT]


def backfill_merged_forward_searchable_text(apps, schema_editor):
    Message = apps.get_model('knowledge_project', 'Message')
    qs = Message.objects.filter(content__startswith=MERGED_FORWARD_PREFIX).only('id', 'content', 'searchable_text')
    for message in qs.iterator(chunk_size=500):
        data = parse_merged_forward(message.content)
        text = merged_forward_text(data)
        if text and text != message.searchable_text:
            message.searchable_text = text
            message.save(update_fields=['searchable_text'])


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_project', '0026_message_searchable_text_alter_message_content'),
    ]

    operations = [
        migrations.RunPython(backfill_merged_forward_searchable_text, migrations.RunPython.noop),
    ]
