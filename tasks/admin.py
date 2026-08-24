from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Attachment, Task, TaskUpdate


class TaskUpdateInline(admin.TabularInline):
    model = TaskUpdate
    extra = 0
    readonly_fields = ["created_at"]


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    readonly_fields = ["uploaded_at"]


@admin.register(Task)
class TaskAdmin(SimpleHistoryAdmin):
    list_display = [
        "ref",
        "title",
        "branch",
        "category",
        "status",
        "priority",
        "assignee",
        "due_date",
    ]
    list_filter = ["status", "priority", "branch", "category"]
    search_fields = ["ref", "title", "description"]
    readonly_fields = ["ref", "created_at", "updated_at", "completed_at", "cancelled_at"]
    autocomplete_fields = ["branch", "category", "opened_by", "assignee", "watchers"]
    inlines = [TaskUpdateInline, AttachmentInline]

    # Every list-page render needs these FKs — this is the N+1 guard called
    # out in spec §6 applied to the changelist itself, not just the API.
    list_select_related = ["branch", "category", "assignee", "opened_by"]

    def get_readonly_fields(self, request, obj=None):
        """
        §4: no admin action may write `status` directly — only
        tasks/services.py::change_status() may. Read-only on change; still
        editable on add, since a new task's status is just its default 'new'.
        """
        if obj is None:
            return self.readonly_fields
        return [*self.readonly_fields, "status"]
