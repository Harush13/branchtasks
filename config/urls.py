"""
URL configuration. /api/ is the JSON surface (config/api_urls.py); the
remaining paths are the §11 HTML screens, keyed by ref the same way the API
is (/tasks/TSK-000142/).
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("config.api_urls")),
    path("notifications/", include("notifications.urls")),
    path("", include("accounts.urls")),
    # LOGIN_REDIRECT_URL is "/" — send it straight to the task list.
    path("", RedirectView.as_view(pattern_name="tasks:list", permanent=False)),
    path("tasks/", include("tasks.urls")),
]

if settings.DEBUG:
    # Dev-only: serve uploaded attachments straight off disk so they're
    # retrievable without a separate media server (nginx does this in prod —
    # see nginx.conf, Phase 7).
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
