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


@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display = (
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


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("job_offer", "worker", "proposed_price", "status", "applied_at")
    list_filter = ("status", "applied_at")
    search_fields = (
        "job_offer__title",
        "worker__user__first_name",
        "worker__user__last_name",
    )


admin.site.register(Category)
admin.site.register(SubCategory)
admin.site.register(Job)
admin.site.register(JobFavorite)
admin.site.register(PaidService)
