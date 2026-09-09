from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model so we can attach a role and area to every account."""

    class Role(models.TextChoices):
        CITIZEN = "CITIZEN", "Citizen"
        OFFICER = "OFFICER", "Officer"
        DEPT_ADMIN = "DEPT_ADMIN", "Department Admin"
        MANDAL_HEAD = "MANDAL_HEAD", "Mandal Head"
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CITIZEN)
    phone_number = models.CharField(max_length=15, blank=True)

    # Officers / Dept Admins belong to one department.
    department = models.ForeignKey(
        "core.Department", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="staff",
    )

    # Citizens (and officers) are tied to the area they operate in.
    area = models.ForeignKey(
        "core.Area", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="residents",
    )

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"