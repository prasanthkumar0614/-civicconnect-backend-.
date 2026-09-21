from django.core.management.base import BaseCommand
from django.db import transaction

from assets.models import Asset, AssetType
from core.models import Area


class Command(BaseCommand):
    help = (
        "Create 7 assets for every ward that does not already "
        "have the corresponding asset type."
    )

    BATCH_SIZE = 2000

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write("POPULATING ASSETS FOR ALL WARDS")
        self.stdout.write("=" * 70)

        # ---------------------------------------------------------
        # Get all asset types
        # ---------------------------------------------------------
        asset_types = list(
            AssetType.objects
            .select_related("default_department")
            .order_by("id")
        )

        if not asset_types:
            self.stdout.write(
                self.style.ERROR("No AssetType records found.")
            )
            return

        self.stdout.write(
            f"Asset types found: {len(asset_types)}"
        )

        for asset_type in asset_types:
            self.stdout.write(
                f"  {asset_type.id}: "
                f"{asset_type.name} "
                f"({asset_type.id_prefix})"
            )

        # ---------------------------------------------------------
        # Get all wards
        # ---------------------------------------------------------
        wards = list(
            Area.objects
            .filter(level=Area.Level.WARD)
            .only("id", "name", "parent_id")
            .order_by("id")
        )

        self.stdout.write(f"Wards found: {len(wards)}")

        if not wards:
            self.stdout.write(
                self.style.ERROR("No wards found.")
            )
            return

        # ---------------------------------------------------------
        # Existing ward + asset type combinations
        #
        # This prevents duplicates and makes the command
        # safe to run repeatedly.
        # ---------------------------------------------------------
        existing_pairs = set(
            Asset.objects.values_list("area_id", "asset_type_id")
        )

        self.stdout.write(
            f"Existing ward/asset combinations: "
            f"{len(existing_pairs)}"
        )

        # ---------------------------------------------------------
        # Find the highest existing number for each prefix.
        #
        # Example:
        # SL-001
        # SL-002
        # ...
        # SL-330
        #
        # New assets will continue from the highest number.
        # ---------------------------------------------------------
        next_number = {}

        existing_asset_ids = Asset.objects.values_list(
            "asset_id",
            flat=True,
        )

        for asset_id in existing_asset_ids:
            if not asset_id or "-" not in asset_id:
                continue

            prefix, number_text = asset_id.rsplit("-", 1)

            try:
                number = int(number_text)
            except ValueError:
                continue

            if number >= next_number.get(prefix, 0):
                next_number[prefix] = number

        # ---------------------------------------------------------
        # Prepare missing assets
        # ---------------------------------------------------------
        total_missing = 0
        created_total = 0

        batch = []

        for ward_index, ward in enumerate(wards, start=1):
            for asset_type in asset_types:
                pair = (ward.id, asset_type.id)

                if pair in existing_pairs:
                    continue

                prefix = asset_type.id_prefix

                next_number[prefix] = (
                    next_number.get(prefix, 0) + 1
                )

                asset_id = (
                    f"{prefix}-{next_number[prefix]:03d}"
                )

                department_id = (
                    asset_type.default_department_id
                )

                batch.append(
                    Asset(
                        asset_id=asset_id,
                        asset_type_id=asset_type.id,
                        area_id=ward.id,
                        department_id=department_id,
                        status=Asset.Status.ACTIVE,
                    )
                )

                total_missing += 1

                if len(batch) >= self.BATCH_SIZE:
                    with transaction.atomic():
                        Asset.objects.bulk_create(
                            batch,
                            batch_size=self.BATCH_SIZE,
                        )

                    created_total += len(batch)

                    self.stdout.write(
                        f"Created {created_total} "
                        f"/ {total_missing} assets..."
                    )

                    batch = []

        # ---------------------------------------------------------
        # Insert remaining records
        # ---------------------------------------------------------
        if batch:
            with transaction.atomic():
                Asset.objects.bulk_create(
                    batch,
                    batch_size=self.BATCH_SIZE,
                )

            created_total += len(batch)

        # ---------------------------------------------------------
        # Final counts
        # ---------------------------------------------------------
        total_assets = Asset.objects.count()
        total_wards = Area.objects.filter(
            level=Area.Level.WARD
        ).count()

        expected_assets = total_wards * len(asset_types)

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write("ASSET POPULATION COMPLETE")
        self.stdout.write("=" * 70)
        self.stdout.write(
            f"Wards:             {total_wards}"
        )
        self.stdout.write(
            f"Asset types:       {len(asset_types)}"
        )
        self.stdout.write(
            f"New assets:        {created_total}"
        )
        self.stdout.write(
            f"Total assets:      {total_assets}"
        )
        self.stdout.write(
            f"Expected coverage: {expected_assets}"
        )
        self.stdout.write("=" * 70)
        self.stdout.write(
            "Every ward now has the configured asset types."
        )
        self.stdout.write(
            "These asset records are project-generated data, "
            "not an official government asset inventory."
        )
        self.stdout.write("=" * 70)