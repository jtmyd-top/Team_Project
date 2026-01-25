"""
目录提取工具 - 基于 BeautifulSoup
用于从 HTML 内容中提取标题结构，并自动为标题添加 ID
"""

from bs4 import BeautifulSoup
import re
import uuid
from django.utils.text import slugify


def extract_toc_from_html(html_content):
    """
    从 HTML 内容中提取目录结构，并为标题自动添加 ID

    Args:
        html_content: 原始 HTML 内容字符串

    Returns:
        tuple: (toc_list, updated_html)
            - toc_list: 目录列表，每个元素包含 {text, level, id}
            - updated_html: 注入了 ID 的新 HTML 内容
    """
    if not html_content:
        return [], html_content

    soup = BeautifulSoup(html_content, 'html.parser')
    toc = []

    # 查找所有 h1 到 h6 标签
    headers = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

    if not headers:
        return [], html_content

    # 用于跟踪已使用的 ID，避免重复
    used_ids = set()

    # 遍历标题
    for header in headers:
        # 获取纯文本
        text = header.get_text().strip()
        if not text:
            continue

        # 获取层级 (h1 -> 1, h2 -> 2)
        level = int(header.name[1])

        # 获取或生成 ID
        header_id = header.get('id')

        if not header_id:
            # 生成基于文本的 slug
            base_id = slugify(text)[:50]  # 限制长度
            header_id = base_id

            # 确保唯一性
            counter = 1
            while header_id in used_ids:
                counter += 1
                header_id = f"{base_id}-{counter}"

            header['id'] = header_id

        used_ids.add(header_id)

        toc.append({
            'text': text,
            'level': level,
            'id': header_id
        })

    # 返回目录列表和更新后的 HTML
    # 使用 str() 而不是 prettify() 来避免改变 HTML 格式
    updated_html = str(soup)

    return toc, updated_html


def build_nested_toc(toc_list):
    """
    将扁平的目录列表转换为嵌套结构（用于渲染多级菜单）

    Args:
        toc_list: 扁平的目录列表

    Returns:
        list: 嵌套的目录结构
    """
    if not toc_list:
        return []

    nested = []
    stack = []  # 存储当前路径的父级节点

    for item in toc_list:
        node = {
            **item,
            'children': []
        }

        # 弹出栈中层级大于等于当前节点的元素
        while stack and stack[-1]['level'] >= item['level']:
            stack.pop()

        if stack:
            # 添加为子节点
            stack[-1]['children'].append(node)
        else:
            # 添加为根节点
            nested.append(node)

        # 当前节点入栈
        stack.append(node)

    return nested


def inject_heading_ids(html_content):
    """
    仅注入 ID 到标题，不提取目录（用于轻量级处理）

    Args:
        html_content: 原始 HTML 内容

    Returns:
        str: 注入了 ID 的 HTML 内容
    """
    toc, updated_html = extract_toc_from_html(html_content)
    return updated_html
