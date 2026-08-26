"""
§6 request/response shapes. Serializers validate shape only — every write
delegates to tasks/services.py, and reads lean on tasks/selectors.py's
select_related so the nested branch/category/assignee/opened_by below don't
reintroduce the N+1 that selector was built to avoid.
"""

from rest_framework import serializers

from accounts.serializers import UserBriefSerializer
from core.serializers import BranchSerializer, CategorySerializer

from .models import Attachment, Task, TaskUpdate


class DashboardSummarySerializer(serializers.Serializer):
    """§8's four headline counters. Read-only — this endpoint has no write side."""

    open = serializers.IntegerField()
    closed = serializers.IntegerField()
    overdue = serializers.IntegerField()
    urgent = serializers.IntegerField()


class TaskListSerializer(serializers.ModelSerializer):
    """Read shape for GET /api/tasks. `overdue` is selectors.annotate_overdue's
    annotation, never a stored column (§3.3) — declared read-only here so it
    can only ever come from that annotation, not from client input."""

    branch = BranchSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    assignee = UserBriefSerializer(read_only=True)
    opened_by = UserBriefSerializer(read_only=True)
    overdue = serializers.BooleanField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)

    class Meta:
        model = Task
        fields = [
            "ref",
            "title",
            "branch",
            "category",
            "opened_by",
            "assignee",
            "priority",
            "priority_display",
            "status",
            "status_display",
            "due_date",
            "overdue",
            "created_at",
            "updated_at",
        ]


class TaskUpdateSerializer(serializers.ModelSerializer):
    author = UserBriefSerializer(read_only=True)

    class Meta:
        model = TaskUpdate
        fields = ["id", "author", "body", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = UserBriefSerializer(read_only=True)
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Attachment
        fields = [
            "id",
            "update",
            "file",
            "original_name",
            "mime_type",
            "size_bytes",
            "uploaded_by",
            "uploaded_at",
        ]
        read_only_fields = ["id", "original_name", "mime_type", "size_bytes", "uploaded_at"]


class TaskHistorySerializer(serializers.Serializer):
    """Flat view over django-simple-history's HistoricalTask rows (spec
    §3.4's audit trail) — plain Serializer since the historical model isn't
    one we own the fields list for."""

    history_id = serializers.IntegerField()
    history_date = serializers.DateTimeField()
    history_type = serializers.CharField()
    history_user = serializers.SerializerMethodField()
    status = serializers.CharField()
    title = serializers.CharField()

    def get_history_user(self, obj):
        return obj.history_user.username if obj.history_user else None


class TaskDetailSerializer(TaskListSerializer):
    updates = TaskUpdateSerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    history = TaskHistorySerializer(many=True, read_only=True)

    class Meta(TaskListSerializer.Meta):
        fields = TaskListSerializer.Meta.fields + [
            "description",
            "blocker",
            "completed_at",
            "cancelled_at",
            "updates",
            "attachments",
            "history",
        ]


class TaskCreateSerializer(serializers.ModelSerializer):
    """Writable subset for POST /api/tasks. `opened_by`, `ref`, `status`, and
    the timestamps are all server-owned — create() delegates to
    services.create_task, which is the single place that sets them."""

    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "branch",
            "category",
            "assignee",
            "priority",
            "due_date",
            "watchers",
        ]

    def create(self, validated_data):
        from .services import create_task

        actor = self.context["request"].user
        return create_task(actor, **validated_data)


class TaskPatchSerializer(serializers.ModelSerializer):
    """PATCH /api/tasks/{ref} — mutable fields only. `status` must be
    rejected with a 400 pointing at the dedicated endpoint (§6); `assignee`
    is accepted here but the view routes it through services.assign_task
    instead of a plain field write, since reassignment carries its own
    permission check and notification/alert-pruning side effects."""

    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "category",
            "assignee",
            "priority",
            "due_date",
            "watchers",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}

    def validate(self, attrs):
        if "status" in self.initial_data:
            raise serializers.ValidationError(
                {"status": "Use POST /api/tasks/{ref}/status to change status."}
            )
        return attrs


class StatusChangeSerializer(serializers.Serializer):
    """POST /api/tasks/{ref}/status — shape only; change_status() owns every
    transition/permission/blocker rule."""

    status = serializers.ChoiceField(choices=Task.Status.choices)
    blocker = serializers.CharField(required=False, allow_blank=True, default="")
