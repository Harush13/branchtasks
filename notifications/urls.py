from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("dropdown/", views.notification_dropdown, name="dropdown"),
    path("<int:pk>/read/", views.mark_read, name="mark_read"),
    path("read-all/", views.mark_all_read, name="read_all"),
]
