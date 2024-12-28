from django.contrib import admin

from .models import Job, JobApplication, JobOffer

admin.site.register(JobOffer)
admin.site.register(JobApplication)
admin.site.register(Job)
