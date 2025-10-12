const { createApp, ref, reactive } = Vue;

    // CSRF Token 辅助函数
    function getCookie(name) {
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
    }

    createApp({
        setup() {
            const pageTitle = ref('欢迎来到, 知识协作平台');
            const form = reactive({
                username: '',
                password: ''
            });
            const loginError = ref('');
            const passwordFieldType = ref('password');

            const togglePasswordVisibility = () => {
                passwordFieldType.value = passwordFieldType.value === 'password' ? 'text' : 'password';
            };

            const handleLogin = async () => {
                loginError.value = ''; // 清空旧错误

                const formData = new FormData();
                formData.append('username', form.username);
                formData.append('password', form.password);
                formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));

                try {
                    const response = await fetch(login, {
                        method: 'POST',
                        body: formData,
                    });

                    const contentType = response.headers.get("content-type");
                    if (contentType && contentType.includes("application/json")) {
                        const data = await response.json();
                        if (data.status === 'success') {
                            // 登录成功，执行跳转！
                            window.location.href = data.redirect_url || '/';
                        } else {
                            loginError.value = data.message || '登录失败，请重试。';
                        }
                    } else {
                        // 后端返回的不是JSON，说明登录失败（例如，AuthenticationForm验证失败会重新渲染页面）
                        // 在这种情况下，我们给出一个通用的错误提示
                        loginError.value = '用户名或密码不正确。';
                    }
                } catch (error) {
                    console.error('登录请求失败:', error);
                    loginError.value = '网络错误，请稍后重试。';
                }
            };

            return {
                pageTitle,
                form,
                loginError,
                passwordFieldType,
                togglePasswordVisibility,
                handleLogin
            };
        },
        delimiters: ['[[', ']]']
    }).mount('#login-app');