"""
URL configuration. Phase 3 adds the /api/ surface (config/api_urls.py);
template-based UI routes (tasks/, accounts/, notifications/) are still Phase
4's job.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("config.api_urls")),
]

if settings.DEBUG:
    # Dev-only: serve uploaded attachments straight off disk so they're
    # retrievable without a separate media server (nginx does this in prod —
    # see nginx.conf, Phase 7).
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
