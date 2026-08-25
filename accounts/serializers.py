from rest_framework import serializers

from .models import User


class UserBriefSerializer(serializers.ModelSerializer):
    """Minimal user shape for embedding into task/notification payloads and
    the /api/meta dropdown list — never the full User (no email/password)."""

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "role"]
