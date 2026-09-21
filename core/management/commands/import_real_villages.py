"""
Import real Andhra Pradesh villages from the LGD CSV.

CSV location:
    core/data/andhra_pradesh_villages.csv

LGD attribution:
    Local Government Directory (LGD)
    Ministry of Panchayati Raj
    Government of India
    Used under GODL-India.
"""

import csv
import os
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Area


DEFAULT_CSV_PATH = os.path.join(
    "core",
    "data",
    "andhra_pradesh_villages.csv",
)


def normalize(name):
    """Normalize names for matching."""
    name = str(name or "").replace(".", "")
    name = re.sub(r"\s+", " ", name)
    return name.strip().lower()


class Command(BaseCommand):
    help = "Import real Andhra Pradesh villages from the LGD CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            default=DEFAULT_CSV_PATH,
        )

    def handle(self, *args, **options):
        csv_path = options["csv"]

        if not os.path.exists(csv_path):
            self.stdout.write(
                self.style.ERROR(
                    f"CSV not found: {csv_path}"
                )
            )
            return

        # ---------------------------------------------------------
        # Load existing districts
        # ---------------------------------------------------------
        districts = list(
            Area.objects.filter(
                level=Area.Level.DISTRICT
            )
        )

        district_by_norm = {
            normalize(d.name): d
            for d in districts
        }

        rows_by_mandal = {}
        unmatched_districts = set()
        total_rows = 0

        # ---------------------------------------------------------
        # Read CSV
        # ---------------------------------------------------------
        with open(
            csv_path,
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:

            reader = csv.reader(f)

            # Your CSV has a header row.
            header = next(reader, None)

            self.stdout.write(
                f"CSV header detected: {header}"
            )

            for row in reader:
                total_rows += 1

                if len(row) < 6:
                    continue

                # Columns:
                # 0 State
                # 1 District
                # 2 District Code
                # 3 Mandal
                # 4 Mandal Code
                # 5 Village
                district_name = row[1].strip()
                mandal_name = row[3].strip()
                village_name = row[5].strip()

                if (
                    not district_name
                    or not mandal_name
                    or not village_name
                ):
                    continue

                district = district_by_norm.get(
                    normalize(district_name)
                )

                if not district:
                    unmatched_districts.add(
                        district_name
                    )
                    continue

                key = (
                    district.id,
                    normalize(mandal_name),
                )

                if key not in rows_by_mandal:
                    rows_by_mandal[key] = {
                        "district": district,
                        "mandal_name": mandal_name,
                        "villages": [],
                    }

                rows_by_mandal[key]["villages"].append(
                    village_name
                )

        self.stdout.write(
            f"Parsed {total_rows} CSV rows."
        )

        self.stdout.write(
            f"Found {len(rows_by_mandal)} "
            f"district/mandal groups."
        )

        if unmatched_districts:
            self.stdout.write(
                self.style.WARNING(
                    "Unmatched districts: "
                    + ", ".join(
                        sorted(unmatched_districts)
                    )
                )
            )

        # ---------------------------------------------------------
        # Load existing mandals
        # ---------------------------------------------------------
        district_ids = [
            district.id
            for district in districts
        ]

        mandal_cache = {}

        existing_mandals = Area.objects.filter(
            level=Area.Level.MANDAL,
            parent_id__in=district_ids,
        )

        for mandal in existing_mandals:
            mandal_cache[
                (
                    mandal.parent_id,
                    normalize(mandal.name),
                )
            ] = mandal

        # ---------------------------------------------------------
        # Create missing mandals
        # ---------------------------------------------------------
        new_mandals = []

        for key, data in rows_by_mandal.items():

            if key not in mandal_cache:
                new_mandal = Area(
                    name=data["mandal_name"],
                    level=Area.Level.MANDAL,
                    parent_id=data["district"].id,
                )

                new_mandals.append(new_mandal)
                mandal_cache[key] = new_mandal

        if new_mandals:
            with transaction.atomic():
                Area.objects.bulk_create(
                    new_mandals,
                    batch_size=500,
                )

            # Refresh cache because bulk-created objects
            # now have database IDs.
            existing_mandals = Area.objects.filter(
                level=Area.Level.MANDAL,
                parent_id__in=district_ids,
            )

            mandal_cache = {
                (
                    m.parent_id,
                    normalize(m.name),
                ): m
                for m in existing_mandals
            }

        self.stdout.write(
            f"Mandals ready: "
            f"{len(mandal_cache)}"
        )

        # ---------------------------------------------------------
        # Load existing villages
        # ---------------------------------------------------------
        existing_village_keys = set(
            Area.objects.filter(
                level=Area.Level.VILLAGE
            ).values_list(
                "parent_id",
                "name",
            )
        )

        # ---------------------------------------------------------
        # Prepare villages
        # ---------------------------------------------------------
        village_objects = []

        for key, data in rows_by_mandal.items():

            mandal = mandal_cache.get(key)

            if not mandal or not mandal.id:
                continue

            for village_name in data["villages"]:

                village_key = (
                    mandal.id,
                    village_name,
                )

                if village_key in existing_village_keys:
                    continue

                village_objects.append(
                    Area(
                        name=village_name,
                        level=Area.Level.VILLAGE,
                        parent_id=mandal.id,
                    )
                )

                existing_village_keys.add(
                    village_key
                )

        # ---------------------------------------------------------
        # Insert villages
        # ---------------------------------------------------------
        created_count = 0

        if village_objects:
            with transaction.atomic():
                Area.objects.bulk_create(
                    village_objects,
                    batch_size=1000,
                    ignore_conflicts=True,
                )

            created_count = len(village_objects)

        # ---------------------------------------------------------
        # Final result
        # ---------------------------------------------------------
        self.stdout.write(
            self.style.SUCCESS(
                "\n========================================\n"
                "REAL VILLAGE IMPORT COMPLETE\n"
                "========================================\n"
                f"CSV rows read: {total_rows}\n"
                f"District/mandal groups: {len(rows_by_mandal)}\n"
                f"Mandals available: {len(mandal_cache)}\n"
                f"Real villages created: {created_count}\n"
                "========================================\n"
                "Data source: Local Government Directory "
                "(LGD), Ministry of Panchayati Raj, "
                "Government of India.\n"
                "Used under GODL-India.\n"
                "========================================"
            )
        )
