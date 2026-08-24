from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User

# Stock UserAdmin until Phase 1 adds the extra fields (full_name, phone,
# home_branch, role) and a proper fieldset for them.
admin.site.register(User, UserAdmin)
