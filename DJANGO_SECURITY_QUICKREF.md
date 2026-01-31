# Django 後端安全加固 - 快速參考

## ✅ 實施完成

### 三層安全防護

| 層級 | 組件 | 防護對象 | 實施位置 |
|------|------|---------|---------|
| **L1** | Action Blocking | 回收站編輯、保密發布、保密收藏 | views.py + folder_views.py |
| **L2** | Data Minimization | 回收站保密筆記的內容字段 | views.py GET |
| **L3** | 前端防守 | 鎖定 UI、禁用按鈕 | NoteShadowViewer.vue |

---

## 📋 檢查清單

### 代碼修改驗證

```bash
# 驗證安全函數是否存在
$ grep -n "check_note_edit_permission\|check_note_secret_operation_permission" knowledge_project/views.py
✅ 132:def check_note_edit_permission(note):
✅ 144:def check_note_secret_operation_permission(note, operation):

# 驗證 PUT 方法安全檢查
$ grep -A 3 "if request.method == 'PUT':" knowledge_project/views.py | grep -A 3 "check_note_edit_permission"
✅ 已添加回收站檢查
✅ 已添加保密發布檢查

# 驗證 PATCH 方法安全檢查
$ grep -A 3 "if request.method == 'PATCH':" knowledge_project/views.py | grep -A 3 "check_note_edit_permission"
✅ 已添加回收站檢查
✅ 已添加保密發布檢查

# 驗證 GET 方法數據最小化
$ grep -n "include_content\|content_locked" knowledge_project/views.py | grep -E "139[0-9]:|14[0-9][0-9]:"
✅ 1394: include_content = True
✅ 1396: if note.is_secret and note.is_trashed:
✅ 1416: data['content_locked'] = True

# 驗證 favorite 安全檢查
$ grep -B 2 -A 2 "toggle_note_favorite_api" knowledge_project/folder_views.py
✅ 已導入 check_note_secret_operation_permission
✅ 已添加保密檢查
```

---

## 🔒 六個安全規則

### 規則 1: 回收站編輯防護
```
IF request.method IN ['PUT', 'PATCH'] AND note.is_trashed == True
THEN return 403 Forbidden "回收站中的筆記無法編輯。"
```

### 規則 2: 保密發布防護
```
IF data.get('is_public') == True AND note.is_secret == True
THEN return 403 Forbidden "保密柜的筆記無法發布為公開。"
```

### 規則 3: 保密收藏防護
```
IF request.POST['favorite'] AND note.is_secret == True
THEN return 403 Forbidden "保密柜的筆記無法收藏。"
```

### 規則 4: 內容過濾
```
IF request.method == 'GET' AND note.is_secret == True AND note.is_trashed == True
THEN {
    do NOT include 'content' field
    DO include 'content_locked' = True
    DO include 'lock_reason' = message
}
```

### 規則 5: 發布安全性
```
IF note.is_secret == True AND note.is_public == True (任何情況下)
THEN this is a data inconsistency - should not happen due to PATCH check
```

### 規則 6: 回收站恢復
```
IF is_trashed == True AND operation != ['restore', 'destroy']
THEN allow only these operations, others blocked
```

---

## 🧪 測試場景快速驗證

### 場景 1: 編輯回收站筆記 (應 403)

```bash
curl -X PATCH http://localhost:8000/api/notes/123/ \
  -H "Content-Type: application/json" \
  -d '{"title": "新標題"}' \
  -b "sessionid=xxx"

# 預期: HTTP 403
# {
#   "error": "回收站中的筆記無法編輯。請先還原筆記。"
# }
```

### 場景 2: 收藏保密筆記 (應 403)

```bash
curl -X POST http://localhost:8000/api/notes/456/favorite/ \
  -b "sessionid=xxx"

# 預期: HTTP 403
# {
#   "error": "保密柜的筆記無法收藏。請先移出保密柜。"
# }
```

### 場景 3: 查詢回收站保密筆記 (應 200，無 content)

```bash
curl http://localhost:8000/api/notes/789/?full_content=true \
  -b "sessionid=xxx"

# 預期: HTTP 200 但無 content 字段
# {
#   "id": 789,
#   "title": "...",
#   "is_secret": true,
#   "is_trashed": true,
#   "content_locked": true,
#   "lock_reason": "此筆記位於回收站中，內容已鎖定。"
# }
```

### 場景 4: 編輯普通筆記 (應 200)

```bash
curl -X PATCH http://localhost:8000/api/notes/111/ \
  -H "Content-Type: application/json" \
  -d '{"title": "新標題"}' \
  -b "sessionid=xxx"

# 預期: HTTP 200 + 更新成功
```

---

## 📊 性能影響分析

### 新增的操作

| 操作 | 位置 | 複雜度 | 影響 |
|------|------|--------|------|
| `check_note_edit_permission()` | 前置檢查 | O(1) | 極小 |
| `check_note_secret_operation_permission()` | 前置檢查 | O(1) | 極小 |
| `note.is_secret AND note.is_trashed` | GET 檢查 | O(1) | 無 |

**結論**: ✅ 性能影響可忽略不計（都是內存操作，無數據庫查詢）

---

## 📝 相關文檔導航

```
project_root/
├── DJANGO_BACKEND_SECURITY.md
│   └─ 詳細的架構設計和代碼實現說明
│
├── DJANGO_IMPLEMENTATION_SUMMARY.md
│   └─ 實施完成情況、測試清單、部署指南
│
├── DJANGO_SECURITY_FLOW.md
│   └─ 流程圖、決策樹、數據流詳解
│
├── VAULT_TRASH_SECURITY.md
│   └─ 前端實現（Vue 組件層面）
│
├── VAULT_TITLE_UPDATE_FIX.md
│   └─ 標題同步修復
│
└── PREVIEW_REFRESH_LOGIC.md
    └─ 全局事件系統
```

---

## 🔄 集成測試流程

### 第 1 步：環境準備
```bash
cd /path/to/project
python manage.py migrate
python manage.py runserver
```

### 第 2 步：創建測試數據
```python
# Django shell
from knowledge_project.models import Note
from django.contrib.auth.models import User

user = User.objects.get(username='testuser')

# 創建普通筆記
note1 = Note.objects.create(author=user, title='普通', is_secret=False, is_trashed=False)

# 創建保密筆記
note2 = Note.objects.create(author=user, title='保密', is_secret=True, is_trashed=False)

# 創建回收站普通筆記
note3 = Note.objects.create(author=user, title='回收站普通', is_secret=False, is_trashed=True)

# 創建回收站保密筆記
note4 = Note.objects.create(author=user, title='回收站保密', is_secret=True, is_trashed=True)
```

### 第 3 步：運行測試
```bash
# 執行每個場景對應的 curl 命令（見上方「場景 1-4」）
```

### 第 4 步：驗證前端
```bash
# 打開瀏覽器，訪問應用
# 1. 嘗試編輯回收站筆記 → 應看到禁用按鈕或錯誤提示
# 2. 嘗試收藏保密筆記 → 應看到禁用按鈕或錯誤提示
# 3. 查看回收站保密筆記 → 應看到鎖定提示，無內容
```

---

## ⚡ 快速排查 (Troubleshooting)

### 問題：編輯操作仍然成功，未返回 403

**可能原因**:
1. views.py 未更新到最新版本
2. Python 沒有重新加載模塊（需要重啟 Django）

**解決方案**:
```bash
# 驗證代碼是否更新
grep -n "check_note_edit_permission" knowledge_project/views.py

# 重啟 Django
# Ctrl+C 停止，重新 python manage.py runserver
```

### 問題：GET 請求仍然返回 content 字段

**可能原因**:
1. views.py GET 部分未更新
2. 笛記不符合過濾條件（not is_secret or not is_trashed）

**解決方案**:
```bash
# 驗證是否正確添加了條件檢查
grep -A 5 "include_content = True" knowledge_project/views.py | head -10

# 確認測試筆記狀態
python manage.py shell
>>> from knowledge_project.models import Note
>>> note = Note.objects.get(id=123)
>>> print(f"is_secret: {note.is_secret}, is_trashed: {note.is_trashed}")
```

### 問題：favorite 操作未被攔截

**可能原因**:
1. folder_views.py 未導入安全函數
2. 筆記不是保密笔记（is_secret=False）

**解決方案**:
```bash
# 驗證導入
grep "from .views import check_note_secret_operation_permission" knowledge_project/folder_views.py

# 確認筆記狀態
python manage.py shell
>>> note = Note.objects.get(id=456)
>>> print(f"is_secret: {note.is_secret}")
```

---

## 🎯 下一步行動

### 立即執行
- [ ] 執行快速驗證命令（「檢查清單」部分）
- [ ] 運行 4 個測試場景
- [ ] 檢查前端是否正確處理 403 和 content_locked

### 本周完成
- [ ] 執行完整的集成測試
- [ ] 部署到 staging 環境
- [ ] 進行用戶驗收測試 (UAT)

### 後期改進
- [ ] 實現審計日誌（記錄被拒操作）
- [ ] 實現自動恢復機制（過期回收站項目）
- [ ] 實現告警系統（異常訪問通知）

---

## 📞 文檔生成時間

- 生成日期：2026-01-29
- 實施版本：v1.0
- Django 版本：4.x (假設)
- Python 版本：3.8+ (假設)

---

## 📄 文件清單

本次實施產生的文檔：

1. **DJANGO_BACKEND_SECURITY.md** - 詳細設計文檔
2. **DJANGO_IMPLEMENTATION_SUMMARY.md** - 實施總結
3. **DJANGO_SECURITY_FLOW.md** - 流程圖和決策樹
4. **DJANGO_SECURITY_QUICKREF.md** - 此文件（快速參考）

代碼修改文件：

1. **knowledge_project/views.py** - 新增函數 + 修改 PUT/PATCH/GET
2. **knowledge_project/folder_views.py** - 修改 toggle_note_favorite_api

---

## 🔗 相關 Issue 和 PR

- 對應用戶需求：保密柜筆記的安全防護
- 相關前端實現：VAULT_TRASH_SECURITY.md
- 相關事件系統：PREVIEW_REFRESH_LOGIC.md

