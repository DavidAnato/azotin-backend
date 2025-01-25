from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import Review, User

# Modifier le nom affiché dans l'en-tête de l'interface d'administration
admin.site.site_header = "Administration de Connecte Me"

# Modifier le nom affiché dans l'onglet du navigateur
admin.site.site_title = "Jobhub Admin"

# Modifier le titre de la page principale de l'interface d'administration
admin.site.index_title = "Bienvenue sur l'interface d'administration de Jobhub"


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 1


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    search_fields = (
        "id",
        "phone_number",
        "username",
        "first_name",
        "last_name",
    )  # Champs de recherche

    list_display = (
        "id",
        "phone_number",
        "first_name",
        "last_name",
        "gender",
        "profile_picture_image",
        "is_active",
        "is_staff",
        "is_superuser",
    )

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Informations personnelles",
            {
                "fields": (
                    "code_pin",
                    "first_name",
                    "last_name",
                    "email",
                    "phone_number",
                    "date_of_birth",
                    "gender",
                    "city",
                    "country",
                    "bio",
                )
            },
        ),
        ("Photo de profil", {"fields": ("profile_picture_image", "profile_picture")}),
        ("Mode", {"fields": ("theme_mode",)}),
        ("Statut en ligne", {"fields": ("online_status",)}),
        (
            "Social Media",
            {"fields": ("linkedin", "twitter", "facebook", "instagram", "website")},
        ),
        (
            "Compte",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("OTP", {"fields": ("otp_code", "otp_generated_at")}),
        (
            "Localisation",
            {"fields": ("location_longitude", "location_latitude")},
        ),
        ("Google Auth", {"fields": ("google_id", "picture_url", "verified_email")}),
    )

    readonly_fields = ("profile_picture_image",)

    inlines = [ReviewInline]

    def profile_picture_image(self, obj):
        if obj.profile_picture:
            return format_html(
                '<img src="{}" style="max-width: 100px; max-height: 100px; border-radius:20px" />'.format(
                    obj.profile_picture.url
                )
            )
        else:
            return format_html("(Aucune image)")

    profile_picture_image.short_description = "Photo de profil"
