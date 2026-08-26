"""§6's /api/ surface."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views import LoginView, LogoutView
from core.views import MetaView
from notifications.views import NotificationViewSet
from tasks.api import (
    AttachmentDestroyView,
    DashboardBreakdownView,
    DashboardKpisView,
    DashboardSummaryView,
    TaskViewSet,
)

router = DefaultRouter(trailing_slash=False)
router.register("tasks", TaskViewSet, basename="task")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="api-login"),
    path("auth/logout", LogoutView.as_view(), name="api-logout"),
    path("meta", MetaView.as_view(), name="api-meta"),
    path("attachments/<int:pk>", AttachmentDestroyView.as_view(), name="api-attachment-delete"),
    path("dashboard/summary", DashboardSummaryView.as_view(), name="api-dashboard-summary"),
    path("dashboard/breakdown", DashboardBreakdownView.as_view(), name="api-dashboard-breakdown"),
    path("dashboard/kpis", DashboardKpisView.as_view(), name="api-dashboard-kpis"),
    path("", include(router.urls)),
]
