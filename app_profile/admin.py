from django.contrib import admin

from .models import WorkerProfile, ClientProfile, PreviousWorkPhoto

# Register your models here.

class PreviousWorkPhotoInline(admin.TabularInline):
    model = PreviousWorkPhoto
    extra = 1

@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Utilisateur', {'fields': ('user',)}),
        ('Profil professionnel', {'fields': ('title', 'skills', 'experience', 'hourly_rate', 'certifications', 'available_for_hire', 'total_jobs_completed')}),
    )
    inlines = [PreviousWorkPhotoInline]

@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Utilisateur', {'fields': ('user',)}),
        ('Informations de base', {'fields': ('preferred_payment_method', 'total_jobs_posted', 'job_completion_rate', 'average_spent', 'loyalty_points')}),
        ('Service', {'fields': ('service_name', 'service_type', 'service_description')}),
    )
