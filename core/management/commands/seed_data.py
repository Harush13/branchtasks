from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from core.models import Branch, Category

BRANCHES = [
    ("תל יצחק", "Tel Yitzhak"),
    ("חבצלת", "Havatzelet"),
    ("ניר אליהו", "Nir Eliyahu"),
    ("עמק חפר", "Emek Hefer"),
]

CATEGORIES = [
    ("תפעול", "Operations"),
    ("אחזקה", "Maintenance"),
    ("כספים", "Finance"),
    ('כ"א', "HR"),
    ("רכש", "Procurement"),
    ("לקוחות", "Customers"),
    ("בטיחות", "Safety"),
    ("אחר", "Other"),
]

# (username, full_name, role, branch index into BRANCHES)
DEMO_USERS = [
    ("member1", "נועה כהן", User.Role.MEMBER, 0),
    ("member2", "איתי לוי", User.Role.MEMBER, 1),
    ("member3", "מיכל אברהם", User.Role.MEMBER, 2),
    ("manager1", "דניאל פרץ", User.Role.MANAGER, 0),
    ("manager2", "יעל שפירא", User.Role.MANAGER, 3),
    ("admin1", "רון גולן", User.Role.ADMIN, 0),
]
DEMO_PASSWORD = "demo1234"  # dev only — never used against DATABASE_URL in prod


class Command(BaseCommand):
    help = "Seed branches, categories, and demo users for local development."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_data refuses to run with DEBUG=False (prod safety).")

        for order, (name_he, name_en) in enumerate(BRANCHES):
            branch, created = Branch.objects.get_or_create(
                name_he=name_he, defaults={"name_en": name_en, "sort_order": order}
            )
            self._report("branch", branch, created)

        for order, (name_he, name_en) in enumerate(CATEGORIES):
            category, created = Category.objects.get_or_create(
                name_he=name_he, defaults={"name_en": name_en, "sort_order": order}
            )
            self._report("category", category, created)

        branches = list(Branch.objects.order_by("sort_order"))
        for username, full_name, role, branch_idx in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "full_name": full_name,
                    "role": role,
                    "home_branch": branches[branch_idx],
                    "is_staff": role == User.Role.ADMIN,
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=["password"])
            self._report("user", user, created)

    def _report(self, label, obj, created):
        verb = "created" if created else "exists"
        self.stdout.write(f"  {label}: {obj} ({verb})")
