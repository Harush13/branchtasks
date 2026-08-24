from django.contrib import admin

from .models import Branch, Category


@admin.register(Branch)
@admin.register(Category)
class LookupAdmin(admin.ModelAdmin):
    list_display = ["name_he", "name_en", "sort_order", "is_active"]
    list_editable = ["sort_order", "is_active"]
    search_fields = ["name_he", "name_en"]
