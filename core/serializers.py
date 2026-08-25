from rest_framework import serializers

from .models import Branch, Category


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name_he", "name_en", "sort_order", "is_active"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name_he", "name_en", "sort_order", "is_active"]
