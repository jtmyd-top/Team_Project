import { ref, reactive, computed } from 'vue';
import { useUserStore } from '../stores/user.js';
import { apiService } from '../services/apiService.js';
import { createDebouncedRequest, useCountdown } from '../utils/request.js';
import { ElMessage } from 'element-plus';

export function useSettingsAccount() {
  const userStore = useUserStore();

  // 对话框显示状态
  const showEmailDialog = ref(false);

  // 倒计时（两个独立的倒计时）
  const emailCountdown = useCountdown();  // 新邮箱验证码倒计时
  const twoFaCountdown = useCountdown();  // 2FA验证码倒计时

  // 验证码组件引用
  const captchaWidgetRef = ref(null);

  // 验证码参数（由 CaptchaWidget 更新）
  const captchaParams = ref({
    captcha_type: 'turnstile',
    turnstile_token: '',
    image_captcha: ''
  });

  // 监听验证码变化
  const onCaptchaChange = (params) => {
    captchaParams.value = params;
  };

  // 判断验证码是否已验证
  const isCaptchaVerified = computed(() => {
    const params = captchaParams.value;
    if (params.captcha_type === 'turnstile') {
      return !!params.turnstile_token;
    }
    return params.image_captcha && params.image_captcha.length >= 4;
  });

  // 邮箱表单
  const emailForm = reactive({
    new_email: '',
    password: '',
    code: '',
    codeSending: false,
    show2FA: false,
    twoFaMethod: '',
    twoFaCode: '',
    useBackup: false,
    twoFaCodeSending: false,
  });

  // 邮箱检查状态
  const emailCheck = reactive({
    status: null,
    message: ''
  });

  // 邮箱正则
  const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  /**
   * 刷新验证码
   */
  const refreshCaptcha = () => {
    if (captchaWidgetRef.value) {
      captchaWidgetRef.value.reset();
    }
  };

  /**
   * 邮箱检查核心逻辑
   */
  const checkEmailAvailabilityCore = async (signal) => {
    const email = (emailForm.new_email || '').trim();
    if (!email) {
      emailCheck.status = null;
      emailCheck.message = '';
      return;
    }

    if (!EMAIL_REGEX.test(email)) {
      emailCheck.status = 'invalid';
      emailCheck.message = '邮箱格式不正确';
      return;
    }

    try {
      const data = await apiService.checkEmail(email, true);
      if (data.is_taken) {
        emailCheck.status = 'taken';
        emailCheck.message = '该邮箱已被绑定';
      } else {
        emailCheck.status = 'ok';
        emailCheck.message = '该邮箱可用';
      }
    } catch (error) {
      if (error.name === 'AbortError') return;
      emailCheck.status = 'invalid';
      emailCheck.message = '邮箱检查失败，请稍后再试';
    }
  };

  /**
   * 防抖的邮箱检查
   */
  const checkEmailAvailability = createDebouncedRequest(checkEmailAvailabilityCore, 400);

  /**
   * 是否可以发送验证码
   */
  const canSendCode = computed(() => {
    return EMAIL_REGEX.test((emailForm.new_email || '').trim()) &&
           emailCheck.status === 'ok' &&
           isCaptchaVerified.value;
  });

  /**
   * 是否可以提交表单
   */
  const canSubmitEmail = computed(() => {
    if (!EMAIL_REGEX.test((emailForm.new_email || '').trim())) return false;
    if (emailCheck.status !== 'ok') return false;
    if (!(emailForm.password || '').trim()) return false;
    if (!(emailForm.code || '').trim()) return false;

    // 如果2FA已显示，则必须输入2FA代码
    if (emailForm.show2FA && !(emailForm.twoFaCode || '').trim()) return false;

    return true;
  });

  /**
   * 发送邮箱验证码
   */
  const sendEmailCode = async () => {
    const email = (emailForm.new_email || '').trim();
    if (!EMAIL_REGEX.test(email)) return ElMessage.warning("请输入正确邮箱");
    if (emailCheck.status !== 'ok') return ElMessage.warning(emailCheck.message || "该邮箱不可用");

    // 验证验证码
    if (captchaWidgetRef.value && !captchaWidgetRef.value.validate()) {
      return;
    }

    emailForm.codeSending = true;
    try {
      const data = await apiService.sendEmailCode({
        email,
        purpose: "email_change",
        ...captchaParams.value
      });

      if (data.status === "success") {
        ElMessage.success({
          message: `验证码已发送至新邮箱 ${emailForm.new_email}，请查收`,
          duration: 4000
        });
        emailCountdown.start(120);
        refreshCaptcha();
      } else {
        ElMessage.error(data.message || "发送验证码失败");
        refreshCaptcha();
      }
    } catch (error) {
      ElMessage.error(error.message || "网络错误");
      refreshCaptcha();
    } finally {
      emailForm.codeSending = false;
    }
  };

  /**
   * 修改邮箱
   */
  const changeEmail = async () => {
    // 基础客户端验证
    if (emailCheck.status !== 'ok') return ElMessage.warning(emailCheck.message || "该邮箱不可用");
    if (!emailForm.password) return ElMessage.warning("请输入当前密码");
    if (!emailForm.code) return ElMessage.warning("请输入新邮箱的验证码");

    // 如果2FA输入框可见，则验证2FA代码
    if (emailForm.show2FA && !emailForm.twoFaCode) {
      return ElMessage.warning("请输入两因素验证码");
    }

    try {
      // 构建请求体
      const requestBody = {
        password: emailForm.password,
        new_email: (emailForm.new_email || '').trim(),
        code: (emailForm.code || '').trim(),
      };

      // 如果是第二步，则添加2FA详情
      if (emailForm.show2FA) {
        requestBody.two_fa_code = (emailForm.twoFaCode || '').trim();
        requestBody.use_backup = emailForm.useBackup;
      }

      const data = await apiService.updateEmail(requestBody);

      if (data.status === "require_2fa") {
        // 后端要求2FA，进入第二步
        emailForm.show2FA = true;
        emailForm.twoFaMethod = data.method;

        // 根据2FA方法通知用户
        if (data.method === 'email') {
          ElMessage.info({
            message: "为保证安全，验证码已自动发送至您的原邮箱（非新邮箱），请查收",
            duration: 5000
          });
          // 启动2FA倒计时
          twoFaCountdown.start(120);
        } else { // totp
          ElMessage.info("请输入验证器应用中的验证码以完成操作");
        }
      } else if (data.status === "success") {
        // 成功！
        userStore.updateEmail(data.email);
        showEmailDialog.value = false;
        resetEmailForm();
        ElMessage.success("邮箱修改成功");
      } else {
        // 处理后端返回的其他错误
        ElMessage.error(data.message || "邮箱修改失败");
        // 如果是第一步出错，刷新验证码以便重试
        if (!emailForm.show2FA) {
          refreshCaptcha();
        }
      }
    } catch (error) {
      ElMessage.error(error.message || "网络错误");
      // 网络错误时也刷新验证码
      if (!emailForm.show2FA) {
        refreshCaptcha();
      }
    }
  };

  /**
   * 重新发送2FA验证码（修改邮箱场景）
   */
  const resend2FACode = async () => {
    if (twoFaCountdown.counting) return;

    emailForm.twoFaCodeSending = true;
    try {
      const data = await apiService.sendOperation2FACode();

      if (data.status === 'success') {
        ElMessage.success({
          message: '2FA验证码已重新发送至您的原邮箱',
          duration: 3000
        });
        twoFaCountdown.start(120);
      } else {
        ElMessage.error(data.message || '发送失败');
      }
    } catch (error) {
      ElMessage.error(error.message || '网络错误');
    } finally {
      emailForm.twoFaCodeSending = false;
    }
  };

  /**
   * 切换备用验证码（邮箱修改）
   */
  const toggleEmailBackupCode = () => {
    emailForm.useBackup = !emailForm.useBackup;
    emailForm.twoFaCode = '';
    const message = emailForm.useBackup
      ? "已切换到备用验证码模式"
      : `已切换回${emailForm.twoFaMethod === 'totp' ? '验证器' : '邮箱'}验证模式`;
    ElMessage.info(message);
  };

  /**
   * 重置邮箱表单
   */
  const resetEmailForm = () => {
    emailForm.new_email = '';
    emailForm.password = '';
    emailForm.code = '';
    emailForm.show2FA = false;
    emailForm.twoFaCode = '';
    emailForm.twoFaMethod = '';
    emailForm.useBackup = false;
    emailCheck.status = null;
    emailCheck.message = '';
    emailCountdown.stop();
    twoFaCountdown.stop();
    refreshCaptcha();
  };

  return {
    userStore,
    showEmailDialog,
    emailCountdown,
    twoFaCountdown,
    captchaWidgetRef,
    captchaParams,
    onCaptchaChange,
    isCaptchaVerified,
    emailForm,
    emailCheck,
    refreshCaptcha,
    checkEmailAvailability,
    canSendCode,
    canSubmitEmail,
    sendEmailCode,
    changeEmail,
    resend2FACode,
    toggleEmailBackupCode,
    resetEmailForm
  };
}
