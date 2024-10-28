from django.contrib import admin
from .models import JobOffer, JobApplication, Job

admin.site.register(JobOffer)
admin.site.register(JobApplication)
admin.site.register(Job)
