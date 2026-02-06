<template>
  <div class="note-toolbar">
    <div class="toolbar-left">
      <!-- 移动端菜单按钮 -->
      <button
        v-if="isMobile"
        class="icon-btn"
        @click="handleOpenSidebar"
        style="margin-right: 8px;"
      >
        <i class="fas fa-bars"></i>
      </button>

      <span v-if="note && !isLoading" class="meta-info">
        {{ getAuthorName(note.author) }} · 更新于 {{ formatDate(note.updated_at) }}
      </span>
    </div>

    <div class="toolbar-right">
      <button class="icon-btn theme-btn" @click="handleToggleTheme" title="切换主题">
        <i :class="isLightTheme ? 'fas fa-moon' : 'fas fa-sun'"></i>
      </button>

      <template v-if="note && !isLoading">
        <div class="divider-vertical"></div>

        <button class="icon-btn" @click="handleTogglePublic" :title="note.is_public ? '设为私密' : '设为公开'">
          <i :class="note.is_public ? 'fas fa-globe' : 'fas fa-lock'"></i>
        </button>

        <button v-if="note.is_public" class="icon-btn" @click="handleCopyLink" title="复制链接">
          <i class="fas fa-link"></i>
        </button>

        <div class="divider-vertical"></div>

        <template v-if="!isEditing">
          <button class="btn primary" @click="handleStartEdit">
            <i class="fas fa-edit"></i> <span>编辑</span>
          </button>
        </template>
        <template v-else>
          <button class="btn text" @click="handleCancelEdit">取消</button>
          <button class="btn primary" @click="handleSave">保存</button>
          <button class="icon-btn danger" @click="handleDelete" title="删除">
            <i class="fas fa-trash"></i>
          </button>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup>
import { useNoteToolbar } from '@composables/useNoteToolbar'
import '@/assets/styles/components/note-toolbar.css'

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

const emit = defineEmits([
  'open-sidebar',
  'toggle-theme',
  'toggle-public',
  'copy-link',
  'start-edit',
  'cancel-edit',
  'save',
  'delete'
])

const {
  formatDate,
  getAuthorName,
  handleOpenSidebar,
  handleToggleTheme,
  handleTogglePublic,
  handleCopyLink,
  handleStartEdit,
  handleCancelEdit,
  handleSave,
  handleDelete
} = useNoteToolbar(props, emit)
</script>
