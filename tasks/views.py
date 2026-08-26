"""
§11's HTML screens. Views stay thin exactly like tasks/api.py's DRF views —
same selectors/services underneath, just rendering templates instead of
JSON. Every inline-edit endpoint is a small POST view that calls one
tasks/services.py function and re-renders the matching field partial; HTMX
never receives a full page from these, so every one of them checks for the
HX-Request header is unnecessary — they're only ever wired to hx-post.
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.permissions import can_view_dashboard
from accounts.validators import ACTIVE_STATUSES
from core.models import Branch

from .filters import apply_query_params
from .forms import TaskForm
from .models import Task
from .selectors import (
    annotate_overdue,
    dashboard_counters,
    needs_attention,
    order_by_hebrew_name,
    task_queryset,
)
from .services import (
    add_update,
    assign_task,
    attach_file,
    change_status,
    create_task,
    update_task_fields,
)

PAGE_SIZE = 25


def _assignable_users():
    return order_by_hebrew_name(User.objects.filter(is_active=True), "full_name")


def _active_branches():
    return order_by_hebrew_name(Branch.objects.filter(is_active=True), "name_he")


class _TaskListBase(LoginRequiredMixin, View):
    """Shared list rendering for TaskListView and MyTasksView (§11: 'same
    component, pre-filtered' for My Tasks)."""

    page_title = ""
    hide_assignee = False
    hide_status = False

    def base_queryset(self, request):
        return annotate_overdue(task_queryset())

    def list_url_name(self):
        raise NotImplementedError

    def get(self, request):
        qs = apply_query_params(self.base_queryset(request), request.GET)
        page_obj = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))

        query_params = request.GET.copy()
        query_params.pop("page", None)

        context = {
            "page_title": self.page_title,
            "list_url": self.list_url_name(),
            "page_obj": page_obj,
            "querystring": query_params.urlencode(),
            "branches": _active_branches(),
            "assignable_users": _assignable_users(),
            "status_choices": Task.Status.choices,
            "hide_assignee": self.hide_assignee,
            "hide_status": self.hide_status,
            "filters": {
                "q": request.GET.get("q", ""),
                "branch": request.GET.get("branch", ""),
                "assignee": request.GET.get("assignee", ""),
                "priority_min": request.GET.get("priority_min", ""),
                "status": request.GET.getlist("status"),
                "overdue": request.GET.get("overdue") == "1",
            },
        }

        template = (
            "tasks/_task_list_results.html"
            if request.headers.get("HX-Request")
            else "tasks/task_list.html"
        )
        return render(request, template, context)


class TaskListView(_TaskListBase):
    page_title = "כל המשימות"

    def list_url_name(self):
        return reverse("tasks:list")


class MyTasksView(_TaskListBase):
    """§11: same component as TaskListView, pre-filtered to assignee=me and
    active only — forced server-side, not just hidden in the filter bar, so
    a hand-crafted query string can't widen it."""

    page_title = "המשימות שלי"
    hide_assignee = True
    hide_status = True

    def list_url_name(self):
        return reverse("tasks:my_tasks")

    def base_queryset(self, request):
        return (
            super().base_queryset(request).filter(assignee=request.user, status__in=ACTIVE_STATUSES)
        )


class TaskDetailView(LoginRequiredMixin, View):
    def get(self, request, ref):
        # django-simple-history's `history` isn't a real reverse FK, so
        # prefetch_related("history") raises ValueError (see tasks/api.py).
        task = get_object_or_404(
            annotate_overdue(task_queryset()).prefetch_related(
                "updates__author", "attachments__uploaded_by"
            ),
            ref=ref,
        )
        return render(
            request,
            "tasks/task_detail.html",
            {"task": task, "assignable_users": _assignable_users()},
        )


class TaskCreateView(LoginRequiredMixin, View):
    def get(self, request):
        form = TaskForm(home_branch=request.user.home_branch_id)
        return render(request, "tasks/task_form.html", {"form": form})

    def post(self, request):
        form = TaskForm(request.POST, home_branch=request.user.home_branch_id)
        if not form.is_valid():
            return render(request, "tasks/task_form.html", {"form": form})

        task = create_task(request.user, **form.cleaned_data)
        return redirect("tasks:detail", ref=task.ref)


class _ManagerOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    §5/§8: manager/admin only. `raise_exception` is a plain class attribute
    on Django's shared `AccessMixin`, so `True` would also make
    LoginRequiredMixin 403 an anonymous visitor instead of redirecting them
    to login. Making it a property keyed on authentication state gives each
    mixin the behavior it should have: redirect-to-login when logged out,
    403 when logged in but the wrong role — matching the nav link already
    being hidden for members.
    """

    @property
    def raise_exception(self):
        return self.request.user.is_authenticated

    def test_func(self):
        return can_view_dashboard(self.request.user)


class DashboardView(_ManagerOnlyMixin, View):
    def get(self, request):
        return render(
            request,
            "tasks/dashboard.html",
            {
                "counters": dashboard_counters(),
                "needs_attention": needs_attention(),
                # Fed to the Chart.js legends via json_script — without these
                # the JS-side STATUS_LABELS/PRIORITY_LABELS maps are empty
                # and every chart legend reads "undefined".
                "status_choices": Task.Status.choices,
                "priority_choices": Task.Priority.choices,
            },
        )


class DashboardCountersView(_ManagerOnlyMixin, View):
    """HTMX polling target (§8: refresh counters every 60s) — same partial
    both on first render and on each poll, so the two can never drift."""

    def get(self, request):
        return render(request, "tasks/_dashboard_counters.html", {"counters": dashboard_counters()})


@login_required
@require_POST
def set_status(request, ref):
    task = get_object_or_404(Task, ref=ref)
    error = None
    try:
        change_status(
            task,
            request.POST.get("status", ""),
            request.user,
            blocker=request.POST.get("blocker", ""),
        )
        task = get_object_or_404(annotate_overdue(task_queryset()), pk=task.pk)
    except (ValidationError, PermissionDenied) as exc:
        error = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
        task = get_object_or_404(annotate_overdue(task_queryset()), pk=task.pk)
    return render(request, "tasks/_field_status.html", {"task": task, "status_error": error})


@login_required
@require_POST
def set_priority(request, ref):
    task = get_object_or_404(Task, ref=ref)
    error = None
    try:
        update_task_fields(
            task, request.user, priority=int(request.POST.get("priority", task.priority))
        )
    except (ValidationError, PermissionDenied) as exc:
        error = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
    task.refresh_from_db()
    return render(request, "tasks/_field_priority.html", {"task": task, "priority_error": error})


@login_required
@require_POST
def set_assignee(request, ref):
    task = get_object_or_404(Task, ref=ref)
    error = None
    assignee_id = request.POST.get("assignee") or None
    assignee = get_object_or_404(User, pk=assignee_id) if assignee_id else None
    try:
        assign_task(task, assignee, request.user)
    except (ValidationError, PermissionDenied) as exc:
        error = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
    task.refresh_from_db()
    return render(
        request,
        "tasks/_field_assignee.html",
        {"task": task, "assignable_users": _assignable_users(), "assignee_error": error},
    )


@login_required
@require_POST
def set_due_date(request, ref):
    task = get_object_or_404(Task, ref=ref)
    error = None
    raw = request.POST.get("due_date") or None
    try:
        update_task_fields(task, request.user, due_date=raw)
    except (ValidationError, PermissionDenied) as exc:
        error = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)
    task.refresh_from_db()
    return render(request, "tasks/_field_due_date.html", {"task": task, "due_date_error": error})


@login_required
@require_POST
def add_task_update(request, ref):
    task = get_object_or_404(task_queryset().prefetch_related("updates__author"), ref=ref)
    body = (request.POST.get("body") or "").strip()
    error = None
    if body:
        add_update(task, request.user, body)
    else:
        error = "העדכון לא יכול להיות ריק."
    task.refresh_from_db()
    return render(request, "tasks/_updates_thread.html", {"task": task, "update_error": error})


@login_required
@require_POST
def add_task_attachment(request, ref):
    task = get_object_or_404(task_queryset().prefetch_related("attachments__uploaded_by"), ref=ref)
    error = None
    uploaded = request.FILES.get("file")
    if uploaded is None:
        error = "יש לבחור קובץ."
    else:
        try:
            attach_file(task, request.user, uploaded)
        except ValidationError as exc:
            error = "; ".join(exc.messages)
    task.refresh_from_db()
    return render(
        request, "tasks/_attachments_grid.html", {"task": task, "attachment_error": error}
    )
