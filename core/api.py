"""
core/serializers.py, core/views.py, core/urls.py (combined here for readability —
split into three files in the real project).
"""

# ---------------------------------------------------------------------------
# core/serializers.py
# ---------------------------------------------------------------------------
from rest_framework import serializers
from .models import Area, Department


class AreaSerializer(serializers.ModelSerializer):
    level_display = serializers.CharField(source="get_level_display", read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True, default=None)

    class Meta:
        model = Area
        fields = ["id", "name", "level", "level_display", "parent", "parent_name"]

    def validate(self, attrs):
        # A District has no parent; every other level must have one.
        level = attrs.get("level", getattr(self.instance, "level", None))
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if level == Area.Level.DISTRICT and parent is not None:
            raise serializers.ValidationError("A district cannot have a parent area.")
        if level != Area.Level.DISTRICT and parent is None:
            raise serializers.ValidationError(f"{level.title()} areas must have a parent area.")
        return attrs


class AreaTreeSerializer(serializers.ModelSerializer):
    """Nested read-only representation — used by the citizen app's area picker."""

    children = serializers.SerializerMethodField()

    class Meta:
        model = Area
        fields = ["id", "name", "level", "children"]

    def get_children(self, obj):
        return AreaTreeSerializer(obj.children.order_by("name"), many=True).data


class DepartmentSerializer(serializers.ModelSerializer):
    open_issue_count = serializers.IntegerField(read_only=True)  # annotated in queryset

    class Meta:
        model = Department
        fields = ["id", "name", "description", "open_issue_count"]


# ---------------------------------------------------------------------------
# core/views.py
# ---------------------------------------------------------------------------
from django.db.models import Count, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .permissions import ReadOnlyOrAdmin


class AreaViewSet(viewsets.ModelViewSet):
    """
    /api/areas/            list/create
    /api/areas/{id}/       retrieve/update/delete
    /api/areas/tree/       nested tree, for the citizen app's cascading picker
    """

    queryset = Area.objects.select_related("parent").all()
    serializer_class = AreaSerializer
    permission_classes = [ReadOnlyOrAdmin]
    filterset_fields = ["level", "parent"]
    
    from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

class AreaViewSet(viewsets.ModelViewSet):
    ...

    @method_decorator(cache_page(60 * 60 * 6))  # cache for 6 hours
    @action(detail=False, methods=["get"])
    def tree(self, request):
        all_areas = list(self.get_queryset().order_by("name"))
        children_map = {}
        for area in all_areas:
            children_map.setdefault(area.parent_id, []).append(area)

        def build(area):
            return {
                "id": area.id,
                "name": area.name,
                "level": area.level,
                "children": [build(child) for child in children_map.get(area.id, [])],
            }

        roots = children_map.get(None, [])
        return Response([build(r) for r in roots])


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer
    permission_classes = [ReadOnlyOrAdmin]

    def get_queryset(self):
        # Annotate each department with its current open-issue count —
        # powers the admin analytics screen without N+1 queries.
        return Department.objects.annotate(
            open_issue_count=Count("assets__issues", filter=Q(assets__issues__status="OPEN"))
        )


# ---------------------------------------------------------------------------
# core/urls.py
# ---------------------------------------------------------------------------
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"areas", AreaViewSet, basename="area")
router.register(r"departments", DepartmentViewSet, basename="department")

urlpatterns = router.urls
