import geopandas as gpd
import osmnx as ox
from shapely.geometry import LineString, Point, box
import numpy as np
from typing import Optional


# Niveaux de détail prédéfinis
PRESETS = {
    "trail": {
        "routes": ["primary", "secondary"],
        "chemins": ["track", "path", "footway"],
        "eau": True,
    },
    "standard": {
        "routes": ["primary", "secondary", "tertiary"],
        "chemins": ["track", "path", "footway"],
        "eau": True,
    },
    "detaille": {
        "routes": ["primary", "secondary", "tertiary", "residential", "unclassified"],
        "chemins": ["track", "path", "footway", "bridleway", "cycleway", "steps"],
        "eau": True,
    },
}

ROUTE_STYLES = {
    "motorway":      {"largeur": 1.2},
    "trunk":         {"largeur": 1.0},
    "primary":       {"largeur": 0.9},
    "secondary":     {"largeur": 0.7},
    "tertiary":      {"largeur": 0.55},
    "residential":   {"largeur": 0.4},
    "unclassified":  {"largeur": 0.4},
}

CHEMIN_STYLES = {
    "track":     {"largeur": 0.5, "dash": False},
    "path":      {"largeur": 0.4, "dash": True},
    "footway":   {"largeur": 0.4, "dash": True},
    "bridleway": {"largeur": 0.4, "dash": True},
    "cycleway":  {"largeur": 0.4, "dash": False},
    "steps":     {"largeur": 0.3, "dash": True},
}


def fetch_osm_geometries(bbox: dict, config: dict, marge_km: float = 1.5) -> dict:
    """
    Télécharge les géométries OSM pour la zone de la course.
    Retourne un dict de géométries GeoJSON-like pour le générateur SVG.
    """
    lat_min = bbox["lat_min"]
    lat_max = bbox["lat_max"]
    lon_min = bbox["lon_min"]
    lon_max = bbox["lon_max"]

    # Marge en degrés (~1.5km)
    marge_deg = marge_km / 111.0
    poly = box(lon_min - marge_deg, lat_min - marge_deg,
                lon_max + marge_deg, lat_max + marge_deg)

    from shapely.geometry import mapping
    import json

    result = {
        "routes": {},
        "chemins": {},
        "eau_polygones": [],
        "eau_lignes": [],
    }

    # Résoudre le preset ou config custom
    if isinstance(config, str):
        cfg = PRESETS.get(config, PRESETS["standard"])
    else:
        cfg = config

    routes_actives = cfg.get("routes", [])
    chemins_actifs = cfg.get("chemins", [])
    afficher_eau = cfg.get("eau", True)

    # Routes
    for route_type in routes_actives:
        try:
            tags = {"highway": [route_type]}
            gdf = ox.features_from_polygon(poly, tags).to_crs(epsg=3857)
            lignes = gdf[gdf.geometry.type.isin(["LineString", "MultiLineString"])]
            if not lignes.empty:
                coords_list = []
                for geom in lignes.geometry:
                    if geom.geom_type == "LineString":
                        coords_list.append(list(geom.coords))
                    elif geom.geom_type == "MultiLineString":
                        for line in geom.geoms:
                            coords_list.append(list(line.coords))
                result["routes"][route_type] = {
                    "coords": coords_list,
                    "largeur": ROUTE_STYLES.get(route_type, {}).get("largeur", 0.5),
                }
        except Exception:
            pass

    # Chemins
    for chemin_type in chemins_actifs:
        try:
            tags = {"highway": [chemin_type]}
            gdf = ox.features_from_polygon(poly, tags).to_crs(epsg=3857)
            lignes = gdf[gdf.geometry.type.isin(["LineString", "MultiLineString"])]
            if not lignes.empty:
                coords_list = []
                for geom in lignes.geometry:
                    if geom.geom_type == "LineString":
                        coords_list.append(list(geom.coords))
                    elif geom.geom_type == "MultiLineString":
                        for line in geom.geoms:
                            coords_list.append(list(line.coords))
                style = CHEMIN_STYLES.get(chemin_type, {})
                result["chemins"][chemin_type] = {
                    "coords": coords_list,
                    "largeur": style.get("largeur", 0.4),
                    "dash": style.get("dash", False),
                }
        except Exception:
            pass

    # Eau
    if afficher_eau:
        try:
            tags_water = {
                "natural": ["water"],
                "waterway": ["river", "stream", "canal", "lake"]
            }
            gdf_water = ox.features_from_polygon(poly, tags_water).to_crs(epsg=3857)

            polys = gdf_water[gdf_water.geometry.type.isin(["Polygon", "MultiPolygon"])]
            for geom in polys.geometry:
                if geom.geom_type == "Polygon":
                    result["eau_polygones"].append(list(geom.exterior.coords))
                elif geom.geom_type == "MultiPolygon":
                    for p in geom.geoms:
                        result["eau_polygones"].append(list(p.exterior.coords))

            lignes_eau = gdf_water[gdf_water.geometry.type.isin(["LineString", "MultiLineString"])]
            for geom in lignes_eau.geometry:
                if geom.geom_type == "LineString":
                    result["eau_lignes"].append(list(geom.coords))
                elif geom.geom_type == "MultiLineString":
                    for line in geom.geoms:
                        result["eau_lignes"].append(list(line.coords))
        except Exception:
            pass

    return result
