# CKEditor 5 前端代码清理指南

**更新时间**: 2026-01-25
**目标**: 清理前端未使用的 CKEditor 代码，保留 Django admin 的功能

---

## 📊 现状分析

### 编辑器使用情况

| 编辑器 | 位置 | 状态 | 用途 |
|-------|------|------|------|
| **TinyMCE** | 前端 | ✅ 主动使用 | 笔记编辑（NoteEditor.vue） |
| **CKEditor 5** | Django admin | ✅ 主要使用 | Admin 后台笔记编辑 |
| **CKEditor 5** | 前端 | ❌ 未使用 | - |

### 验证结果

```
✓ 前端 Vue 组件：无 CKEditor 5 导入
✓ HTML templates：无 CKEditor 5 脚本引用
✓ 前端 JavaScript：无 CKEditor 5 调用
✓ Django admin：需要 CKEditor 5（NoteAdmin.py 第 12、50 行使用）
```

---

## 🎯 清理方案

### 方案 A：完全清理（推荐）- 删除冗余的 django-ckeditor

**适用场景**：
- 不使用 django-ckeditor（非 -5 版本）
- 只使用 django-ckeditor-5（推荐）

**步骤**：

1. **更新 requirements.txt**
   ```bash
   # 删除这一行：
   django-ckeditor==6.7.3

   # 保留这一行：
   django-ckeditor-5==0.2.18
   ```

2. **验证 Django 配置**
   ```bash
   # 检查 settings.py
   grep "django_ckeditor" Team_Project/settings.py
   # 应该只有 django_ckeditor_5，没有 django_ckeditor
   ```

3. **更新依赖**
   ```bash
   pip uninstall django-ckeditor -y
   pip install -r requirements.txt
   ```

4. **验证 Admin 功能**
   ```bash
   python manage.py runserver
   # 访问 /admin/knowledge_project/note/
   # 确认可以编辑笔记内容
   ```

### 方案 B：保持现状

如果不想修改 requirements.txt（由于 UTF-16 编码问题），目前的设置也是安全的：
- admin.py 只导入 `django_ckeditor_5` 的 `CKEditor5Widget`
- 不导入任何 `django_ckeditor`（非 -5）的模块
- django-ckeditor==6.7.3 是冗余的但不会破坏功能

---

## 📝 清理检查清单

### 已验证不使用（可安全忽视）

- ❌ 前端 Vue 组件未使用 CKEditor 5
  - NoteEditor.vue 使用 TinyMCE
  - 无 import CKEditor5 语句

- ❌ 前端 JavaScript 未调用 CKEditor 5
  - 无 window.CKEditor 引用
  - 无 CKEditor5 初始化代码

- ❌ HTML templates 未加载 CKEditor 5
  - knowledge_list.html 只加载 TinyMCE
  - 无 ckeditor.js 或 ckeditor5.js 引用

### 必须保留（Django admin 需要）

- ✅ django-ckeditor-5 包（requirements.txt）
- ✅ admin.py 中的 CKEditor5Widget 导入
- ✅ admin.py 中的 NoteAdminForm
- ✅ models.py 中的 CKEditor5Field
- ✅ settings.py 中的 CKEDITOR_5_* 配置
- ✅ /api/upload/ckeditor_image/ 端点

---

## 🔧 手动清理（如果编码问题持续）

如果自动删除失败，可以手动编辑：

### requirements.txt 修改

```diff
- django-ckeditor==6.7.3
  django-ckeditor-5==0.2.18
```

使用方法：
1. 用文本编辑器打开 requirements.txt
2. 找到 `django-ckeditor==6.7.3` 这一行
3. 删除整行
4. 保存文件

### 验证修改

```bash
# 检查是否还有多余的包
grep -i "^django-ckeditor" requirements.txt
# 应该只返回：django-ckeditor-5==0.2.18
```

---

## 📚 相关文件位置

### Django Admin 使用 CKEditor 5

| 文件 | 行号 | 用途 |
|-----|------|------|
| `knowledge_project/models.py` | 9, 92 | CKEditor5Field 定义 |
| `knowledge_project/admin.py` | 12, 47-51, 59 | CKEditor5Widget 使用 |
| `Team_Project/settings.py` | 38, 166-236 | CKEDITOR_5_* 配置 |
| `knowledge_project/urls.py` | 26 | ckeditor_image_upload_view 路由 |

### 前端使用 TinyMCE（非 CKEditor）

| 文件 | 位置 | 用途 |
|-----|------|------|
| `frontend/src/components/knowledge/NoteEditor.vue` | 整个文件 | TinyMCE 编辑器 |
| `knowledge_project/templates/knowledge/knowledge_list.html` | 8-10 | TinyMCE 脚本加载 |

---

## ✅ 清理前后对比

### 清理前

```
requirements.txt:
- django-ckeditor==6.7.3              (冗余)
- django-ckeditor-5==0.2.18           (需要)

admin.py:
- 使用 CKEditor5Widget                (✓ 正确)

前端:
- 无 CKEditor 使用                    (✓ 正确)
- 使用 TinyMCE                        (✓ 正确)
```

### 清理后

```
requirements.txt:
- django-ckeditor-5==0.2.18           (保留)

admin.py:
- 使用 CKEditor5Widget                (✓ 正确，无变化)

前端:
- 无 CKEditor 使用                    (✓ 正确，无变化)
- 使用 TinyMCE                        (✓ 正确，无变化)
```

---

## 🔍 故障排除

### 问题：Admin 后台无法编辑笔记

**原因**：删除了必要的 django-ckeditor-5 包
**解决**：
```bash
pip install django-ckeditor-5==0.2.18
```

### 问题：前端笔记编辑器不工作

**原因**：意外删除了 TinyMCE（不在本清理范围内）
**解决**：
```bash
git checkout frontend/src/components/knowledge/NoteEditor.vue
```

### 问题：图片上传失败

**原因**：删除了上传视图
**解决**：
确保 `knowledge_project/views.py` 中有 `ckeditor_image_upload_view` 和 `image_upload_view`

---

## 📋 完整清理清单

- [ ] 更新 requirements.txt（删除 django-ckeditor==6.7.3）
- [ ] 运行 `pip install -r requirements.txt`
- [ ] 运行 `pip uninstall django-ckeditor -y`
- [ ] 测试 Django admin 笔记编辑
- [ ] 测试前端笔记编辑（应该使用 TinyMCE）
- [ ] 上传图片测试
- [ ] 提交更改到 Git

---

## 🚀 自动化清理脚本

详见 `cleanup_ckeditor.py` 文件

```bash
python cleanup_ckeditor.py
```

---

## 总结

✅ **前端代码**：已验证无 CKEditor 5 使用，无需修改
✅ **Django admin**：保留所有 CKEditor 5 配置，功能完整
✅ **优化**：可删除冗余的 django-ckeditor 包（非 -5 版本）

**建议行动**：执行 `cleanup_ckeditor.py` 脚本自动清理 requirements.txt

---

**文档版本**: 1.0
**最后更新**: 2026-01-25
**维护者**: Backend Team
