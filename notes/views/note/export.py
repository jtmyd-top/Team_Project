"""Note export views — download a note as Markdown or standalone HTML.

The HTML→Markdown conversion is built on BeautifulSoup (already a dependency)
so we don't pull in an extra package. It covers the tag set that notes can
actually contain (see ``Note.save`` sanitizer allowlist): headings, lists,
links, images, code, blockquotes, tables, and inline emphasis.
"""
from .common import *  # noqa: F401, F403

from django.http import HttpResponse
from django.utils.text import slugify


def _inline_to_md(node):
    """Render an inline/flow node's children to Markdown text."""
    from bs4 import NavigableString

    parts = []
    for child in getattr(node, 'children', []):
        if isinstance(child, NavigableString):
            parts.append(str(child))
            continue

        name = child.name
        inner = _inline_to_md(child)
        if name in ('strong', 'b'):
            parts.append(f'**{inner}**')
        elif name in ('em', 'i'):
            parts.append(f'*{inner}*')
        elif name in ('code',):
            parts.append(f'`{inner}`')
        elif name in ('del', 'strike', 's'):
            parts.append(f'~~{inner}~~')
        elif name == 'a':
            href = child.get('href', '')
            parts.append(f'[{inner}]({href})' if href else inner)
        elif name == 'img':
            alt = child.get('alt', '')
            src = child.get('src', '')
            parts.append(f'![{alt}]({src})')
        elif name == 'br':
            parts.append('  \n')
        else:
            parts.append(inner)
    return ''.join(parts)


def _block_to_md(node, depth=0):
    """Render a block-level node to a Markdown fragment."""
    from bs4 import NavigableString

    name = getattr(node, 'name', None)
    if name is None:
        text = str(node).strip()
        return text if text else ''

    if name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
        level = int(name[1])
        return f'{"#" * level} {_inline_to_md(node).strip()}\n'

    if name == 'p':
        return f'{_inline_to_md(node).strip()}\n'

    if name == 'blockquote':
        inner = '\n'.join(
            _block_to_md(child, depth).strip()
            for child in node.children
            if not isinstance(child, NavigableString) or child.strip()
        ).strip()
        return '\n'.join(f'> {line}' for line in inner.splitlines()) + '\n'

    if name == 'pre':
        code = node.get_text()
        return f'```\n{code.rstrip()}\n```\n'

    if name in ('ul', 'ol'):
        lines = []
        ordered = name == 'ol'
        index = 1
        for li in node.find_all('li', recursive=False):
            marker = f'{index}.' if ordered else '-'
            text = _inline_to_md(li).strip()
            # Take only the direct inline text; nested lists handled recursively.
            first_line = text.splitlines()[0] if text else ''
            lines.append(f'{"  " * depth}{marker} {first_line}')
            for sub in li.find_all(['ul', 'ol'], recursive=False):
                lines.append(_block_to_md(sub, depth + 1).rstrip())
            index += 1
        return '\n'.join(lines) + '\n'

    if name == 'table':
        return _table_to_md(node)

    if name == 'hr':
        return '---\n'

    if name in ('div', 'section', 'article', 'figure'):
        return '\n'.join(
            _block_to_md(child, depth)
            for child in node.children
            if not isinstance(child, NavigableString) or child.strip()
        )

    return _inline_to_md(node).strip() + '\n'


def _table_to_md(table):
    rows = table.find_all('tr')
    if not rows:
        return ''
    md_rows = []
    for i, tr in enumerate(rows):
        cells = tr.find_all(['th', 'td'])
        md_rows.append('| ' + ' | '.join(_inline_to_md(c).strip() for c in cells) + ' |')
        if i == 0:
            md_rows.append('| ' + ' | '.join('---' for _ in cells) + ' |')
    return '\n'.join(md_rows) + '\n'


def html_to_markdown(html, title=''):
    """Convert sanitized note HTML into a Markdown document."""
    from bs4 import BeautifulSoup, NavigableString

    soup = BeautifulSoup(html or '', 'html.parser')
    blocks = []
    for child in soup.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                blocks.append(text)
            continue
        fragment = _block_to_md(child)
        if fragment.strip():
            blocks.append(fragment.rstrip())

    body = '\n\n'.join(blocks).strip()
    header = f'# {title.strip()}\n\n' if title and title.strip() else ''
    return f'{header}{body}\n'


def _safe_filename(title, extension):
    base = slugify(title) or 'note'
    # slugify drops non-ASCII (CJK); fall back to a readable ASCII-only stem.
    return f'{base[:60]}.{extension}'


@login_required
@require_http_methods(["GET"])
def export_note_api(request, note_id):
    """Export a note as Markdown (``?format=md``) or standalone HTML.

    Secret (vault) notes are never exported server-side: their content is E2E
    encrypted, so a server export would leak ciphertext with no benefit.
    """
    note = get_object_or_404(Note, pk=note_id)
    if not note.has_read_permission(request.user):
        return JsonResponse({'error': '您没有权限访问此笔记'}, status=403)
    if note.is_secret:
        return JsonResponse({'error': '保密笔记无法导出'}, status=400)

    export_format = (request.GET.get('format') or 'md').lower()
    content = note.content or ''

    if export_format in ('md', 'markdown'):
        markdown = html_to_markdown(content, note.title)
        response = HttpResponse(markdown, content_type='text/markdown; charset=utf-8')
        filename = _safe_filename(note.title, 'md')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    if export_format == 'html':
        document = (
            '<!DOCTYPE html>\n<html lang="zh">\n<head>\n'
            '<meta charset="utf-8">\n'
            f'<title>{note.title}</title>\n'
            '<style>body{max-width:760px;margin:40px auto;padding:0 20px;'
            'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;'
            'line-height:1.7;color:#1a1a1a}img{max-width:100%}'
            'pre{background:#f5f5f5;padding:12px;border-radius:8px;overflow:auto}'
            'blockquote{border-left:3px solid #ddd;margin:0;padding-left:16px;color:#666}'
            'table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:6px 10px}'
            '</style>\n</head>\n<body>\n'
            f'<h1>{note.title}</h1>\n{content}\n</body>\n</html>\n'
        )
        response = HttpResponse(document, content_type='text/html; charset=utf-8')
        filename = _safe_filename(note.title, 'html')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    return JsonResponse({'error': '不支持的导出格式'}, status=400)
