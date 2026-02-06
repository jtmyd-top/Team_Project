import { ref, reactive, onMounted } from 'vue';
import { useUserStore } from '../stores/user.js';
import { apiService } from '../services/apiService.js';
import { useCountdown } from '../utils/request.js';
import { ElMessage } from 'element-plus';

export function useSettingsSecurity() {
  const userStore = useUserStore();

  // 添加密码修改验证码倒计时
  const passwordCountdown = useCountdown();

  // 添加调试日志
  onMounted(() => {
    console.log('=== 安全设置页面调试信息 ===');
    console.log('window.SETTINGS_INITIAL:', window.SETTINGS_INITIAL);
    console.log('userStore.two_fa_enabled:', userStore.two_fa_enabled);
    console.log('userStore.two_fa_method:', userStore.two_fa_method);
    console.log('============================');
  });

  // 对话框显示状态
  const showPasswordDialog = ref(false);
  const show2faSetupDialog = ref(false);
  const show2faDisableDialog = ref(false);
  const showBackupCodesDialog = ref(false);

  // 修改密码表单
  const passwordForm = reactive({
    current: '',
    new: '',
    confirm: '',
    show2FA: false,
    twoFaMethod: '',
    twoFaCode: '',
    useBackup: false,
    twoFaCodeSending: false,
    submitting: false,
  });

  // 2FA设置
  const twoFaSetup = reactive({
    step: null,
    method: null,
    qrCode: '',
    secret: '',
    verifyCode: '',
    backupCodes: [],
  });

  // 2FA禁用
  const twoFaDisable = reactive({
    password: '',
  });

  // 备用码管理
  const backupCodes = reactive({
    password: '',
    newCodes: null,
  });

  /**
   * 修改密码
   */
  const changePassword = async () => {
    // 防止重复提交
    if (passwordForm.submitting) return;

    if (!passwordForm.current) return ElMessage.warning("请输入当前密码");
    if (!passwordForm.new) return ElMessage.warning("请输入新密码");
    if (!passwordForm.confirm) return ElMessage.warning("请确认新密码");
    if (passwordForm.new !== passwordForm.confirm) return ElMessage.warning("两次输入的密码不一致");
    if (passwordForm.new.length < 8) return ElMessage.warning("新密码至少8位");

    // 检查新密码是否与旧密码相同
    if (passwordForm.current === passwordForm.new) {
      return ElMessage.warning("新密码不能与旧密码一致");
    }

    if (passwordForm.show2FA && !passwordForm.twoFaCode) {
      return ElMessage.warning("请输入两因素验证码");
    }

    passwordForm.submitting = true;
    try {
      const requestBody = {
        current_password: passwordForm.current,
        new_password: passwordForm.new,
        confirm_password: passwordForm.confirm,
      };

      if (passwordForm.show2FA) {
        requestBody.two_fa_code = (passwordForm.twoFaCode || '').trim();
        requestBody.use_backup = passwordForm.useBackup;
      }

      const data = await apiService.changePassword(requestBody);

      if (data.status === "require_2fa") {
        passwordForm.show2FA = true;
        passwordForm.twoFaMethod = data.method;

        // 对于邮箱验证方式，后端已经发送了验证码，无需再次发送
        // 只需要启动倒计时即可
        if (data.method === 'email') {
          ElMessage.info("验证码已发送到您的邮箱，请查收");
          passwordCountdown.start(90);
        } else {
          ElMessage.info("请输入验证器应用中的验证码");
        }
      } else if (data.status === "success") {
        ElMessage.success("密码修改成功");
        showPasswordDialog.value = false;
        resetPasswordForm();
      } else {
        ElMessage.error(data.message || "密码修改失败");
      }
    } catch (error) {
      console.error('修改密码错误:', error);
      ElMessage.error(error.message || "网络错误");
    } finally {
      passwordForm.submitting = false;
    }
  };

  /**
   * 重置密码表单
   */
  const resetPasswordForm = () => {
    passwordForm.current = '';
    passwordForm.new = '';
    passwordForm.confirm = '';
    passwordForm.show2FA = false;
    passwordForm.twoFaCode = '';
    passwordForm.twoFaMethod = '';
    passwordForm.useBackup = false;
    passwordForm.submitting = false;
  };

  /**
   * 发送密码修改2FA验证码
   */
  const sendPassword2faCode = async () => {
    if (passwordCountdown.counting) {
      return ElMessage.warning(`请等待 ${passwordCountdown.seconds} 秒后重试`);
    }

    passwordForm.twoFaCodeSending = true;
    try {
      const data = await apiService.sendOperation2FA();
      if (data.status === "success" && data.requires_2fa) {
        ElMessage.success("验证码已发送至您的邮箱");
        passwordCountdown.start(90);
      }
    } catch (error) {
      ElMessage.error(error.message || "发送验证码失败");
    } finally {
      passwordForm.twoFaCodeSending = false;
    }
  };

  /**
   * 切换备用验证码（密码修改）
   */
  const togglePasswordBackupCode = () => {
    passwordForm.useBackup = !passwordForm.useBackup;
    passwordForm.twoFaCode = '';
    const message = passwordForm.useBackup
      ? "已切换到备用验证码模式"
      : `已切换回${passwordForm.twoFaMethod === 'totp' ? '验证器' : '邮箱'}验证模式`;
    ElMessage.info(message);
  };

  /**
   * 开始2FA设置
   */
  const start2faSetup = async (method) => {
    twoFaSetup.method = method;

    try {
      const data = await apiService.enable2FA(method);
      if (data.status === "success") {
        if (method === 'totp') {
          twoFaSetup.step = 'totp-scan';
          twoFaSetup.qrCode = data.qr_code;
          twoFaSetup.secret = data.secret;
        } else {
          twoFaSetup.step = 'backup-codes';
          twoFaSetup.backupCodes = data.backup_codes || [];
          ElMessage.success("邮箱两因素认证已启用，请务必保存您的备用验证码！");
        }
      } else {
        ElMessage.error(data.message || "启用失败");
      }
    } catch (error) {
      ElMessage.error(error.message || "网络错误");
    }
  };

  /**
   * 验证2FA设置
   */
  const verify2faSetup = async () => {
    if (!twoFaSetup.verifyCode) return ElMessage.warning("请输入验证码");

    try {
      const data = await apiService.verify2FASetup(twoFaSetup.verifyCode);
      if (data.status === "success") {
        twoFaSetup.step = 'backup-codes';
        twoFaSetup.backupCodes = data.backup_codes || [];
        ElMessage.success("验证成功，请保存备用验证码");
      } else {
        ElMessage.error(data.message || "验证失败");
      }
    } catch (error) {
      ElMessage.error(error.message || "网络错误");
    }
  };

  /**
   * 完成2FA设置
   */
  const finish2faSetup = () => {
    userStore.update2FAStatus(true, twoFaSetup.method);
    show2faSetupDialog.value = false;
    twoFaSetup.step = null;
    twoFaSetup.verifyCode = '';
    twoFaSetup.backupCodes = [];
    ElMessage.success("两因素认证已成功启用");
  };

  /**
   * 取消2FA设置
   */
  const cancel2faSetup = () => {
    show2faSetupDialog.value = false;
    twoFaSetup.step = null;
    twoFaSetup.verifyCode = '';
    twoFaSetup.backupCodes = [];
  };

  /**
   * 复制备用码
   */
  const copyBackupCodes = () => {
    const text = twoFaSetup.backupCodes.join('\n');
    copyToClipboard(text);
  };

  /**
   * 禁用2FA
   */
  const disable2fa = async () => {
    if (!twoFaDisable.password) return ElMessage.warning("请输入密码");

    try {
      const data = await apiService.disable2FA(twoFaDisable.password);
      if (data.status === "success") {
        userStore.update2FAStatus(false);
        show2faDisableDialog.value = false;
        twoFaDisable.password = '';
        ElMessage.success("两因素认证已禁用");
      } else {
        ElMessage.error(data.message || "禁用失败");
      }
    } catch (error) {
      ElMessage.error(error.message || "网络错误");
    }
  };

  /**
   * 重新生成备用码
   */
  const regenerateBackupCodes = async () => {
    if (!backupCodes.password) return ElMessage.warning("请输入密码");

    try {
      const data = await apiService.regenerateBackupCodes(backupCodes.password);
      if (data.status === "success") {
        backupCodes.newCodes = data.backup_codes || [];
        ElMessage.success("备用验证码已重新生成");
      } else {
        ElMessage.error(data.message || "生成失败");
      }
    } catch (error) {
      ElMessage.error(error.message || "网络错误");
    }
  };

  /**
   * 复制新备用码
   */
  const copyNewBackupCodes = () => {
    const text = backupCodes.newCodes.join('\n');
    copyToClipboard(text);
  };

  /**
   * 关闭备用码对话框
   */
  const closeBackupCodesDialog = () => {
    showBackupCodesDialog.value = false;
    backupCodes.password = '';
    backupCodes.newCodes = null;
  };

  /**
   * 复制到剪贴板
   */
  const copyToClipboard = (text) => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        ElMessage.success("已复制到剪贴板");
      }).catch(() => {
        fallbackCopyText(text);
      });
    } else {
      fallbackCopyText(text);
    }
  };

  /**
   * 备用复制方法
   */
  const fallbackCopyText = (text) => {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();

    try {
      const successful = document.execCommand('copy');
      if (successful) {
        ElMessage.success("已复制到剪贴板");
      } else {
        ElMessage.error("复制失败，请手动复制");
      }
    } catch (err) {
      ElMessage.error("复制失败，请手动复制");
    } finally {
      document.body.removeChild(textarea);
    }
  };

  return {
    // Store
    userStore,

    // Countdown
    passwordCountdown,

    // Dialog states
    showPasswordDialog,
    show2faSetupDialog,
    show2faDisableDialog,
    showBackupCodesDialog,

    // Form states
    passwordForm,
    twoFaSetup,
    twoFaDisable,
    backupCodes,

    // Methods
    changePassword,
    resetPasswordForm,
    sendPassword2faCode,
    togglePasswordBackupCode,
    start2faSetup,
    verify2faSetup,
    finish2faSetup,
    cancel2faSetup,
    copyBackupCodes,
    disable2fa,
    regenerateBackupCodes,
    copyNewBackupCodes,
    closeBackupCodesDialog,
  };
}
