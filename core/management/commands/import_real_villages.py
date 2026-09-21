import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Area


CSV_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "andhra_pradesh_villages.csv"
)


def normalize(value):
    value = str(value or "").strip().casefold()
    return re.sub(r"[^a-z0-9]+", "", value)


class Command(BaseCommand):
    help = "Import all real Andhra Pradesh villages from the LGD CSV."

    def handle(self, *args, **options):

        if not CSV_PATH.exists():
            raise FileNotFoundError(
                f"CSV not found: {CSV_PATH}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Reading: {CSV_PATH}"
            )
        )

        # ---------------------------------------------------------
        # DISTRICTS
        # ---------------------------------------------------------
        districts = {}

        for district in Area.objects.filter(
            level=Area.Level.DISTRICT
        ):
            districts[normalize(district.name)] = district

        self.stdout.write(
            f"Districts in database: {len(districts)}"
        )

        # ---------------------------------------------------------
        # MANDALS
        # ---------------------------------------------------------
        mandals = {}

        for mandal in Area.objects.filter(
            level=Area.Level.MANDAL
        ):
            if mandal.parent_id:
                mandals[
                    (
                        mandal.parent_id,
                        normalize(mandal.name),
                    )
                ] = mandal

        self.stdout.write(
            f"Mandals in database: {len(mandals)}"
        )

        # ---------------------------------------------------------
        # READ CSV
        # ---------------------------------------------------------
        rows = []

        with CSV_PATH.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:

            reader = csv.DictReader(f)

            self.stdout.write(
                f"CSV columns: {reader.fieldnames}"
            )

            for row in reader:

                district_name = (
                    row.get("District") or ""
                ).strip()

                mandal_name = (
                    row.get("Mandal") or ""
                ).strip()

                village_name = (
                    row.get("Village") or ""
                ).strip()

                if not district_name:
                    continue

                if not mandal_name:
                    continue

                if not village_name:
                    continue

                rows.append(
                    (
                        district_name,
                        mandal_name,
                        village_name,
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"CSV rows read: {len(rows)}"
            )
        )

        # ---------------------------------------------------------
        # PREPARE VILLAGES
        # ---------------------------------------------------------
        village_objects = []
        village_keys = set()

        unmatched_districts = set()
        missing_mandals = set()

        for district_name, mandal_name, village_name in rows:

            district = districts.get(
                normalize(district_name)
            )

            if not district:
                unmatched_districts.add(
                    district_name
                )
                continue

            mandal_key = (
                district.id,
                normalize(mandal_name),
            )

            mandal = mandals.get(mandal_key)

            if not mandal:

                mandal = Area.objects.create(
                    name=mandal_name,
                    level=Area.Level.MANDAL,
                    parent=district,
                )

                mandals[mandal_key] = mandal

                missing_mandals.add(
                    f"{district.name} > {mandal_name}"
                )

            village_key = (
                mandal.id,
                normalize(village_name),
            )

            # Prevent duplicate CSV rows.
            if village_key in village_keys:
                continue

            village_keys.add(village_key)

            village_objects.append(
                Area(
                    name=village_name,
                    level=Area.Level.VILLAGE,
                    parent=mandal,
                )
            )

        self.stdout.write(
            f"Village records prepared: {len(village_objects)}"
        )

        # ---------------------------------------------------------
        # FIND EXISTING VILLAGES
        # ---------------------------------------------------------
        existing_keys = set()

        village_parent_ids = {
            village.parent_id
            for village in village_objects
        }

        if village_parent_ids:

            existing_villages = Area.objects.filter(
                level=Area.Level.VILLAGE,
                parent_id__in=village_parent_ids,
            ).values_list(
                "parent_id",
                "name",
            )

            for parent_id, name in existing_villages:
                existing_keys.add(
                    (
                        parent_id,
                        normalize(name),
                    )
                )

        # ---------------------------------------------------------
        # REMOVE ALREADY EXISTING VILLAGES
        # ---------------------------------------------------------
        new_villages = [
            village
            for village in village_objects
            if (
                village.parent_id,
                normalize(village.name),
            ) not in existing_keys
        ]

        self.stdout.write(
            f"New villages to insert: {len(new_villages)}"
        )

        # ---------------------------------------------------------
        # BULK INSERT
        # ---------------------------------------------------------
        created_count = 0

        with transaction.atomic():

            batch_size = 1000

            for start in range(
                0,
                len(new_villages),
                batch_size,
            ):

                batch = new_villages[
                    start:start + batch_size
                ]

                Area.objects.bulk_create(
                    batch,
                    batch_size=batch_size,
                    ignore_conflicts=True,
                )

                created_count += len(batch)

                self.stdout.write(
                    f"Inserted {min(start + batch_size, len(new_villages))}"
                    f"/{len(new_villages)} villages"
                )

        # ---------------------------------------------------------
        # FINAL COUNTS
        # ---------------------------------------------------------
        total_villages = Area.objects.filter(
            level=Area.Level.VILLAGE
        ).count()

        total_mandals = Area.objects.filter(
            level=Area.Level.MANDAL
        ).count()

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(
            self.style.SUCCESS(
                "REAL VILLAGE IMPORT COMPLETE"
            )
        )
        self.stdout.write("=" * 60)

        self.stdout.write(
            f"CSV rows read:          {len(rows)}"
        )

        self.stdout.write(
            f"Village records prepared:{len(village_objects)}"
        )

        self.stdout.write(
            f"New villages inserted:  {created_count}"
        )

        self.stdout.write(
            f"Total mandals now:      {total_mandals}"
        )

        self.stdout.write(
            f"Total villages now:     {total_villages}"
        )

        if unmatched_districts:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "UNMATCHED DISTRICTS:"
                )
            )

            for name in sorted(unmatched_districts):
                self.stdout.write(
                    f"  - {name}"
                )

        if missing_mandals:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    f"Mandals created from CSV: "
                    f"{len(missing_mandals)}"
                )
            )

        self.stdout.write("")
        self.stdout.write(
            "Source: Local Government Directory (LGD), "
            "Ministry of Panchayati Raj, Government of India."
        )
        self.stdout.write(
            "Used under GODL-India."
        )
        self.stdout.write("=" * 60)
