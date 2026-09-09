"""
core/management/commands/expand_areas.py

Auto-fills a Mandal -> Village -> Ward chain (plus a couple of sample assets
per ward) under every District that doesn't already have one. Safe to run
more than once -- it only adds children to districts that have none yet, so
it won't duplicate anything you've already built by hand.

Usage:
    python manage.py expand_areas
    python manage.py expand_areas --mandals 2 --wards 3 --assets 2
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Area, Department
from assets.models import Asset, AssetType


class Command(BaseCommand):
    help = "Auto-generate Mandal/Village/Ward areas (+ sample assets) under every District that has none yet."

    def add_arguments(self, parser):
        parser.add_argument("--mandals", type=int, default=1, help="Mandals to create per district (default 1)")
        parser.add_argument("--wards", type=int, default=2, help="Wards to create per village (default 2)")
        parser.add_argument("--assets", type=int, default=2, help="Assets to create per ward (default 2)")

    @transaction.atomic
    def handle(self, *args, **options):
        n_mandals = options["mandals"]
        n_wards = options["wards"]
        n_assets = options["assets"]

        asset_types = list(AssetType.objects.all())
        if not asset_types:
            self.stdout.write(self.style.ERROR(
                "No AssetTypes found -- run seed_demo first so Street Light/Water Pump/etc. exist."
            ))
            return

        districts = Area.objects.filter(level=Area.Level.DISTRICT)
        if not districts.exists():
            self.stdout.write(self.style.ERROR("No districts found. Add districts first, then re-run this."))
            return

        made_mandals = made_villages = made_wards = made_assets = 0

        for district in districts:
            # Skip districts that already have mandals under them -- don't touch what you built by hand.
            if Area.objects.filter(parent=district, level=Area.Level.MANDAL).exists():
                continue

            for m in range(1, n_mandals + 1):
                mandal_name = district.name if n_mandals == 1 else f"{district.name} Mandal {m}"
                mandal, created = Area.objects.get_or_create(
                    name=mandal_name, level=Area.Level.MANDAL, parent=district
                )
                made_mandals += created

                village, created = Area.objects.get_or_create(
                    name=f"{mandal_name} Town", level=Area.Level.VILLAGE, parent=mandal
                )
                made_villages += created

                for w in range(1, n_wards + 1):
                    ward, created = Area.objects.get_or_create(
                        name=f"Ward {w}", level=Area.Level.WARD, parent=village
                    )
                    made_wards += created

                    for a in range(n_assets):
                        asset_type = asset_types[(w + a) % len(asset_types)]
                        exists = Asset.objects.filter(asset_type=asset_type, area=ward).exists()
                        if exists:
                            continue
                        Asset.objects.create(
                            asset_type=asset_type,
                            area=ward,
                            department=asset_type.default_department,
                        )
                        made_assets += 1

            self.stdout.write(f"  {district.name}: done")

        self.stdout.write(self.style.SUCCESS(
            f"\nCreated {made_mandals} mandals, {made_villages} villages, "
            f"{made_wards} wards, {made_assets} assets."
        ))