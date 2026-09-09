"""
config/urls.py — project root URL configuration.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.api")),
    path("api/", include("core.api")),
    path("api/", include("assets.api")),
    path("api/", include("assets.map_urls")),
    path("api/", include("issues.api")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
