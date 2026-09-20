"""
core/management/commands/fill_empty_mandals.py

Fills a Village -> Ward -> Asset chain for any Mandal that has none yet.
Uses bulk_create and a single efficient query (not one-by-one checks) so
it runs in seconds instead of minutes, even across ~700 mandals.

IMPORTANT: run this from Build Command only, NOT Start Command. The build
phase has no port-binding deadline; the start/deploy phase does.

Usage:
    python manage.py fill_empty_mandals
    python manage.py fill_empty_mandals --wards 3 --villages 1
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Area
from assets.models import Asset, AssetType


class Command(BaseCommand):
    help = "Fill in a Village/Ward/Asset chain for any Mandal that has none yet (bulk, fast)."

    def add_arguments(self, parser):
        parser.add_argument("--villages", type=int, default=1)
        parser.add_argument("--wards", type=int, default=2)

    def handle(self, *args, **options):
        n_villages = options["villages"]
        n_wards = options["wards"]

        asset_types = list(AssetType.objects.all())
        if not asset_types:
            self.stdout.write(self.style.ERROR("No AssetTypes found -- run seed_demo first."))
            return

        # Single query instead of checking each mandal one at a time.
        mandals_with_villages = Area.objects.filter(
            level=Area.Level.VILLAGE
        ).values_list("parent_id", flat=True)

        empty_mandals = list(
            Area.objects.filter(level=Area.Level.MANDAL).exclude(id__in=mandals_with_villages)
        )
        self.stdout.write(f"Found {len(empty_mandals)} empty mandals. Building villages...")

        # --- Step 1: bulk-create all villages at once ---
        village_objs = []
        for mandal in empty_mandals:
            for v in range(1, n_villages + 1):
                name = mandal.name if n_villages == 1 else f"{mandal.name} Village {v}"
                village_objs.append(Area(name=name, level=Area.Level.VILLAGE, parent=mandal))

        with transaction.atomic():
            Area.objects.bulk_create(village_objs, batch_size=500, ignore_conflicts=True)
        self.stdout.write(f"Created {len(village_objs)} villages. Building wards...")

        villages = Area.objects.filter(
            level=Area.Level.VILLAGE, parent__in=[m.id for m in empty_mandals]
        )

        # --- Step 2: bulk-create all wards at once ---
        ward_objs = []
        for village in villages:
            for w in range(1, n_wards + 1):
                ward_objs.append(Area(name=f"Ward {w}", level=Area.Level.WARD, parent=village))

        with transaction.atomic():
            Area.objects.bulk_create(ward_objs, batch_size=500, ignore_conflicts=True)
        self.stdout.write(f"Created {len(ward_objs)} wards. Building assets...")

        wards = Area.objects.filter(level=Area.Level.WARD, parent__in=villages)

        # --- Step 3: bulk-create all assets at once ---
        asset_objs = []
        for ward in wards:
            for asset_type in asset_types:
                asset_objs.append(Asset(
                    asset_type=asset_type, area=ward, department=asset_type.default_department,
                ))

        with transaction.atomic():
            Asset.objects.bulk_create(asset_objs, batch_size=1000, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(
            f"\nFilled {len(empty_mandals)} previously-empty mandals.\n"
            f"Created {len(village_objs)} villages, {len(ward_objs)} wards, "
            f"{len(asset_objs)} assets."
        ))