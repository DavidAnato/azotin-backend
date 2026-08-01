"""
URL configuration for jobhub_api project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from app_escrow.urls import (
    contract_urlpatterns,
    payments_urlpatterns,
    wallet_urlpatterns,
)

schema_view = get_schema_view(
    openapi.Info(
        title="JobHub API",
        default_version="v1",
        description="API documentation for JobHub",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@jobhub.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("authentication/", include("authentication.urls")),
    path("job/", include("app_job.urls")),
    path("profile/", include("app_profile.urls")),
    path("messaging/", include("app_messaging.urls")),
    path("notification/", include("app_notification.urls")),
    path("backoffice/", include("app_backoffice.urls")),
    # Escrow
    path("contracts/", include(contract_urlpatterns)),
    path("wallet/", include(wallet_urlpatterns)),
    path("api/payments/", include(payments_urlpatterns)),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
