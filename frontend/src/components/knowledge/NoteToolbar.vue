<template>
  <div class="note-toolbar">
    <div class="toolbar-left">
      <!-- 移动端菜单按钮 -->
      <button
        v-if="isMobile"
        class="icon-btn"
        @click="$emit('open-sidebar')"
        style="margin-right: 8px;"
      >
        <i class="fas fa-bars"></i>
      </button>

      <span v-if="note && !isLoading" class="meta-info">
        {{ getAuthorName(note.author) }} · 更新于 {{ formatDate(note.updated_at) }}
      </span>
    </div>

    <div class="toolbar-right">
      <button class="icon-btn theme-btn" @click="$emit('toggle-theme')" title="切换主题">
        <i :class="isLightTheme ? 'fas fa-moon' : 'fas fa-sun'"></i>
      </button>

      <template v-if="note && !isLoading">
        <div class="divider-vertical"></div>

        <button class="icon-btn" @click="$emit('toggle-public')" :title="note.is_public ? '设为私密' : '设为公开'">
          <i :class="note.is_public ? 'fas fa-globe' : 'fas fa-lock'"></i>
        </button>

        <button v-if="note.is_public" class="icon-btn" @click="$emit('copy-link')" title="复制链接">
          <i class="fas fa-link"></i>
        </button>

        <div class="divider-vertical"></div>

        <template v-if="!isEditing">
          <button class="btn primary" @click="$emit('start-edit')">
            <i class="fas fa-edit"></i> <span>编辑</span>
          </button>
        </template>
        <template v-else>
          <button class="btn text" @click="$emit('cancel-edit')">取消</button>
          <button class="btn primary" @click="$emit('save')">保存</button>
          <button class="icon-btn danger" @click="$emit('delete')" title="删除">
            <i class="fas fa-trash"></i>
          </button>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  note: {
    type: Object,
    default: null
  },
  isLoading: {
    type: Boolean,
    default: false
  },
  isEditing: {
    type: Boolean,
    default: false
  },
  isMobile: {
    type: Boolean,
    default: false
  },
  isLightTheme: {
    type: Boolean,
    default: true
  }
})

defineEmits([
  'open-sidebar',
  'toggle-theme',
  'toggle-public',
  'copy-link',
  'start-edit',
  'cancel-edit',
  'save',
  'delete'
])

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString()
}

const getAuthorName = (author) => author?.username || author || 'Unknown'
</script>

<style scoped>
.note-toolbar {
  height: 60px;
  border-bottom: 1px solid var(--k-border, #e0e0e0);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: var(--k-bg, #fff);
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.meta-info {
  font-size: 14px;
  color: var(--k-text-sec, #666);
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.icon-btn {
  background: transparent;
  border: none;
  color: var(--k-text-sec, #666);
  cursor: pointer;
  padding: 6px;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.icon-btn:hover {
  background: var(--k-hover, #f5f5f5);
  color: var(--k-text, #1a1a1a);
}

.icon-btn.danger:hover {
  color: #ef4444;
  background: #fee2e2;
}

.btn {
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.btn.primary {
  background: var(--k-primary, #1890ff);
  color: white;
}

.btn.primary:hover {
  opacity: 0.9;
}

.btn.text {
  background: transparent;
  color: var(--k-text, #1a1a1a);
}

.btn.text:hover {
  background: var(--k-hover, #f5f5f5);
}

.divider-vertical {
  width: 1px;
  height: 20px;
  background: var(--k-border, #e0e0e0);
  margin: 0 4px;
}

@media (max-width: 768px) {
  .note-toolbar {
    padding: 0 12px;
  }

  .btn {
    padding: 6px 10px;
    font-size: 12px;
  }

  .btn.primary span {
    display: none;
  }
}
</style>
