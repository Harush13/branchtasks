"""
§6: GET /api/notifications, POST /api/notifications/{id}/read, POST
/api/notifications/read-all — all scoped to request.user so one user can
never read or mark-read another user's notifications. The Phase 4 HTML
views at the bottom of this file cover the same three operations for the
header bell (§11) — same scoping rule, different rendering.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user, read_at__isnull=True)

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = Notification.objects.filter(pk=pk, user=request.user).first()
        if notification is None:
            return Response(status=404)
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        Notification.objects.filter(user=request.user, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        return Response(status=204)


# --- Phase 4 HTML views (§11: bell dropdown, mark-read) ---


def _dropdown_context(user):
    return {"notifications": Notification.objects.filter(user=user, read_at__isnull=True)}


@login_required
def notification_dropdown(request):
    return render(request, "notifications/_dropdown.html", _dropdown_context(request.user))


@login_required
@require_POST
def mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return render(request, "notifications/_dropdown.html", _dropdown_context(request.user))


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return render(request, "notifications/_dropdown.html", _dropdown_context(request.user))
