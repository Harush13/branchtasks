from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    AUTH_USER_MODEL since Phase 0, so this class has existed since the first
    migration. Phase 1 adds the real fields from spec §3.2.
    """

    class Role(models.TextChoices):
        MEMBER = "member", "Member"
        MANAGER = "manager", "Manager"
        ADMIN = "admin", "Admin"

    full_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    # Form convenience only (pre-select this branch on the create-task form).
    # Must never be used to filter task visibility — see spec §1: visibility
    # is global regardless of home_branch.
    home_branch = models.ForeignKey("core.Branch", null=True, blank=True, on_delete=models.PROTECT)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
