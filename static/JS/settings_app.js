const { createApp, ref, reactive, watch, computed, nextTick, onMounted } = Vue;

createApp({
  delimiters: ['[[', ']]'], // 使用自定义分隔符避免与Django模板冲突
  setup() {

    const initialData = window.SETTINGS_INITIAL || {};
    const profile = reactive({
        avatar: initialData.avatar || "/static/img/default-avatar.png",
        banner: initialData.banner || "",
        bannerIsVideo: initialData.banner ? isVideoUrl(initialData.banner) : false,  // ✅ 检测是否为视频
        nickname: initialData.nickname || "",
        email: initialData.email || "",
        bio: initialData.bio || "",
        likes_count: initialData.likes_count || 0,
      });

    // 点赞相关状态
    const isLiked = ref(initialData.is_liked || false);
    const notesCount = ref(initialData.notes_count || 0);
    const viewsCount = ref(initialData.views_count || 0);

    // 视频音量控制相关状态
    const videoHasAudio = ref(false);  // 视频是否有声音
    const videoMuted = ref(true);      // 是否静音（默认静音）
    const bannerVideo = ref(null);     // video元素的引用

    // ✅ 通知偏好设置状态
    const notifications = reactive({
      notify_login: initialData.notify_login !== undefined ? initialData.notify_login : true,
      notify_password_change: initialData.notify_password_change !== undefined ? initialData.notify_password_change : true,
      notify_password_reset: initialData.notify_password_reset !== undefined ? initialData.notify_password_reset : true,
      notify_note_activities: initialData.notify_note_activities !== undefined ? initialData.notify_note_activities : false,
      notify_profile_likes: initialData.notify_profile_likes !== undefined ? initialData.notify_profile_likes : true,
    });

    // ✅ 工具函数：判断 URL 是否为视频
    function isVideoUrl(url) {
      const videoExtensions = ['.mp4', '.webm', '.ogg'];
      return videoExtensions.some(ext => url.toLowerCase().includes(ext));
    }

    // ✅ 检测视频是否有音轨
    const checkVideoAudio = async () => {
      await nextTick();  // 确保DOM已渲染
      const video = bannerVideo.value;
      if (!video) return;

      try {
        // 等待视频元数据加载完成
        if (video.readyState < 1) {
          await new Promise(resolve => {
            video.addEventListener('loadedmetadata', resolve, { once: true });
          });
        }

        // 检查是否有音频轨道
        if (video.mozHasAudio !== undefined) {
          // Firefox
          videoHasAudio.value = video.mozHasAudio;
        } else if (video.webkitAudioDecodedByteCount !== undefined) {
          // Chrome/Safari
          videoHasAudio.value = video.webkitAudioDecodedByteCount > 0;
        } else if (video.audioTracks && video.audioTracks.length > 0) {
          // 标准 API
          videoHasAudio.value = true;
        } else {
          // 备用方案：尝试播放一小段来检测
          const context = new (window.AudioContext || window.webkitAudioContext)();
          const source = context.createMediaElementSource(video);
          const analyser = context.createAnalyser();
          source.connect(analyser);
          analyser.connect(context.destination);

          const bufferLength = analyser.frequencyBinCount;
          const dataArray = new Uint8Array(bufferLength);

          // 检查音频数据
          analyser.getByteFrequencyData(dataArray);
          const hasAudio = dataArray.some(value => value > 0);
          videoHasAudio.value = hasAudio;

          // 清理
          source.disconnect();
          analyser.disconnect();
          context.close();
        }
      } catch (error) {
        console.warn('检测视频音频失败:', error);
        // 出错时假设没有音频，不显示按钮
        videoHasAudio.value = false;
      }
    };

    // ✅ 切换视频静音状态
    const toggleVideoMute = () => {
      const video = bannerVideo.value;
      if (!video) return;

      videoMuted.value = !videoMuted.value;
      video.muted = videoMuted.value;
    };

    const active = ref("profile");
    const { ElMessage } = ElementPlus;
    const usernameRegex = /^[a-z][a-z0-9_]{5,}$/;

    const bioEditing = ref(false);
    const bioDraft = ref(profile.bio || "");

    const captchaUrl = ref('/captcha/?_=' + Date.now());
    const refreshCaptcha = () => {
      captchaUrl.value = '/captcha/?_=' + Date.now();
    };

    const csrfHeader = { "X-CSRFToken": initialData.csrfToken || "" };

    // ✅ 头像上传成功处理
    const handleAvatarSuccess = (res) => {
      if (res && res.status === "success" && res.avatar_url) {
        const newAvatarUrl = res.avatar_url + "?t=" + Date.now();
        profile.avatar = newAvatarUrl;

        // 更新导航栏头像
        const navAvatar = document.getElementById("nav-avatar");
        if (navAvatar) {
          navAvatar.src = newAvatarUrl;
        }

        ElMessage.success("头像更新成功");
      } else {
        ElMessage.error(res?.message || "头像上传失败，请稍后重试");
      }
    };

    // ✅ 新增：横幅上传成功处理
    const handleBannerSuccess = (res) => {
      if (res && res.status === "success" && res.banner_url) {
        const newBannerUrl = res.banner_url + "?t=" + Date.now();
        profile.banner = newBannerUrl;
        profile.bannerIsVideo = res.is_video || false;  // ✅ 根据后端返回判断
        ElMessage.success(res.is_video ? "横幅视频更新成功" : "横幅图片更新成功");
      } else {
        ElMessage.error(res?.message || "横幅上传失败，请稍后重试");
      }
    };

    // ✅ 计算属性：实时判断表单是否可提交
    const canSubmitEmail = computed(() => {
      if (!EMAIL_REGEX.test(emailForm.new_email.trim())) return false;
      if (emailCheck.status !== "ok") return false;
      if (!emailForm.password.trim()) return false;
      if (!emailForm.imageCaptcha.trim()) return false;
      if (!emailForm.code.trim()) return false;
      return true;
    });

    const showEmailDialog = ref(false);
    const emailForm = reactive({
      password: "",
      new_email: "",
      imageCaptcha: "",
      code: "",
      codeSending: false,
      codeCountdown: 0,
      // ✅ 2FA相关
      show2FA: false,          // 是否显示2FA输入框
      twoFaMethod: '',         // 2FA方式：totp | email
      twoFaCode: '',           // 2FA验证码
      useBackup: false,        // 是否使用备用码
      twoFaCodeSending: false, // 2FA验证码发送中
    });
    const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    // 实时邮箱检验状态
    const emailCheck = reactive({
      status: null,   // 'ok' | 'taken' | 'invalid' | null
      message: ''
    });

    // 防抖工具
    const debounce = (fn, delay = 400) => {
      let t;
      return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), delay);
      };
    };

    const editBio = () => {
      bioDraft.value = profile.bio || "";
      bioEditing.value = true;
    };

    const cancelBio = () => {
      bioDraft.value = profile.bio || "";
      bioEditing.value = false;
    };

    const saveBio = async () => {
      try {
        const res = await fetch(window.API_ENDPOINTS.updateProfile, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
          body: JSON.stringify({ bio: bioDraft.value }),
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          profile.bio = data.bio;
          bioDraft.value = data.bio;
          ElMessage.success("个性签名已保存");
          bioEditing.value = false;
        } else {
          ElMessage.error(data.message || "保存失败");
        }
      } catch {
        ElMessage.error("网络错误");
      }
    };

    // 检查邮箱可用性（输入时实时检查）
    const checkEmailAvailability = debounce(async () => {
      const email = emailForm.new_email.trim();
      if (!email) { emailCheck.status = null; emailCheck.message = ''; return; }
      if (!EMAIL_REGEX.test(email)) {
        emailCheck.status = 'invalid';
        emailCheck.message = '邮箱格式不正确';
        return;
      }
      try {
        const res = await fetch(`${window.API_ENDPOINTS.checkEmail}?email=${encodeURIComponent(email)}&exclude_self=1`);
        const data = await res.json();
        if (data.is_taken) {
          emailCheck.status = 'taken';
          emailCheck.message = '该邮箱已被绑定';
        } else {
          emailCheck.status = 'ok';
          emailCheck.message = '';
        }
      } catch {
        emailCheck.status = 'invalid';
        emailCheck.message = '邮箱检查失败，请稍后再试';
      }
    }, 400);

    // 监听邮箱输入变化
    watch(() => emailForm.new_email, checkEmailAvailability);

    // 发送邮箱验证码
    const sendEmailCode = async () => {
      const email = emailForm.new_email.trim();
      if (!EMAIL_REGEX.test(email)) return ElMessage.warning("请输入正确邮箱");
      if (emailCheck.status !== 'ok') return ElMessage.warning(emailCheck.message || "该邮箱不可用");
      if (!emailForm.imageCaptcha) return ElMessage.warning("请输入图片验证码");

      emailForm.codeSending = true;
      try {
        const res = await fetch(window.API_ENDPOINTS.sendEmailCode, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
          body: JSON.stringify({
            email,
            image_captcha_code: emailForm.imageCaptcha,
            "purpose": "change"
          }),
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          ElMessage.success("验证码已发送到新邮箱");
          startCountdown();
          refreshCaptcha();
          emailForm.imageCaptcha = "";
        } else {
          ElMessage.error(data.message || "发送验证码失败");
          refreshCaptcha();
          emailForm.imageCaptcha = "";
        }
      } catch {
        ElMessage.error("网络错误");
      }
      emailForm.codeSending = false;
    };

    // 确认修改邮箱
    const changeEmail = async () => {
      if (emailCheck.status !== 'ok') return ElMessage.warning(emailCheck.message || "该邮箱不可用");
      if (!emailForm.password) return ElMessage.warning("请输入当前密码");
      if (!emailForm.imageCaptcha) return ElMessage.warning("请输入图片验证码");
      if (!emailForm.code) return ElMessage.warning("请输入邮箱验证码");

      // 如果显示2FA输入框，验证2FA验证码
      if (emailForm.show2FA && !emailForm.twoFaCode) {
        return ElMessage.warning("请输入两因素验证码");
      }

      try {
        const requestBody = {
          password: emailForm.password,
          new_email: emailForm.new_email.trim(),
          code: emailForm.code.trim(),
          image_captcha_code: emailForm.imageCaptcha.trim(),
        };

        // 如果已显示2FA输入框，添加2FA验证码
        if (emailForm.show2FA) {
          requestBody.two_fa_code = emailForm.twoFaCode;
          requestBody.use_backup = emailForm.useBackup;
        }

        const res = await fetch(window.API_ENDPOINTS.updateEmail, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
          body: JSON.stringify(requestBody),
        });
        const data = await res.json();

        if (data.status === "require_2fa") {
          // 需要2FA验证，显示2FA输入框
          emailForm.show2FA = true;
          emailForm.twoFaMethod = data.method;

          // 如果是邮箱验证方式，自动发送验证码
          if (data.method === 'email') {
            await sendEmail2faCode();
          } else {
            ElMessage.info("请输入验证器应用中的验证码");
          }
        } else if (res.ok && data.status === "success") {
          profile.email = data.email;
          showEmailDialog.value = false;
          resetEmailForm();
          ElMessage.success("邮箱修改成功");
        } else {
          ElMessage.error(data.message || "邮箱修改失败");
        }
      } catch {
        ElMessage.error("网络错误");
      } finally {
        if (!emailForm.show2FA) {
          refreshCaptcha();
          emailForm.imageCaptcha = "";
        }
      }
    };

    // 重置邮箱表单
    const resetEmailForm = () => {
      emailForm.password = '';
      emailForm.new_email = '';
      emailForm.imageCaptcha = '';
      emailForm.code = '';
      emailForm.show2FA = false;
      emailForm.twoFaCode = '';
      emailForm.twoFaMethod = '';
      emailForm.useBackup = false;
      refreshCaptcha();
    };

    // 发送修改邮箱的2FA验证码（邮箱方式）
    const sendEmail2faCode = async () => {
      emailForm.twoFaCodeSending = true;
      try {
        const res = await fetch('/api/security/send-operation-2fa/', {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          if (data.requires_2fa) {
            ElMessage.success("验证码已发送至您的邮箱");
          }
        } else {
          ElMessage.error(data.message || "发送验证码失败");
        }
      } catch {
        ElMessage.error("网络错误");
      } finally {
        emailForm.twoFaCodeSending = false;
      }
    };

    // 切换到备用验证码模式（邮箱修改）
    const toggleEmailBackupCode = () => {
      emailForm.useBackup = !emailForm.useBackup;
      emailForm.twoFaCode = '';
      if (emailForm.useBackup) {
        ElMessage.info("已切换到备用验证码模式，请输入8位备用码");
      } else {
        ElMessage.info("已切换回验证器模式，请输入6位验证码");
      }
    };

    const startCountdown = () => {
      emailForm.codeCountdown = 60;
      const timer = setInterval(() => {
        emailForm.codeCountdown--;
        if (emailForm.codeCountdown <= 0) clearInterval(timer);
      }, 1000);
    };

    const openEmailDialog = () => {
      emailForm.password = "";
      emailForm.new_email = "";
      showEmailDialog.value = true;
    };

    const validateUsername = async (nickname) => {
      const usernameRegex = /^[a-z][a-z0-9_]{5,}$/;
      if (!usernameRegex.test(nickname)) {
        ElMessage.warning("用户名至少6位，以小写字母开头，只能包含字母、数字和下划线");
        return false;
      }

      try {
        const res = await fetch(`/check-username/?username=${encodeURIComponent(nickname)}`);
        const data = await res.json();
        if (data.is_taken) {
          ElMessage.error("用户名已被占用，请换一个");
          return false;
        }
      } catch (err) {
        ElMessage.error("无法检查用户名，请稍后再试");
        return false;
      }

      return true;
    };

    const saveProfile = async () => {
      if (!await validateUsername(profile.nickname)) return;

      try {
        const res = await fetch(window.API_ENDPOINTS.updateProfile, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
          body: JSON.stringify({ nickname: profile.nickname }),
        });

        const data = await res.json();
        if (res.ok && data.status === "success") {
          ElMessage.success("用户名修改成功");

          // 更新导航栏显示的用户名
          const navUsername = document.getElementById("id_username");
          const navUsername2 = document.getElementsByClassName("username");
          if (navUsername) {
            navUsername.textContent = data.nickname;
          }
          for (let i = 0; i < navUsername2.length; i++) {
            navUsername2[i].textContent = data.nickname;
          }
        } else {
          ElMessage.error(data.message || "更新失败");
        }
      } catch (e) {
        ElMessage.error("网络错误");
      }
    };

    // ✅ 点赞切换功能
    const toggleLike = async () => {
      try {
        const res = await fetch(window.API_ENDPOINTS.toggleLike || '/api/toggle-like/', {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          isLiked.value = data.is_liked;
          profile.likes_count = data.likes_count;
          ElMessage.success(data.is_liked ? "已点赞 ❤️" : "已取消点赞");
        } else {
          ElMessage.error(data.message || "操作失败");
        }
      } catch {
        ElMessage.error("网络错误");
      }
    };

    // ==================== 账户安全相关 ====================

    // 安全信息状态
    const security = reactive({
      twoFaEnabled: initialData.two_fa_enabled || false,  // 是否已启用2FA
      twoFaMethod: initialData.two_fa_method || 'totp',  // 2FA方式
    });

    // 修改密码相关
    const showPasswordDialog = ref(false);
    const passwordForm = reactive({
      current: '',
      new: '',
      confirm: '',
      imageCaptcha: '',
      emailCode: '',
      codeSending: false,
      codeCountdown: 0,
      // ✅ 2FA相关
      show2FA: false,          // 是否显示2FA输入框
      twoFaMethod: '',         // 2FA方式：totp | email
      twoFaCode: '',           // 2FA验证码
      useBackup: false,        // 是否使用备用码
      twoFaCodeSending: false, // 2FA验证码发送中
    });

    // 发送修改密码的邮箱验证码
    const sendPasswordEmailCode = async () => {
      if (!passwordForm.imageCaptcha) return ElMessage.warning("请输入图片验证码");

      passwordForm.codeSending = true;
      try {
        const res = await fetch(window.API_ENDPOINTS.sendEmailCode, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
          body: JSON.stringify({
            email: profile.email,  // 传递当前邮箱（后端会自动使用，这个参数可选）
            image_captcha_code: passwordForm.imageCaptcha,
            purpose: "password_change"  // ✅ 修改为 password_change
          }),
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          ElMessage.success("验证码已发送到您的邮箱");
          startPasswordCountdown();
          refreshCaptcha();
          passwordForm.imageCaptcha = "";
        } else {
          ElMessage.error(data.message || "发送验证码失败");
          refreshCaptcha();
          passwordForm.imageCaptcha = "";
        }
      } catch {
        ElMessage.error("网络错误");
      }
      passwordForm.codeSending = false;
    };

    const startPasswordCountdown = () => {
      passwordForm.codeCountdown = 60;
      const timer = setInterval(() => {
        passwordForm.codeCountdown--;
        if (passwordForm.codeCountdown <= 0) clearInterval(timer);
      }, 1000);
    };

    // 提交修改密码
    const changePassword = async () => {
      if (!passwordForm.current) return ElMessage.warning("请输入当前密码");
      if (!passwordForm.new) return ElMessage.warning("请输入新密码");
      if (!passwordForm.confirm) return ElMessage.warning("请确认新密码");
      if (passwordForm.new !== passwordForm.confirm) return ElMessage.warning("两次输入的密码不一致");
      if (passwordForm.new.length < 8) return ElMessage.warning("新密码至少8位");

      // 如果显示2FA输入框，验证2FA验证码
      if (passwordForm.show2FA && !passwordForm.twoFaCode) {
        return ElMessage.warning("请输入两因素验证码");
      }

      try {
        const requestBody = {
          current_password: passwordForm.current,
          new_password: passwordForm.new,
          confirm_password: passwordForm.confirm,
        };

        // 如果已显示2FA输入框，添加2FA验证码
        if (passwordForm.show2FA) {
          requestBody.two_fa_code = passwordForm.twoFaCode;
          requestBody.use_backup = passwordForm.useBackup;
        }

        const res = await fetch('/api/security/change-password/', {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
          body: JSON.stringify(requestBody),
        });
        const data = await res.json();

        if (data.status === "require_2fa") {
          // 需要2FA验证，显示2FA输入框
          passwordForm.show2FA = true;
          passwordForm.twoFaMethod = data.method;

          // 如果是邮箱验证方式，自动发送验证码
          if (data.method === 'email') {
            await sendPassword2faCode();
          } else {
            ElMessage.info("请输入验证器应用中的验证码");
          }
        } else if (res.ok && data.status === "success") {
          ElMessage.success("密码修改成功");
          showPasswordDialog.value = false;
          // 重置表单
          resetPasswordForm();
        } else {
          ElMessage.error(data.message || "密码修改失败");
        }
      } catch {
        ElMessage.error("网络错误");
      }
    };

    // 重置密码表单
    const resetPasswordForm = () => {
      passwordForm.current = '';
      passwordForm.new = '';
      passwordForm.confirm = '';
      passwordForm.show2FA = false;
      passwordForm.twoFaCode = '';
      passwordForm.twoFaMethod = '';
      passwordForm.useBackup = false;
    };

    // 发送修改密码的2FA验证码（邮箱方式）
    const sendPassword2faCode = async () => {
      passwordForm.twoFaCodeSending = true;
      try {
        const res = await fetch('/api/security/send-operation-2fa/', {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          if (data.requires_2fa) {
            ElMessage.success("验证码已发送至您的邮箱");
          }
        } else {
          ElMessage.error(data.message || "发送验证码失败");
        }
      } catch {
        ElMessage.error("网络错误");
      } finally {
        passwordForm.twoFaCodeSending = false;
      }
    };

    // 切换到备用验证码模式（密码修改）
    const togglePasswordBackupCode = () => {
      passwordForm.useBackup = !passwordForm.useBackup;
      passwordForm.twoFaCode = '';
      if (passwordForm.useBackup) {
        ElMessage.info("已切换到备用验证码模式，请输入8位备用码");
      } else {
        ElMessage.info("已切换回验证器模式，请输入6位验证码");
      }
    };

    // 2FA 设置相关
    const show2faSetupDialog = ref(false);
    const twoFaSetup = reactive({
      step: null,  // null | 'totp-scan' | 'backup-codes'
      method: null,  // 'totp' | 'email'
      qrCode: '',
      secret: '',
      verifyCode: '',
      backupCodes: [],
    });

    // 开始2FA设置
    const start2faSetup = async (method) => {
      twoFaSetup.method = method;

      try {
        const res = await fetch('/api/security/enable-2fa/', {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
          body: JSON.stringify({ method }),
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          if (method === 'totp') {
            twoFaSetup.step = 'totp-scan';
            twoFaSetup.qrCode = data.qr_code;
            twoFaSetup.secret = data.secret;
          } else {
            // 邮箱方式直接启用 - 等待后端确认
            if (data.two_fa_enabled === true) {
              // 只有在后端确认启用成功后才更新前端状态
              security.twoFaEnabled = true;
              security.twoFaMethod = 'email';
              show2faSetupDialog.value = false;
              ElMessage.success("邮箱两因素认证已启用");
            } else {
              // 如果后端没有确认启用，显示错误
              ElMessage.error("启用邮箱两因素认证失败，请重试");
            }
          }
        } else {
          ElMessage.error(data.message || "启用失败");
        }
      } catch {
        ElMessage.error("网络错误");
      }
    };

    // 验证并完成2FA设置
    const verify2faSetup = async () => {
      if (!twoFaSetup.verifyCode) return ElMessage.warning("请输入验证码");

      try {
        const res = await fetch('/api/security/verify-2fa-setup/', {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
          body: JSON.stringify({ code: twoFaSetup.verifyCode }),
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          // 显示备用码
          twoFaSetup.step = 'backup-codes';
          twoFaSetup.backupCodes = data.backup_codes || [];
          ElMessage.success("验证成功，请保存备用验证码");
        } else {
          ElMessage.error(data.message || "验证失败");
        }
      } catch {
        ElMessage.error("网络错误");
      }
    };

    // 完成2FA设置
    const finish2faSetup = () => {
      security.twoFaEnabled = true;
      security.twoFaMethod = twoFaSetup.method;
      show2faSetupDialog.value = false;
      // 重置设置流程
      twoFaSetup.step = null;
      twoFaSetup.verifyCode = '';
      twoFaSetup.backupCodes = [];
      ElMessage.success("两因素认证已成功启用");
    };

    // 取消2FA设置
    const cancel2faSetup = () => {
      show2faSetupDialog.value = false;
      twoFaSetup.step = null;
      twoFaSetup.verifyCode = '';
      twoFaSetup.backupCodes = [];
    };

    // 复制备用码
    const copyBackupCodes = () => {
      const text = twoFaSetup.backupCodes.join('\n');

      // 尝试使用现代 Clipboard API
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
          ElMessage.success("备用验证码已复制到剪贴板");
        }).catch(() => {
          fallbackCopyText(text);
        });
      } else {
        // 降级到传统方法
        fallbackCopyText(text);
      }
    };

    // 备用复制方法（兼容旧浏览器）
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
          ElMessage.success("备用验证码已复制到剪贴板");
        } else {
          ElMessage.error("复制失败，请手动复制");
        }
      } catch (err) {
        ElMessage.error("复制失败，请手动复制");
      } finally {
        document.body.removeChild(textarea);
      }
    };

    // 禁用2FA相关
    const show2faDisableDialog = ref(false);
    const twoFaDisable = reactive({
      password: '',
    });

    // 禁用2FA
    const disable2fa = async () => {
      if (!twoFaDisable.password) return ElMessage.warning("请输入密码");

      try {
        const res = await fetch('/api/security/disable-2fa/', {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
          body: JSON.stringify({ password: twoFaDisable.password }),
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          security.twoFaEnabled = false;
          show2faDisableDialog.value = false;
          twoFaDisable.password = '';
          ElMessage.success("两因素认证已禁用");
        } else {
          ElMessage.error(data.message || "禁用失败");
        }
      } catch {
        ElMessage.error("网络错误");
      }
    };

    // 备用验证码管理
    const showBackupCodesDialog = ref(false);
    const backupCodes = reactive({
      password: '',
      newCodes: null,
    });

    // 重新生成备用码
    const regenerateBackupCodes = async () => {
      if (!backupCodes.password) return ElMessage.warning("请输入密码");

      try {
        const res = await fetch('/api/security/regenerate-backup-codes/', {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
          body: JSON.stringify({ password: backupCodes.password }),
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          backupCodes.newCodes = data.backup_codes || [];
          ElMessage.success("备用验证码已重新生成");
        } else {
          ElMessage.error(data.message || "生成失败");
        }
      } catch {
        ElMessage.error("网络错误");
      }
    };

    // 复制新备用码
    const copyNewBackupCodes = () => {
      const text = backupCodes.newCodes.join('\n');

      // 尝试使用现代 Clipboard API
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
          ElMessage.success("备用验证码已复制到剪贴板");
        }).catch(() => {
          fallbackCopyText(text);
        });
      } else {
        // 降级到传统方法
        fallbackCopyText(text);
      }
    };

    // 关闭备用码对话框
    const closeBackupCodesDialog = () => {
      showBackupCodesDialog.value = false;
      backupCodes.password = '';
      backupCodes.newCodes = null;
    };

    // ==================== 通知偏好设置相关 ====================

    // 加载通知偏好设置
    const loadNotificationPreferences = async () => {
      try {
        const res = await fetch('/api/notification-preferences/', {
          method: "GET",
          headers: { ...csrfHeader },
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          // 更新通知偏好设置状态
          if (data.preferences) {
            Object.assign(notifications, data.preferences);
          }
        }
      } catch (error) {
        console.error("加载通知偏好设置失败:", error);
      }
    };

    // 保存通知偏好设置
    const saveNotificationPreferences = async () => {
      try {
        const res = await fetch('/api/notification-preferences/', {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
          body: JSON.stringify(notifications),
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          ElMessage.success("通知偏好设置已保存");
        } else {
          ElMessage.error(data.message || "保存失败");
        }
      } catch {
        ElMessage.error("网络错误");
      }
    };

    // 在组件挂载时加载通知偏好设置
    onMounted(() => {
      loadNotificationPreferences();
    });

    return {
      active,
      profile,
      csrfHeader,
      showEmailDialog,
      emailForm,
      openEmailDialog,
      saveProfile,
      changeEmail,
      sendEmailCode,
      startCountdown,
      refreshCaptcha,
      captchaUrl,
      handleAvatarSuccess,
      handleBannerSuccess,  // ✅ 横幅上传处理函数
      validateUsername,
      emailCheck,
      canSubmitEmail,
      bioEditing,
      bioDraft,
      editBio,
      cancelBio,
      saveBio,
      isLiked,
      notesCount,
      viewsCount,
      toggleLike,
      // ✅ 视频音量控制相关
      bannerVideo,
      videoHasAudio,
      videoMuted,
      checkVideoAudio,
      toggleVideoMute,
      // ✅ 账户安全相关
      security,
      showPasswordDialog,
      passwordForm,
      sendPasswordEmailCode,
      changePassword,
      resetPasswordForm,
      sendPassword2faCode,
      togglePasswordBackupCode,
      resetEmailForm,
      sendEmail2faCode,
      toggleEmailBackupCode,
      show2faSetupDialog,
      twoFaSetup,
      start2faSetup,
      verify2faSetup,
      finish2faSetup,
      cancel2faSetup,
      copyBackupCodes,
      show2faDisableDialog,
      twoFaDisable,
      disable2fa,
      showBackupCodesDialog,
      backupCodes,
      regenerateBackupCodes,
      copyNewBackupCodes,
      closeBackupCodesDialog,
      // ✅ 通知偏好设置相关
      notifications,
      saveNotificationPreferences,
    };
  },
}).use(ElementPlus).mount("#settings-app");
