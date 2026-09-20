"""
core/management/commands/fill_empty_mandals.py

expand_areas.py and fill_all_assets.py both check "does this DISTRICT
already have a mandal?" and skip the whole district if so. That worked
fine when a district had exactly one mandal. But add_all_real_mandals.py
added real-named mandals ALONGSIDE the old placeholder mandals in the
same district -- so the district-level check now skips over these new
real mandals too, leaving them with zero villages/wards/assets under
them (hence "No registered assets found in this area yet" for citizens).

This command fixes it at the correct level: it looks at every MANDAL
individually, and for any mandal that has zero Village children, builds
one Village -> a few Wards -> every asset type in each Ward. Mandals that
already have villages (old placeholder ones, or ones you've hand-built)
are left completely untouched.

Safe to re-run any time.

Usage:
    python manage.py fill_empty_mandals
    python manage.py fill_empty_mandals --wards 3 --villages 1
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Area
from assets.models import Asset, AssetType


class Command(BaseCommand):
    help = "Fill in a Village/Ward/Asset chain for any Mandal that has none yet."

    def add_arguments(self, parser):
        parser.add_argument("--villages", type=int, default=1, help="Villages to create per empty mandal (default 1)")
        parser.add_argument("--wards", type=int, default=2, help="Wards to create per new village (default 2)")

    @transaction.atomic
    def handle(self, *args, **options):
        n_villages = options["villages"]
        n_wards = options["wards"]

        asset_types = list(AssetType.objects.all())
        if not asset_types:
            self.stdout.write(self.style.ERROR("No AssetTypes found -- run seed_demo first."))
            return

        made_villages = made_wards = made_assets = 0
        mandals_filled = 0

        empty_mandals = [
            m for m in Area.objects.filter(level=Area.Level.MANDAL)
            if not Area.objects.filter(parent=m, level=Area.Level.VILLAGE).exists()
        ]

        for mandal in empty_mandals:
            for v in range(1, n_villages + 1):
                village_name = mandal.name if n_villages == 1 else f"{mandal.name} Village {v}"
                village, created = Area.objects.get_or_create(
                    name=village_name, level=Area.Level.VILLAGE, parent=mandal
                )
                made_villages += created

                for w in range(1, n_wards + 1):
                    ward, created = Area.objects.get_or_create(
                        name=f"Ward {w}", level=Area.Level.WARD, parent=village
                    )
                    made_wards += created

                    existing_type_ids = set(
                        Asset.objects.filter(area=ward).values_list("asset_type_id", flat=True)
                    )
                    for asset_type in asset_types:
                        if asset_type.id in existing_type_ids:
                            continue
                        Asset.objects.create(
                            asset_type=asset_type,
                            area=ward,
                            department=asset_type.default_department,
                        )
                        made_assets += 1

            mandals_filled += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nFilled {mandals_filled} previously-empty mandals.\n"
            f"Created {made_villages} villages, {made_wards} wards, {made_assets} assets."
        ))