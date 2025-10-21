import { request, createDebouncedRequest, useCountdown } from '/static/JS/utils/request.js';

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
    const videoVolume = ref(0);        // 视频音量 (0-1) - 初始为0表示静音
    const volumeSliderVisible = ref(false); // 音量滑块是否可见
    const previousVolume = ref(0.5);   // 保存之前的音量,用于取消静音时恢复

    // ✅ 通知偏好设置状态
    const notifications = reactive({
      notify_login: initialData.notify_login !== undefined ? initialData.notify_login : true,
      notify_password_change: initialData.notify_password_change !== undefined ? initialData.notify_password_change : true,
      notify_password_reset: initialData.notify_password_reset !== undefined ? initialData.notify_password_reset : true,
      notify_note_activities: initialData.notify_note_activities !== undefined ? initialData.notify_note_activities : false,
      notify_profile_likes: initialData.notify_profile_likes !== undefined ? initialData.notify_profile_likes : true,
    });

    // ✅ 添加加载状态管理
    const loadingStates = reactive({
      notificationSaving: false,  // 通知偏好保存中
      profileSaving: false,        // 个人资料保存中
      bioSaving: false,            // 个性签名保存中
      likeSaving: false,           // 点赞操作中
      notificationLoading: false,  // 通知偏好加载中
    });

    // ✅ 保存通知偏好的原始状态（用于错误时回滚）
    const notificationsOriginal = ref({});

    // ✅ 防抖计时器
    let notificationSaveTimer = null;

    // ✅ 工具函数：判断 URL 是否为视频
    function isVideoUrl(url) {
      const videoExtensions = ['.mp4', '.webm', '.ogg'];
      return videoExtensions.some(ext => url.toLowerCase().includes(ext));
    }

    // ✅ 检测视频是否有音轨
    const checkVideoAudio = async () => {
      console.log('开始检测视频音频...');
      await nextTick();  // 确保DOM已渲染
      const video = bannerVideo.value;
      if (!video) {
        videoHasAudio.value = false;
        console.log('视频元素未找到');
        return;
      }
      videoHasAudio.value = false;

      try {
        // 等待视频元数据加载完成
        if (video.readyState < 1) {
          console.log('等待视频元数据加载...');
          await new Promise(resolve => {
            video.addEventListener('loadedmetadata', resolve, { once: true });
          });
        }

        console.log('视频元数据已加载，readyState:', video.readyState);
        console.log('视频时长:', video.duration);

        // 方法1：检查是否有音频轨道（最可靠）
        if (video.audioTracks && video.audioTracks.length !== undefined) {
          console.log('audioTracks数量:', video.audioTracks.length);
          videoHasAudio.value = video.audioTracks.length > 0;
          console.log('使用audioTracks API检测，有音频:', videoHasAudio.value);
          return;
        }

        // 方法2：Firefox特有API
        if (video.mozHasAudio !== undefined) {
          videoHasAudio.value = video.mozHasAudio;
          console.log('使用Firefox API检测，有音频:', videoHasAudio.value);
          return;
        }

        // 方法3：Chrome/Safari特有API（需要等待一些数据加载）
        if (video.webkitAudioDecodedByteCount !== undefined) {
          // 等待一小段时间让音频数据加载
          await new Promise(resolve => setTimeout(resolve, 500));
          videoHasAudio.value = video.webkitAudioDecodedByteCount > 0;
          console.log('webkitAudioDecodedByteCount:', video.webkitAudioDecodedByteCount);
          console.log('使用Chrome/Safari API检测，有音频:', videoHasAudio.value);
          return;
        }

        // 方法4：使用Web Audio API分析（备用方案）
        console.log('尝试使用Web Audio API检测...');
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) {
          const context = new AudioContext();
          try {
            const source = context.createMediaElementSource(video);
            const analyser = context.createAnalyser();
            source.connect(analyser);
            analyser.connect(context.destination);

            // 播放一小段时间来检测音频
            video.volume = 0; // 静音播放
            const playPromise = video.play();
            if (playPromise) {
              await playPromise;
              // 等待一些帧
              await new Promise(resolve => setTimeout(resolve, 100));
            }

            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);
            analyser.getByteFrequencyData(dataArray);

            // 检查是否有任何音频数据
            const hasAudio = dataArray.some(value => value > 0);
            videoHasAudio.value = hasAudio;

            console.log('音频数据分析结果:', hasAudio ? '有音频' : '无音频');
            console.log('音频数据样本:', dataArray.slice(0, 10));

            // 暂停并重置
            video.pause();
            video.currentTime = 0;
            video.volume = 1;

            // 清理
            source.disconnect();
            analyser.disconnect();
            context.close();
          } catch (err) {
            console.error('Web Audio API检测失败:', err);
            context.close();
            // 如果Web Audio API失败，默认认为有音频（显示按钮让用户控制）
            videoHasAudio.value = true;
          }
        } else {
          // 如果没有任何检测方法可用，默认显示音量按钮
          console.log('无可用的音频检测API，默认显示音量按钮');
          videoHasAudio.value = true;
        }
      } catch (error) {
        console.error('检测视频音频失败:', error);
        // 出错时默认显示按钮，让用户可以控制
        videoHasAudio.value = true;
      }

      // 如果检测到有音频，只设置初始音量，不自动播放声音
      // 保持默认静音状态，让用户主动选择是否播放声音
      if (videoHasAudio.value) {
        const currentVideo = bannerVideo.value;
        if (currentVideo) {
          currentVideo.muted = true;
          videoMuted.value = true;
          currentVideo.volume = Number(videoVolume.value);
        }
      }

      console.log('最终检测结果 - videoHasAudio:', videoHasAudio.value);
      console.log('profile.bannerIsVideo:', profile.bannerIsVideo);
    };

    // ✅ 切换视频静音状态
    const toggleVideoMute = async () => {
      const video = bannerVideo.value;
      if (!video) return;

      if (videoMuted.value) {
        // 当前是静音状态，要取消静音
        // 恢复到之前保存的音量，如果没有保存的音量或为0，则设置为0.5
        const targetVolume = previousVolume.value > 0 ? previousVolume.value : 0.5;

        // 先设置视频属性
        video.muted = false;
        video.volume = targetVolume;

        // 然后更新 Vue 状态
        videoMuted.value = false;
        videoVolume.value = targetVolume;

        // 尝试播放视频（如果视频被暂停了）
        if (video.paused) {
          try {
            await video.play();
          } catch (error) {
            console.log("用户交互后视频自动播放:", error);
          }
        }

        console.log('取消静音成功 - 音量:', targetVolume, '静音状态:', video.muted);

      } else {
        // 当前是非静音状态，要静音
        // 保存当前音量以便恢复
        if (videoVolume.value > 0) {
          previousVolume.value = Number(videoVolume.value);
        }

      // 先设置视频属性
      video.muted = true;
      video.volume = 0; // 确保视频对象实际音量为0

      // 然后更新 Vue 状态
      videoMuted.value = true;
      videoVolume.value = 0;

        console.log('静音成功 - 保存音量:', previousVolume.value, '静音状态:', video.muted);
      }

      // 强制 Vue 更新
      await nextTick();

      console.log('图标更新完成，当前类:', volumeIconClass.value);
    };

    // ✅ 更新视频音量 - 由于使用了v-model,videoVolume会自动更新,这里只需同步到video元素
    const updateVideoVolume = () => {
      const video = bannerVideo.value;
      if (!video) return;

      const volume = Number(videoVolume.value);
      video.volume = volume;
      
      // 当音量大于0时，取消静音；音量为0时，设为静音
      const newMutedState = volume === 0;
      videoMuted.value = newMutedState;
      video.muted = newMutedState;
      
      if (!newMutedState) {
        previousVolume.value = volume;
      }
      
      console.log('音量更新 - 音量:', volume, '静音状态:', newMutedState, '图标类:', volumeIconClass.value);
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

    const volumeIconClass = computed(() => {
      const volume = Number(videoVolume.value);
      
      // 优先根据音量值判断,而不是静音状态
      // 因为静音状态可能与音量值不同步
      if (volume === 0) {
        return 'fas fa-volume-xmark';
      }
      if (volume > 0 && volume <= 0.5) {
        return 'fas fa-volume-low';
      }
      return 'fas fa-volume-high';
    });

    // 监听videoVolume变化,确保图标能响应更新
    watch(videoVolume, (newVolume) => {
      console.log('videoVolume changed:', newVolume, 'new icon class:', volumeIconClass.value);
    });

    // ✅ 计算属性：实时判断表单是否可提交
    const canSubmitEmail = computed(() => {
      if (!EMAIL_REGEX.test(emailForm.new_email.trim())) return false;
      if (emailCheck.status !== "ok") return false;
      if (!emailForm.password.trim()) return false;
      if (!emailForm.imageCaptcha.trim()) return false;
      if (!emailForm.code.trim()) return false;
      return true;
    });

    // 使用倒计时hook
    const emailCountdown = useCountdown();
    const passwordCountdown = useCountdown();

    const showEmailDialog = ref(false);
    const emailForm = reactive({
      password: "",
      new_email: "",
      imageCaptcha: "",
      code: "",
      codeSending: false,
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

    // 创建防抖的邮箱检查函数（带AbortController）
    const checkEmailAvailabilityCore = async (signal) => {
      const email = emailForm.new_email.trim();
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
        const res = await fetch(
          `${window.API_ENDPOINTS.checkEmail}?email=${encodeURIComponent(email)}&exclude_self=1`,
          { signal }
        );
        const data = await res.json();
        if (data.is_taken) {
          emailCheck.status = 'taken';
          emailCheck.message = '该邮箱已被绑定';
        } else {
          emailCheck.status = 'ok';
          emailCheck.message = '';
        }
      } catch (error) {
        // 如果是取消的请求，不更新状态
        if (error.name === 'AbortError') {
          return;
        }
        emailCheck.status = 'invalid';
        emailCheck.message = '邮箱检查失败，请稍后再试';
      }
    };

    // 使用createDebouncedRequest创建防抖函数
    const checkEmailAvailability = createDebouncedRequest(checkEmailAvailabilityCore, 400);

    const editBio = () => {
      bioDraft.value = profile.bio || "";
      bioEditing.value = true;
    };

    const cancelBio = () => {
      bioDraft.value = profile.bio || "";
      bioEditing.value = false;
    };

    const saveBio = async () => {
      if (loadingStates.bioSaving) return; // 防止重复请求

      loadingStates.bioSaving = true;
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
      } catch (error) {
        ElMessage.error("网络错误");
        console.error("保存个性签名失败:", error);
      } finally {
        loadingStates.bioSaving = false;
      }
    };

    // 监听邮箱输入变化
    watch(() => emailForm.new_email, checkEmailAvailability);

    // 发送邮箱验证码（改进版：添加finally确保状态恢复）
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
            "purpose": "email_change"  // 统一改为 email_change
          }),
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          ElMessage.success("验证码已发送到新邮箱");
          emailCountdown.start(60);  // 使用倒计时hook
          refreshCaptcha();
          emailForm.imageCaptcha = "";
        } else {
          ElMessage.error(data.message || "发送验证码失败");
          refreshCaptcha();
          emailForm.imageCaptcha = "";
        }
      } catch {
        ElMessage.error("网络错误");
        refreshCaptcha();
        emailForm.imageCaptcha = "";
      } finally {
        emailForm.codeSending = false;  // 确保状态恢复
      }
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
      if (loadingStates.profileSaving) return; // 防止重复请求

      loadingStates.profileSaving = true;
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
      } catch (error) {
        ElMessage.error("网络错误");
        console.error("保存个人资料失败:", error);
      } finally {
        loadingStates.profileSaving = false;
      }
    };

    // ✅ 点赞切换功能（改进版：添加加载状态）
    const toggleLike = async () => {
      if (loadingStates.likeSaving) return; // 防止重复请求

      // 乐观更新UI
      const previousState = isLiked.value;
      const previousCount = profile.likes_count;

      isLiked.value = !isLiked.value;
      profile.likes_count += isLiked.value ? 1 : -1;

      loadingStates.likeSaving = true;
      try {
        const res = await fetch(window.API_ENDPOINTS.toggleLike || '/api/toggle-like/', {
          method: "POST",
          headers: { "Content-Type": "application/json", ...csrfHeader },
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          // 使用服务器返回的实际值更新
          isLiked.value = data.is_liked;
          profile.likes_count = data.likes_count;
          ElMessage.success(data.is_liked ? "已点赞 ❤️" : "已取消点赞");
        } else {
          // 错误时回滚
          isLiked.value = previousState;
          profile.likes_count = previousCount;
          ElMessage.error(data.message || "操作失败");
        }
      } catch (error) {
        // 网络错误时回滚
        isLiked.value = previousState;
        profile.likes_count = previousCount;
        ElMessage.error("网络错误");
        console.error("点赞操作失败:", error);
      } finally {
        loadingStates.likeSaving = false;
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
          passwordCountdown.start(60);  // 使用倒计时hook
          refreshCaptcha();
          passwordForm.imageCaptcha = "";
        } else {
          ElMessage.error(data.message || "发送验证码失败");
          refreshCaptcha();
          passwordForm.imageCaptcha = "";
        }
      } catch {
        ElMessage.error("网络错误");
        refreshCaptcha();
        passwordForm.imageCaptcha = "";
      } finally {
        passwordForm.codeSending = false;
      }
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

    // 加载通知偏好设置（改进版：添加加载状态）
    const loadNotificationPreferences = async () => {
      loadingStates.notificationLoading = true;
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
            // 保存原始状态以便错误时回滚
            notificationsOriginal.value = { ...data.preferences };
          }
        } else {
          ElMessage.warning("加载通知偏好设置失败，使用默认设置");
        }
      } catch (error) {
        console.error("加载通知偏好设置失败:", error);
        ElMessage.warning("网络错误，无法加载通知偏好设置");
      } finally {
        loadingStates.notificationLoading = false;
      }
    };

    // 保存通知偏好设置（改进版：防抖、加载状态、错误处理）
    const saveNotificationPreferences = async (fieldName = null) => {
      // 清除之前的防抖计时器
      if (notificationSaveTimer) {
        clearTimeout(notificationSaveTimer);
      }

      // 设置防抖延迟（500ms）
      notificationSaveTimer = setTimeout(async () => {
        // 如果正在保存，避免重复请求
        if (loadingStates.notificationSaving) {
          console.log("正在保存中，跳过重复请求");
          return;
        }

        loadingStates.notificationSaving = true;
        const currentSettings = { ...notifications };

        try {
          const res = await fetch('/api/notification-preferences/', {
            method: "POST",
            headers: { "Content-Type": "application/json", ...csrfHeader },
            body: JSON.stringify(notifications),
          });

          if (!res.ok) {
            // 处理不同的HTTP错误状态
            if (res.status === 401) {
              throw new Error("未授权，请重新登录");
            } else if (res.status === 403) {
              throw new Error("没有权限修改通知设置");
            } else if (res.status === 500) {
              throw new Error("服务器内部错误，请稍后重试");
            } else if (res.status === 429) {
              throw new Error("操作过于频繁，请稍后再试");
            }
          }

          const data = await res.json();

          if (data.status === "success") {
            // 更新原始状态为当前成功保存的状态
            notificationsOriginal.value = { ...currentSettings };

            // 显示具体更改的字段信息
            if (fieldName && data.updated_fields) {
              const fieldNameMap = {
                'notify_login': '登录通知',
                'notify_password_change': '密码修改通知',
                'notify_password_reset': '密码重置通知',
                'notify_note_activities': '笔记活动通知',
                'notify_profile_likes': '点赞通知'
              };
              const fieldLabel = fieldNameMap[fieldName] || fieldName;
              const status = notifications[fieldName] ? '已开启' : '已关闭';
              ElMessage.success(`${fieldLabel}${status}`);
            } else {
              ElMessage.success("通知偏好设置已保存");
            }
          } else if (data.status === "warning") {
            ElMessage.warning(data.message || "没有需要更新的字段");
          } else {
            throw new Error(data.message || "保存失败");
          }
        } catch (error) {
          // 错误时回滚到原始状态
          if (notificationsOriginal.value && Object.keys(notificationsOriginal.value).length > 0) {
            Object.assign(notifications, notificationsOriginal.value);
          }

          // 显示详细的错误信息
          if (error.message) {
            ElMessage.error(error.message);
          } else if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
            ElMessage.error("网络连接失败，请检查网络设置");
          } else {
            ElMessage.error("保存失败，请稍后重试");
          }

          console.error("保存通知偏好设置失败:", error);
        } finally {
          loadingStates.notificationSaving = false;
        }
      }, 500); // 500ms 防抖延迟
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
      emailCountdown,  // 使用倒计时hook
      passwordCountdown,  // 使用倒计时hook
      openEmailDialog,
      saveProfile,
      changeEmail,
      sendEmailCode,
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
      videoVolume,
      volumeSliderVisible,
      updateVideoVolume,
      volumeIconClass,
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
      // ✅ 加载状态管理
      loadingStates,
    };
  },
}).use(ElementPlus).mount("#settings-app");
