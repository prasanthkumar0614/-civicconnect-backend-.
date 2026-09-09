"""
assets/serializers.py, assets/views.py, assets/urls.py (combined for readability).
"""

# ---------------------------------------------------------------------------
# assets/serializers.py
# ---------------------------------------------------------------------------
from rest_framework import serializers
from .models import Asset, AssetType


class AssetTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetType
        fields = ["id", "name", "id_prefix", "default_department"]


class AssetSerializer(serializers.ModelSerializer):
    asset_type_name = serializers.CharField(source="asset_type.name", read_only=True)
    area_name = serializers.CharField(source="area.name", read_only=True)
    open_issue_count = serializers.IntegerField(read_only=True)  # annotated

    class Meta:
        model = Asset
        fields = [
            "id", "asset_id", "asset_type", "asset_type_name", "area", "area_name",
            "department", "latitude", "longitude", "status",
            "installed_on", "last_maintained_on", "open_issue_count",
        ]
        read_only_fields = ["asset_id"]  # auto-generated in Asset.save()


class AssetPickerSerializer(serializers.ModelSerializer):
    """Slim payload for the citizen app's asset dropdown — id + display label only."""

    label = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = ["id", "asset_id", "label"]

    def get_label(self, obj):
        return f"{obj.asset_id} — {obj.asset_type.name}"


# ---------------------------------------------------------------------------
# assets/views.py
# ---------------------------------------------------------------------------
from django.db.models import Count, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import ReadOnlyOrAdmin


class AssetTypeViewSet(viewsets.ModelViewSet):
    queryset = AssetType.objects.all()
    serializer_class = AssetTypeSerializer
    permission_classes = [ReadOnlyOrAdmin]


class AssetViewSet(viewsets.ModelViewSet):
    """
    /api/assets/                       list/create/retrieve/update/delete
    /api/assets/?area=3&asset_type=2    filter by area or type (citizen picker flow)
    /api/assets/picker/?area=3          slim list for a dropdown
    """

    serializer_class = AssetSerializer
    permission_classes = [ReadOnlyOrAdmin]
    filterset_fields = ["area", "asset_type", "department", "status"]

    def get_queryset(self):
        return (
            Asset.objects.select_related("asset_type", "area", "department")
            .annotate(open_issue_count=Count("issues", filter=Q(issues__status="OPEN")))
        )

    @action(detail=False, methods=["get"])
    def picker(self, request):
        area_id = request.query_params.get("area")
        qs = self.get_queryset()
        if area_id:
            qs = qs.filter(area_id=area_id)
        return Response(AssetPickerSerializer(qs, many=True).data)


# ---------------------------------------------------------------------------
# assets/urls.py
# ---------------------------------------------------------------------------
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"asset-types", AssetTypeViewSet, basename="asset-type")
router.register(r"assets", AssetViewSet, basename="asset")

urlpatterns = router.urls
