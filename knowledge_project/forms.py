from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    # 在原有UserCreationForm的基础上，增加一个email字段
    email = forms.EmailField(
        required=True,
        help_text='必填项。请输入一个有效的邮箱地址。'
    )
    
    # 添加邮箱验证码字段（不做长度验证，因为前端无法实时检测）
    emailCode = forms.CharField(
        required=False,  # 在这里设为False，实际验证在views.py中进行
        max_length=10,   # 宽松的最大长度限制
        help_text='邮箱验证码'
    )

    class Meta(UserCreationForm.Meta):
        # 继承元数据
        model = User
        # 在原有字段（用户名、密码1、密码2）的基础上，加上email
        fields = UserCreationForm.Meta.fields + ('email',)

    def clean_email(self):
        """
        增加一个额外的验证，确保邮箱地址是唯一的（不区分大小写）。
        """
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("该邮箱地址已被注册，请使用其他邮箱。")
        return email
    
    def clean_emailCode(self):
        """
        邮箱验证码的验证逻辑移到views.py中处理，
        这里只做简单的清洗，不返回长度验证错误
        """
        code = self.cleaned_data.get('emailCode', '')
        # 移除所有空格
        return code.strip()
