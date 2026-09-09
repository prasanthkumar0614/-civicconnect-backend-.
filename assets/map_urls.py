"""
assets/map_urls.py — add these to config/urls.py:

    path("api/", include("assets.map_urls")),
"""

from django.urls import path
from .map_api import assets_for_map, asset_clusters

urlpatterns = [
    path("assets/map/", assets_for_map, name="assets-map"),
    path("assets/map/clusters/", asset_clusters, name="asset-clusters"),
]
