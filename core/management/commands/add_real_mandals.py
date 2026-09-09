"""
core/management/commands/add_real_mandals.py

Replaces the auto-generated single mandal under specific districts with
REAL mandal names (sourced from Wikipedia + official AP government district
sites). Only covers districts where the source data was clean and reliable
-- Bapatla, Prakasam, Chittoor, Guntur. Other districts keep their existing
auto-generated mandal untouched.

Each real mandal gets 1 village + a fixed number of wards (default 5) with
one asset of every type, same as the rest of the system.

Safe to re-run -- uses get_or_create throughout.

Usage:
    python manage.py add_real_mandals
    python manage.py add_real_mandals --wards 3
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Area
from assets.models import Asset, AssetType

REAL_MANDALS = {
    "Bapatla": [
        "Bapatla", "Bhattiprolu", "Cherukupalle", "Chirala", "Karlapalem",
                "Kollur", "Martur", "Nizampatnam", "Parchur", "Pittalavanipalem", "Repalle", "Santhamaguluru", "Tsunduru", "Vemuru", "Vetapalem", "Yeddanapudi",
    ],
    "Prakasam": [
        "Addanki", "Ballikurava", "Chimakurthy", "Kandukur", "Kondapi",
        "Lingasamudram", "Maddipadu", "Naguluppalapadu", "Ongole Rural",
        "Ongole Urban", "Singarayakonda",
    ],
    "Chittoor": [
        "Palasamudram", "Karvetinagar", "Nagari", "Nindra", "Vijayapuram",
        "Chittoor Urban", "Chittoor Rural", "Gudipala", "Yadamarri",
        "Gangadharanellore", "Puthalapattu", "Penumuru", "Thavanampalle",
    ],
    "Guntur": [
        "Amaravathi", "Chebrolu", "Duggirala", "Guntur East", "Guntur West",
        "Kollipara", "Mangalagiri", "Medikonduru", "Narasaraopet",
        "Pedakakani", "Pedanandipadu", "Ponnur", "Prathipadu", "Tadikonda",
        "Tenali", "Thullur",
    ],
}


class Command(BaseCommand):
    help = "Add real mandal names (with village/wards/assets) for Bapatla, Prakasam, Chittoor, Guntur."

    def add_arguments(self, parser):
        parser.add_argument("--wards", type=int, default=5, help="Wards per mandal (default 5)")

    @transaction.atomic
    def handle(self, *args, **options):
        n_wards = options["wards"]
        asset_types = list(AssetType.objects.all())
        if not asset_types:
            self.stdout.write(self.style.ERROR("No AssetTypes found -- run seed_demo first."))
            return

        made_mandals = made_villages = made_wards = made_assets = 0

        for district_name, mandal_names in REAL_MANDALS.items():
            try:
                district = Area.objects.get(name=district_name, level=Area.Level.DISTRICT)
            except Area.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"District '{district_name}' not found -- skipping."))
                continue

            for mandal_name in mandal_names:
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

                    existing_type_ids = set(
                        Asset.objects.filter(area=ward).values_list("asset_type_id", flat=True)
                    )
                    for asset_type in asset_types:
                        if asset_type.id in existing_type_ids:
                            continue
                        Asset.objects.create(
                            asset_type=asset_type, area=ward, department=asset_type.default_department,
                        )
                        made_assets += 1

            self.stdout.write(f"  {district_name}: {len(mandal_names)} mandals done")

        self.stdout.write(self.style.SUCCESS(
            f"\nCreated {made_mandals} mandals, {made_villages} villages, "
            f"{made_wards} wards, {made_assets} assets."
        ))