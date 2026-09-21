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
    """
    Makes names comparable even when punctuation, dots,
    extra spaces, hyphens, etc. differ.

    Example:
        Dr. B. R. Ambedkar Konaseema
        Dr. B.R. Ambedkar Konaseema

    become the same key.
    """
    value = str(value or "").strip().casefold()
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


class Command(BaseCommand):
    help = "Import all real Andhra Pradesh villages/areas from the LGD CSV."

    @transaction.atomic
    def handle(self, *args, **options):

        if not CSV_PATH.exists():
            raise FileNotFoundError(
                f"CSV file not found: {CSV_PATH}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Reading CSV: {CSV_PATH}"
            )
        )

        # ---------------------------------------------------------
        # 1. LOAD ALL DISTRICTS
        # ---------------------------------------------------------
        districts = {}

        for district in Area.objects.filter(
            level=Area.Level.DISTRICT
        ):
            districts[normalize(district.name)] = district

        self.stdout.write(
            f"Database districts found: {len(districts)}"
        )

        # ---------------------------------------------------------
        # 2. LOAD ALL EXISTING MANDALS
        # ---------------------------------------------------------
        mandals = {}

        for mandal in Area.objects.filter(
            level=Area.Level.MANDAL
        ).select_related("parent"):

            if mandal.parent_id:
                key = (
                    mandal.parent_id,
                    normalize(mandal.name),
                )
                mandals[key] = mandal

        self.stdout.write(
            f"Database mandals found: {len(mandals)}"
        )

        # ---------------------------------------------------------
        # 3. READ CSV
        # ---------------------------------------------------------
        rows = []

        with CSV_PATH.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:

            reader = csv.DictReader(csv_file)

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
        # 4. IMPORT
        # ---------------------------------------------------------
        villages_created = 0
        villages_existing = 0
        mandals_created = 0

        unmatched_districts = set()
        unmatched_mandals = set()

        for district_name, mandal_name, village_name in rows:

            # -----------------------------------------------------
            # FIND DISTRICT
            # -----------------------------------------------------
            district = districts.get(
                normalize(district_name)
            )

            if not district:
                unmatched_districts.add(
                    district_name
                )
                continue

            # -----------------------------------------------------
            # FIND / CREATE MANDAL
            # -----------------------------------------------------
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
                mandals_created += 1

            # -----------------------------------------------------
            # FIND / CREATE VILLAGE
            # -----------------------------------------------------
            village, created = Area.objects.get_or_create(
                name=village_name,
                level=Area.Level.VILLAGE,
                parent=mandal,
            )

            if created:
                villages_created += 1
            else:
                villages_existing += 1

        # ---------------------------------------------------------
        # 5. FINAL REPORT
        # ---------------------------------------------------------
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
            f"New mandals created:    {mandals_created}"
        )

        self.stdout.write(
            f"New villages created:   {villages_created}"
        )

        self.stdout.write(
            f"Villages already exist: {villages_existing}"
        )

        self.stdout.write(
            f"Total villages now:     "
            f"{Area.objects.filter(level=Area.Level.VILLAGE).count()}"
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

        self.stdout.write("")
        self.stdout.write(
            "Data source: Local Government Directory (LGD), "
            "Ministry of Panchayati Raj, Government of India."
        )
        self.stdout.write(
            "Used under GODL-India."
        )
        self.stdout.write("=" * 60)
