"""
core/permissions.py

Shared, reusable DRF permission classes used across apps.
Role checks read from request.user.role (see accounts.models.User.Role).
"""

from rest_framework import permissions


class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role == "SUPER_ADMIN")


class IsDepartmentAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role in ("DEPT_ADMIN", "MANDAL_HEAD", "SUPER_ADMIN"))


class IsOfficerOrAbove(permissions.BasePermission):
    """Officers, department admins, mandal heads, and super admins — the authority side."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role in ("OFFICER", "DEPT_ADMIN", "MANDAL_HEAD", "SUPER_ADMIN"))


class IsCitizen(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role == "CITIZEN")


class ReadOnlyOrAdmin(permissions.BasePermission):
    """Anyone authenticated can read; only Dept/Super admins can write.
    Used for reference data like Area, Department, AssetType."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.role in ("DEPT_ADMIN", "SUPER_ADMIN")