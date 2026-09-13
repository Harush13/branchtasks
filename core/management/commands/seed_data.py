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

# (username, full_name, role, branch index into BRANCHES, password override or None)
DEMO_USERS = [
    ("member1", "נועה כהן", User.Role.MEMBER, 0, None),
    ("member2", "איתי לוי", User.Role.MEMBER, 1, None),
    ("member3", "מיכל אברהם", User.Role.MEMBER, 2, None),
    ("manager1", "אבי אשכנזי", User.Role.MANAGER, 0, None),
    ("manager2", "יניב הרוש", User.Role.MANAGER, 1, None),
    ("manager3", "שמוליק טחן", User.Role.MANAGER, 2, None),
    ("manager4", "איתי טננבאום", User.Role.MANAGER, 3, None),
    ("manager5", "עידן עבאדי", User.Role.MANAGER, 0, None),
    ("manager6", "רעות טננבאום", User.Role.MANAGER, 1, None),
    ("manager7", "כרמל נר גאון", User.Role.MANAGER, 2, None),
    ("ADMIN", "מנהל כללי", User.Role.ADMIN, 0, "12345678"),
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
        for username, full_name, role, branch_idx, password in DEMO_USERS:
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
                user.set_password(password or DEMO_PASSWORD)
                user.save(update_fields=["password"])
            self._report("user", user, created)

            if role == User.Role.MANAGER:
                branch = branches[branch_idx]
                if branch.manager_id != user.id:
                    branch.manager = user
                    branch.save(update_fields=["manager"])
                    self._report("branch manager", branch, created=False)

    def _report(self, label, obj, created):
        verb = "created" if created else "exists"
        self.stdout.write(f"  {label}: {obj} ({verb})")
