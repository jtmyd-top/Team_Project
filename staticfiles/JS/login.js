const { createApp, ref, reactive, computed } = Vue;
const { ElMessage } = ElementPlus;

createApp({
    delimiters: ['[[', ']]'],  // 使用自定义分隔符避免与Django模板冲突

    setup() {
        // ==================== 状态管理 ====================

        // 登录表单数据
        const loginForm = reactive({
            username: '',
            password: ''
        });

        // 登录表单验证规则
        const loginRules = {
            username: [
                { required: true, message: '请输入用户名', trigger: 'blur' },
                { min: 6, message: '用户名至少6位', trigger: 'blur' }
            ],
            password: [
                { required: true, message: '请输入密码', trigger: 'blur' },
                { min: 8, message: '密码至少8位', trigger: 'blur' }
            ]
        };

        // 2FA验证表单数据
        const twoFaForm = reactive({
            code: ''
        });

        // 2FA验证规则（动态根据是否使用备用码调整）
        const twoFaRules = computed(() => {
            if (useBackupCode.value) {
                return {
                    code: [
                        { required: true, message: '请输入备用验证码', trigger: 'blur' },
                        { len: 8, message: '备用验证码为8位', trigger: 'blur' }
                    ]
                };
            } else {
                return {
                    code: [
                        { required: true, message: '请输入验证码', trigger: 'blur' },
                        { len: 6, message: '验证码为6位', trigger: 'blur' }
                    ]
                };
            }
        });

        // 状态标志
        const loading = ref(false);  // 登录按钮加载状态
        const verifying = ref(false);  // 2FA验证按钮加载状态
        const require2fa = ref(false);  // 是否需要2FA验证
        const twoFaMethod = ref('');  // 2FA验证方式：'totp' 或 'email'
        const useBackupCode = ref(false);  // 是否使用备用验证码
        const resendCountdown = ref(0);  // 重发邮件倒计时

        // 表单引用
        const loginFormRef = ref(null);
        const twoFaFormRef = ref(null);

        // 计算属性：是否显示步骤指示器
        const showStepIndicator = computed(() => require2fa.value);

        // ==================== CSRF Token ====================

        const getCsrfToken = () => {
            return window.CSRF_TOKEN || '';
        };

        // ==================== 第一步：用户名密码登录 ====================

        const handleLogin = async () => {
            // 表单验证
            if (!loginFormRef.value) {
                return;
            }

            try {
                await loginFormRef.value.validate();
            } catch (error) {
                return;
            }

            loading.value = true;

            try {
                // 使用 FormData 发送登录请求（因为后端期望 POST 数据）
                const formData = new FormData();
                formData.append('username', loginForm.username);
                formData.append('password', loginForm.password);
                formData.append('csrfmiddlewaretoken', getCsrfToken());

                const response = await fetch(window.LOGIN_API.login, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': getCsrfToken()
                    }
                });

                const data = await response.json();

                if (data.status === 'success') {
                    // 登录成功，直接跳转
                    ElMessage.success('登录成功！');
                    setTimeout(() => {
                        window.location.href = data.redirect_url || window.LOGIN_API.home;
                    }, 500);

                } else if (data.status === 'require_2fa') {
                    // 需要2FA验证
                    require2fa.value = true;
                    twoFaMethod.value = data.method;

                    if (data.method === 'email' && data.email_sent) {
                        ElMessage.info('验证码已发送至您的邮箱');
                        startResendCountdown();
                    } else if (data.method === 'totp') {
                        ElMessage.info('请输入验证器应用中的验证码');
                    }

                } else {
                    // 登录失败
                    ElMessage.error(data.message || '登录失败，请检查用户名和密码');
                }

            } catch (error) {
                console.error('Login error:', error);
                ElMessage.error('网络错误，请稍后重试');
            } finally {
                loading.value = false;
            }
        };

        // ==================== 第二步：2FA验证 ====================

        const verify2fa = async () => {
            // 表单验证
            if (!twoFaFormRef.value) {
                return;
            }

            try {
                await twoFaFormRef.value.validate();
            } catch (error) {
                return;
            }

            verifying.value = true;

            try {
                const response = await fetch(window.LOGIN_API.verify2fa, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        code: twoFaForm.code,
                        use_backup: useBackupCode.value
                    })
                });

                const data = await response.json();

                if (data.status === 'success') {
                    // 验证成功
                    ElMessage.success('验证成功，正在登录...');
                    setTimeout(() => {
                        window.location.href = data.redirect_url || window.LOGIN_API.home;
                    }, 500);

                } else {
                    // 验证失败
                    ElMessage.error(data.message || '验证码错误');
                    twoFaForm.code = '';  // 清空验证码输入框
                }

            } catch (error) {
                console.error('2FA verification error:', error);
                ElMessage.error('网络错误，请稍后重试');
            } finally {
                verifying.value = false;
            }
        };

        // ==================== 邮箱验证码重发 ====================

        const resendEmailCode = async () => {
            try {
                const response = await fetch(window.LOGIN_API.resendEmail, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    }
                });

                const data = await response.json();

                if (data.status === 'success') {
                    ElMessage.success('验证码已重新发送');
                    startResendCountdown();
                } else {
                    ElMessage.error(data.message || '发送失败，请稍后重试');
                }

            } catch (error) {
                console.error('Resend email error:', error);
                ElMessage.error('网络错误，请稍后重试');
            }
        };

        // 启动重发倒计时
        const startResendCountdown = () => {
            resendCountdown.value = 60;
            const timer = setInterval(() => {
                resendCountdown.value--;
                if (resendCountdown.value <= 0) {
                    clearInterval(timer);
                }
            }, 1000);
        };

        // ==================== 返回登录 ====================

        const backToLogin = () => {
            // 重置所有状态
            require2fa.value = false;
            twoFaMethod.value = '';
            useBackupCode.value = false;
            twoFaForm.code = '';
            loginForm.password = '';  // 清空密码
            resendCountdown.value = 0;
        };

        // ==================== 切换验证方式 ====================

        // 切换到备用验证码模式
        const switchToBackupCode = () => {
            useBackupCode.value = true;
            twoFaForm.code = '';  // 清空输入框
            ElMessage.info('已切换到备用验证码模式，请输入8位备用码');
        };

        // 切换回TOTP验证器模式
        const switchToTotp = () => {
            useBackupCode.value = false;
            twoFaForm.code = '';  // 清空输入框
            ElMessage.info('已切换回验证器模式，请输入6位验证码');
        };

        // ==================== 返回值 ====================

        return {
            // 表单数据
            loginForm,
            loginRules,
            twoFaForm,
            twoFaRules,

            // 表单引用
            loginFormRef,
            twoFaFormRef,

            // 状态
            loading,
            verifying,
            require2fa,
            twoFaMethod,
            useBackupCode,
            resendCountdown,
            showStepIndicator,

            // 方法
            handleLogin,
            verify2fa,
            resendEmailCode,
            backToLogin,
            switchToBackupCode,
            switchToTotp
        };
    }
}).use(ElementPlus).mount('#login-app');