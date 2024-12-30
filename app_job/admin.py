from django.contrib import admin

from .models import Category, Job, JobApplication, JobOffer, SubCategory

admin.site.register(Category)
admin.site.register(SubCategory)
admin.site.register(JobOffer)
admin.site.register(JobApplication)
admin.site.register(Job)
