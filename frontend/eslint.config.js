import vue from 'eslint-plugin-vue'

export default [
  {
    ignores: ['**/*.timestamp-*.mjs', '**/dist/**', '**/node_modules/**'],
  },
  ...vue.configs['flat/recommended'],
  {
    files: ['**/*.{js,mjs,cjs,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
    },
    rules: {
      'vue/multi-word-component-names': 'off',
    },
  },
]
