from django.db import models

from core.models import Area, Department


class AssetType(models.Model):
    """Street Light, Transformer, Water Pump, Water Tank, Traffic Signal, Garbage Bin..."""

    name = models.CharField(max_length=100, unique=True)
    id_prefix = models.CharField(max_length=5, unique=True)  # SL, TR, WP, WT, TS, GB
    default_department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, related_name="asset_types"
    )

    def __str__(self):
        return self.name


class Asset(models.Model):
    """A single physical asset, e.g. SL-030 in Naynapalli."""

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        FAULTY = "FAULTY", "Faulty"
        UNDER_MAINTENANCE = "MAINTENANCE", "Under maintenance"
        DECOMMISSIONED = "DECOMMISSIONED", "Decommissioned"

    asset_id = models.CharField(max_length=20, unique=True)  # e.g. "SL-030"
    asset_type = models.ForeignKey(AssetType, on_delete=models.PROTECT, related_name="assets")
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="assets")
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, related_name="assets"
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    installed_on = models.DateField(null=True, blank=True)
    last_maintained_on = models.DateField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Auto-generate asset_id from prefix + running number if not supplied.
        if not self.asset_id:
            count = Asset.objects.filter(asset_type=self.asset_type).count() + 1
            self.asset_id = f"{self.asset_type.id_prefix}-{count:03d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.asset_id
