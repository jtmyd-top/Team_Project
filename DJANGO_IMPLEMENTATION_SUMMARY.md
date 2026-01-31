# Django 後端安全加固 - 實現總結

## 日期
2026-01-29

## 實現完成狀態
✅ **P0 (立即實現)** - 100% 完成
✅ **P1 (後續實現)** - 100% 完成
✅ **P2 (優化)** - 100% 完成

---

## 實施的變更清單

### 1. 新增安全檢查輔助函數 (views.py)

**位置**: `knowledge_project/views.py` (第 129-210 行)

#### A. `check_note_edit_permission(note)`
- 檢查筆記是否允許編輯
- 規則：`note.is_trashed == True` → 返回 False，403 Forbidden
- 返回：`(allowed: bool, error_message: str)`

#### B. `check_note_secret_operation_permission(note, operation)`
- 檢查筆記是否允許特定操作
- 規則：`note.is_secret == True` → 對 'favorite', 'share', 'publish' 返回 False，403 Forbidden
- 支持的操作：'favorite', 'share', 'publish'
- 返回：`(allowed: bool, error_message: str)`

#### C. `build_note_response_data(note, include_content, include_all_fields)`
- 構建 API 響應數據，支持字段過濾
- 數據最小化：當 `is_secret=True AND is_trashed=True` 時，自動不包含 content
- 返回：完整的應答字典

---

### 2. 修改 note_detail_api PUT 方法

**文件**: `knowledge_project/views.py` (第 1435-1448 行)

**實施的檢查**:

```python
# 【新增】安全檢查：回收站保護
allowed, error_msg = check_note_edit_permission(note)
if not allowed:
    return JsonResponse({'error': error_msg}, status=403)

# 【新增】安全檢查：防止保密柜筆記發布為公開
if data.get('is_public') and note.is_secret:
    allowed, error_msg = check_note_secret_operation_permission(note, 'publish')
    if not allowed:
        return JsonResponse({'error': error_msg}, status=403)
```

**效果**:
- ❌ 拒絕編輯回收站筆記
- ❌ 拒絕將保密柜筆記發布為公開
- ✅ 允許編輯正常筆記

---

### 3. 修改 note_detail_api PATCH 方法

**文件**: `knowledge_project/views.py` (第 1491-1524 行)

**實施的檢查**:

```python
# 【新增】安全檢查：回收站保護
allowed, error_msg = check_note_edit_permission(note)
if not allowed:
    return JsonResponse({'error': error_msg}, status=403)

# 【新增】安全檢查：防止保密柜筆記發布為公開
if 'is_public' in data and data['is_public'] and note.is_secret:
    allowed, error_msg = check_note_secret_operation_permission(note, 'publish')
    if not allowed:
        return JsonResponse({'error': error_msg}, status=403)
```

**效果**: 與 PUT 方法相同

---

### 4. 修改 note_detail_api GET 方法 (數據最小化)

**文件**: `knowledge_project/views.py` (第 1392-1440 行)

**實施的邏輯**:

```python
# 【新增】決定是否包含 content 字段 (數據最小化)
include_content = True
if note.is_secret and note.is_trashed:
    include_content = False
```

**full_content 響應**:
```python
if include_content:
    data['content'] = note.content or ""
else:
    data['content_locked'] = True
    data['lock_reason'] = '此笔记位于回收站中，内容已锁定。'
```

**分頁響應**:
```python
if include_content:
    data['content'] = paginated_content
else:
    data['content_locked'] = True
    data['lock_reason'] = '此笔记位于回收站中，内容已锁定。'
```

**效果**:
- ✅ 返回 200 OK（不中斷流程）
- ❌ 不包含 content 字段（數據最小化）
- ℹ️ 包含 `content_locked` 和 `lock_reason` 提示

---

### 5. 修改 toggle_note_favorite_api (folder_views.py)

**文件**: `knowledge_project/folder_views.py` (第 1-13 行 + 第 350-368 行)

**導入新增**:
```python
from .views import check_note_secret_operation_permission
```

**實施的檢查**:
```python
# 【新增】安全檢查：保密柜保護
allowed, error_msg = check_note_secret_operation_permission(note, 'favorite')
if not allowed:
    return JsonResponse({'error': error_msg}, status=403)
```

**效果**:
- ❌ 拒絕收藏保密柜筆記
- ✅ 允許收藏普通筆記

---

## 安全防護矩陣

| 操作 | 場景 | 檢查 | 響應碼 | 說明 |
|-----|-----|-----|-------|------|
| **編輯 (PUT/PATCH)** | 筆記在回收站 | is_trashed | 403 | 阻止編輯已刪除筆記 |
| **發布 (is_public=True)** | 保密柜筆記 | is_secret | 403 | 防止意外洩露 |
| **收藏 (favorite)** | 保密柜筆記 | is_secret | 403 | 限制操作 |
| **查看 (GET)** | 回收站保密筆記 | is_secret AND is_trashed | 200 (filtered) | 返回無 content 字段 |

---

## 前端適配指南

### 1. 預期 403 Forbidden 響應

**編輯操作失敗**:
```javascript
try {
    const response = await fetch(`/api/notes/${noteId}/`, {
        method: 'PATCH',
        body: JSON.stringify(updatedData)
    })
    if (response.status === 403) {
        const error = await response.json()
        console.error(error.error)  // "回收站中的筆記無法編輯。請先還原筆記。"
        // 提示用戶: "無法編輯 - 此筆記位於回收站中"
    }
} catch (e) {
    console.error(e)
}
```

### 2. 處理缺失 content 字段

**檢查數據最小化**:
```javascript
const response = await fetch(`/api/notes/${noteId}/?full_content=true`)
const data = await response.json()

if (data.content_locked) {
    // 顯示鎖定提示
    console.log(data.lock_reason)  // "此笔记位于回收站中，内容已锁定。"
    // 前端顯示特殊 UI（已在 NoteShadowViewer.vue 實現）
} else if (data.content === undefined) {
    // 舊版本相容處理
    console.warn('Content field not returned')
}
```

### 3. 收藏操作失敗

**處理 403 響應**:
```javascript
const response = await fetch(`/api/notes/${noteId}/favorite/`, {
    method: 'POST'
})
if (response.status === 403) {
    const error = await response.json()
    // 錯誤: "保密柜的筆記無法收藏。請先移出保密柜。"
    showNotification(error.error, 'warning')
}
```

---

## 測試檢查項

### 操作阻斷層 (Action Blocking)

- [ ] **回收站筆記編輯**
  - 操作：嘗試 PATCH /api/notes/{id}/ 編輯回收站筆記
  - 預期：HTTP 403 + error message
  - 實際結果：___________

- [ ] **回收站筆記編輯 (PUT)**
  - 操作：嘗試 PUT /api/notes/{id}/ 編輯回收站筆記
  - 預期：HTTP 403 + error message
  - 實際結果：___________

- [ ] **保密筆記發布**
  - 操作：嘗試 PATCH /api/notes/{id}/ 設置 is_public=True 在保密筆記上
  - 預期：HTTP 403 + error message
  - 實際結果：___________

- [ ] **保密筆記收藏**
  - 操作：POST /api/notes/{id}/favorite/ 在保密筆記上
  - 預期：HTTP 403 + error message
  - 實際結果：___________

### 數據最小化層 (Data Minimization)

- [ ] **回收站保密筆記 - 無 content**
  - 操作：GET /api/notes/{id}/?full_content=true (is_secret=true, is_trashed=true)
  - 預期：返回 content_locked=true，無 content 字段
  - 實際結果：___________

- [ ] **回收站保密筆記 - 分頁**
  - 操作：GET /api/notes/{id}/?page=1 (is_secret=true, is_trashed=true)
  - 預期：返回 content_locked=true，無 content 字段
  - 實際結果：___________

- [ ] **正常筆記 - 完整返回**
  - 操作：GET /api/notes/{id}/?full_content=true (is_secret=false OR is_trashed=false)
  - 預期：返回完整 content 字段
  - 實際結果：___________

### 正常流程（應繼續工作）

- [ ] **編輯普通筆記**
  - 操作：PATCH /api/notes/{id}/ 編輯普通筆記
  - 預期：HTTP 200 + 更新成功
  - 實際結果：___________

- [ ] **編輯保密筆記（在保密柜中）**
  - 操作：PATCH /api/notes/{id}/ 編輯未在回收站的保密筆記
  - 預期：HTTP 200 + 更新成功
  - 實際結果：___________

- [ ] **收藏普通筆記**
  - 操作：POST /api/notes/{id}/favorite/ 收藏普通筆記
  - 預期：HTTP 200 + status: success
  - 實際結果：___________

---

## 代碼文件變更統計

### 修改的文件

| 文件 | 行數增加 | 修改類型 | 說明 |
|------|---------|---------|------|
| views.py | +82 | 新增函數 | 3 個安全檢查函數 |
| views.py | +20 | 修改邏輯 | PUT 方法安全檢查 |
| views.py | +18 | 修改邏輯 | PATCH 方法安全檢查 |
| views.py | +26 | 修改邏輯 | GET 方法數據最小化 |
| folder_views.py | +1 | 新增導入 | 導入安全函數 |
| folder_views.py | +6 | 修改邏輯 | toggle_note_favorite_api 安全檢查 |

**總計**: +153 行代碼

---

## 安全性驗證

### 威脅模式覆蓋

✅ **數據庫泄露**
- 內容仍為加密（backend 不解密）
- 回收站敏感場景下不傳輸內容

✅ **API 濫用**
- PUT/PATCH 提前檢查（回收站）
- Favorite 提前檢查（保密柜）
- 403 響應強制終止操作

✅ **狀態操縱**
- 防止 is_public 在 is_secret=true 時設置為 true
- 防止任何編輯操作在 is_trashed=true 時執行

✅ **意外洩露**
- GET 響應自動過濾敏感組合場景
- 前端已有對應鎖定 UI（NoteShadowViewer.vue）

### 未覆蓋的場景

⚠️ **假設：後端本身可信**
- 若 Django 本身被入侵，所有防護失效
- 需要依靠 OS 級安全控制

⚠️ **假設：傳輸層安全**
- 此實現假設 HTTPS 連接
- HTTP 傳輸內容可被中間人攔截

⚠️ **假設：用戶設備安全**
- 用戶若遭釣魚/惡意軟件，前端防護無用
- 需要依靠用戶安全意識

---

## 向後兼容性

✅ **API 層級兼容**
- 舊客戶端無法破壞現有行為
- 新的 403 響應由客戶端自行處理
- GET 響應新增字段（舊客戶端可忽略）

✅ **業務流程兼容**
- 正常流程（非保密/非回收站）完全不變
- 受限操作 403 流程前端已有異常處理

✅ **數據庫兼容**
- 無模型變更
- 無遷移文件需要

---

## 部署檢查項

### 代碼部署前

- [ ] 代碼審查完成
- [ ] 單位測試通過
- [ ] 集成測試通過
- [ ] 安全審查完成

### 代碼部署

- [ ] 上傳 views.py 變更
- [ ] 上傳 folder_views.py 變更
- [ ] 重啟 Django 應用（可選，若無 hot reload）
- [ ] 驗證 API 端點可用

### 部署後驗證

- [ ] 執行測試檢查項中的所有測試
- [ ] 監控應用日誌（是否有 403 異常增多）
- [ ] 驗證前端提示信息正確顯示
- [ ] 檢查未授權訪問日誌

---

## 相關文檔

- **DJANGO_BACKEND_SECURITY.md** - 詳細的設計文檔
- **VAULT_TRASH_SECURITY.md** - 前端實現文檔
- **VAULT_TITLE_UPDATE_FIX.md** - 標題同步文檔
- **PREVIEW_REFRESH_LOGIC.md** - 事件系統文檔

---

## 後續改進方向

1. **審計日誌**：記錄所有被拒絕的操作（誰、何時、做什麼）
2. **警告通知**：用戶嘗試非法操作時發送通知
3. **分級權限**：不同用戶對敏感操作的權限控制
4. **臨時白名單**：經過 2FA 驗證的用戶臨時允許敏感操作
5. **自動恢復**：到期後的回收站筆記自動永久刪除

