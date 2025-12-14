<template>
  <div class="forgot-password-container">
    <div class="forgot-password-card">
      <div class="card-header">
        <h1 class="card-title">
          <i class="fas fa-key"></i>
          重置密码
        </h1>
        <p class="card-subtitle">
          输入您的邮箱地址，我们将发送重置密码的链接
        </p>
      </div>

      <el-form
        ref="forgotFormRef"
        :model="forgotForm"
        :rules="forgotRules"
        class="forgot-form"
        label-position="top">

        <el-form-item label="邮箱地址" prop="email">
          <el-input
            v-model="forgotForm.email"
            type="email"
            placeholder="请输入您的邮箱地址"
            size="large"
            :prefix-icon="Message"
            clearable>
          </el-input>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="isLoading"
            :disabled="isCountingDown"
            class="submit-btn"
            @click="submitForm">
            <span v-if="!isCountingDown">发送重置链接</span>
            <span v-else>{{ countdown }}秒后可重新发送</span>
          </el-button>
        </el-form-item>

        <el-form-item v-if="message.text" class="message-item">
          <el-alert
            :title="message.text"
            :type="message.type"
            :closable="false"
            show-icon>
          </el-alert>
        </el-form-item>
      </el-form>

      <div class="card-footer">
        <a href="/login" class="back-to-login">
          <i class="fas fa-arrow-left"></i>
          返回登录
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Message } from '@element-plus/icons-vue';
const forgotFormRef = ref(null);
const isLoading = ref(false);
const isCountingDown = ref(false);
const countdown = ref(60);

// 表单数据
const forgotForm = reactive({
  email: ''
});

// 消息提示
const message = reactive({
  text: '',
  type: 'info' // 'success', 'error', 'warning', 'info'
});

// 表单验证规则
const forgotRules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    {
      type: 'email',
      message: '请输入正确的邮箱格式',
      trigger: ['blur', 'change']
    }
  ]
};

// 提交表单
const submitForm = async () => {
  if (!forgotFormRef.value) return;

  try {
    const valid = await forgotFormRef.value.validate();
    if (!valid) return;

    isLoading.value = true;
    message.text = '';

    // 调用后端API发送重置密码邮件
    const response = await fetch('/api/password-reset/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCSRFToken()
      },
      body: JSON.stringify({
        email: forgotForm.email
      })
    });

    const data = await response.json();

    if (response.ok) {
      message.text = data.message || '重置密码链接已发送到您的邮箱，请查收';
      message.type = 'success';

      // 开始倒计时
      startCountdown();

      ElMessage.success('邮件发送成功，请查收邮箱');
    } else {
      message.text = data.message || '发送失败，请稍后重试';
      message.type = 'error';
      ElMessage.error(data.message || '发送失败');
    }
  } catch (error) {
    console.error('发送重置密码邮件失败:', error);
    message.text = '网络错误，请稍后重试';
    message.type = 'error';
    ElMessage.error('网络错误，请稍后重试');
  } finally {
    isLoading.value = false;
  }
};

// 倒计时
const startCountdown = () => {
  isCountingDown.value = true;
  countdown.value = 60;

  const timer = setInterval(() => {
    countdown.value--;
    if (countdown.value <= 0) {
      clearInterval(timer);
      isCountingDown.value = false;
    }
  }, 1000);
};

// 获取CSRF Token
const getCSRFToken = () => {
  const name = 'csrftoken';
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
};
</script>

<style scoped>
.forgot-password-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  background-image: url('/static/img/白金极简纹理.jpg');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}

.forgot-password-card {
  width: 100%;
  max-width: 450px;
  padding: 3rem;
  background: var(--bg-primary);
  border-radius: 20px;
  box-shadow: var(--shadow-dark);
  transition: var(--transition-base);
}

.card-header {
  text-align: center;
  margin-bottom: 2rem;
}

.card-title {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.card-subtitle {
  color: var(--text-secondary);
  font-size: 0.95rem;
  margin: 0;
}

.forgot-form {
  margin-bottom: 2rem;
}

.submit-btn {
  width: 100%;
  font-size: 1rem;
  font-weight: 600;
  padding: 1rem;
  border-radius: 12px;
}

.message-item {
  margin-top: 1.5rem;
}

.card-footer {
  text-align: center;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-light);
}

.back-to-login {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.9rem;
  transition: var(--transition-fast);
}

.back-to-login:hover {
  color: var(--primary-color);
}

/* 响应式设计 */
@media (max-width: 480px) {
  .forgot-password-container {
    padding: 1rem;
  }

  .forgot-password-card {
    padding: 2rem 1.5rem;
  }

  .card-title {
    font-size: 1.75rem;
  }
}
</style>