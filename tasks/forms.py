"""
HTML forms. Views call tasks/services.py with the cleaned data — forms here
validate shape only, the same division Phase 3's serializers keep.
"""

from django import forms
from django.contrib.auth import get_user_model

from core.models import Branch, Category

from .models import Task, TaskUpdate
from .selectors import order_by_hebrew_name

User = get_user_model()

_INPUT = (
    "w-full rounded-lg border border-gray-300 px-3 py-2 text-base "
    "focus:border-blue-500 focus:outline-none"
)
_SELECT = _INPUT
_TEXTAREA = _INPUT + " min-h-[6rem]"


class TaskForm(forms.ModelForm):
    """§11's "7 creation fields, max 6 required" — title/branch/category are
    the only ones the model itself requires; description/assignee/priority/
    due_date stay optional so the mobile form clears in one screen.

    due_date uses a native <input type="date">: the value/submission format
    is always ISO regardless of locale (HTML5 spec), while the picker UI a
    phone shows is locale-driven — satisfying §10.3's "Hebrew locale,
    DD/MM/YYYY display" without any custom parsing.
    """

    due_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"class": _INPUT, "type": "date"})
    )

    class Meta:
        model = Task
        fields = ["title", "description", "branch", "category", "assignee", "priority", "due_date"]
        widgets = {
            "title": forms.TextInput(attrs={"class": _INPUT}),
            "description": forms.Textarea(attrs={"class": _TEXTAREA}),
            "branch": forms.Select(attrs={"class": _SELECT}),
            "category": forms.Select(attrs={"class": _SELECT}),
            "assignee": forms.Select(attrs={"class": _SELECT}),
            "priority": forms.Select(attrs={"class": _SELECT}),
        }

    def __init__(self, *args, home_branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].required = False
        self.fields["assignee"].required = False
        self.fields["assignee"].queryset = order_by_hebrew_name(
            User.objects.filter(is_active=True, is_superuser=False), "full_name"
        )
        self.fields["branch"].queryset = Branch.objects.filter(is_active=True)
        self.fields["category"].queryset = Category.objects.filter(is_active=True)
        if home_branch is not None:
            self.fields["branch"].initial = home_branch


class TaskUpdateForm(forms.ModelForm):
    class Meta:
        model = TaskUpdate
        fields = ["body"]
        widgets = {
            "body": forms.Textarea(
                attrs={"class": _TEXTAREA, "rows": 2, "placeholder": "הוסף עדכון..."}
            )
        }
