from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm

from .models import User
from .validators import assert_can_deactivate


class UserChangeFormWithGuard(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User

    def clean(self):
        cleaned = super().clean()
        was_active = self.instance.pk and User.objects.get(pk=self.instance.pk).is_active
        if was_active and not cleaned.get("is_active"):
            assert_can_deactivate(self.instance)
        return cleaned


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserChangeFormWithGuard
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Branch profile", {"fields": ("full_name", "phone", "home_branch", "role")}),
    )
    list_display = ["username", "full_name", "role", "home_branch", "is_active", "is_staff"]
    list_filter = ["role", "home_branch", "is_active"]
