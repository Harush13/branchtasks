"""
§6's /api/tasks* surface. Views stay thin: permission classes wrap
accounts/permissions.py predicates, filtering/ordering delegates to
tasks/filters.py + tasks/selectors.py, and every write calls straight into
tasks/services.py — no business logic lives here.
"""

import csv
import io

from django.http import HttpResponse
from rest_framework import generics, mixins, status, views, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api_permissions import CanDeleteAttachment, CanEditTask, IsManager

from .filters import apply_query_params
from .models import Attachment
from .selectors import (
    annotate_overdue,
    dashboard_breakdown,
    dashboard_counters,
    kpi_summary,
    task_queryset,
)
from .serializers import (
    AttachmentSerializer,
    DashboardSummarySerializer,
    StatusChangeSerializer,
    TaskCreateSerializer,
    TaskDetailSerializer,
    TaskListSerializer,
    TaskPatchSerializer,
    TaskUpdateSerializer,
)
from .services import add_update, assign_task, attach_file, change_status, update_task_fields

_EXPORT_HEADERS = [
    "ref",
    "title",
    "branch",
    "category",
    "status",
    "priority",
    "assignee",
    "opened_by",
    "due_date",
    "created_at",
    "completed_at",
    "overdue",
]


# Excel/Sheets treats a cell starting with any of these as a formula, not
# text. `title`/`description` are free-text user input (everything else in
# a row is server-controlled), so a title like `=cmd|'/c calc'!A1` would
# execute on open — prefix with a leading apostrophe to force it to render
# as literal text instead (CSV Formula Injection / CWE-1236).
_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(_FORMULA_TRIGGERS) else text


def _export_row(task):
    return [
        _csv_safe(v)
        for v in [
            task.ref,
            task.title,
            task.branch.name_he,
            task.category.name_he,
            task.get_status_display(),
            task.get_priority_display(),
            task.assignee.full_name if task.assignee else "",
            task.opened_by.full_name,
            task.due_date.isoformat() if task.due_date else "",
            task.created_at.isoformat(),
            task.completed_at.isoformat() if task.completed_at else "",
            "כן" if task.overdue else "לא",
        ]
    ]


class TaskViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """No PUT (§6 lists PATCH only) and no plain DELETE (out of scope) —
    UpdateModelMixin/DestroyModelMixin are deliberately not mixed in."""

    lookup_field = "ref"
    lookup_value_regex = "[^/]+"
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = annotate_overdue(task_queryset())
        if self.action == "retrieve":
            # django-simple-history's `history` isn't a real reverse FK, so
            # prefetch_related("history") raises ValueError — only the two
            # genuine relations can be prefetched here.
            qs = qs.prefetch_related("updates__author", "attachments__uploaded_by")
        return qs

    def get_serializer_class(self):
        return {
            "list": TaskListSerializer,
            "create": TaskCreateSerializer,
            "retrieve": TaskDetailSerializer,
            "partial_update": TaskPatchSerializer,
        }[self.action]

    def get_permissions(self):
        if self.action == "partial_update":
            return [IsAuthenticated(), CanEditTask()]
        return super().get_permissions()

    def list(self, request, *args, **kwargs):
        qs = apply_query_params(self.get_queryset(), request.query_params)
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page if page is not None else qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        return Response(
            TaskDetailSerializer(task, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        task = self.get_object()
        serializer = self.get_serializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        fields = dict(serializer.validated_data)

        if "assignee" in fields:
            assign_task(task, fields.pop("assignee"), request.user)
        if fields:
            update_task_fields(task, request.user, **fields)

        task.refresh_from_db()
        return Response(TaskDetailSerializer(task, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="status")
    def set_status(self, request, ref=None):
        task = self.get_object()
        serializer = StatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        change_status(
            task,
            serializer.validated_data["status"],
            request.user,
            blocker=serializer.validated_data.get("blocker"),
        )
        task.refresh_from_db()
        return Response(TaskDetailSerializer(task, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="updates")
    def add_task_update(self, request, ref=None):
        task = self.get_object()
        serializer = TaskUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update = add_update(task, request.user, serializer.validated_data["body"])
        return Response(
            TaskUpdateSerializer(update).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """
        §7 (Phase 7 build note): CSV export using the same filters as the
        list endpoint, no pagination — the whole point is the file leaves
        the app. `utf-8-sig` (a BOM) is an Excel-specific requirement, not a
        Django one: without it, Excel on Windows guesses cp1252 and renders
        the Hebrew branch/category/status names as mojibake.
        """
        qs = apply_query_params(self.get_queryset(), request.query_params)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(_EXPORT_HEADERS)
        for task in qs:
            writer.writerow(_export_row(task))
        response = HttpResponse(buffer.getvalue().encode("utf-8-sig"), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="tasks.csv"'
        return response

    @action(
        detail=True,
        methods=["post"],
        url_path="attachments",
        parser_classes=[MultiPartParser, FormParser],
    )
    def add_attachment(self, request, ref=None):
        task = self.get_object()
        serializer = AttachmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attachment = attach_file(
            task,
            request.user,
            serializer.validated_data["file"],
            update=serializer.validated_data.get("update"),
        )
        return Response(
            AttachmentSerializer(attachment).data,
            status=status.HTTP_201_CREATED,
        )


class AttachmentDestroyView(generics.DestroyAPIView):
    """DELETE /api/attachments/{id} — uploader-or-admin (§6)."""

    queryset = Attachment.objects.all()
    permission_classes = [IsAuthenticated, CanDeleteAttachment]


class DashboardSummaryView(views.APIView):
    """GET /api/dashboard/summary — manager/admin only (§5, §8)."""

    permission_classes = [IsAuthenticated, IsManager]

    def get(self, request):
        return Response(DashboardSummarySerializer(dashboard_counters()).data)


class DashboardBreakdownView(views.APIView):
    """GET /api/dashboard/breakdown?by=branch|assignee|status|priority|category (§8)."""

    permission_classes = [IsAuthenticated, IsManager]

    def get(self, request):
        by = request.query_params.get("by")
        try:
            return Response(dashboard_breakdown(by))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class DashboardKpisView(views.APIView):
    """GET /api/dashboard/kpis — §9's four KPIs, manager/admin only like the
    rest of the dashboard (§5). Exposed last, per §9's own heading note."""

    permission_classes = [IsAuthenticated, IsManager]

    def get(self, request):
        return Response(kpi_summary())
