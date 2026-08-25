"""
§6's /api/tasks* surface. Views stay thin: permission classes wrap
accounts/permissions.py predicates, filtering/ordering delegates to
tasks/filters.py + tasks/selectors.py, and every write calls straight into
tasks/services.py — no business logic lives here.
"""

from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.api_permissions import CanDeleteAttachment, CanEditTask

from .filters import apply_query_params
from .models import Attachment
from .selectors import annotate_overdue, task_queryset
from .serializers import (
    AttachmentSerializer,
    StatusChangeSerializer,
    TaskCreateSerializer,
    TaskDetailSerializer,
    TaskListSerializer,
    TaskPatchSerializer,
    TaskUpdateSerializer,
)
from .services import add_update, assign_task, attach_file, change_status, update_task_fields


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
