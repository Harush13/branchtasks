from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.TaskListView.as_view(), name="list"),
    path("my/", views.MyTasksView.as_view(), name="my_tasks"),
    path("new/", views.TaskCreateView.as_view(), name="create"),
    path("<str:ref>/", views.TaskDetailView.as_view(), name="detail"),
    path("<str:ref>/status/", views.set_status, name="set_status"),
    path("<str:ref>/priority/", views.set_priority, name="set_priority"),
    path("<str:ref>/assignee/", views.set_assignee, name="set_assignee"),
    path("<str:ref>/due-date/", views.set_due_date, name="set_due_date"),
    path("<str:ref>/updates/", views.add_task_update, name="add_update"),
    path("<str:ref>/attachments/", views.add_task_attachment, name="add_attachment"),
]
