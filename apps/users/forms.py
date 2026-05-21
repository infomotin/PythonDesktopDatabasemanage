from django.contrib.auth import (
    get_user_model,
    authenticate,
    login as django_login,
    logout as django_logout,
)
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
    UserChangeForm,
    PasswordChangeForm,
)
from django import forms

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    company = forms.CharField(max_length=100, required=False)

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "company", "password1", "password2")


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone", "company", "avatar", "preferences")


class ChangePasswordForm(PasswordChangeForm):
    pass
