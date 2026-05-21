from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth import forms as auth_forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


User = get_user_model()


class UserAdminCreationForm(auth_forms.UserCreationForm):
    class Meta(auth_forms.UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "role", "company")
        field_classes = {}

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError(_("The two password fields didn't match."))
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class UserAdminChangeForm(auth_forms.UserChangeForm):
    class Meta(auth_forms.UserChangeForm.Meta):
        model = User
        fields = [f for f in auth_forms.UserChangeForm.Meta.fields if f != "password"]


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label=_("Email"), widget=forms.EmailInput(attrs={"class": "input"}))
    first_name = forms.CharField(required=False, label=_("First Name"), widget=forms.TextInput(attrs={"class": "input"}))
    last_name = forms.CharField(required=False, label=_("Last Name"), widget=forms.TextInput(attrs={"class": "input"}))
    company = forms.CharField(required=False, label=_("Company"), widget=forms.TextInput(attrs={"class": "input"}))
    terms = forms.BooleanField(required=True, label=_("I agree to the Terms of Service"))

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2", "company", "terms")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        user.company = self.cleaned_data.get("company", "")
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone", "company", "avatar"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "input", "readonly": "readonly"}),
            "first_name": forms.TextInput(attrs={"class": "input"}),
            "last_name": forms.TextInput(attrs={"class": "input"}),
            "phone": forms.TextInput(attrs={"class": "input"}),
            "company": forms.TextInput(attrs={"class": "input"}),
            "avatar": forms.FileInput(attrs={"class": "file-input"}),
        }


class ChangePasswordForm(auth_forms.PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs = {"class": "input"}
