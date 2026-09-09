"""
issues/permissions.py

This is the most important permission logic in the whole system: it decides who
can see and touch which complaints.

Rules:
- Citizens can view/edit only issues they reported.
- Officers can view/edit only issues assigned to them.
- Department admins can view/edit any issue routed to their department.
- Mandal heads can view/edit any issue anywhere within their mandal (any department).
- Super admins can view/edit everything.
"""

from rest_framework import permissions


class IssueAccessPolicy(permissions.BasePermission):

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.role == "SUPER_ADMIN":
            return True

        if user.role == "CITIZEN":
            # Citizens can read their own issues, and attach photos to them,
            # but can't edit anything else once submitted.
            if request.method in permissions.SAFE_METHODS:
                return obj.reporter_id == user.id
            if getattr(view, "action", None) == "upload_photo":
                return obj.reporter_id == user.id
            return False

        if user.role == "OFFICER":
            if request.method in permissions.SAFE_METHODS:
                return obj.assigned_officer_id == user.id or obj.asset.department_id == user.department_id
            return obj.assigned_officer_id == user.id

        if user.role == "DEPT_ADMIN":
            return obj.asset.department_id == user.department_id

        if user.role == "MANDAL_HEAD":
            if not user.area_id:
                return False
            return obj.asset.area_id in user.area.get_descendant_ids()

        return False