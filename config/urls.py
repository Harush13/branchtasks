"""
URL configuration. Empty besides Django Admin in Phase 0 — app routes
(tasks/, accounts/, notifications/, api/) are wired in as each phase adds
its views.
"""

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
