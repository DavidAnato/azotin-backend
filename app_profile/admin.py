from django.contrib import admin

from .models import ClientProfile, PreviousWorkPhoto, WorkerProfile

# Register your models here.


class PreviousWorkPhotoInline(admin.TabularInline):
    model = PreviousWorkPhoto
    extra = 1


@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Utilisateur", {"fields": ("user",)}),
        (
            "Profil professionnel",
            {
                "fields": (
                    "title",
                    "category",
                    "skills",
                    "experience",
                    "price",
                    "frequency",
                    "certifications",
                    "available_for_hire",
                    "total_jobs_completed",
                )
            },
        ),
    )
    inlines = [PreviousWorkPhotoInline]
    list_display = (
        "user",
        "title",
        "category",
        "available_for_hire",
        "total_jobs_completed",
    )
    list_filter = ("category", "available_for_hire")
    search_fields = ("user__first_name", "user__last_name", "skills", "certifications")


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Utilisateur", {"fields": ("user",)}),
        (
            "Informations de base",
            {
                "fields": (
                    "preferred_payment_method",
                    "average_spent",
                    "loyalty_points",
                )
            },
        ),
        (
            "Service",
            {"fields": ("service_name", "service_type", "service_description")},
        ),
        (
            "Localisation",
            {"fields": ("location_description",)},
        ),
    )
    list_display = ("user", "category", "service_type", "loyalty_points")
    list_filter = ("category", "service_type")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "service_name",
        "service_description",
    )
