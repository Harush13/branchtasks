"""
§6: GET /api/meta — branches, categories, active users for dropdowns
(create-task form, assignee picker). Hebrew-sorted via
tasks.selectors.order_by_hebrew_name (§10.4) so the dropdowns don't need
their own copy of the Postgres-collation-vs-SQLite-fallback logic.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.serializers import UserBriefSerializer
from tasks.selectors import order_by_hebrew_name

from .models import Branch, Category
from .serializers import BranchSerializer, CategorySerializer


class MetaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        branches = order_by_hebrew_name(Branch.objects.filter(is_active=True), "name_he")
        categories = order_by_hebrew_name(Category.objects.filter(is_active=True), "name_he")
        users = order_by_hebrew_name(User.objects.filter(is_active=True), "full_name")

        return Response(
            {
                "branches": BranchSerializer(branches, many=True).data,
                "categories": CategorySerializer(categories, many=True).data,
                "users": UserBriefSerializer(users, many=True).data,
            }
        )
