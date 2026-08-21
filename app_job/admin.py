from django.contrib import admin

from .models import (
    Category,
    Job,
    JobApplication,
    JobFavorite,
    JobOffer,
    PaidService,
    SubCategory,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category")
    list_filter = ("category",)
    search_fields = ("name",)


@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "client",
        "category",
        "sub_category",
        "price",
        "is_urgent",
        "deadline",
        "created_at",
    )
    list_filter = ("category", "sub_category", "created_at", "is_urgent")
    search_fields = (
        "title",
        "description",
        "client__user__first_name",
        "client__user__last_name",
    )
    raw_id_fields = ("client",)


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "job_offer", "worker", "proposed_price", "status", "applied_at")
    list_filter = ("status", "applied_at")
    search_fields = (
        "job_offer__title",
        "worker__user__first_name",
        "worker__user__last_name",
    )
    raw_id_fields = ("job_offer", "worker")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "job_offer",
        "client",
        "worker",
        "price",
        "completed",
        "created_at",
    )
    list_filter = ("completed", "frequency", "created_at")
    search_fields = (
        "description",
        "location",
        "client__user__first_name",
        "worker__user__first_name",
    )
    raw_id_fields = ("job_offer", "client", "worker")


@admin.register(JobFavorite)
class JobFavoriteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "job_offer", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__first_name", "user__last_name", "job_offer__title")
    raw_id_fields = ("user", "job_offer")


@admin.register(PaidService)
class PaidServiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "is_job_offer_paid",
        "is_job_offer_paid_price",
        "is_job_application_paid",
        "is_job_application_paid_price",
    )
