"""
assets/management/commands/check_asset_clusters.py

Run periodically (cron, or Celery beat in production — see note below) to
detect newly-formed asset clusters and notify department admins once per
cluster. This is intentionally NOT triggered from the map GET endpoint
(assets/map_api.py) — firing an email every time someone loads the map
would spam admins on every page view rather than on a real new event.

Deduplication: a cluster is identified by the sorted set of asset IDs in
it. We keep a simple DB-backed record of clusters we've already notified
about (NotifiedCluster model below) so re-running this command doesn't
re-send the same alert every time it's scheduled.

Usage:
    python manage.py check_asset_clusters

Production scheduling (cron example, every 15 minutes):
    */15 * * * * cd /path/to/project && python manage.py check_asset_clusters
"""

from django.core.management.base import BaseCommand
from django.db import models

from core.models import Department
from assets.models import Asset
from assets.clustering import find_asset_clusters
from services.notification_service import notify_cluster_detected


class NotifiedCluster(models.Model):
    """
    Lightweight dedup record — add this model to assets/models.py and
    migrate before using this command. Kept here inline for visibility
    since it only exists to support this one command.
    """
    asset_ids_key = models.CharField(max_length=255, unique=True)  # sorted, comma-joined asset IDs
    notified_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "assets"


class Command(BaseCommand):
    help = "Detect newly-formed asset clusters (nearby faulty assets) and notify department admins."

    def handle(self, *args, **options):
        faulty_qs = (
            Asset.objects.filter(issues__status="OPEN")
            .exclude(latitude__isnull=True)
            .exclude(longitude__isnull=True)
            .distinct()
            .select_related("asset_type", "department")
        )

        clusters = find_asset_clusters(list(faulty_qs))
        new_count = 0

        for group in clusters:
            key = ",".join(sorted(a.asset_id for a in group))
            if NotifiedCluster.objects.filter(asset_ids_key=key).exists():
                continue  # already alerted on this exact cluster

            # Group by department, since a cluster could span two departments'
            # assets in rare cases (e.g. a street light + a traffic signal).
            by_department = {}
            for asset in group:
                by_department.setdefault(asset.department_id, []).append(asset)

            for dept_id, assets_in_dept in by_department.items():
                department = Department.objects.filter(id=dept_id).first()
                notify_cluster_detected(department, assets_in_dept)

            NotifiedCluster.objects.create(asset_ids_key=key)
            new_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Checked clusters: {len(clusters)} found, {new_count} newly notified.")
        )
