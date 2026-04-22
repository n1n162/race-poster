import gpxpy
import math
from typing import Optional


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2*R*math.atan2(math.sqrt(a), math.sqrt(1-a))


def parse_gpx(content: bytes) -> dict:
    gpx = gpxpy.parse(content)

    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                points.append({
                    "lat": pt.latitude,
                    "lon": pt.longitude,
                    "ele": pt.elevation or 0
                })

    if not points:
        for route in gpx.routes:
            for pt in route.points:
                points.append({
                    "lat": pt.latitude,
                    "lon": pt.longitude,
                    "ele": pt.elevation or 0
                })

    if len(points) < 2:
        raise ValueError("GPX invalide : moins de 2 points")

    # Distance cumulée
    cum_dist = [0.0]
    for i in range(1, len(points)):
        d = haversine(
            points[i-1]["lat"], points[i-1]["lon"],
            points[i]["lat"], points[i]["lon"]
        )
        cum_dist.append(cum_dist[-1] + d)

    total_distance_m = cum_dist[-1]

    # D+ / D-
    d_plus = 0.0
    d_minus = 0.0
    SMOOTH = 5  # fenêtre lissage
    for i in range(SMOOTH, len(points)):
        diff = points[i]["ele"] - points[i-SMOOTH]["ele"]
        if diff > 0:
            d_plus += diff
        else:
            d_minus += abs(diff)

    # Altitude min/max
    altitudes = [p["ele"] for p in points]
    alt_min = min(altitudes)
    alt_max = max(altitudes)

    # Bounding box (pour requête OSM)
    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    bbox = {
        "lat_min": min(lats),
        "lat_max": max(lats),
        "lon_min": min(lons),
        "lon_max": max(lons),
    }

    # Centroïde
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    # Sous-échantillonnage trace pour SVG (max 800 points)
    step = max(1, len(points) // 800)
    sampled = points[::step]
    sampled_dist = cum_dist[::step]

    # Profil sous-échantillonné (max 500 points)
    step_profil = max(1, len(points) // 500)
    profil = [
        {"dist_km": round(cum_dist[i] / 1000, 3), "alt": round(points[i]["ele"], 1)}
        for i in range(0, len(points), step_profil)
    ]

    # Nom de la course depuis le GPX
    nom_gpx = None
    if gpx.tracks and gpx.tracks[0].name:
        nom_gpx = gpx.tracks[0].name
    elif gpx.name:
        nom_gpx = gpx.name

    return {
        "nom_gpx": nom_gpx,
        "total_distance_km": round(total_distance_m / 1000, 2),
        "d_plus": round(d_plus),
        "d_minus": round(d_minus),
        "alt_min": round(alt_min),
        "alt_max": round(alt_max),
        "bbox": bbox,
        "center": {"lat": center_lat, "lon": center_lon},
        "trace": [{"lat": p["lat"], "lon": p["lon"]} for p in sampled],
        "profil": profil,
        "nb_points_total": len(points),
    }
