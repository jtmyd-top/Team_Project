import { ref, reactive, computed, onUnmounted } from 'vue';
import { useUserStore } from '../stores/user.js';
import { createDebouncedRequest, useCountdown } from '../utils/request.js';
import { ElMessage } from 'element-plus';

export function useSettingsProfile() {
  const userStore = useUserStore();

  // API端点和CSRF令牌
  const API_ENDPOINTS = window.API_ENDPOINTS || {};
  const csrfHeader = { "X-CSRFToken": window.SETTINGS_INITIAL?.csrfToken || "" };

  // 加载状态
  const bioSaving = ref(false);
  const profileSaving = ref(false);

  // 个性签名编辑
  const bioEditing = ref(false);
  const bioDraft = ref(userStore.bio || "");

  // 邮箱对话框
  const showEmailDialog = ref(false);

  // 倒计时
  const emailCountdown = useCountdown();

  // 验证码组件引用
  const captchaWidgetRef = ref(null);

  // 验证码参数
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

  // 刷新验证码
  const refreshCaptcha = () => {
    if (captchaWidgetRef.value) {
      captchaWidgetRef.value.reset();
    }
  };

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

  // 临时邮箱（用于输入新邮箱）
  const tempEmail = ref(userStore.email);

  // 邮箱是否改变
  const emailChanged = computed(() => {
    return (tempEmail.value || '').trim() !== userStore.email &&
           EMAIL_REGEX.test((tempEmail.value || '').trim());
  });

  /**
   * 打开邮箱修改对话框
   */
  const openEmailChangeDialog = async () => {
    // 检查邮箱是否有效改变
    if (!emailChanged.value) {
      ElMessage.warning('请先输入新的邮箱地址');
      return;
    }

    emailForm.new_email = (tempEmail.value || '').trim();
    showEmailDialog.value = true;
    // 立即触发邮箱可用性检查（不使用防抖）
    await checkEmailAvailabilityCore();
  };

  /**
   * 编辑个性签名
   */
  const editBio = () => {
    bioDraft.value = userStore.bio || "";
    bioEditing.value = true;
  };

  /**
   * 取消编辑
   */
  const cancelBio = () => {
    bioDraft.value = userStore.bio || "";
    bioEditing.value = false;
  };

  /**
   * 保存个性签名
   */
  const saveBio = async () => {
    if (bioSaving.value) return;

    bioSaving.value = true;
    try {
      const data = await window.apiService.updateProfile({ bio: bioDraft.value });
      if (data.status === "success") {
        userStore.updateBio(data.bio);
        bioDraft.value = data.bio;
        bioEditing.value = false;
        ElMessage.success("个性签名已保存");
      } else {
        ElMessage.error(data.message || "保存失败");
      }
    } catch (error) {
      console.error('操作失败:', error);
      handleApiError(error);
    } finally {
      bioSaving.value = false;
    }
  };

  /**
   * 处理API错误
   */
  const handleApiError = (error) => {
    if (error.response?.data) {
      const data = error.response.data;
      if (data.error) {
        ElMessage.error(data.error);
      } else if (data.message) {
        ElMessage.error(data.message);
      } else if (typeof data === 'object' && data !== null) {
        const errors = [];
        for (const [field, messages] of Object.entries(data)) {
          if (Array.isArray(messages)) {
            errors.push(`${field}: ${messages.join(', ')}`);
          } else {
            errors.push(`${field}: ${messages}`);
          }
        }
        ElMessage.error(errors.join('; '));
      } else {
        ElMessage.error("操作失败");
      }
    } else {
      ElMessage.error(error.message || "网络错误");
    }
  };

  /**
   * 验证用户名
   */
  const validateUsername = async (nickname) => {
    const usernameRegex = /^[a-z][a-z0-9_]{5,}$/;
    if (!usernameRegex.test(nickname)) {
      ElMessage.warning("用户名至少6位，以小写字母开头，只能包含字母、数字和下划线");
      return false;
    }

    try {
      const data = await window.apiService.auth.checkUsername(nickname);
      if (data.is_taken) {
        ElMessage.error("用户名已被占用，请换一个");
        return false;
      }
    } catch (err) {
      console.error('检查用户名失败:', err);
      ElMessage.error(err.message || "无法检查用户名，请稍后再试");
      return false;
    }

    return true;
  };

  /**
   * 保存用户名
   */
  const saveProfile = async () => {
    if (!await validateUsername(userStore.nickname)) return;
    if (profileSaving.value) return;

    profileSaving.value = true;
    try {
      const data = await window.apiService.updateProfile({ nickname: userStore.nickname });
      if (data.status === "success") {
        userStore.updateNickname(data.nickname);
        ElMessage.success("用户名修改成功");
      } else {
        ElMessage.error(data.message || "更新失败");
      }
    } catch (error) {
      console.error('操作失败:', error);
      handleApiError(error);
    } finally {
      profileSaving.value = false;
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
      const data = await window.apiService.auth.checkEmail(email, true);
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
    return true;
  });

  /**
   * 发送邮箱验证码
   */
  const sendEmailCode = async () => {
    const email = (emailForm.new_email || '').trim();
    if (!EMAIL_REGEX.test(email)) return ElMessage.warning("请输入正确邮箱");
    if (emailCheck.status !== 'ok') return ElMessage.warning(emailCheck.message || "该邮箱不可用");

    // 验证人机验证
    if (captchaWidgetRef.value && !captchaWidgetRef.value.validate()) {
      return;
    }

    emailForm.codeSending = true;
    try {
      const data = await window.apiService.auth.sendEmailCode({
        email,
        purpose: "email_change",
        ...captchaParams.value
      });

      if (data.status === "success") {
        ElMessage.success("验证码已发送到新邮箱");
        emailCountdown.start(60);
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
    if (emailCheck.status !== 'ok') return ElMessage.warning(emailCheck.message || "该邮箱不可用");
    if (!emailForm.password) return ElMessage.warning("请输入当前密码");
    if (!emailForm.code) return ElMessage.warning("请输入邮箱验证码");

    if (emailForm.show2FA && !emailForm.twoFaCode) {
      return ElMessage.warning("请输入两因素验证码");
    }

    try {
      const requestBody = {
        password: emailForm.password,
        new_email: (emailForm.new_email || '').trim(),
        code: (emailForm.code || '').trim(),
      };

      if (emailForm.show2FA) {
        requestBody.two_fa_code = emailForm.twoFaCode;
        requestBody.use_backup = emailForm.useBackup;
      }

      const data = await window.apiService.updateEmail(requestBody);

      if (data.status === "require_2fa") {
        emailForm.show2FA = true;
        emailForm.twoFaMethod = data.method;

        if (data.method === 'email') {
          await sendEmail2faCode();
        } else {
          ElMessage.info("请输入验证器应用中的验证码");
        }
      } else if (data.status === "success") {
        userStore.updateEmail(data.email);
        tempEmail.value = data.email;
        showEmailDialog.value = false;
        resetEmailForm();
        ElMessage.success("邮箱修改成功");
      } else {
        ElMessage.error(data.message || "邮箱修改失败");
      }
    } catch (error) {
      console.error('操作失败:', error);
      handleApiError(error);
    }
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
    tempEmail.value = userStore.email;
    refreshCaptcha();
  };

  /**
   * 发送邮箱修改2FA验证码
   */
  const sendEmail2faCode = async () => {
    emailForm.twoFaCodeSending = true;
    try {
      const data = await window.apiService.auth.sendOperation2FA();
      if (data.status === "success" && data.requires_2fa) {
        ElMessage.success("验证码已发送至您的邮箱");
      }
    } catch (error) {
      ElMessage.error(error.message || "发送验证码失败");
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
    ElMessage.info(emailForm.useBackup
      ? "已切换到备用验证码模式，请输入8位备用码"
      : "已切换回验证器模式，请输入6位验证码");
  };

  return {
    userStore,
    bioSaving,
    profileSaving,
    bioEditing,
    bioDraft,
    showEmailDialog,
    emailCountdown,
    captchaWidgetRef,
    captchaParams,
    onCaptchaChange,
    isCaptchaVerified,
    refreshCaptcha,
    emailForm,
    emailCheck,
    tempEmail,
    emailChanged,
    openEmailChangeDialog,
    editBio,
    cancelBio,
    saveBio,
    saveProfile,
    checkEmailAvailability,
    canSendCode,
    canSubmitEmail,
    sendEmailCode,
    changeEmail,
    resetEmailForm,
    sendEmail2faCode,
    toggleEmailBackupCode
  };
}
