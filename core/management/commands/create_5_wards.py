from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Area


class Command(BaseCommand):
    help = "Create 5 assumed wards for every village."

    @transaction.atomic
    def handle(self, *args, **options):

        villages = list(
            Area.objects.filter(
                level=Area.Level.VILLAGE
            ).only("id")
        )

        self.stdout.write(
            f"Villages found: {len(villages)}"
        )

        existing = set(
            Area.objects.filter(
                level=Area.Level.WARD
            ).values_list("parent_id", "name")
        )

        wards_to_create = []

        for village in villages:
            for number in range(1, 6):

                name = f"Ward {number}"
                key = (village.id, name)

                if key not in existing:
                    wards_to_create.append(
                        Area(
                            name=name,
                            level=Area.Level.WARD,
                            parent_id=village.id,
                        )
                    )

        self.stdout.write(
            f"New wards to create: {len(wards_to_create)}"
        )

        created = 0

        for start in range(0, len(wards_to_create), 2000):

            batch = wards_to_create[start:start + 2000]

            Area.objects.bulk_create(
                batch,
                batch_size=2000,
                ignore_conflicts=True,
            )

            created += len(batch)

            self.stdout.write(
                f"Inserted {min(start + 2000, len(wards_to_create))}"
                f"/{len(wards_to_create)}"
            )

        total_wards = Area.objects.filter(
            level=Area.Level.WARD
        ).count()

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write("5 ASSUMED WARDS COMPLETE")
        self.stdout.write("=" * 60)
        self.stdout.write(
            f"Villages:       {len(villages)}"
        )
        self.stdout.write(
            f"New wards:      {created}"
        )
        self.stdout.write(
            f"Total wards:    {total_wards}"
        )
        self.stdout.write("=" * 60)
        self.stdout.write(
            "NOTE: These 5 wards per village are project assumptions, "
            "not official government ward data."
        )