from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    task_ref = serializers.CharField(source="task.ref", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "task_ref", "kind", "body", "created_at", "read_at"]
        read_only_fields = fields
