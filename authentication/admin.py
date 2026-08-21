from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import KycSubmission, Review, User, UserSettings

admin.site.site_header = "Administration Azotin"
admin.site.site_title = "Azotin Admin"
admin.site.index_title = "Bienvenue sur l'interface d'administration d'Azotin"


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    search_fields = (
        "id",
        "phone_number",
        "username",
        "email",
        "first_name",
        "last_name",
    )
    list_display = (
        "id",
        "full_name",
        "phone_number",
        "profile_type",
        "kyc_link",
        "is_certified",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = (
        "profile_type",
        "is_certified",
        "is_active",
        "is_staff",
        "gender",
    )
    ordering = ("-date_joined",)

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "phone_number",
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                    "profile_type",
                ),
            },
        ),
    )

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Informations personnelles",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "phone_number",
                    "date_of_birth",
                    "gender",
                    "city",
                    "country",
                    "bio",
                    "code_pin",
                )
            },
        ),
        ("Photo de profil", {"fields": ("profile_picture_image", "profile_picture")}),
        (
            "KYC / Vérification d'identité",
            {
                "fields": ("is_certified", "kyc_link"),
                "description": (
                    "Le dossier KYC (pièces, statut, revue) se gère via "
                    "« Dossiers KYC ». is_certified est dérivé du statut approved."
                ),
            },
        ),
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
                    "profile_type",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Localisation",
            {"fields": ("location_longitude", "location_latitude")},
        ),
        ("Google Auth", {"fields": ("google_id", "picture_url", "verified_email")}),
        ("Dates", {"fields": ("date_joined", "last_login")}),
    )

    readonly_fields = (
        "profile_picture_image",
        "kyc_link",
        "date_joined",
        "last_login",
    )
    filter_horizontal = ("groups", "user_permissions")
    inlines = [ReviewInline]

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name or ''}".strip()

    full_name.short_description = "Nom complet"
    full_name.admin_order_field = "first_name"

    def profile_picture_image(self, obj):
        if obj.profile_picture:
            return format_html(
                '<img src="{}" style="max-width:100px;max-height:100px;border-radius:8px" />',
                obj.profile_picture.url,
            )
        return "—"

    profile_picture_image.short_description = "Aperçu photo"

    def kyc_link(self, obj):
        try:
            kyc = obj.kyc_submission
        except KycSubmission.DoesNotExist:
            return "—"
        url = reverse("admin:authentication_kycsubmission_change", args=[kyc.pk])
        return format_html('<a href="{}">{}</a>', url, kyc.status)

    kyc_link.short_description = "Dossier KYC"


@admin.register(KycSubmission)
class KycSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "full_name",
        "status",
        "id_type",
        "id_number",
        "submitted_at",
        "reviewed_at",
        "id_document_preview",
        "selfie_preview",
    )
    list_filter = ("status", "submitted_at", "reviewed_at")
    search_fields = (
        "full_name",
        "id_number",
        "user__first_name",
        "user__last_name",
        "user__phone_number",
        "user__email",
    )
    raw_id_fields = ("user",)
    readonly_fields = (
        "id_document_preview",
        "selfie_preview",
        "submitted_at",
        "reviewed_at",
    )
    actions = ("approve_submissions", "reject_submissions")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "user",
                    "status",
                    "full_name",
                    "id_type",
                    "id_number",
                    "submitted_at",
                    "reviewed_at",
                    "review_notes",
                )
            },
        ),
        (
            "Documents",
            {
                "fields": (
                    "id_document_preview",
                    "id_document",
                    "selfie_preview",
                    "selfie",
                )
            },
        ),
    )

    @admin.action(description="Approuver les dossiers sélectionnés")
    def approve_submissions(self, request, queryset):
        now = timezone.now()
        for submission in queryset:
            submission.status = "approved"
            submission.reviewed_at = now
            submission.save()
        self.message_user(request, f"{queryset.count()} dossier(s) approuvé(s).")

    @admin.action(description="Rejeter les dossiers sélectionnés")
    def reject_submissions(self, request, queryset):
        now = timezone.now()
        for submission in queryset:
            submission.status = "rejected"
            submission.reviewed_at = now
            submission.save()
        self.message_user(request, f"{queryset.count()} dossier(s) rejeté(s).")

    def id_document_preview(self, obj):
        if obj.id_document:
            return format_html(
                '<a href="{0}" target="_blank">'
                '<img src="{0}" style="max-width:280px;max-height:200px;border-radius:4px" />'
                "</a>",
                obj.id_document.url,
            )
        return "—"

    id_document_preview.short_description = "Pièce d'identité (aperçu)"

    def selfie_preview(self, obj):
        if obj.selfie:
            return format_html(
                '<a href="{0}" target="_blank">'
                '<img src="{0}" style="max-width:280px;max-height:200px;border-radius:4px" />'
                "</a>",
                obj.selfie.url,
            )
        return "—"

    selfie_preview.short_description = "Selfie KYC (aperçu)"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "rating")
    search_fields = ("user__first_name", "user__last_name", "user__phone_number")
    raw_id_fields = ("user",)


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "use_biometric",
        "use_face_id",
        "use_pin",
        "profile_visibility",
        "language",
    )
    list_filter = (
        "use_biometric",
        "use_face_id",
        "use_pin",
        "profile_visibility",
        "language",
    )
    search_fields = ("user__first_name", "user__last_name", "user__email", "user__phone_number")
    raw_id_fields = ("user",)
