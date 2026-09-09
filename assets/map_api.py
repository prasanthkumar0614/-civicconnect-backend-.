"""
assets/map_api.py

Two endpoints powering Step 8 (Maps / asset visualization):

  GET /api/assets/map/?area=3       -> all assets in an area, with status
                                        and open-issue count, for markers
  GET /api/assets/map/clusters/     -> groups of nearby assets that each
                                        have open issues — surfaced as a
                                        "possible larger fault" warning
"""

from django.db.models import Count, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Asset
from .clustering import find_asset_clusters


def _asset_map_payload(asset):
    return {
        "id": asset.id,
        "asset_id": asset.asset_id,
        "asset_type": asset.asset_type.name,
        "status": asset.status,
        "latitude": asset.latitude,
        "longitude": asset.longitude,
        "open_issue_count": getattr(asset, "open_issue_count", 0),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def assets_for_map(request):
    """All assets with coordinates in the given area, annotated with open-issue count."""
    area_id = request.query_params.get("area")
    qs = (
        Asset.objects.exclude(latitude__isnull=True)
        .exclude(longitude__isnull=True)
        .annotate(open_issue_count=Count("issues", filter=Q(issues__status="OPEN")))
        .select_related("asset_type")
    )
    if area_id:
        qs = qs.filter(area_id=area_id)

    return Response([_asset_map_payload(a) for a in qs])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def asset_clusters(request):
    """
    Assets that currently have open issues, grouped by physical proximity.
    A cluster of 2+ nearby assets with open issues is a signal worth an
    officer's attention — likely one shared fault, not several unrelated ones.
    """
    area_id = request.query_params.get("area")
    faulty_qs = (
        Asset.objects.filter(issues__status="OPEN")
        .exclude(latitude__isnull=True)
        .exclude(longitude__isnull=True)
        .distinct()
        .select_related("asset_type")
        .annotate(open_issue_count=Count("issues", filter=Q(issues__status="OPEN")))
    )
    if area_id:
        faulty_qs = faulty_qs.filter(area_id=area_id)

    clusters = find_asset_clusters(list(faulty_qs))

    return Response([
        {
            "assets": [_asset_map_payload(a) for a in group],
            "center": {
                "latitude": sum(float(a.latitude) for a in group) / len(group),
                "longitude": sum(float(a.longitude) for a in group) / len(group),
            },
        }
        for group in clusters
    ])
