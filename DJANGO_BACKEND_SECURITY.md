# Django 後端安全加固實現

## 安全架構概述

本文檔描述了 Django 後端的兩層安全控制實現：

### 第一層：操作阻斷 (Action Blocking)
- 基於筆記狀態（回收站、保密等）阻止特定操作
- 返回 403 Forbidden 拒絕不允許的操作
- 位置：視圖層（Views）

### 第二層：數據最小化傳輸 (Data Minimization)
- 在 API 響應中動態過濾敏感字段
- 防止加密內容在不必要的情況下傳輸
- 位置：序列化層 & 視圖層（返回數據構建）

---

## 第一層：操作阻斷 (Action Blocking)

### 規則 A：回收站保護
**狀態**: `note.is_trashed = True`
**保護操作**: PUT/PATCH (編輯)
**允許操作**: restore (還原), destroy (永久刪除)
**响應**: 403 Forbidden

### 規則 B：保密柜保護
**狀態**: `note.is_secret = True`
**保護操作**: share (分享), star/favorite (收藏)
**响應**: 403 Forbidden

---

## 實現細節

### A. 輔助函數 (Helper Functions)

```python
# 添加到 knowledge_project/views.py 頂部（在其他函數定義之前）

def check_note_edit_permission(note):
    """
    檢查筆記是否允許編輯操作。

    Return: (allowed: bool, error_message: str or None)
    - 回收站筆記不允許編輯
    """
    if note.is_trashed:
        return False, '回收站中的筆記無法編輯。請先還原筆記。'
    return True, None


def check_note_secret_operation_permission(note, operation):
    """
    檢查筆記是否允許特定操作（針對保密柜）。

    Args:
        note: Note 模型實例
        operation: 'share', 'favorite' 等操作名稱

    Return: (allowed: bool, error_message: str or None)
    - 保密柜筆記不允許分享和收藏
    """
    if note.is_secret:
        messages = {
            'share': '保密柜的筆記無法分享。請先移出保密柜。',
            'favorite': '保密柜的筆記無法收藏。請先移出保密柜。',
            'publish': '保密柜的筆記無法發布為公開。請先移出保密柜。'
        }
        return False, messages.get(operation, f'保密柜的筆記無法執行 {operation} 操作。')
    return True, None


def build_note_response_data(note, include_content=True, include_all_fields=True):
    """
    構建筆記 API 響應數據，支持字段過濾。

    Args:
        note: Note 模型實例
        include_content: 是否包含 content 字段
        include_all_fields: 是否包含所有字段（True），或僅包含必要字段（False）

    Return: dict - 完整的應答數據結構

    說明：
    - 當 is_secret=True AND is_trashed=True 時，自動不包含 content
    - 前端可根據需要傳遞 include_content 參數
    """
    # 數據最小化：不傳輸敏感組合的加密內容
    if note.is_secret and note.is_trashed:
        include_content = False

    local_updated_at = timezone.localtime(note.updated_at)
    local_created_at = timezone.localtime(note.created_at)

    data = {
        'id': note.id,
        'title': note.title,
        'is_public': note.is_public,
        'is_secret': note.is_secret,
        'is_trashed': note.is_trashed,
        'public_url': f"/notes/public/{note.public_id}/" if note.public_id and note.is_public else "",
        'updated_at': local_updated_at.strftime('%Y-%m-%d %H:%M'),
        'created_at': local_created_at.strftime('%Y-%m-%d %H:%M'),
    }

    if include_content:
        data['content'] = note.content or ""

    if include_all_fields:
        data['author'] = {'id': note.author.id, 'username': note.author.username}
        data['last_modified_by'] = {'username': note.last_modified_by.username} if note.last_modified_by else None
        data['tags'] = [{'id': tag.id, 'name': tag.name} for tag in note.tags.all()]
        data['toc'] = note.toc or []

    return data
```

---

### B. 修改 note_detail_api (PATCH 方法)

**文件位置**: `knowledge_project/views.py` → `note_detail_api` 函數，PATCH 部分

**變更**: 添加回收站檢查，防止編輯回收站中的筆記

```python
# 在 PATCH 部分的開始添加安全檢查

if request.method == 'PATCH':
    # 【新增】安全檢查：回收站保護
    allowed, error_msg = check_note_edit_permission(note)
    if not allowed:
        return JsonResponse({'error': error_msg}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': '無效的JSON格式'}, status=400)

    try:
        # ... 現有的字段更新邏輯 ...
```

---

### C. 修改 PUT 方法 (編輯操作)

**文件位置**: `knowledge_project/views.py` → `note_detail_api` 函數，PUT 部分

**變更**: 添加回收站檢查

```python
if request.method == 'PUT':
    # 【新增】安全檢查：回收站保護
    allowed, error_msg = check_note_edit_permission(note)
    if not allowed:
        return JsonResponse({'error': error_msg}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': '無效的JSON格式'}, status=400)

    # ... 現有的更新邏輯 ...
```

---

### D. 修改 toggle_note_favorite_api (收藏操作)

**文件位置**: `knowledge_project/folder_views.py` → `toggle_note_favorite_api` 函數

**變更**: 添加保密柜檢查

```python
@login_required
@require_http_methods(["POST"])
def toggle_note_favorite_api(request, note_id):
    """切換筆記的收藏狀態"""
    user = request.user
    note = get_object_or_404(Note, id=note_id, author=user)

    # 【新增】安全檢查：保密柜保護
    allowed, error_msg = check_note_secret_operation_permission(note, 'favorite')
    if not allowed:
        return JsonResponse({'error': error_msg}, status=403)

    note.is_favorited = not note.is_favorited
    note.save(update_fields=['is_favorited'])

    return JsonResponse({
        'status': 'success',
        'is_favorited': note.is_favorited
    })
```

---

### E. 修改 PUT 方法中的 is_public 邏輯

**文件位置**: `knowledge_project/views.py` → `note_detail_api` 函數，PUT 部分

**變更**: 防止保密柜筆記被設為公開

```python
if request.method == 'PUT':
    allowed, error_msg = check_note_edit_permission(note)
    if not allowed:
        return JsonResponse({'error': error_msg}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': '無效的JSON格式'}, status=400)

    # 【新增】安全檢查：防止保密柜筆記發布為公開
    if data.get('is_public') and note.is_secret:
        allowed, error_msg = check_note_secret_operation_permission(note, 'publish')
        if not allowed:
            return JsonResponse({'error': error_msg}, status=403)

    note.title = data.get('title', note.title)
    note.is_public = data.get('is_public', note.is_public)
    # ... 其餘邏輯 ...
```

---

### F. 修改 PATCH 方法中的 is_public 邏輯

**文件位置**: `knowledge_project/views.py` → `note_detail_api` 函數，PATCH 部分

**變更**: 防止保密柜筆記被設為公開

```python
if request.method == 'PATCH':
    allowed, error_msg = check_note_edit_permission(note)
    if not allowed:
        return JsonResponse({'error': error_msg}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': '無效的JSON格式'}, status=400)

    try:
        # 【新增】安全檢查：防止保密柜筆記發布為公開
        if 'is_public' in data and data['is_public'] and note.is_secret:
            allowed, error_msg = check_note_secret_operation_permission(note, 'publish')
            if not allowed:
                return JsonResponse({'error': error_msg}, status=403)

        # 現有的字段更新邏輯...
```

---

## 第二層：數據最小化傳輸 (Data Minimization)

### GET 請求的應答過濾

**文件位置**: `knowledge_project/views.py` → `note_detail_api` 函數，GET 部分

**規則**: 當 `is_secret=True AND is_trashed=True` 時，不返回 `content` 字段

```python
if request.method == 'GET':
    # 決定是否包含 content 字段
    include_content = True

    # 【新增】數據最小化：敏感場景下不傳輸加密內容
    if note.is_secret and note.is_trashed:
        include_content = False

    if request.GET.get('full_content') == 'true':
        data = build_note_response_data(
            note,
            include_content=include_content,
            include_all_fields=True
        )
        return JsonResponse(data)

    page = request.GET.get('page', 1)
    paginated_content, total_pages = get_paginated_html(note.content, page) if include_content else ("", 1)

    data = build_note_response_data(
        note,
        include_content=include_content,
        include_all_fields=True
    )

    if include_content:
        data['content'] = paginated_content
        data['pagination'] = {
            'current_page': int(page),
            'total_pages': total_pages,
        }
    else:
        # 提示前端為什麼沒有內容
        data['content_locked'] = True
        data['lock_reason'] = '此筆記位於回收站中，內容已鎖定。'

    return JsonResponse(data)
```

---

## 第三層：通用邏輯檢查表

| 操作 | 觸發器 | 安全檢查 | 響應碼 |
|-----|------|--------|-------|
| 編輯 (PUT/PATCH) | 任何修改 | `is_trashed` 檢查 | 403 |
| 發布 (is_public=True) | 修改 is_public | `is_secret` 檢查 | 403 |
| 收藏 (toggle_favorite) | POST /favorite | `is_secret` 檢查 | 403 |
| 讀取 (GET) | 任何查詢 | 按需過濾 content | 200 (filtered) |

---

## 完整流程示例

### 場景 1：用戶嘗試編輯回收站筆記

```
Request: PATCH /api/notes/123/
Body: {"title": "新標題"}

檢查: note.is_trashed == True
↓
返回: HTTP 403
{
  "error": "回收站中的筆記無法編輯。請先還原筆記。"
}
```

### 場景 2：用戶嘗試收藏保密柜筆記

```
Request: POST /api/notes/456/favorite/
檢查: note.is_secret == True
↓
返回: HTTP 403
{
  "error": "保密柜的筆記無法收藏。請先移出保密柜。"
}
```

### 場景 3：前端請求回收站保密筆記

```
Request: GET /api/notes/789/?full_content=true
檢查: note.is_secret=True AND note.is_trashed=True
↓
返回: HTTP 200
{
  "id": 789,
  "title": "我的銀行密碼",  // ✅ 包含
  "content": undefined,      // ❌ 不包含
  "is_secret": true,
  "is_trashed": true,
  "content_locked": true,
  "lock_reason": "此筆記位於回收站中，內容已鎖定。"
}
```

---

## 測試檢查項

- [ ] 嘗試編輯回收站筆記 → 返回 403
- [ ] 嘗試編輯正常筆記 → 成功 (200)
- [ ] 嘗試收藏保密柜筆記 → 返回 403
- [ ] 嘗試收藏普通筆記 → 成功 (200)
- [ ] 嘗試發布保密柜筆記為公開 → 返回 403
- [ ] 嘗試發布普通筆記為公開 → 成功 (200)
- [ ] GET 回收站保密筆記 → 返回不含 content 字段
- [ ] GET 普通筆記 → 返回完整數據

---

## 實現優先級

**P0 (立即實現)**:
1. `check_note_edit_permission` 函數
2. PATCH/PUT 方法中添加 is_trashed 檢查

**P1 (後續實現)**:
1. `check_note_secret_operation_permission` 函數
2. toggle_note_favorite_api 中添加 is_secret 檢查
3. PUT/PATCH 中添加 is_public + is_secret 檢查

**P2 (優化)**:
1. `build_note_response_data` 通用函數
2. GET 響應中的數據最小化邏輯

---

## 向後兼容性

✅ 現有客戶端無法破壞現有行為
✅ 新的 403 響應由前端使用者自行處理
✅ 若不涉及敏感操作，API 行為完全不變
✅ Content 字段缺失時前端已有兼容邏輯

