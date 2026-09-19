from django.db import models


class Area(models.Model):
    """
    Self-referential hierarchy: District -> Mandal/Municipality -> Village/Area -> Ward
    Using one table with a `level` + `parent` field keeps this flexible
    instead of hard-coding four separate tables.
    """

    class Level(models.TextChoices):
        DISTRICT = "DISTRICT", "District"
        MANDAL = "MANDAL", "Mandal/Municipality"
        VILLAGE = "VILLAGE", "Village/Area"
        WARD = "WARD", "Ward"

    name = models.CharField(max_length=150)
    level = models.CharField(max_length=20, choices=Level.choices)
    parent = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.CASCADE, related_name="children",
    )

    class Meta:
        unique_together = ("name", "level", "parent")

    def __str__(self):
        return f"{self.name} ({self.get_level_display()})"

    def get_descendant_ids(self):
        """This area's id plus every area nested under it (villages, wards, etc.),
        found level by level. Used to scope a Mandal Head to their whole mandal."""
        ids = {self.id}
        frontier = [self.id]
        while frontier:
            children = list(Area.objects.filter(parent_id__in=frontier).values_list("id", flat=True))
            new_ids = [c for c in children if c not in ids]
            if not new_ids:
                break
            ids.update(new_ids)
            frontier = new_ids
        return ids

    def full_path(self):
        """Returns 'Prakasam > Darsi > Naynapalli' style breadcrumb —
        walks up the parent chain and joins the names together."""
        parts = [self.name]
        node = self.parent
        while node:
            parts.append(node.name)
            node = node.parent
        return " > ".join(reversed(parts))


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)  # Electricity, Water, Roads, Sanitation...
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name
