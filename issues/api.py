"""
issues/serializers.py, issues/views.py, issues/urls.py (combined for readability).
"""

# ---------------------------------------------------------------------------
# issues/serializers.py
# ---------------------------------------------------------------------------
from rest_framework import serializers
from .models import Issue, IssuePhoto, IssueStatusHistory, Notification


class IssuePhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = IssuePhoto
        fields = ["id", "image", "video", "is_resolution_photo", "uploaded_at"]
        read_only_fields = ["uploaded_at"]


class IssueStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.username", read_only=True)

    class Meta:
        model = IssueStatusHistory
        fields = ["status", "changed_by_name", "note", "changed_at"]


class IssueCreateSerializer(serializers.ModelSerializer):
    """What a citizen submits. AI fields are never writable from the client."""

    class Meta:
        model = Issue
        fields = ["id", "asset", "description"]

    def validate_description(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "Please describe the problem in a bit more detail (at least 10 characters)."
            )
        return value.strip()


class IssueSerializer(serializers.ModelSerializer):
    """Full read representation shown to citizens (their own issues) and authorities."""

    asset_display = serializers.CharField(source="asset.asset_id", read_only=True)
    asset_area_path = serializers.CharField(source="asset.area.full_path", read_only=True)
    reporter_name = serializers.CharField(source="reporter.username", read_only=True)
    assigned_officer_name = serializers.CharField(
        source="assigned_officer.username", read_only=True, default=None
    )
    photos = IssuePhotoSerializer(many=True, read_only=True)
    status_history = IssueStatusHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Issue
        fields = [
            "id", "asset", "asset_display", "asset_area_path", "reporter", "reporter_name", "description",
            "ai_category", "ai_priority", "ai_summary", "ai_department_suggestion",
            "duplicate_of", "status", "assigned_officer", "assigned_officer_name",
            "resolution_notes", "photos", "status_history", "created_at", "updated_at",
        ]
        read_only_fields = [
            "reporter", "ai_category", "ai_priority", "ai_summary",
            "ai_department_suggestion", "duplicate_of", "created_at", "updated_at",
        ]


class IssueStatusUpdateSerializer(serializers.Serializer):
    """Payload for the officer 'update status' action — validated separately
    from the main serializer since it's a narrow, workflow-specific write."""

    status = serializers.ChoiceField(choices=Issue.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_status(self, value):
        # Prevent skipping backwards, e.g. RESOLVED -> OPEN, except by admins.
        current = self.instance.status if self.instance else None
        forward_only = {
            Issue.Status.OPEN: {Issue.Status.IN_PROGRESS},
            Issue.Status.IN_PROGRESS: {Issue.Status.RESOLVED},
            Issue.Status.RESOLVED: {Issue.Status.CLOSED},
        }
        request = self.context.get("request")
        is_admin = request and request.user.role in ("DEPT_ADMIN", "MANDAL_HEAD", "SUPER_ADMIN")
        if not is_admin and current in forward_only and value not in forward_only[current]:
            raise serializers.ValidationError(
                f"Cannot move status from {current} to {value} directly."
            )
        return value


class NotificationSerializer(serializers.ModelSerializer):
    asset_display = serializers.CharField(source="issue.asset.asset_id", read_only=True, default=None)

    class Meta:
        model = Notification
        fields = ["id", "message", "issue", "asset_display", "is_read", "created_at"]


# ---------------------------------------------------------------------------
# issues/views.py
# ---------------------------------------------------------------------------
import threading

from django.db import close_old_connections
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from core.permissions import IsCitizen, IsOfficerOrAbove
from .permissions import IssueAccessPolicy
from services.ai_service import classify_issue, find_possible_duplicates, AIServiceError
from core.models import Department
from services.notification_service import (
    notify_issue_submitted, notify_new_complaint, notify_status_changed,
    notify_officer_assigned, notify_department_high_priority,
)


def _send_submission_notifications_in_background(issue):
    """
    Runs in a separate thread, AFTER the citizen already has their success
    response. Emails are slow and the citizen doesn't need to wait for them —
    this is what was previously causing intermittent "Couldn't submit your
    report" errors when the total request time ran too long.
    """
    close_old_connections()  # this thread needs its own fresh DB connection
    notify_issue_submitted(issue)
    notify_new_complaint(issue)
    notify_department_high_priority(issue)  # no-op unless ai_priority == HIGH


class IssueViewSet(viewsets.ModelViewSet):
    """
    /api/issues/                    citizen: create + list own; authority: list scoped queue
    /api/issues/{id}/                retrieve/update (scoped by IssueAccessPolicy)
    /api/issues/{id}/assign/         POST {officer_id}  — dept admin assigns an officer
    /api/issues/{id}/update_status/  POST {status, note} — officer/admin workflow transition
    /api/issues/{id}/upload_photo/   POST multipart image/video — citizen or officer
    """

    permission_classes = [IssueAccessPolicy]
    filterset_fields = ["status", "ai_priority", "asset__area", "asset__department"]

    def get_serializer_class(self):
        if self.action == "create":
            return IssueCreateSerializer
        return IssueSerializer

    def get_queryset(self):
        user = self.request.user
        base = Issue.objects.select_related(
            "asset", "asset__area", "asset__department", "reporter", "assigned_officer"
        ).prefetch_related("photos", "status_history")

        if user.role == "SUPER_ADMIN":
            return base
        if user.role == "CITIZEN":
            return base.filter(reporter=user)
        if user.role == "OFFICER":
            return base.filter(Q(assigned_officer=user) | Q(asset__department=user.department))
        if user.role == "DEPT_ADMIN":
            return base.filter(asset__department=user.department)
        if user.role == "MANDAL_HEAD":
            if not user.area_id:
                return base.none()
            return base.filter(asset__area_id__in=user.area.get_descendant_ids())
        return base.none()

    def perform_create(self, serializer):
        issue = serializer.save(reporter=self.request.user)

        # Run AI triage. A failed AI call must never block the citizen's
        # submission — the issue is still saved as OPEN with empty AI fields
        # and can be triaged manually.
        try:
            department_names = list(Department.objects.values_list("name", flat=True))
            result = classify_issue(
                description=issue.description,
                asset_type=issue.asset.asset_type.name,
                area_name=issue.asset.area.name,
                department_names=department_names,
            )
            issue.ai_category = result["category"]
            issue.ai_priority = result["priority"]
            issue.ai_summary = result["summary"]
            suggested_name = result.get("department")
            if suggested_name:
                issue.ai_department_suggestion = Department.objects.filter(name=suggested_name).first()
        except AIServiceError:
            pass  # issue stays OPEN with blank AI fields; visible to admins for manual triage

        # Duplicate check against other OPEN issues on the same asset.
        open_siblings = Issue.objects.filter(
            asset=issue.asset, status=Issue.Status.OPEN
        ).exclude(pk=issue.pk)
        dup_ids = find_possible_duplicates(issue.description, open_siblings)
        if dup_ids:
            issue.duplicate_of_id = dup_ids[0]

        issue.save()

        # Automatic acknowledgment — appears immediately in the citizen's
        # "Update from the department" card, no officer action needed.
        IssueStatusHistory.objects.create(
            issue=issue,
            status=issue.status,
            changed_by=None,
            note="Thanks for reporting! We've received your complaint and will work to resolve it within 2 working days.",
        )

        # Emails happen in the background so the citizen's app gets its
        # "success" response immediately, instead of waiting on 1-3 emails.
        threading.Thread(
            target=_send_submission_notifications_in_background,
            args=(issue,),
            daemon=True,
        ).start()

    @action(detail=True, methods=["post"], permission_classes=[IsOfficerOrAbove])
    def assign(self, request, pk=None):
        issue = self.get_object()
        officer_id = request.data.get("officer_id")
        if not officer_id:
            return Response({"detail": "officer_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        issue.assigned_officer_id = officer_id
        issue.save(update_fields=["assigned_officer"])
        IssueStatusHistory.objects.create(
            issue=issue, status=issue.status, changed_by=request.user,
            note=f"Assigned to officer #{officer_id}",
        )
        notify_officer_assigned(issue)
        return Response(IssueSerializer(issue).data)

    @action(detail=True, methods=["post"], permission_classes=[IsOfficerOrAbove])
    def update_status(self, request, pk=None):
        issue = self.get_object()
        serializer = IssueStatusUpdateSerializer(
            instance=issue, data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        old_status = issue.status
        issue.status = serializer.validated_data["status"]
        if issue.status == Issue.Status.RESOLVED:
            issue.resolution_notes = serializer.validated_data.get("note", "")
        issue.save()

        IssueStatusHistory.objects.create(
            issue=issue, status=issue.status, changed_by=request.user,
            note=serializer.validated_data.get("note", ""),
        )
        notify_status_changed(issue, old_status)
        return Response(IssueSerializer(issue).data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload_photo(self, request, pk=None):
        issue = self.get_object()
        is_resolution = request.data.get("is_resolution_photo", "false").lower() == "true"
        image = request.data.get("image")
        video = request.data.get("video")
        if not image and not video:
            return Response({"detail": "An image or video file is required."}, status=status.HTTP_400_BAD_REQUEST)
        photo = IssuePhoto.objects.create(
            issue=issue, image=image, video=video,
            uploaded_by=request.user, is_resolution_photo=is_resolution,
        )
        return Response(IssuePhotoSerializer(photo).data, status=status.HTTP_201_CREATED)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    /api/notifications/                 list -- only the logged-in user's own
    /api/notifications/unread_count/    GET  -- {"count": N}, for the bell badge
    /api/notifications/{id}/mark_read/  POST -- marks one as read
    /api/notifications/mark_all_read/   POST -- marks every notification read
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsOfficerOrAbove]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related("issue", "issue__asset")

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"count": count})

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"status": "ok"})


# ---------------------------------------------------------------------------
# issues/urls.py
# ---------------------------------------------------------------------------
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"issues", IssueViewSet, basename="issue")
router.register(r"notifications", NotificationViewSet, basename="notification")

urlpatterns = router.urls
