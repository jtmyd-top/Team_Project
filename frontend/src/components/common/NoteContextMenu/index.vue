<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="visible"
        class="context-menu-overlay"
        @click="handleOverlayClick"
        @contextmenu.prevent
      >
        <div
          ref="menuRef"
          class="context-menu"
          :style="menuStyle"
          @click.stop
        >
          <!-- 新建笔记 -->
          <div class="menu-item" @click="handleAction('create')">
            <i class="fas fa-plus"></i>
            <span>新建笔记</span>
          </div>

          <div class="menu-divider"></div>

          <!-- 重命名 -->
          <div class="menu-item" @click="handleAction('rename')">
            <i class="fas fa-edit"></i>
            <span>重命名</span>
            <span class="shortcut">F2</span>
          </div>

          <!-- 收藏/取消收藏 -->
          <div class="menu-item" @click="handleAction('favorite')">
            <i class="fas" :class="note?.is_favorited ? 'fa-star' : 'fa-star'"></i>
            <span>{{ note?.is_favorited ? '取消收藏' : '添加收藏' }}</span>
          </div>

          <div class="menu-divider"></div>

          <!-- 加入/移出保险柜 -->
          <div class="menu-item" @click="handleAction('toggle-secret')">
            <i class="fas" :class="note?.is_secret ? 'fa-unlock' : 'fa-lock'"></i>
            <span>{{ note?.is_secret ? '移出保险柜' : '加入保险柜' }}</span>
          </div>

          <div class="menu-divider"></div>

          <!-- 移动到 -->
          <div class="menu-item has-submenu" @click="handleAction('move')">
            <i class="fas fa-folder-open"></i>
            <span>移动到...</span>
            <i class="fas fa-chevron-right submenu-arrow"></i>
          </div>

          <!-- 复制到 -->
          <div class="menu-item has-submenu" @click="handleAction('copy')">
            <i class="fas fa-copy"></i>
            <span>复制到...</span>
            <i class="fas fa-chevron-right submenu-arrow"></i>
          </div>

          <div class="menu-divider"></div>

          <!-- 复制链接 -->
          <div class="menu-item" @click="handleAction('copyLink')">
            <i class="fas fa-link"></i>
            <span>复制链接</span>
          </div>

          <!-- 在新窗口打开 -->
          <div class="menu-item" @click="handleAction('openNew')">
            <i class="fas fa-external-link-alt"></i>
            <span>在新标签页打开</span>
          </div>

          <div class="menu-divider"></div>

          <!-- 移入回收站 -->
          <div class="menu-item danger" @click="handleAction('trash')">
            <i class="fas fa-trash"></i>
            <span>移入回收站</span>
            <span class="shortcut">Del</span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { useNoteContextMenu } from '@/composables/useNoteContextMenu'
import '@/assets/styles/components/note-context-menu.css'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  x: {
    type: Number,
    default: 0
  },
  y: {
    type: Number,
    default: 0
  },
  note: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'action'])

const {
  menuRef,
  menuStyle,
  handleOverlayClick,
  handleAction
} = useNoteContextMenu(props, emit)
</script>
