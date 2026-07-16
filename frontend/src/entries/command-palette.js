import { createApp } from 'vue'

import CommandPalette from '@components/common/CommandPalette/index.vue'

// Global command palette (Ctrl+K). Mounted on every authenticated page via
// base.html. Self-injects its own mount node so templates don't need markup.
function mountCommandPalette() {
  if (document.getElementById('command-palette-app')) return
  const host = document.createElement('div')
  host.id = 'command-palette-app'
  document.body.appendChild(host)
  createApp(CommandPalette).mount(host)
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mountCommandPalette)
} else {
  mountCommandPalette()
}
