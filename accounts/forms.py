from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm

from .models import User, normalize_phone, validate_phone


class SignupForm(forms.ModelForm):
    # Wider than the model field: people type +92 300 1234567; clean_phone() shortens it.
    phone = forms.CharField(label="Mobile number (03xxxxxxxxx)", max_length=20,
                            widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}))
    password = forms.CharField(label="Password", widget=forms.PasswordInput, min_length=6)

    class Meta:
        model = User
        fields = ["phone", "name", "language"]
        labels = {"phone": "Mobile number (03xxxxxxxxx)", "name": "Your name", "language": "Chat language"}
        widgets = {"phone": forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"})}

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data["phone"])
        validate_phone(phone)
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError("This number already has an account. Please log in.")
        return phone

    def clean_password(self):
        pw = self.cleaned_data["password"]
        password_validation.validate_password(pw)
        return pw

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class PhoneLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Mobile number", widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel", "autofocus": True})
    )

    def clean_username(self):
        return normalize_phone(self.cleaned_data["username"])
