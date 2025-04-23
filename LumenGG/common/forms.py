from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import UserData

class LoginForm(forms.Form):
    username = forms.CharField(label="아이디", max_length=150)
    password = forms.CharField(label="비밀번호", widget=forms.PasswordInput)
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.add_error('username', '존재하지 않는 아이디입니다.')
            return cleaned_data
        else:
            if not user.check_password(password):
                self.add_error('password', '비밀번호가 틀렸습니다.')
        
        return cleaned_data

class UserForm(UserCreationForm):
    email = forms.EmailField(label="이메일")
    
    class Meta:
        model = User
        fields = ("username", "password1", "password2", "email")

class UserDataForm(forms.ModelForm):
    class Meta:
        model = UserData
        fields = ("character", )