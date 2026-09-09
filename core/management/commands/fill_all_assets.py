"""
core/management/commands/fill_all_assets.py

Two jobs, both safe to re-run any time:

1. For every District that has NO mandal at all yet, create one default
   Mandal -> Village -> Ward chain (districts that already have a mandal,
   e.g. hand-built ones like Prakasam/Ongole or Bapatla, are left alone --
   nothing gets duplicated).

2. For every Ward that exists anywhere in the system, make sure it has at
   least one Asset of EVERY AssetType (Street Light, Water Pump, Transformer,
   Road, Drainage Line, etc.) -- only the missing ones are created, existing
   assets are never touched or duplicated.

Usage:
    python manage.py fill_all_assets
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Area
from assets.models import Asset, AssetType


class Command(BaseCommand):
    help = "Ensure every district has an area chain and every ward has one asset of every type."

    @transaction.atomic
    def handle(self, *args, **options):
        asset_types = list(AssetType.objects.all())
        if not asset_types:
            self.stdout.write(self.style.ERROR("No AssetTypes found -- run seed_demo first."))
            return

        # --- Part 1: make sure every district has at least one full chain ---
        made_mandals = made_villages = made_wards = 0

        for district in Area.objects.filter(level=Area.Level.DISTRICT):
            if Area.objects.filter(parent=district, level=Area.Level.MANDAL).exists():
                continue  # already has a mandal (hand-built or from an earlier run) -- leave it alone

            mandal, created = Area.objects.get_or_create(
                name=district.name, level=Area.Level.MANDAL, parent=district
            )
            made_mandals += created

            village, created = Area.objects.get_or_create(
                name=f"{district.name} Town", level=Area.Level.VILLAGE, parent=mandal
            )
            made_villages += created

            for w in (1, 2):
                _, created = Area.objects.get_or_create(
                    name=f"Ward {w}", level=Area.Level.WARD, parent=village
                )
                made_wards += created

        # --- Part 2: every ward gets one asset of every type, gaps only ---
        made_assets = 0
        for ward in Area.objects.filter(level=Area.Level.WARD):
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

        self.stdout.write(self.style.SUCCESS(
            f"Areas created: {made_mandals} mandals, {made_villages} villages, {made_wards} wards.\n"
            f"Assets created (gap-filled only): {made_assets}."
        ))