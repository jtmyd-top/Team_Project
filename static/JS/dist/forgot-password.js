import{aQ as y}from"./chunks/vue-vendor-DlJU6D6d.js";import{i as p}from"./chunks/element-plus-Ba3kSmXS.js";import"./chunks/vendor-BYwPJZNa.js";const x={template:`
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
              clearable>
              <template #prefix>
                <i class="fas fa-envelope"></i>
              </template>
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
  `,setup(){const{ref:a,reactive:d}=Vue,{ElMessage:i}=p,n=a(null),l=a(!1),c=a(!1),s=a(60),g=d({email:""}),e=d({text:"",type:"info"}),v={email:[{required:!0,message:"请输入邮箱地址",trigger:"blur"},{type:"email",message:"请输入正确的邮箱格式",trigger:["blur","change"]}]},b=async()=>{if(n.value)try{if(!await n.value.validate())return;l.value=!0,e.text="";const r=await fetch("/password-reset/",{method:"POST",headers:{"Content-Type":"application/json","X-CSRFToken":w()},body:JSON.stringify({email:g.email})}),o=await r.json();r.ok?(e.text=o.message||"重置密码链接已发送到您的邮箱，请查收",e.type="success",h(),i.success("邮件发送成功，请查收邮箱")):(e.text=o.message||"发送失败，请稍后重试",e.type="error",i.error(o.message||"发送失败"))}catch(t){console.error("发送重置密码邮件失败:",t),e.text="网络错误，请稍后重试",e.type="error",i.error("网络错误，请稍后重试")}finally{l.value=!1}},h=()=>{c.value=!0,s.value=60;const t=setInterval(()=>{s.value--,s.value<=0&&(clearInterval(t),c.value=!1)},1e3)},w=()=>{const t="csrftoken";let r=null;if(document.cookie&&document.cookie!==""){const o=document.cookie.split(";");for(let m=0;m<o.length;m++){const f=o[m].trim();if(f.substring(0,t.length+1)===t+"="){r=decodeURIComponent(f.substring(t.length+1));break}}}return r};return{forgotFormRef:n,forgotForm:g,forgotRules:v,isLoading:l,isCountingDown:c,countdown:s,message:e,submitForm:b}},style:`
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
  `},u=y(x);u.use(p);u.mount("#forgot-password-app");
