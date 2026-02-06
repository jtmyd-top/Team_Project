// frontend/src/composables/useDashboard.js
import { ref } from 'vue'

export function useDashboard() {
  const isFullscreen = ref(false)

  async function toggleFullscreen() {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen()
        isFullscreen.value = true
      } else {
        await document.exitFullscreen()
        isFullscreen.value = false
      }
    } catch {
      // Fullscreen may be blocked by browser policy or user denial
    }
  }

  function onFullscreenChange() {
    isFullscreen.value = !!document.fullscreenElement
  }

  function setupFullscreenListener() {
    document.addEventListener('fullscreenchange', onFullscreenChange)
  }

  function removeFullscreenListener() {
    document.removeEventListener('fullscreenchange', onFullscreenChange)
  }

  return {
    isFullscreen,
    toggleFullscreen,
    setupFullscreenListener,
    removeFullscreenListener,
  }
}
