const { createApp } = Vue;

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

function levenshteinDistance(a, b){
    if(a.length==0)return b.length;
    if(b.length==0)return a.length;
    var c=Array(a.length+1).fill(null).map(()=>Array(b.length+1).fill(null));
    for(let d=0;d<=a.length;d+=1){c[d][0]=d}
    for(let d=0;d<=b.length;d+=1){c[0][d]=d}
    for(let d=1;d<=a.length;d+=1){
        for(let e=1;e<=b.length;e+=1){
            c[d][e]=b[e-1]===a[d-1]?c[d-1][e-1]:
            Math.min(c[d][e-1]+1,c[d-1][e]+1,c[d-1][e-1]+1)
        }
    }
    return c[a.length][b.length]
};

createApp({
    data() {
        return {
            pageTitle: '创建您的新账户',
            serverErrors: [],
            formErrors: {},
            username: '',
            password: '',
            password2: '',
            email: '',
            emailCode: '',
            passwordFieldType: 'password',

            usernameError: '',
            passwordError: '',
            password2Error: '',
            usernameRules: [
                { text: '至少包含 6 个字符', valid: false, test: (u) => u.length >= 6 },
                { text: '必须以小写字母开头', valid: false, test: (u) => /^[a-z]/.test(u) },
                { text: '只能包含小写字母、数字和下划线', valid: false, test: (u) => /^[a-z][a-z0-9_]*$/.test(u) },
            ],
            passwordRules: [
                { text: '至少包含 8 个字符', valid: false, test: (p) => p.length >= 8 },
                { text: '至少包含一个数字', valid: false, test: (p) => /\d/.test(p) },
                { text: '至少包含一个字母', valid: false, test: (p) => /[a-zA-Z]/.test(p) },
                { text: '不能与用户名太相似', valid: false, test: (p, u) => u ? (1 - levenshteinDistance(p, u) / Math.max(p.length, u.length)) <= 0.7 : true },
            ],

            isModalVisible: false,
            imageCaptchaInput: '',
            modalError: '',
            captchaUrl: captcha_image,
            countdown: 0,
            isSending: false,
            clickTracker: { count: 0, timer: null },

            // === 新增提示模态框状态 ===
            isPromptVisible: false,
            promptType: 'success',
            promptTitle: '',
            promptMessage: ''
        };
    },
    computed: {
        isCountdownActive() {
            return this.countdown > 0;
        },

        getCodeButtonText() {
            return this.isCountdownActive ? `${this.countdown}秒后重试` : '获取验证码';
        }
    },
    watch: {
        username(newUsername) {
            this.updateUsernameRules(newUsername);
            this.updatePasswordRules(this.password, newUsername);
        },
        password(newPassword) {
            this.updatePasswordRules(newPassword, this.username);
            this.checkFinalPasswordMatch();
        },
        password2() {
            this.checkFinalPasswordMatch();
        }
    },
    methods: {
        updateUsernameRules(username) { this.usernameRules.forEach(rule => rule.valid = rule.test(username)); },
        updatePasswordRules(password, username) { this.passwordRules.forEach(rule => rule.valid = rule.test(password, username)); },
        checkFinalPassword() { this.passwordError = this.passwordRules.every(rule => rule.valid) ? "" : "密码未满足所有安全要求。"; },
        checkFinalPasswordMatch() { this.password2Error = (!this.password || !this.password2 || this.password === this.password2) ? "" : "两次输入的密码不一致。"; },
        checkFinalUsername() {
            if (!this.username) { this.usernameError = ""; return; }
            const firstInvalidRule = this.usernameRules.find(rule => !rule.valid);
            this.usernameError = firstInvalidRule ? firstInvalidRule.text + '。' : "";
        },

        // === 通用提示方法 ===
        showPrompt(type, title, message) {
            this.promptType = type;
            this.promptTitle = title;
            this.promptMessage = message;
            this.isPromptVisible = true;
        },
        closePrompt() {
            this.isPromptVisible = false;
        },

        checkUsernameOnServer() {
            this.checkFinalUsername();
            if (this.username && !this.usernameError) {
                fetch(`${check_username}?username=${encodeURIComponent(this.username)}`)
                    .then(response => response.json())
                    .then(data => { if (data.is_taken) { this.usernameError = '该用户名已被占用。'; } });
            }
        },

        async submitForm() {
            this.serverErrors = [];
            this.formErrors = {};
            const formData = new FormData(document.getElementById('signup-form'));
            ['username', 'password', 'password2', 'email', 'emailCode'].forEach(key => formData.set(key, this[key]));

            try {
                const response = await fetch(signup, {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-CSRFToken': getCookie('csrftoken') }
                });
                const data = await response.json();

                if (response.ok) {
                    this.showPrompt('success', '注册成功', '您的账号已创建成功，即将跳转到登录页。');
                    setTimeout(() => { window.location.href = data.redirect_url; }, 2000);
                } else {
                    if (data.errors) this.formErrors = data.errors;
                    else this.showPrompt('error', '注册失败', data.message || '发生未知错误，请稍后再试。');
                }
            } catch (error) {
                console.error('Error:', error);
                this.showPrompt('error', '网络错误', '无法连接到服务器，请稍后再试。');
            }
        },

        refreshCaptcha() { this.captchaUrl = `${captcha_image}?t=${new Date().getTime()}`; },

        openCaptchaModal() {
            if (!this.email || !/^\S+@\S+\.\S+$/.test(this.email)) {
                this.showPrompt('error', '邮箱无效', '请先输入正确的邮箱地址！');
                return;
            }
            this.modalError = '';
            this.imageCaptchaInput = '';
            this.refreshCaptcha();
            this.isModalVisible = true;
        },

        async verifyImageAndSendEmail() {
            this.clickTracker.count++;
            if (this.clickTracker.timer) clearTimeout(this.clickTracker.timer);
            this.clickTracker.timer = setTimeout(() => { this.clickTracker.count = 0; }, 5000);

            if (this.clickTracker.count > 3) {
                this.modalError = '您点击的太快了，请稍后再试。';
                this.refreshCaptcha();
                return;
            }

            if (this.isSending) return;

            try {
                this.isSending = true;
                this.modalError = '';
                const response = await fetch(send_email_code, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                    body: JSON.stringify({ email: this.email, image_captcha_code: this.imageCaptchaInput })
                });
                const data = await response.json();

                if (!response.ok) {
                    if (response.status === 429) {
                        this.isModalVisible = false;
                        this.formErrors = { 'emailCode': [{ 'message': data.message }] };
                    } else {
                        this.modalError = data.message || '验证失败，请重试。';
                        this.refreshCaptcha();
                    }
                } else {
                    this.isModalVisible = false;
                    this.startCountdown();
                    this.showPrompt('success', '验证码已发送', data.message);
                }

            } catch (error) {
                this.modalError = '请求失败，请检查网络。';
                this.refreshCaptcha();
            } finally {
                this.isSending = false;
            }
        },

        startCountdown() {
            this.countdown = 60;
            const timer = setInterval(() => {
                if (this.countdown > 0) this.countdown--;
                else clearInterval(timer);
            }, 1000);
        }
    },
    delimiters: ['[[', ']]']
}).mount('#signup-app');