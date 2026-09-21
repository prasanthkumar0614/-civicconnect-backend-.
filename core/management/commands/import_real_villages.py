"""
core/management/commands/import_real_villages.py

Imports real Andhra Pradesh village names from the official LGD (Local
Government Directory, Ministry of Panchayati Raj, Government of India)
dataset, compiled as a CSV by github.com/mchittineni/india-village-finder
(data licensed under GODL-India; attribution: LGD, Ministry of Panchayati
Raj, Government of India).

Expected CSV columns (no header row in the source file):
    State, District, DistrictLGDCode, Mandal, MandalLGDCode,
    VillageNameEnglish, VillageNameTelugu, SourceType,
    VillageLGDCode, Pincode, (unused), (unused)

Place the CSV at: core/data/andhra_pradesh_villages.csv

DESIGN DECISION: this command is ADDITIVE ONLY -- it never deletes or
modifies existing Areas, Assets, or Issues. Some mandal names in this
official file differ slightly in spelling from the Wikipedia-sourced
names already loaded (e.g. "Chinthapalli" vs "Chintapalle" for the same
place) -- rather than risk deleting real data trying to reconcile that,
non-matching mandals are created fresh. This can result in a small
number of near-duplicate mandal entries; that's a deliberate, disclosed
tradeoff in exchange for zero risk to existing complaints/assets.

District name normalization handles known variants (e.g. "Y.S.R. Kadapa"
in this file vs "YSR Kadapa" in your database).

Uses bulk_create throughout -- with ~16,000+ villages, a naive one-by-one
loop would risk the same deploy timeout we hit with fill_empty_mandals.

Usage:
    python manage.py import_real_villages
    python manage.py import_real_villages --csv path/to/file.csv
"""

import csv
import os
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Area

DEFAULT_CSV_PATH = os.path.join("core", "data", "andhra_pradesh_villages.csv")


def normalize(name):
    """Lowercase, strip periods and extra whitespace -- for robust district matching.
    Removes periods entirely (not replaced with a space) so 'Y.S.R.' normalizes to
    'ysr', matching a stored 'YSR' -- an earlier version of this function replaced
    periods with spaces, which incorrectly produced 'y s r' instead."""
    name = name.replace(".", "")
    name = re.sub(r"\s+", " ", name)
    return name.strip().lower()


class Command(BaseCommand):
    help = "Import real AP village names from the official LGD dataset CSV (additive only)."

    def add_arguments(self, parser):
        parser.add_argument("--csv", type=str, default=DEFAULT_CSV_PATH)

    def handle(self, *args, **options):
        csv_path = options["csv"]
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(
                f"CSV not found at {csv_path}. Download it from the india-village-finder "
                f"repo's latest release and place it there first."
            ))
            return

        districts = list(Area.objects.filter(level=Area.Level.DISTRICT))
        district_by_norm = {normalize(d.name): d for d in districts}

        rows_by_mandal = {}
        unmatched_districts = set()

        with open(csv_path, encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)

    # Skip the CSV header
    header = next(reader, None)

    for row in reader:
        if len(row) < 6:
            continue

        _, district_name, _, mandal_name, _, village_name = row[:6]

        district_name = district_name.strip()
        mandal_name = mandal_name.strip()
        village_name = village_name.strip()

        if not district_name or not mandal_name or not village_name:
            continue

                district = district_by_norm.get(normalize(district_name))
                if not district:
                    unmatched_districts.add(district_name)
                    continue

                key = (district.id, mandal_name.strip())
                rows_by_mandal.setdefault(key, []).append(village_name.strip())

        self.stdout.write(f"Parsed CSV. Found {len(rows_by_mandal)} distinct (district, mandal) groups.")
        if unmatched_districts:
            self.stdout.write(self.style.WARNING(
                f"Skipped rows for unmatched districts: {', '.join(sorted(unmatched_districts))}"
            ))

        mandal_cache = {}
        district_ids = list({d_id for d_id, _ in rows_by_mandal})
        existing_mandals = Area.objects.filter(
            level=Area.Level.MANDAL, parent_id__in=district_ids
        )
        for m in existing_mandals:
            mandal_cache[(m.parent_id, normalize(m.name))] = m

        new_mandals = []
        for (district_id, mandal_name) in rows_by_mandal:
            cache_key = (district_id, normalize(mandal_name))
            if cache_key not in mandal_cache:
                new_mandal = Area(name=mandal_name, level=Area.Level.MANDAL, parent_id=district_id)
                new_mandals.append(new_mandal)
                mandal_cache[cache_key] = new_mandal

        if new_mandals:
            with transaction.atomic():
                Area.objects.bulk_create(new_mandals, batch_size=500, ignore_conflicts=True)
            existing_mandals = Area.objects.filter(level=Area.Level.MANDAL, parent_id__in=district_ids)
            for m in existing_mandals:
                mandal_cache[(m.parent_id, normalize(m.name))] = m

        self.stdout.write(f"Mandals ready: {len(new_mandals)} newly created, {len(mandal_cache) - len(new_mandals)} matched existing.")

        existing_village_keys = set(
            Area.objects.filter(level=Area.Level.VILLAGE).values_list("parent_id", "name")
        )

        village_objs = []
        for (district_id, mandal_name), village_names in rows_by_mandal.items():
            mandal = mandal_cache.get((district_id, normalize(mandal_name)))
            if not mandal or not mandal.id:
                continue
            for village_name in village_names:
                if (mandal.id, village_name) in existing_village_keys:
                    continue
                village_objs.append(Area(name=village_name, level=Area.Level.VILLAGE, parent_id=mandal.id))

        with transaction.atomic():
            Area.objects.bulk_create(village_objs, batch_size=1000, ignore_conflicts=True)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Created {len(village_objs)} real villages "
            f"across {len(mandal_cache)} mandals.\n"
            f"Data source: LGD, Ministry of Panchayati Raj, Government of India "
            f"(via india-village-finder, GODL-India license)."
        ))
      
