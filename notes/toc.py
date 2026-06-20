"""Table-of-contents helpers for note HTML content."""

from bs4 import BeautifulSoup
from django.utils.text import slugify


def extract_toc_from_html(html_content):
    if not html_content:
        return [], html_content

    soup = BeautifulSoup(html_content, 'html.parser')
    toc = []
    headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

    if not headers:
        return [], html_content

    used_ids = set()

    for header in headers:
        text = header.get_text().strip()
        if not text:
            continue

        level = int(header.name[1])
        header_id = header.get('id')

        if not header_id:
            base_id = slugify(text)[:50]
            header_id = base_id

            counter = 1
            while header_id in used_ids:
                counter += 1
                header_id = f'{base_id}-{counter}'

            header['id'] = header_id

        used_ids.add(header_id)
        toc.append({
            'text': text,
            'level': level,
            'id': header_id,
        })

    return toc, str(soup)


def build_nested_toc(toc_list):
    if not toc_list:
        return []

    nested = []
    stack = []

    for item in toc_list:
        node = {
            **item,
            'children': [],
        }

        while stack and stack[-1]['level'] >= item['level']:
            stack.pop()

        if stack:
            stack[-1]['children'].append(node)
        else:
            nested.append(node)

        stack.append(node)

    return nested


def inject_heading_ids(html_content):
    _, updated_html = extract_toc_from_html(html_content)
    return updated_html
