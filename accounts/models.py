from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Swapped in as AUTH_USER_MODEL from Phase 0 onward. Django cannot change
    AUTH_USER_MODEL after the first migration without dropping the database,
    so this class exists as soon as any migration does — even though it is
    still just AbstractUser today.

    Phase 1 adds the real fields from spec §3.2 (full_name, phone,
    home_branch FK to core.Branch, role) plus the migration for them.
    """
