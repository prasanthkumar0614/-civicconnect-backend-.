from django.db import models

from core.models import Area, Department


class AssetType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    id_prefix = models.CharField(max_length=5, unique=True)
    default_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        related_name="asset_types",
    )

    def __str__(self):
        return self.name


class Asset(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        FAULTY = "FAULTY", "Faulty"
        UNDER_MAINTENANCE = "MAINTENANCE", "Under maintenance"
        DECOMMISSIONED = "DECOMMISSIONED", "Decommissioned"

    asset_id = models.CharField(max_length=20, unique=True)
    asset_type = models.ForeignKey(
        AssetType,
        on_delete=models.PROTECT,
        related_name="assets",
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.PROTECT,
        related_name="assets",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        related_name="assets",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    installed_on = models.DateField(null=True, blank=True)
    last_maintained_on = models.DateField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.asset_id:
            last_asset = (
                Asset.objects
                .filter(asset_type=self.asset_type)
                .exclude(asset_id__isnull=True)
                .order_by("-id")
                .first()
            )

            if last_asset and last_asset.asset_id:
                try:
                    last_number = int(
                        last_asset.asset_id.rsplit("-", 1)[1]
                    )
                except (ValueError, IndexError):
                    last_number = 0
            else:
                last_number = 0

            self.asset_id = (
                f"{self.asset_type.id_prefix}-{last_number + 1:03d}"
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.asset_id
