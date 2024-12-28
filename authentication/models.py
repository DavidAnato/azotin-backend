import os
import random

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.files.storage import default_storage
from django.db import models
from django.utils.text import slugify

from .managers import CustomUserManager
from .utils import *


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model extending AbstractBaseUser and PermissionsMixin.
    """

    # Category
    category = models.ForeignKey(
        "app_job.Category",
        on_delete=models.CASCADE,
        related_name="users",
        null=True,
        blank=True,
    )

    # Personal Information
    email = models.EmailField(
        "Email Address", unique=True, max_length=255, blank=True, null=True
    )
    first_name = models.CharField("First Name", max_length=100)
    last_name = models.CharField("Last Name", max_length=100, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True)
    profile_picture = models.ImageField(upload_to="profile_pictures/", blank=True)
    bio = models.TextField(max_length=500, blank=True)
    GENDER_CHOICES = (
        ("male", "Homme"),
        ("female", "Femme"),
    )
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Security Information
    code_pin = models.CharField(max_length=4, null=True, blank=True)

    # Account Information
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    username = models.CharField(max_length=100, unique=True, null=True, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    is_certified = models.BooleanField(default=False)
    online_status = models.BooleanField(default=False)

    # Preferences
    THEME_CHOICES = (
        ("dark_mode", "dark"),
        ("light_mode", "light"),
    )
    theme_mode = models.CharField(
        max_length=10, default="light_mode", choices=THEME_CHOICES
    )
    bg_color = models.CharField(max_length=10, default="#FFFFFF", blank=True)
    text_color = models.CharField(max_length=10, default="#000000", blank=True)

    # Status fields
    online_status = models.BooleanField(default=False)

    # Location fields
    localisation_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True
    )
    localisation_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True
    )

    # Google authentication fields
    google_id = models.CharField("Google ID", max_length=255, blank=True, null=True)
    picture_url = models.URLField("Picture URL", blank=True, null=True)
    verified_email = models.BooleanField("Verified Email", default=False)

    # OTP fields
    otp_code = models.CharField("OTP Code", max_length=5, null=True, blank=True)
    otp_generated_at = models.DateTimeField("OTP Generated At", null=True, blank=True)

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["email", "first_name"]

    objects = CustomUserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def save(self, *args, **kwargs):
        """
        Override the save method to handle custom logic for the User model.
        """
        if not self.username:
            slug = slugify(f"{self.first_name} {self.last_name} {self.phone_number}")
            self.username = slug

        if not self.bg_color or not self.text_color:
            self.bg_color, self.text_color = self.generate_contrasting_colors()

        if self.pk and self.profile_picture:
            try:
                old_profile_picture = User.objects.get(pk=self.pk).profile_picture
                if old_profile_picture != self.profile_picture:
                    if old_profile_picture and os.path.isfile(old_profile_picture.path):
                        default_storage.delete(old_profile_picture.name)
            except User.DoesNotExist:
                pass

        super().save(*args, **kwargs)

    def generate_contrasting_colors(self):
        def random_color():
            return "#{:06x}".format(random.randint(0, 0xFFFFFF))

        def contrast_ratio(color1, color2):
            def luminance(color):
                r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
                a = [v / 255.0 for v in (r, g, b)]
                a = [
                    v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
                    for v in a
                ]
                return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722

            lum1, lum2 = luminance(color1), luminance(color2)
            return (
                (lum1 + 0.05) / (lum2 + 0.05)
                if lum1 > lum2
                else (lum2 + 0.05) / (lum1 + 0.05)
            )

        bg_color = random_color()
        text_color = random_color()

        while contrast_ratio(bg_color, text_color) < 4.5:
            text_color = random_color()

        return bg_color, text_color

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    rating = models.DecimalField(max_digits=3, decimal_places=2, blank=True, null=True)
    testimonials = models.TextField(max_length=1000, blank=True)

    def __str__(self):
        return f"Review by {self.user.first_name} {self.user.last_name}"
