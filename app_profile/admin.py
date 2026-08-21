from django.contrib import admin

from .models import ClientProfile, FavoriteWorker, PreviousWorkPhoto, WorkerProfile


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
                    "job_types",
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
    filter_horizontal = ("job_types",)
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
    raw_id_fields = ("user",)


@admin.register(PreviousWorkPhoto)
class PreviousWorkPhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "worker_profile", "photo")
    search_fields = (
        "worker_profile__user__first_name",
        "worker_profile__user__last_name",
    )
    raw_id_fields = ("worker_profile",)


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Utilisateur", {"fields": ("user",)}),
        (
            "Informations de base",
            {
                "fields": (
                    "category",
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
    raw_id_fields = ("user",)


@admin.register(FavoriteWorker)
class FavoriteWorkerAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "worker_profile", "created_at")
    list_filter = ("created_at",)
    search_fields = (
        "user__first_name",
        "user__last_name",
        "worker_profile__user__first_name",
        "worker_profile__user__last_name",
    )
    raw_id_fields = ("user", "worker_profile")
    readonly_fields = ("created_at", "updated_at")
