"""
accounts/serializers.py, accounts/views.py, accounts/urls.py (combined for readability).
Uses djangorestframework-simplejwt for token auth — see config/settings.py notes below.
"""

# ---------------------------------------------------------------------------
# accounts/serializers.py
# ---------------------------------------------------------------------------
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "phone_number", "area"]
        # Note: role is deliberately NOT in this list — citizens self-register
        # via this endpoint only; officer/admin accounts are created by a
        # Super Admin through the admin-only UserAdminViewSet (not shown here)
        # so nobody can grant themselves elevated access via signup.

    def create(self, validated_data):
        user = User.objects.create_user(role=User.Role.CITIZEN, **validated_data)
        return user


class OfficerSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = ["id", "username", "email", "department", "department_name"]


class UserProfileSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    area_name = serializers.CharField(source="area.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "phone_number", "role", "role_display",
            "department", "department_name", "area", "area_name",
        ]
        read_only_fields = ["role", "department"]  # profile edits never change access level


class CivicConnectTokenSerializer(TokenObtainPairSerializer):
    """Adds role/department to the JWT payload so the frontend can route
    users to the right dashboard without an extra API call after login."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["department_id"] = user.department_id
        return token


# ---------------------------------------------------------------------------
# accounts/views.py
# ---------------------------------------------------------------------------
from rest_framework import generics, permissions
from rest_framework_simplejwt.views import TokenObtainPairView

from core.permissions import IsOfficerOrAbove


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — public, citizen self-signup only."""

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ -> {access, refresh} with role embedded in the token."""

    serializer_class = CivicConnectTokenSerializer


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/ — the logged-in user's own profile."""

    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class OfficerListView(generics.ListAPIView):
    """GET /api/officers/ — used by the dashboard's "Assign officer" dropdown.

    Dept Admins and Officers only see officers within their own department
    (so an Electrical dept admin can't assign a Water dept officer).
    Super Admins see every officer, across all departments.
    """

    serializer_class = OfficerSerializer
    permission_classes = [IsOfficerOrAbove]

    def get_queryset(self):
        user = self.request.user
        qs = User.objects.filter(role="OFFICER").select_related("department")
        if user.role == "SUPER_ADMIN":
            return qs
        return qs.filter(department=user.department)


# ---------------------------------------------------------------------------
# accounts/urls.py
# ---------------------------------------------------------------------------
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/login/refresh/", TokenRefreshView.as_view(), name="login-refresh"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("officers/", OfficerListView.as_view(), name="officers"),
]
