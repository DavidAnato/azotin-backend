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
