"""
python manage.py seed_demo

Creates a minimal but complete demo dataset so the citizen app has
something real to pick from: an Area hierarchy (District > Mandal >
Village > Ward), Departments (Electricity, Water Supply, Roads,
Drainage/Sanitation), AssetTypes for each, and a handful of Assets
registered in the ward — so you can immediately walk through the
"report an issue" flow end to end.

Safe to re-run — uses get_or_create throughout.
"""

from django.core.management.base import BaseCommand

from core.models import Area, Department
from assets.models import AssetType, Asset


class Command(BaseCommand):
    help = "Seed demo Areas, Departments, AssetTypes, and Assets for CivicConnect."

    def handle(self, *args, **options):
        # --- Area hierarchy: one path down to a ward ---
        district, _ = Area.objects.get_or_create(name="Prakasam", level=Area.Level.DISTRICT, parent=None)
        mandal, _ = Area.objects.get_or_create(name="Ongole", level=Area.Level.MANDAL, parent=district)
        village, _ = Area.objects.get_or_create(name="Naynapalli", level=Area.Level.VILLAGE, parent=mandal)
        ward, _ = Area.objects.get_or_create(name="Ward 5", level=Area.Level.WARD, parent=village)

        # A second ward so the picker has more than one leaf to choose from
        ward2, _ = Area.objects.get_or_create(name="Ward 7", level=Area.Level.WARD, parent=village)

        # --- Departments (matches: electricity, water, roads, drainage) ---
        dept_names = ["Electricity", "Water Supply", "Roads", "Drainage", "Sanitation"]
        depts = {}
        for name in dept_names:
            dept, _ = Department.objects.get_or_create(name=name)
            depts[name] = dept

        # --- Asset types, each defaulting to the right department ---
        asset_type_defs = [
            ("Street Light", "SL", "Electricity"),
            ("Transformer", "TR", "Electricity"),
            ("Water Pump", "WP", "Water Supply"),
            ("Water Tank", "WT", "Water Supply"),
            ("Road", "RD", "Roads"),
            ("Drainage Line", "DL", "Drainage"),
            ("Garbage Bin", "GB", "Sanitation"),
        ]
        asset_types = {}
        for name, prefix, dept_name in asset_type_defs:
            at, _ = AssetType.objects.get_or_create(
                name=name, defaults={"id_prefix": prefix, "default_department": depts[dept_name]}
            )
            asset_types[name] = at

        # --- A handful of assets citizens can actually report against ---
        asset_defs = [
            ("Street Light", ward, "Electricity"),
            ("Transformer", ward, "Electricity"),
            ("Water Pump", ward, "Water Supply"),
            ("Road", ward, "Roads"),
            ("Drainage Line", ward, "Drainage"),
            ("Street Light", ward2, "Electricity"),
            ("Water Pump", ward2, "Water Supply"),
            ("Road", ward2, "Roads"),
        ]
        created = 0
        for type_name, area, dept_name in asset_defs:
            at = asset_types[type_name]
            # avoid creating duplicates on re-run: check by type+area combo
            exists = Asset.objects.filter(asset_type=at, area=area).exists()
            if not exists:
                Asset.objects.create(asset_type=at, area=area, department=depts[dept_name])
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete. Areas: District > Mandal > Village > (Ward 5, Ward 7). "
            f"Departments: {', '.join(dept_names)}. Asset types: {len(asset_types)}. "
            f"Assets created this run: {created} (total now: {Asset.objects.count()})."
        ))
