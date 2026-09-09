"""
core/management/commands/find_duplicate_areas.py

Lists any Area records that share the same name + level + parent -- these are
true duplicates (most likely created by typing the same district/mandal name
twice, which the database doesn't always catch when the parent is empty).

Usage:
    python manage.py find_duplicate_areas
"""

from django.core.management.base import BaseCommand
from django.db.models import Count

from core.models import Area


class Command(BaseCommand):
    help = "List duplicate Area records (same name + level + parent)."

    def handle(self, *args, **options):
        dupes = (
            Area.objects.values("name", "level", "parent_id")
            .annotate(n=Count("id"))
            .filter(n__gt=1)
        )

        if not dupes:
            self.stdout.write(self.style.SUCCESS("No duplicates found."))
            return

        self.stdout.write(self.style.WARNING(f"Found {len(dupes)} duplicate name/level/parent group(s):\n"))

        for d in dupes:
            matches = Area.objects.filter(
                name=d["name"], level=d["level"], parent_id=d["parent_id"]
            ).order_by("id")

            parent_label = matches.first().parent.name if matches.first().parent else "(top level)"
            self.stdout.write(f"  '{d['name']}' ({d['level']}) under {parent_label}:")

            for a in matches:
                n_children = Area.objects.filter(parent=a).count()
                n_assets = a.assets.count() if hasattr(a, "assets") else 0
                self.stdout.write(f"    id={a.id}  children={n_children}  direct_assets={n_assets}")
            self.stdout.write("")

        self.stdout.write(self.style.WARNING(
            "For each group above, keep the id with more children/assets (the original) "
            "and remove the other in Django admin -- delete its assets first, then its "
            "wards/villages/mandals bottom-up, then the duplicate area itself."
        ))