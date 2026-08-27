from django.contrib import admin

from .models import Branch, Category


@admin.register(Category)
class LookupAdmin(admin.ModelAdmin):
    list_display = ["name_he", "name_en", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    search_fields = ["name_he", "name_en"]


@admin.register(Branch)
class BranchAdmin(LookupAdmin):
    list_display = ["name_he", "name_en", "manager", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    autocomplete_fields = ["manager"]
