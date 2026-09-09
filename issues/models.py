from django.conf import settings
from django.db import models

from assets.models import Asset
from core.models import Department


class Issue(models.Model):
    """A citizen-reported complaint tied to one asset."""

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="issues")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reported_issues"
    )
    description = models.TextField()

    # --- AI-generated fields (filled after the AI classification call) ---
    ai_category = models.CharField(max_length=100, blank=True)
    ai_priority = models.CharField(max_length=10, choices=Priority.choices, blank=True)
    ai_summary = models.TextField(blank=True)
    ai_department_suggestion = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="suggested_issues",
    )
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="duplicates",
    )

    # --- Workflow fields ---
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    assigned_officer = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="assigned_issues",
    )
    resolution_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Issue #{self.pk} — {self.asset.asset_id}"


class IssuePhoto(models.Model):
    """Citizen-submitted or officer-submitted (resolution) media for an issue.
    Either image or video is set, never both -- see upload_photo in issues/api.py."""

    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="issue_photos/%Y/%m/", null=True, blank=True)
    video = models.FileField(upload_to="issue_videos/%Y/%m/", null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_resolution_photo = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)


class IssueStatusHistory(models.Model):
    """Audit trail — every status change on an issue, for the citizen-facing tracker."""

    issue = models.ForeignKey(Issue, on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=20, choices=Issue.Status.choices)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    note = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["changed_at"]


class Notification(models.Model):
    """In-app notification shown in the dashboard's bell icon (officers/admins only)."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    issue = models.ForeignKey(
        Issue, null=True, blank=True, on_delete=models.CASCADE, related_name="notifications"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]