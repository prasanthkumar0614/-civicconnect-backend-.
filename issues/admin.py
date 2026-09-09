from django.contrib import admin

from .models import Issue, IssuePhoto, IssueStatusHistory


class IssuePhotoInline(admin.TabularInline):
    model = IssuePhoto
    extra = 0


class IssueStatusHistoryInline(admin.TabularInline):
    model = IssueStatusHistory
    extra = 0
    readonly_fields = ["changed_at"]


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ["id", "asset", "reporter", "status", "ai_priority", "created_at"]
    list_filter = ["status", "ai_priority"]
    search_fields = ["description"]
    inlines = [IssuePhotoInline, IssueStatusHistoryInline]
