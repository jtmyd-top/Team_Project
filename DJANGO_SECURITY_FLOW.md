# Django 後端安全加固 - 流程圖

## 1. 編輯操作流程 (PUT/PATCH)

```
┌──────────────────────────────────────────────────────────────────┐
│ 用戶發送 PATCH /api/notes/{id}/ 請求                              │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ note_detail_api()    │
        │ 進行安全檢查          │
        └──────────┬───────────┘
                   │
                   ▼
      ┌────────────────────────────┐
      │ check_note_edit_permission │
      │ (檢查回收站狀態)             │
      └────────┬────────────────────┘
               │
        ┌──────┴──────┐
        │             │
    ✅ False       ✅ True
        │             │
        ▼             ▼
    ┌─────────┐  ┌──────────────────────────────┐
    │ 403     │  │ check_note_secret_operation_ │
    │ Forbidden   │ permission (檢查發布意圖)   │
    └─────────┘  └────────┬──────────────────────┘
                          │
                   ┌──────┴──────┐
                   │             │
               ❌ False       ✅ True
                   │             │
                   ▼             ▼
              ┌────────┐    ┌──────────────────┐
              │ 403    │    │ 更新筆記          │
              │Forbidden   │ 執行 save()       │
              └────────┘    └─────┬────────────┘
                                  │
                                  ▼
                          ┌────────────────────┐
                          │ 返回 200 OK        │
                          │ + 更新後的數據      │
                          └────────────────────┘
```

---

## 2. 收藏操作流程 (POST /favorite/)

```
┌─────────────────────────────────────────────────────┐
│ 用戶發送 POST /api/notes/{id}/favorite/ 請求        │
└────────────────┬──────────────────────────────────┘
                 │
                 ▼
      ┌──────────────────────────┐
      │toggle_note_favorite_api()│
      │ 進行安全檢查              │
      └────────────┬─────────────┘
                   │
                   ▼
    ┌──────────────────────────────────┐
    │ check_note_secret_operation_     │
    │ permission(note, 'favorite')    │
    │ (檢查是否為保密筆記)              │
    └────────┬───────────────────────┘
             │
        ┌────┴────┐
        │          │
    ❌ True   ❌ False
    (是密) (非密)
        │          │
        ▼          ▼
    ┌────────┐  ┌─────────────┐
    │ 403    │  │ 切換收藏    │
    │Forbidden │ is_favorited │
    └────────┘  │ = not is_f.. │
                └──────┬──────┘
                       │
                       ▼
              ┌──────────────────┐
              │ 返回 200 OK      │
              │ is_favorited: T/F│
              └──────────────────┘
```

---

## 3. 查詢操作流程 (GET) - 數據最小化

```
┌────────────────────────────────────────────┐
│ 用戶發送 GET /api/notes/{id}/?full_content │
└────────┬─────────────────────────────────┘
         │
         ▼
┌──────────────────────┐
│note_detail_api (GET) │
│ 決定內容包含策略      │
└──────────┬───────────┘
           │
           ▼
    ┌─────────────────────┐
    │ include_content =   │
    │     True            │
    └──────────┬──────────┘
               │
               ▼
   ┌──────────────────────────┐
   │ 檢查：                     │
   │ is_secret AND            │
   │ is_trashed?              │
   └────┬──────────────────────┘
        │
   ┌────┴────┐
   │          │
   ✅ True   ✅ False
   │          │
   ▼          ▼
┌─────────┐  ┌──────────────┐
│include_ │  │ 返回完整數據  │
│content= │  │ +content字段  │
│ False   │  └──────────────┘
└────┬────┘
     │
     ▼
┌──────────────────────┐
│ 返回 200 OK          │
│ + content_locked=T   │
│ + lock_reason=msg    │
│ - content 字段       │
└──────────────────────┘
```

---

## 4. 完整安全檢查決策樹

```
                    ┌─── 操作請求 ───┐
                    │               │
          ┌─────────┼─────────┬─────┘
          │         │         │
          ▼         ▼         ▼
     [編輯]      [收藏]    [查詢]
    PUT/PATCH   POST      GET
          │         │         │
          ▼         ▼         ▼
       ╔════════════════════════════╗
       ║ Layer 1: 操作阻斷           ║
       ║ (Action Blocking)          ║
       ╚════╤═════════════════════╤═╝
            │                     │
       ┌────▼─────┐          ┌────▼─────┐
       │檢查:      │          │檢查:      │
       │is_trashed│          │is_secret  │
       └────┬─────┘          └────┬─────┘
       ┌────┴────┐          ┌────┴────┐
       │          │          │          │
       ▼          ▼          ▼          ▼
   [T] 403   [F] ✅      [T] 403   [F] ✅
    continue        allow   continue  allow
       │
       ▼
   ┌─────────────────────┐
   │檢查:                 │
   │is_secret AND        │
   │is_public=true?      │
   └────┬────────────────┘
   ┌────┴────┐
   │          │
   ▼          ▼
[T] 403   [F] ✅
continue  allow
       │
       ▼
   ╔════════════════════════════╗
   ║ Layer 2: 數據最小化        ║
   ║ (Data Minimization)       ║
   ║ (僅GET)                    ║
   ╚════╤═════════════════════╤═╝
        │
    ┌───▼───┐
    │檢查:   │
    │is_secret AND is_trashed
    └───┬───┘
    ┌───┴───┐
    │       │
    ▼       ▼
  [T] 過濾  [F] 完整
  無content 含content
    │       │
    └───┬───┘
        │
        ▼
    ┌─────────────┐
    │ 返回 200 OK │
    └─────────────┘
```

---

## 5. 狀態轉移圖

```
                    ┌──────────────────────┐
                    │  新建筆記             │
                    │ (is_secret: -, is_tr: F) │
                    └──────────┬───────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                ▼              ▼              ▼
        ┌──────────────┐ ┌────────────┐ ┌─────────────┐
        │ 普通筆記      │ │ 保密筆記    │ │回收站筆記   │
        │ S:F T:F      │ │ S:T T:F    │ │ S:F T:T    │
        └──────┬───────┘ └──────┬────┘ └─────┬───────┘
               │                │            │
         [編輯可] ✅      [編輯可] ✅      [編輯禁] ❌
         [收藏可] ✅      [收藏禁] ❌      [收藏可] ✅
         [發布可] ✅      [發布禁] ❌      [發布禁] ❌
         [查詢全] ✅      [查詢全] ✅      [查詢全] ✅
                │                │            │
                └────────┬───────┴────────────┘
                         │ (還原操作)
                         ▼
            ┌─────────────────────────┐
            │ 回收站保密筆記            │
            │ S:T T:T                 │
            └────────────┬────────────┘
                         │
                   [編輯禁] ❌
                   [收藏禁] ❌
                   [發布禁] ❌
                   [查詢過濾] ⚠️
                    (無content)
                         │
                    (還原操作)
                         ▼
                   回到保密筆記
                   S:T T:F
```

**圖例**:
- S = is_secret (T/F)
- T = is_trashed (T/F)
- ✅ = 允許操作
- ❌ = 拒絕操作 (403)
- ⚠️ = 有條件操作 (部分過濾)

---

## 6. 數據流詳解 - 回收站保密筆記的 GET 請求

```
前端請求
    │
    ▼
GET /api/notes/123/?full_content=true
    │
    ▼
┌─ views.py note_detail_api (GET) ─┐
│                                  │
│ 1. 獲取筆記:                       │
│    note = Note.objects.get(123)  │
│    note.is_secret = True         │
│    note.is_trashed = True        │
│                                  │
│ 2. 決定策略:                       │
│    include_content = True        │
│    if (is_secret AND is_trashed):│
│        include_content = False   │
│                                  │
│ 3. 構建響應:                       │
│    data = {                      │
│      'id': 123,                  │
│      'title': '我的銀行密碼',     │
│      'is_secret': True,          │
│      'is_trashed': True,         │
│      'content': ∅,   # 未包含     │
│      'content_locked': True,     │
│      'lock_reason': '此筆記位... '│
│      ...其他字段...               │
│    }                             │
│                                  │
│ 4. 返回 200 OK                    │
└──────────┬──────────────────────┘
           │
           ▼
前端響應處理:
    if (data.content_locked) {
        showLockedUI()  // 顯示鎖定提示
    } else {
        showContent()  // 顯示內容
    }
```

---

## 7. 錯誤響應示例

### A. 編輯回收站筆記

```http
PATCH /api/notes/456/ HTTP/1.1
Host: example.com
Content-Type: application/json

{"title": "新標題"}
```

**響應**:
```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "error": "回收站中的筆記無法編輯。請先還原筆記。"
}
```

### B. 收藏保密筆記

```http
POST /api/notes/789/favorite/ HTTP/1.1
Host: example.com
```

**響應**:
```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "error": "保密柜的筆記無法收藏。請先移出保密柜。"
}
```

### C. 發布保密筆記

```http
PATCH /api/notes/321/ HTTP/1.1
Host: example.com
Content-Type: application/json

{"is_public": true}
```

**響應**:
```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "error": "保密柜的筆記無法發布為公開。請先移出保密柜。"
}
```

---

## 8. 成功響應示例

### A. 編輯正常筆記 ✅

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "id": 456,
  "title": "新標題",
  "is_secret": false,
  "is_trashed": false,
  "updated_at": "2026-01-29 14:30",
  "message": "更新成功"
}
```

### B. 查詢回收站保密筆記 ✅

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "id": 789,
  "title": "我的銀行密碼",
  "is_secret": true,
  "is_trashed": true,
  "content_locked": true,
  "lock_reason": "此筆記位於回收站中，內容已鎖定。",
  "author": {...},
  "tags": [...]
  # 注意：無 content 字段
}
```

### C. 收藏普通筆記 ✅

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "status": "success",
  "is_favorited": true
}
```

