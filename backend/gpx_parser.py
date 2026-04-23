import gpxpy
import math


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def smooth_altitudes(points, window=5):
    """Lissage par moyenne glissante pour réduire le bruit GPS."""
    n = len(points)
    smoothed = []
    for i in range(n):
        start = max(0, i - window)
        end = min(n, i + window + 1)
        avg = sum(points[j]["ele"] for j in range(start, end)) / (end - start)
        smoothed.append(avg)
    return smoothed


def calc_dplus_seuil(altitudes_lissees, seuil=5.0):
    """
    Calcul D+/D- avec seuil anti-bruit.
    On n'accumule une montée que si elle dépasse `seuil` mètres en continu.
    Méthode hypsométrique : accumulation par segments significatifs.
    """
    d_plus = 0.0
    d_minus = 0.0

    pending_up = 0.0
    pending_down = 0.0

    for i in range(1, len(altitudes_lissees)):
        diff = altitudes_lissees[i] - altitudes_lissees[i - 1]
        if diff > 0:
            # On monte
            if pending_down > 0:
                # Changement de sens descente→montée : valider la descente si > seuil
                if pending_down >= seuil:
                    d_minus += pending_down
                pending_down = 0.0
            pending_up += diff
        elif diff < 0:
            # On descend
            if pending_up > 0:
                # Changement de sens montée→descente : valider la montée si > seuil
                if pending_up >= seuil:
                    d_plus += pending_up
                pending_up = 0.0
            pending_down += abs(diff)

    # Flush final
    if pending_up >= seuil:
        d_plus += pending_up
    if pending_down >= seuil:
        d_minus += pending_down

    return d_plus, d_minus


def detect_sommets(profil, cum_dist_km, min_prominence=30, min_dist_km=1.5):
    """
    Détecte les sommets locaux (cols, sommets) sur le profil altimétrique.

    - min_prominence : dénivelé minimum autour du sommet pour être retenu (m)
    - min_dist_km    : distance minimale entre deux sommets (km)

    Retourne une liste de {"dist_km", "alt", "nom", "type"}
    """
    n = len(profil)
    if n < 5:
        return []

    alts = [p["alt"] for p in profil]
    dists = [p["dist_km"] for p in profil]

    # Fenêtre de détection : ~2km de chaque côté
    dist_total = dists[-1] if dists[-1] > 0 else 1
    win = max(3, int(n * (2.0 / dist_total)))

    candidats = []

    for i in range(win, n - win):
        local_max = True
        for j in range(i - win, i + win + 1):
            if j != i and alts[j] >= alts[i]:
                local_max = False
                break
        if not local_max:
            continue

        # Prominence : différence avec la vallée la plus haute à gauche/droite
        gauche_min = min(alts[max(0, i - win * 3):i]) if i > 0 else alts[i]
        droite_min = min(alts[i + 1:min(n, i + win * 3 + 1)]) if i < n - 1 else alts[i]
        prominence = alts[i] - max(gauche_min, droite_min)

        if prominence >= min_prominence:
            candidats.append({
                "idx": i,
                "dist_km": round(dists[i], 2),
                "alt": round(alts[i]),
                "prominence": prominence,
            })

    # Filtrage : garder les plus proéminents, espacement minimum
    candidats.sort(key=lambda x: -x["prominence"])
    retenus = []
    for c in candidats:
        trop_proche = any(abs(c["dist_km"] - r["dist_km"]) < min_dist_km for r in retenus)
        if not trop_proche:
            retenus.append(c)

    # Trier par distance
    retenus.sort(key=lambda x: x["dist_km"])

    # Nommer automatiquement
    result = []
    for i, r in enumerate(retenus):
        result.append({
            "dist_km": r["dist_km"],
            "alt": r["alt"],
            "nom": f"Sommet {i+1}",
            "type": "col / sommet",
            "source": "auto",
        })

    return result


def extract_waypoints(gpx, cum_dist, points):
    """
    Extrait les waypoints nommés du fichier GPX et calcule leur distance
    depuis le départ en cherchant le point de trace le plus proche.
    """
    waypoints = []
    for wp in gpx.waypoints:
        if not wp.name:
            continue
        # Trouver le point de trace le plus proche
        min_d = float("inf")
        closest_idx = 0
        for i, pt in enumerate(points):
            d = haversine(wp.latitude, wp.longitude, pt["lat"], pt["lon"])
            if d < min_d:
                min_d = d
                closest_idx = i

        # Ignorer les waypoints trop éloignés de la trace (>500m)
        if min_d > 500:
            continue

        waypoints.append({
            "dist_km": round(cum_dist[closest_idx] / 1000, 2),
            "alt": round(wp.elevation or points[closest_idx]["ele"]),
            "nom": wp.name,
            "type": wp.type or wp.symbol or "",
            "source": "gpx",
        })

    # Trier par distance
    waypoints.sort(key=lambda x: x["dist_km"])
    return waypoints


def merge_points_marquants(waypoints, sommets_auto, min_dist_km=1.0):
    """
    Fusionne waypoints GPX et sommets auto détectés.
    Les waypoints GPX ont priorité — les sommets auto trop proches d'un waypoint sont supprimés.
    """
    all_pts = list(waypoints)

    for s in sommets_auto:
        trop_proche = any(abs(s["dist_km"] - w["dist_km"]) < min_dist_km for w in all_pts)
        if not trop_proche:
            all_pts.append(s)

    all_pts.sort(key=lambda x: x["dist_km"])
    return all_pts


def parse_gpx(content: bytes) -> dict:
    gpx = gpxpy.parse(content)

    # ── Extraction des points de trace ──────────────────────────────────────
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for pt in segment.points:
                points.append({
                    "lat": pt.latitude,
                    "lon": pt.longitude,
                    "ele": pt.elevation or 0,
                })

    if not points:
        for route in gpx.routes:
            for pt in route.points:
                points.append({
                    "lat": pt.latitude,
                    "lon": pt.longitude,
                    "ele": pt.elevation or 0,
                })

    if len(points) < 2:
        raise ValueError("GPX invalide : moins de 2 points")

    # ── Distance cumulée ─────────────────────────────────────────────────────
    cum_dist = [0.0]
    for i in range(1, len(points)):
        d = haversine(
            points[i-1]["lat"], points[i-1]["lon"],
            points[i]["lat"], points[i]["lon"]
        )
        cum_dist.append(cum_dist[-1] + d)

    total_distance_m = cum_dist[-1]

    # ── Lissage altitudes ────────────────────────────────────────────────────
    # Fenêtre adaptative selon la densité du GPX
    pts_par_km = len(points) / max(total_distance_m / 1000, 1)
    smooth_window = max(3, min(15, int(pts_par_km * 0.5)))
    alts_smooth = smooth_altitudes(points, window=smooth_window)

    # ── D+ / D- avec seuil anti-bruit ────────────────────────────────────────
    # Seuil adaptatif : plus le GPX est dense, plus le seuil est grand
    seuil = max(5.0, min(15.0, pts_par_km * 0.3))
    d_plus, d_minus = calc_dplus_seuil(alts_smooth, seuil=seuil)

    # ── Altitude min/max ─────────────────────────────────────────────────────
    alt_min = min(p["ele"] for p in points)
    alt_max = max(p["ele"] for p in points)

    # ── Bounding box ─────────────────────────────────────────────────────────
    lats = [p["lat"] for p in points]
    lons = [p["lon"] for p in points]
    bbox = {
        "lat_min": min(lats), "lat_max": max(lats),
        "lon_min": min(lons), "lon_max": max(lons),
    }

    # ── Profil sous-échantillonné (max 600 points) ───────────────────────────
    step_profil = max(1, len(points) // 600)
    profil = [
        {
            "dist_km": round(cum_dist[i] / 1000, 3),
            "alt": round(alts_smooth[i], 1),   # profil lissé
        }
        for i in range(0, len(points), step_profil)
    ]

    # ── Points marquants ─────────────────────────────────────────────────────
    # 1. Waypoints nommés du GPX
    waypoints = extract_waypoints(gpx, cum_dist, points)

    # 2. Sommets détectés automatiquement sur le profil lissé
    sommets_auto = detect_sommets(
        profil,
        cum_dist_km=[p["dist_km"] for p in profil],
        min_prominence=max(25, int(d_plus * 0.04)),  # 4% du D+ total
        min_dist_km=max(1.0, total_distance_m / 1000 * 0.07),  # 7% distance totale
    )

    # 3. Fusion
    points_marquants = merge_points_marquants(waypoints, sommets_auto)

    # ── Trace sous-échantillonnée pour SVG (max 800 points) ──────────────────
    step = max(1, len(points) // 800)
    sampled = points[::step]

    # ── Nom GPX ──────────────────────────────────────────────────────────────
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
        "center": {"lat": sum(lats) / len(lats), "lon": sum(lons) / len(lons)},
        "trace": [{"lat": p["lat"], "lon": p["lon"]} for p in sampled],
        "profil": profil,
        "points_marquants": points_marquants,
        "nb_points_total": len(points),
        "smooth_window": smooth_window,
        "seuil_dplus": round(seuil, 1),
    }
