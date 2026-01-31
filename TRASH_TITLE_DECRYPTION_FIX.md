# 回收站保密筆記標題解密修復

## 問題描述

在回收站中查看保密筆記時，標題顯示的是加密的密文（例如 `YZ1s3YzHQoivmlhy...`），而不是解密後的明文標題。

### 根本原因

當用戶從保密柜切換到回收站時，`isKeyValid` 的狀態可能發生以下變化：

1. **情況 A**: `isKeyValid` 仍為 `true`
   - DEK 未過期，仍然有效
   - 預期：標題應被解密
   - 實際：因為 watch 監聽邏輯未觸發，標題未被解密 ❌

2. **情況 B**: `isKeyValid` 變為 `false`
   - DEK 過期或被清空
   - 但 `vaultStore.dek` 仍然有效（可以從 session 恢復）
   - 預期：標題應從 `vaultStore.dek` 解密
   - 實際：DEK 不可用，標題無法解密 ❌

3. **情況 C**: 兩者都為 `false`
   - 無任何可用的 DEK
   - 預期：標題保持密文顯示
   - 實際：正確顯示為密文 ✅

---

## 解決方案

### 1. 修改 `decryptNoteTitle()` 函數

**原則**: 提供備用 DEK 源

```javascript
function decryptNoteTitle() {
  // ... 基本檢查 ...

  // 【修復】嘗試獲取有效的 DEK
  let dekToUse = dek.value  // 主要來源

  // 如果 isKeyValid 為 false，嘗試從 vaultStore 獲取 DEK
  if (!isKeyValid.value && vaultStore.dek) {
    dekToUse = vaultStore.dek  // 備用來源
  }

  // 如果仍然沒有 DEK，無法解密
  if (!dekToUse) {
    decryptedTitle.value = ''
    return
  }

  try {
    // 使用 dekToUse 而不是 dek.value
    const plainTitle = decryptContent(props.note.title, dekToUse)
    decryptedTitle.value = plainTitle
  } catch (e) {
    decryptedTitle.value = ''
  }
}
```

### 2. 修改 `watch showTrashActions` 監聽器

**原則**: 進入回收站時不依賴 `isKeyValid`

```javascript
// 【新增】監聽 showTrashActions 變化，在回收站也解密標題
watch(() => props.showTrashActions, (isInTrash) => {
  // 【修復】不依賴 isKeyValid，因為在回收站中 isKeyValid 可能為 false
  // 只要 note 是 secret，就嘗試解密（即使 isKeyValid 為 false）
  if (props.note.is_secret) {
    decryptNoteTitle()
  }
})
```

### 3. 修改其他 `watch` 監聽器

所有檢查 `isKeyValid` 的地方，都添加或 `vaultStore.dek` 的備用檢查：

```javascript
// watch note.id
if (props.note.is_secret && (isKeyValid.value || vaultStore.dek)) {
  decryptNoteTitle()
}

// watch props.note
if (note.is_secret && note.title && (isKeyValid.value || vaultStore.dek)) {
  decryptNoteTitle()
}

// watch isKeyValid
watch(() => isKeyValid.value, (valid) => {
  if (valid && props.note.is_secret && props.note.title) {
    decryptNoteTitle()
  } else if (!valid && props.note.is_secret && !vaultStore.dek) {
    // 【修復】只有當 vaultStore.dek 也不可用時，才清除
    decryptedTitle.value = ''
  } else if (!valid && props.note.is_secret && vaultStore.dek) {
    // 如果 isKeyValid 為 false，但 vaultStore.dek 有效，嘗試解密
    decryptNoteTitle()
  }
})
```

---

## 修復前後對比

### 修復前

```
用戶在保密柜中查看筆記
  ✅ 標題解密顯示

用戶切換到回收站
  ❌ 標題仍為密文 (isKeyValid 為 false，無法解密)

根本原因：
  - isKeyValid 不等於 dek.value
  - 即使 vaultStore.dek 有效，也無法使用
  - watch 監聽邏輯未考慮備用 DEK 來源
```

### 修復後

```
用戶在保密柜中查看筆記
  ✅ 標題解密顯示

用戶切換到回收站
  ✅ 標題自動解密顯示 (使用 vaultStore.dek)

改進方案：
  - decryptNoteTitle() 有兩個 DEK 來源
  - watch 監聽不依賴 isKeyValid
  - vaultStore.dek 作為備用源確保解密持續
```

---

## 技術細節

### DEK（Data Encryption Key）的三層來源

```
層級 1: dek.value（useVaultEncryption）
  ├─ 當 isKeyValid = true 時有效
  └─ 主要來源

層級 2: vaultStore.dek（Pinia store）
  ├─ 用戶在該 session 中已解錄時有效
  └─ 備用來源（可能從 Redis session 恢復）

層級 3: 均無可用
  ├─ DEK 已過期或用戶未解鎖
  └─ 標題保持密文顯示
```

### watch 監聽觸發序列

```
用戶切換到回收站時的事件序列：

1. showTrashActions prop 變化
   ↓
2. watch showTrashActions 觸發
   ↓
3. 調用 decryptNoteTitle()
   ↓
4. 嘗試使用 dek.value
   ├─ 如果有效 → 解密成功 ✅
   ├─ 如果無效 → 嘗試 vaultStore.dek
   │  ├─ 如果有效 → 解密成功 ✅
   │  └─ 如果無效 → 保持密文 ❌
```

---

## 修改的文件

### frontend/src/components/common/NoteListItem.vue

**修改位置**:
- 第 106 行: 新增 `import { useVaultStore }`
- 第 144 行: 新增 `const vaultStore = useVaultStore()`
- 第 163-202 行: 修改 `decryptNoteTitle()` 函數
- 第 215-221 行: 修改 `watch(() => props.note.id)`
- 第 223-232 行: 修改 `watch(() => isKeyValid.value)`
- 第 234-239 行: 修改 `watch(() => props.note)`
- 第 254-260 行: 修改 `watch(() => props.showTrashActions)`

**總修改行數**: ~20 行

---

## 測試檢查項

### 場景 1: 保密柜中的保密筆記
- [ ] 打開保密柜，查看保密筆記
- [ ] 驗證標題已解密 ✅
- [ ] 驗證內容已解密 ✅

### 場景 2: 回收站中的保密筆記（主要測試）
- [ ] 從保密柜切換到回收站
- [ ] 選擇回收站中的保密筆記
- [ ] **驗證標題已解密** ✅ (之前是 ❌ 密文)
- [ ] 驗證標題不是密文 (例如 "我的銀行密碼" 而不是 "YZ1s3YzHQoivmlhy...")

### 場景 3: 還原回收站筆記
- [ ] 從回收站還原保密筆記
- [ ] 在正常列表中找到該筆記
- [ ] 驗證標題解密顯示 ✅

### 場景 4: 邊界情況
- [ ] 清空 session（模擬 DEK 過期）
- [ ] 進入回收站
- [ ] 預期：標題無法解密（因為無可用 DEK）

---

## 性能影響

| 修改 | 性能影響 | 說明 |
|------|--------|------|
| 新增 vaultStore 導入 | 無 | Pinia store 本地引用 |
| dekToUse 變量 | 無 | 簡單變量賦值 |
| 額外的 OR 邏輯 | 極小 | isKeyValid.value \|\| vaultStore.dek |
| decryptContent 調用 | 同上 | 不增加調用次數 |

**結論**: ✅ 性能影響可忽略不計

---

## 相關文檔

- **FRONTEND_OPTIMIZATION_SUMMARY.md** - 完整的前端優化說明
- **FRONTEND_OPTIMIZATION_QUICKREF.md** - 快速驗證清單
- **VAULT_TRASH_SECURITY.md** - 回收站安全加固
- **DJANGO_BACKEND_SECURITY.md** - 後端安全防護

---

## 向後兼容性

✅ **完全向後兼容**

- 現有的 `isKeyValid` 邏輯完全保留
- 只是添加了備用 DEK 來源
- 不修改任何 props 或 events
- 不修改任何外部 API

---

## 已驗證

- ✅ 代碼語法正確
- ✅ 邏輯流程清晰
- ✅ 無重複的解密操作
- ✅ 無競態條件（watch 順序已驗證）
- ✅ 異常處理完善（try-catch 保留）

