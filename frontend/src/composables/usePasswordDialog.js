import { ref, watch, computed } from 'vue';
import { ElMessage } from 'element-plus';

export function usePasswordDialog(props, emit) {
  // Local state
  const visible = ref(props.modelValue);
  const form = ref({
    current: '',
    new: '',
    confirm: ''
  });

  // Password strength
  const passwordStrength = ref({
    level: '',
    text: '',
    percent: 0
  });

  // Check password strength
  const checkPasswordStrength = () => {
    const password = form.value.new;
    if (!password) {
      passwordStrength.value = { level: '', text: '', percent: 0 };
      return;
    }

    let score = 0;

    // Length check
    if (password.length >= 8) score += 1;
    if (password.length >= 12) score += 1;
    if (password.length >= 16) score += 1;

    // Character variety
    if (/[a-z]/.test(password)) score += 1;
    if (/[A-Z]/.test(password)) score += 1;
    if (/[0-9]/.test(password)) score += 1;
    if (/[^a-zA-Z0-9]/.test(password)) score += 1;

    if (score <= 2) {
      passwordStrength.value = { level: 'weak', text: '弱', percent: 25 };
    } else if (score <= 4) {
      passwordStrength.value = { level: 'medium', text: '中等', percent: 50 };
    } else if (score <= 5) {
      passwordStrength.value = { level: 'strong', text: '强', percent: 75 };
    } else {
      passwordStrength.value = { level: 'very-strong', text: '非常强', percent: 100 };
    }
  };

  // Can submit
  const canSubmit = computed(() => {
    return form.value.current &&
           form.value.new &&
           form.value.new.length >= 8 &&
           form.value.new === form.value.confirm;
  });

  // Watch for prop changes
  watch(() => props.modelValue, (newValue) => {
    visible.value = newValue;
  });

  // Watch for visibility changes
  watch(visible, (newValue) => {
    emit('update:modelValue', newValue);
  });

  // Reset form
  const resetForm = () => {
    form.value = {
      current: '',
      new: '',
      confirm: ''
    };
    passwordStrength.value = { level: '', text: '', percent: 0 };
  };

  // Handle submit
  const handleSubmit = () => {
    // Validation
    if (!form.value.current) {
      ElMessage.warning('请输入当前密码');
      return;
    }
    if (!form.value.new) {
      ElMessage.warning('请输入新密码');
      return;
    }
    if (!form.value.confirm) {
      ElMessage.warning('请确认新密码');
      return;
    }
    if (form.value.new !== form.value.confirm) {
      ElMessage.warning('两次输入的密码不一致');
      return;
    }
    if (form.value.new.length < 8) {
      ElMessage.warning('新密码至少8位');
      return;
    }

    // Emit submit event with form data
    emit('submit', {
      current_password: form.value.current,
      new_password: form.value.new,
      confirm_password: form.value.confirm
    });
  };

  return {
    visible,
    form,
    passwordStrength,
    canSubmit,
    checkPasswordStrength,
    resetForm,
    handleSubmit
  };
}