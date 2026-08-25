"""Values every template needs, computed once per request instead of once
per view — currently just the notification bell's unread count (§11)."""


def notifications(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"unread_notification_count": 0}

    from notifications.models import Notification

    count = Notification.objects.filter(user=user, read_at__isnull=True).count()
    return {"unread_notification_count": count}
