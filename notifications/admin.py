from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["kind", "user", "task", "created_at", "read_at"]
    list_filter = ["kind", "read_at"]
    list_select_related = ["user", "task"]
    autocomplete_fields = ["user", "task"]
