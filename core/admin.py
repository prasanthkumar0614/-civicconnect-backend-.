from django.contrib import admin

from .models import Area, Department


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ["name", "level", "parent"]
    list_filter = ["level"]
    search_fields = ["name"]
    autocomplete_fields = ["parent"]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]