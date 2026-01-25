/**
 * Composables 统一导出
 *
 * 用法:
 * import { useCodeEnhancer, useNotification, usePasswordStrength, useTurnstile } from '@/composables'
 */

export { useCodeEnhancer, enhanceCodeBlocks, getCodeEnhancerStyles } from './useCodeEnhancer'
export {
  useNotification,
  showNotification,
  showSuccess,
  showError,
  showWarning,
  showInfo,
  closeNotification,
  closeAllNotifications
} from './useNotification'
export {
  usePasswordStrength,
  calculateStrength,
  validatePasswordRules,
  isPasswordValid,
  getPasswordStrengthStyles
} from './usePasswordStrength'
export {
  useTurnstile,
  createTurnstileRule,
  turnstileProps
} from './useTurnstile'

export {
  useTheme,
  getGlobalTheme,
  isLightTheme
} from './useTheme'
export {
  useConfirm,
  showConfirm
} from './useConfirm'