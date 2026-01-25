/**
 * usePasswordStrength - 密码强度检测
 *
 * 统一了 Signup.vue 和 ResetPassword.vue 中的密码强度检测逻辑
 */

import { ref, computed, watch } from 'vue'

// 密码强度等级配置
const STRENGTH_LEVELS = [
  { level: 0, text: '请输入密码', color: '#909399', class: '' },
  { level: 1, text: '太弱', color: '#f56c6c', class: 'weak' },
  { level: 2, text: '较弱', color: '#e6a23c', class: 'fair' },
  { level: 3, text: '一般', color: '#409eff', class: 'good' },
  { level: 4, text: '较强', color: '#67c23a', class: 'strong' },
  { level: 5, text: '很强', color: '#529b2e', class: 'very-strong' }
]

// 默认验证规则
const DEFAULT_RULES = [
  { id: 'length', text: '至少8个字符', test: (p) => p.length >= 8 },
  { id: 'uppercase', text: '包含大写字母', test: (p) => /[A-Z]/.test(p) },
  { id: 'lowercase', text: '包含小写字母', test: (p) => /[a-z]/.test(p) },
  { id: 'number', text: '包含数字', test: (p) => /\d/.test(p) }
]

// 额外的强度加分规则
const BONUS_RULES = [
  { id: 'longLength', text: '长度超过12位', test: (p) => p.length >= 12 },
  { id: 'special', text: '包含特殊字符', test: (p) => /[^a-zA-Z\d]/.test(p) },
  { id: 'mixedCase', text: '同时包含大小写', test: (p) => /[a-z]/.test(p) && /[A-Z]/.test(p) }
]

/**
 * 计算密码强度
 * @param {string} password - 密码
 * @param {Array} rules - 验证规则
 * @returns {Object} 强度信息
 */
export function calculateStrength(password, rules = DEFAULT_RULES) {
  if (!password) {
    return STRENGTH_LEVELS[0]
  }

  let strength = 0

  // 基础规则检测
  if (password.length >= 8) strength++
  if (password.length >= 12) strength++
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++
  if (/\d/.test(password)) strength++
  if (/[^a-zA-Z\d]/.test(password)) strength++

  const level = Math.min(strength, 5)
  return STRENGTH_LEVELS[level]
}

/**
 * 验证密码规则
 * @param {string} password - 密码
 * @param {Array} rules - 验证规则
 * @returns {Array} 带有验证结果的规则数组
 */
export function validatePasswordRules(password, rules = DEFAULT_RULES) {
  return rules.map(rule => ({
    ...rule,
    valid: rule.test(password)
  }))
}

/**
 * 检查密码是否满足所有基本规则
 * @param {string} password - 密码
 * @param {Array} rules - 验证规则
 * @returns {boolean}
 */
export function isPasswordValid(password, rules = DEFAULT_RULES) {
  return rules.every(rule => rule.test(password))
}

/**
 * Vue Composable: usePasswordStrength
 *
 * 用法:
 * ```js
 * import { usePasswordStrength } from '@/composables/usePasswordStrength'
 *
 * const {
 *   password,
 *   strength,
 *   rules,
 *   isValid,
 *   strengthText,
 *   strengthColor,
 *   strengthClass,
 *   strengthPercent
 * } = usePasswordStrength()
 *
 * // 或者传入外部的密码 ref
 * const { strength, rules, isValid } = usePasswordStrength(externalPasswordRef)
 * ```
 */
export function usePasswordStrength(externalPassword = null, customRules = null) {
  // 密码值（可以使用外部传入的 ref 或创建新的）
  const password = externalPassword || ref('')

  // 使用的规则
  const ruleSet = customRules || DEFAULT_RULES

  // 验证规则状态
  const rules = ref(ruleSet.map(rule => ({ ...rule, valid: false })))

  // 密码强度
  const strength = ref(STRENGTH_LEVELS[0])

  // 计算属性
  const isValid = computed(() => rules.value.every(r => r.valid))
  const strengthText = computed(() => strength.value.text)
  const strengthColor = computed(() => strength.value.color)
  const strengthClass = computed(() => strength.value.class)
  const strengthLevel = computed(() => strength.value.level)
  const strengthPercent = computed(() => (strength.value.level / 5) * 100)

  // 更新密码强度和规则验证
  const updateStrength = () => {
    const pwd = password.value || ''

    // 更新规则验证状态
    rules.value = ruleSet.map(rule => ({
      ...rule,
      valid: rule.test(pwd)
    }))

    // 更新强度
    strength.value = calculateStrength(pwd, ruleSet)
  }

  // 监听密码变化
  watch(password, updateStrength, { immediate: true })

  // 手动触发验证
  const validate = () => {
    updateStrength()
    return isValid.value
  }

  // 重置状态
  const reset = () => {
    if (!externalPassword) {
      password.value = ''
    }
    rules.value = ruleSet.map(rule => ({ ...rule, valid: false }))
    strength.value = STRENGTH_LEVELS[0]
  }

  return {
    // 状态
    password,
    strength,
    rules,

    // 计算属性
    isValid,
    strengthText,
    strengthColor,
    strengthClass,
    strengthLevel,
    strengthPercent,

    // 方法
    validate,
    reset,
    updateStrength
  }
}

/**
 * 获取密码强度指示器的 CSS 样式
 * @returns {string} CSS 样式字符串
 */
export function getPasswordStrengthStyles() {
  return `
  .password-strength {
    margin-top: 8px;
  }

  .strength-bars {
    display: flex;
    gap: 4px;
    margin-bottom: 4px;
  }

  .strength-bar {
    flex: 1;
    height: 4px;
    background: #e0e0e0;
    border-radius: 2px;
    transition: background-color 0.3s ease;
  }

  .strength-bar.active.weak { background: #f56c6c; }
  .strength-bar.active.fair { background: #e6a23c; }
  .strength-bar.active.good { background: #409eff; }
  .strength-bar.active.strong { background: #67c23a; }
  .strength-bar.active.very-strong { background: #529b2e; }

  .strength-text {
    font-size: 12px;
    color: #909399;
  }

  .strength-text.weak { color: #f56c6c; }
  .strength-text.fair { color: #e6a23c; }
  .strength-text.good { color: #409eff; }
  .strength-text.strong { color: #67c23a; }
  .strength-text.very-strong { color: #529b2e; }

  /* 密码规则列表 */
  .password-rules {
    margin-top: 8px;
    padding: 8px 12px;
    background: rgba(0, 0, 0, 0.02);
    border-radius: 6px;
    font-size: 12px;
  }

  .password-rule {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 2px 0;
    color: #909399;
    transition: color 0.2s;
  }

  .password-rule.valid {
    color: #67c23a;
  }

  .password-rule i {
    font-size: 10px;
  }
`
}

export default usePasswordStrength
