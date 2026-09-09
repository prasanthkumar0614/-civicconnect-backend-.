from django.contrib import admin

from .models import Asset, AssetType


@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "id_prefix", "default_department"]


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ["asset_id", "asset_type", "area", "department", "status"]
    list_filter = ["status", "asset_type", "department"]
    search_fields = ["asset_id"]
    autocomplete_fields = ["area"]