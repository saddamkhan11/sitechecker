import re

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

PHONE_RE = re.compile(r"^03\d{9}$")


def normalize_phone(raw: str) -> str:
    """Turn +92 300 1234567 / 0300-1234567 / 923001234567 into 03001234567."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("92") and len(digits) == 12:
        digits = "0" + digits[2:]
    elif digits.startswith("3") and len(digits) == 10:
        digits = "0" + digits
    return digits


def validate_phone(value: str):
    if not PHONE_RE.match(value):
        raise ValidationError("Enter a Pakistani mobile number like 03001234567.")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra):
        phone = normalize_phone(phone)
        validate_phone(phone)
        user = self.model(phone=phone, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    LANG_ROMAN = "roman"
    LANG_URDU = "ur"
    LANG_EN = "en"
    LANGUAGE_CHOICES = [
        (LANG_ROMAN, "Roman Urdu"),
        (LANG_URDU, "اردو"),
        (LANG_EN, "English"),
    ]

    phone = models.CharField(max_length=11, unique=True, validators=[validate_phone])
    name = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=8, choices=LANGUAGE_CHOICES, default=LANG_ROMAN)
    UI_CHOICES = [("both", "English + اردو"), ("en", "English"), ("ur", "اردو"), ("roman", "Roman Urdu")]
    ui_language = models.CharField(max_length=8, choices=UI_CHOICES, default="both",
                                   help_text="Language of the website itself (menus, buttons, pages)")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.name or 'User'} ({self.phone})"
