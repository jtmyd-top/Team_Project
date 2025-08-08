from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    # 在原有UserCreationForm的基础上，增加一个email字段
    email = forms.EmailField(
        required=True,
        help_text='必填项。请输入一个有效的邮箱地址。'
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