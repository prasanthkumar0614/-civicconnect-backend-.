from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


class UserAdmin(BaseUserAdmin):
    """Adds our custom role/department/area/phone_number fields to the admin UI."""

    fieldsets = BaseUserAdmin.fieldsets + (
        ("CivicConnect", {"fields": ("role", "department", "area", "phone_number")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("CivicConnect", {"fields": ("role", "department", "area", "phone_number")}),
    )
    list_display = BaseUserAdmin.list_display + ("role", "department")
    list_filter = BaseUserAdmin.list_filter + ("role", "department")
    autocomplete_fields = ["department", "area"]


admin.site.register(User, UserAdmin)