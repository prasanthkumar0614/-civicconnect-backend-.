"""
assets/clustering.py

Detects groups of nearby assets that each have open issues — the
"possible electrical/network problem affecting multiple nearby street
lights" feature from the original design brainstorm.

Approach: simple distance-based grouping (haversine formula) rather than
a full clustering library — fast enough for a city-scale asset count and
easy to explain/justify in a viva. For a production upgrade at large
scale, swap this for PostGIS ST_ClusterDBSCAN.
"""

import math

CLUSTER_RADIUS_METERS = 400  # assets within this distance are considered "nearby"
EARTH_RADIUS_METERS = 6371000


def haversine_distance(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lng points, in meters."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METERS * math.asin(math.sqrt(a))


def find_asset_clusters(assets_with_open_issues):
    """
    assets_with_open_issues: iterable of Asset instances that currently
    have at least one OPEN issue, each with .latitude/.longitude set.

    Returns a list of clusters, where each cluster is a list of asset
    instances (length >= 2) that are all within CLUSTER_RADIUS_METERS of
    each other — i.e. a likely shared underlying fault (e.g. a blown
    transformer taking out several nearby street lights).
    """
    points = [a for a in assets_with_open_issues if a.latitude is not None and a.longitude is not None]
    visited = set()
    clusters = []

    for i, asset in enumerate(points):
        if asset.id in visited:
            continue
        group = [asset]
        visited.add(asset.id)
        for other in points[i + 1:]:
            if other.id in visited:
                continue
            dist = haversine_distance(
                float(asset.latitude), float(asset.longitude),
                float(other.latitude), float(other.longitude),
            )
            if dist <= CLUSTER_RADIUS_METERS:
                group.append(other)
                visited.add(other.id)
        if len(group) >= 2:
            clusters.append(group)

    return clusters
