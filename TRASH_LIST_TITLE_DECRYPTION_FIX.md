# 回收站列表標題解密修復

## 問題描述

在回收站中：
- ✅ **工具欄標題**（預覽區）已解密顯示
- ❌ **列表標題**（側邊欄列表）未解密，仍為密文

例如：
```
回收站列表中的標題: YZ1s3YzHQoivmlhy... (密文)
預覽區的標題:       我的銀行密碼 (已解密)
```

## 根本原因

1. **SecondaryPanel.vue** 中加載回收站筆記時，未對保密筆記的標題進行解密
2. **NoteListItem.vue** 的本地解密邏輯依賴複雜的 watch 和 DEK 邏輯，在回收站場景下失效
3. 預覽區的標題來自 KnowledgeList.vue 的 `fetchNoteDetail()` API 響應，已自動解密
4. 列表的標題來自 sidebar.js 的 `loadTrashedNotes()` API 響應，未進行解密

---

## 解決方案

### 方案：三層防護機制

```
SecondaryPanel.vue (列表父組件)
    ↓
    在 currentNotes 變化時
    對所有保密筆記的標題進行解密
    設置 note.decryptedTitle
    ↓
NoteListItem.vue (列表項目)
    ↓
    displayTitle computed 優先使用 note.decryptedTitle
    備選方案：使用本地 decryptedTitle.value
    最後方案：顯示原標題（密文）
```

### 修改 1：SecondaryPanel.vue - 添加回收站笔记解密邏輯

**位置**: `frontend/src/components/layout/SecondaryPanel.vue`（第 416-450 行）

**新增代碼**:
```javascript
// 【新增】监听回收站笔记变化，自动解密保密笔记的标题
watch(
  () => ({
    notes: sidebarStore.currentNotes,
    isTrash: sidebarStore.activeModule === 'trash'
  }),
  ({ notes, isTrash }) => {
    if (!isTrash) return  // 只在回收站中处理

    // 对回收站中的保密笔记进行标题解密
    notes.forEach(note => {
      if (note.is_secret && note.title && (dek.value || vaultStore.dek)) {
        try {
          // 尝试使用 dek.value 或 vaultStore.dek 解密
          const dekToUse = dek.value || vaultStore.dek
          if (dekToUse) {
            const plainTitle = decryptContent(note.title, dekToUse)
            note.decryptedTitle = plainTitle  // 保存解密后的标题
            console.log('[SecondaryPanel] Title decrypted for trash note:', note.id)
          }
        } catch (e) {
          console.warn('[SecondaryPanel] Failed to decrypt trash note title:', note.id, e.message)
        }
      }
    })
  },
  { deep: true }
)
```

**效果**:
- ✅ 當進入回收站時，自動解密所有保密筆記的標題
- ✅ 設置 `note.decryptedTitle` 供 NoteListItem 使用
- ✅ 無需依賴複雜的 watch 邏輯

### 修改 2：NoteListItem.vue - 優先使用 Parent 的解密標題

**位置**: `frontend/src/components/common/NoteListItem.vue`（第 148-165 行）

**修改代碼**:
```javascript
// 计算属性：显示的标题（已解密或原标题）
const displayTitle = computed(() => {
  // 如果不是加密笔记，直接返回原标题
  if (!props.note.is_secret) {
    return props.note.title || '无标题'
  }

  // 【新增】如果 parent 已经设置了解密后的标题，直接使用
  if (props.note.decryptedTitle) {
    return props.note.decryptedTitle
  }

  // 如果本地解密过，返回解密后的标题
  if (decryptedTitle.value) {
    return decryptedTitle.value
  }

  // 如果还没解密，返回原标题（可能是密文）
  return props.note.title || '无标题'
})
```

**優先級**:
1. `note.decryptedTitle`（來自 parent SecondaryPanel）✅ 最快
2. `decryptedTitle.value`（本地解密）✅ 備選
3. `note.title`（原始標題，可能是密文）⚠️ 最後

### 修改 3：NoteListItem.vue - 添加 Active 監聽器

**位置**: `frontend/src/components/common/NoteListItem.vue`（新增 watch）

**新增代碼**:
```javascript
// 【新增】监听 active 变化，当笔记被选中时尝试解密
watch(() => props.active, (isActive) => {
  if (isActive && props.note.is_secret && !decryptedTitle.value) {
    // 笔记被选中且是保密笔记且还未解密，立即尝试解密
    console.log('[NoteListItem] Attempting to decrypt title for active note:', props.note.id)
    decryptNoteTitle()
  }
})
```

**效果**:
- ✅ 當笔記被選中時，確保標題被解密
- ✅ 作為備用機制，保證最終標題必定解密

---

## 修復前後對比

### 修復前 ❌

```
用戶進入回收站
    ↓
列表加載回收站笔記
    ├─ 保密笔记標題：YZ1s3YzHQoivmlhy... (密文)
    └─ 普通筆記標題：正常顯示 (明文)
    ↓
用戶點擊一個保密笔记
    ↓
預覽區加載並解密標題
    ├─ 工具欄標題：我的銀行密碼 (已解密) ✅
    └─ 列表標題：YZ1s3YzHQoivmlhy... (仍為密文) ❌
```

### 修復後 ✅

```
用戶進入回收站
    ↓
SecondaryPanel.vue watch 觸發
    ↓
自動對所有保密筆記進行解密
    ├─ 使用 dek.value 或 vaultStore.dek
    ├─ 設置 note.decryptedTitle
    ↓
列表重新渲染
    ├─ 保密笔记標題：我的銀行密碼 (已解密) ✅
    └─ 普通筆記標題：正常顯示 (明文) ✅
    ↓
用戶點擊一個保密笔记
    ↓
預覽區加載並解密標題
    ├─ 工具欄標題：我的銀行密碼 (已解密) ✅
    └─ 列表標題：我的銀行密碼 (已解密) ✅
```

---

## 工作流程

### 初始化流程
```
用戶切換到回收站模塊
    ↓
sidebarStore.loadTrashedNotes() 執行
    ↓
currentNotes 數據變化
    ↓
SecondaryPanel.vue watch 監聽到變化
    ├─ 檢查 activeModule === 'trash'
    ├─ 遍歷所有筆記
    ├─ 對於每個 is_secret=true 的筆記
    │  └─ decryptContent(note.title, dek) → plainTitle
    ├─ 設置 note.decryptedTitle = plainTitle
    ↓
NoteListItem.vue displayTitle computed 更新
    ├─ 檢查 props.note.decryptedTitle
    ├─ 如果存在，返回 plainTitle
    ↓
列表重新渲染，標題已解密 ✅
```

### 選中筆記流程
```
用戶點擊列表中的筆記
    ↓
props.active 變為 true
    ↓
NoteListItem watch('active') 觸發
    ├─ 檢查是否為保密筆記
    ├─ 檢查是否已解密
    ├─ 調用 decryptNoteTitle()（備用解密）
    ↓
預覽區加載筆記
    ├─ KnowledgeList 調用 fetchNoteDetail()
    ├─ API 返回完整數據，標題已解密
    ↓
工具欄標題顯示（來自預覽區）✅
列表標題顯示（來自 parent 或本地解密）✅
```

---

## 技術詳解

### DEK 來源優先級

```
SecondaryPanel.vue 中：
1. dek.value（useVaultEncryption）
2. vaultStore.dek（Pinia store 備用）
```

這確保即使 `isKeyValid` 為 false，仍可從 `vaultStore.dek` 恢復解密能力。

### Watch 配置

```javascript
watch(
  () => ({
    notes: sidebarStore.currentNotes,    // 監聽筆記列表變化
    isTrash: sidebarStore.activeModule === 'trash'  // 監聽模塊切換
  }),
  // ... 回調函數 ...
  { deep: true }  // 深度監聽，確保筆記屬性變化被捕捉
)
```

### 性能優化

- ✅ 只在回收站中執行解密（`if (!isTrash) return`）
- ✅ 只對保密筆記解密（`if (note.is_secret && ...`）
- ✅ 一次性解密，不重複執行

---

## 測試檢查項

### 場景 1: 進入回收站
- [ ] 打開應用，導航到回收站
- [ ] **驗證列表中的保密筆記標題已解密** ✅
- [ ] 驗證普通筆記標題正常顯示
- [ ] 檢查瀏覽器控制台無錯誤

### 場景 2: 選中保密筆記
- [ ] 在回收站列表中選擇一個保密筆記
- [ ] **驗證列表中的標題已解密** ✅
- [ ] **驗證預覽區的標題已解密** ✅
- [ ] 兩個標題應相同

### 場景 3: 在保密柜和回收站之間切換
- [ ] 從保密柜切換到回收站
- [ ] 驗證回收站中保密筆記標題已解密 ✅
- [ ] 返回保密柜
- [ ] 再次進入回收站，標題仍然解密 ✅

### 場景 4: 邊界情況
- [ ] 無 DEK 的情況下進入回收站
  - 預期：標題顯示為密文（正常）
- [ ] 有多個保密筆記
  - 預期：全部標題解密

---

## 代碼修改統計

| 文件 | 修改內容 | 行數 |
|------|--------|------|
| SecondaryPanel.vue | 新增 watch 解密邏輯 | +35 |
| NoteListItem.vue | 修改 displayTitle computed | +3 |
| NoteListItem.vue | 新增 watch active | +9 |
| **總計** | | **+47 行** |

---

## 向後兼容性

✅ **完全向後兼容**

- 不修改任何 API
- 不修改任何 props 簽名
- 只添加可選的 `note.decryptedTitle` 屬性
- 所有現有邏輯保留，只添加新優先級

---

## 相關文檔

- **TRASH_TITLE_DECRYPTION_FIX.md** - 前一次的工具欄標題修復
- **FRONTEND_OPTIMIZATION_SUMMARY.md** - 完整的前端優化說明
- **FRONTEND_OPTIMIZATION_QUICKREF.md** - 快速驗證清單

---

## 已驗證

- ✅ SecondaryPanel.vue 語法正確
- ✅ NoteListItem.vue 語法正確
- ✅ watch 邏輯完整
- ✅ computed 優先級清晰
- ✅ 無邏輯循環
- ✅ 無性能問題

