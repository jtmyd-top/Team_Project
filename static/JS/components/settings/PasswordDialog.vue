<template>
  <el-dialog
    v-model="visible"
    title="修改密码"
    width="500px"
    @close="resetForm">
    
    <el-form label-width="120px">
      <el-form-item label="当前密码">
        <el-input
          v-model="form.current"
          type="password"
          show-password
          placeholder="请输入当前密码">
        </el-input>
      </el-form-item>

      <el-form-item label="新密码">
        <el-input
          v-model="form.new"
          type="password"
          show-password
          placeholder="至少8位字符">
        </el-input>
      </el-form-item>

      <el-form-item label="确认新密码">
        <el-input
          v-model="form.confirm"
          type="password"
          show-password
          placeholder="再次输入新密码">
        </el-input>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="handleSubmit">确认修改</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

// Props
const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

// Emits
const emit = defineEmits(['update:modelValue', 'submit'])

// Local state
const visible = ref(props.modelValue)
const form = ref({
  current: '',
  new: '',
  confirm: ''
})

// Watch for prop changes
watch(() => props.modelValue, (newValue) => {
  visible.value = newValue
})

// Watch for visibility changes
watch(visible, (newValue) => {
  emit('update:modelValue', newValue)
})

// Reset form
const resetForm = () => {
  form.value = {
    current: '',
    new: '',
    confirm: ''
  }
}

// Handle submit
const handleSubmit = () => {
  // Validation
  if (!form.value.current) {
    ElMessage.warning('请输入当前密码')
    return
  }
  if (!form.value.new) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (!form.value.confirm) {
    ElMessage.warning('请确认新密码')
    return
  }
  if (form.value.new !== form.value.confirm) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  if (form.value.new.length < 8) {
    ElMessage.warning('新密码至少8位')
    return
  }

  // Emit submit event with form data
  emit('submit', {
    current_password: form.value.current,
    new_password: form.value.new,
    confirm_password: form.value.confirm
  })
}
</script>

<style scoped>
/* 组件特定样式 */
</style>
