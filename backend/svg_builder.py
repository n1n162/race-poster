"""
svg_builder.py — Génère le SVG final de l'affiche de course.

Calques Cricut :
  - calque-noir  : cadres, titres, stats labels, axes profil, encoches dossard
  - calque-vert  : carte OSM (routes/eau/chemins) + tracé GPS + profil altimétrique
  - calque-rouge : valeurs stats + annotations profil

Formats supportés (largeur × hauteur en mm, toujours dans 600×300 Cricut) :
  - "15x20"  → 150×200 mm  portrait
  - "20x30"  → 300×200 mm  paysage
  - "a4"     → 297×210 mm  paysage
  - "30x40"  → 400×300 mm  paysage
"""

import math
from typing import Optional

# Résolution interne : 1mm = 3.7795px (96dpi)
MM_TO_PX = 3.7795

FORMATS = {
    "15x20": (150, 200),   # portrait → on pivote en paysage si nécessaire
    "20x30": (300, 200),
    "a4":    (297, 210),
    "30x40": (400, 300),
}


def mm(v): return v * MM_TO_PX


def coords_to_svg(coords_list, bbox_m, map_x, map_y, map_w, map_h):
    """Convertit une liste de coordonnées Mercator (EPSG:3857) en points SVG."""
    x_min, y_min, x_max, y_max = bbox_m
    span_x = x_max - x_min or 1
    span_y = y_max - y_min or 1

    paths = []
    for coords in coords_list:
        pts = []
        for x, y in coords:
            sx = map_x + (x - x_min) / span_x * map_w
            sy = map_y + map_h - (y - y_min) / span_y * map_h
            pts.append(f"{sx:.1f},{sy:.1f}")
        if pts:
            paths.append("M " + " L ".join(pts))
    return paths


def latlon_to_mercator(lat, lon):
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
    y = y * 20037508.34 / 180
    return x, y


def build_svg(
    race_data: dict,
    osm_data: dict,
    format_key: str = "30x40",
    couleur1: str = "#1a7a1a",   # vert
    couleur2: str = "#cc1a00",   # rouge
    dossard_w_mm: float = 210,
    dossard_h_mm: float = 148,
    points_marquants: list = None,
) -> str:
    """
    Génère et retourne le SVG complet de l'affiche.

    race_data : résultat de gpx_parser.parse_gpx() + infos saisies par l'utilisateur
    osm_data  : résultat de osm_fetcher.fetch_osm_geometries()
    """

    # ── Dimensions affiche ──────────────────────────────────────────────────
    w_mm, h_mm = FORMATS.get(format_key, (400, 300))
    W = mm(w_mm)
    H = mm(h_mm)

    MARGE = mm(6)
    INNER_W = W - 2 * MARGE
    INNER_H = H - 2 * MARGE

    # ── Zones de mise en page ───────────────────────────────────────────────
    # Titre : 12% hauteur
    TITRE_H = INNER_H * 0.12

    # Zone principale (sous le titre) : 88%
    MAIN_H = INNER_H - TITRE_H
    MAIN_Y = MARGE + TITRE_H

    # Colonne gauche (carte) : 60% largeur
    # Colonne droite (stats + dossard) : 40% largeur
    COL_LEFT_W = INNER_W * 0.60
    COL_RIGHT_W = INNER_W * 0.40
    COL_RIGHT_X = MARGE + COL_LEFT_W

    # Dans la colonne gauche : carte 50%, profil 50%
    CARTE_H = MAIN_H * 0.50
    PROFIL_H = MAIN_H * 0.50

    CARTE_X = MARGE
    CARTE_Y = MAIN_Y
    CARTE_W = COL_LEFT_W

    PROFIL_X = MARGE
    PROFIL_Y = MAIN_Y + CARTE_H
    PROFIL_W = INNER_W  # pleine largeur

    # Dossard : taille réelle convertie en px, centré dans la colonne droite
    dos_w_px = mm(dossard_w_mm)
    dos_h_px = mm(dossard_h_mm)

    # Si le dossard est trop grand pour la colonne droite → on le réduit
    max_dos_w = COL_RIGHT_W - mm(4)
    max_dos_h = MAIN_H * 0.58
    scale = min(1.0, max_dos_w / dos_w_px, max_dos_h / dos_h_px)
    dos_w_px *= scale
    dos_h_px *= scale

    # Stats : hauteur disponible au-dessus du dossard
    STATS_H = MAIN_H - dos_h_px - mm(5)
    STATS_Y = MAIN_Y
    STATS_X = COL_RIGHT_X

    DOS_X = COL_RIGHT_X + (COL_RIGHT_W - dos_w_px) / 2
    DOS_Y = MAIN_Y + STATS_H + mm(3)

    # ── Données race ────────────────────────────────────────────────────────
    nom = race_data.get("nom", "Trail")
    sous_titre = race_data.get("sous_titre", "")
    date = race_data.get("date", "")
    lieu = race_data.get("lieu", "")
    distance = race_data.get("total_distance_km", 0)
    d_plus = race_data.get("d_plus", 0)
    temps = race_data.get("temps", "")
    classement = race_data.get("classement", "")
    profil_pts = race_data.get("profil", [])
    trace_pts = race_data.get("trace", [])

    # ── Calcul bounding box Mercator pour la carte ──────────────────────────
    if trace_pts:
        merc = [latlon_to_mercator(p["lat"], p["lon"]) for p in trace_pts]
        mx_list = [p[0] for p in merc]
        my_list = [p[1] for p in merc]
        bbox_m = (min(mx_list), min(my_list), max(mx_list), max(my_list))
        span_x = bbox_m[2] - bbox_m[0] or 1
        span_y = bbox_m[3] - bbox_m[1] or 1
        # Centrage avec marge 5%
        margin_x = span_x * 0.05
        margin_y = span_y * 0.05
        bbox_m = (bbox_m[0]-margin_x, bbox_m[1]-margin_y,
                  bbox_m[2]+margin_x, bbox_m[3]+margin_y)
    else:
        bbox_m = (0, 0, 1, 1)

    def to_svg_xy(lat, lon):
        x, y = latlon_to_mercator(lat, lon)
        bx0, by0, bx1, by1 = bbox_m
        sx = CARTE_X + (x - bx0) / (bx1 - bx0) * CARTE_W
        sy = CARTE_Y + CARTE_H - (y - by0) / (by1 - by0) * CARTE_H
        return sx, sy

    # ── Profil altimétrique ──────────────────────────────────────────────────
    PROFIL_INNER_X = PROFIL_X + mm(10)  # marge gauche pour altitude label
    PROFIL_INNER_W = PROFIL_W - mm(14)
    PROFIL_INNER_Y = PROFIL_Y + mm(12)  # marge haut pour annotations
    PROFIL_INNER_H = PROFIL_H - mm(18)  # marge bas pour labels km

    alt_vals = [p["alt"] for p in profil_pts] if profil_pts else [0, 1]
    alt_min = min(alt_vals)
    alt_max = max(alt_vals)
    alt_span = (alt_max - alt_min) or 1
    dist_max = profil_pts[-1]["dist_km"] if profil_pts else 1

    def profil_xy(dist_km, alt):
        px = PROFIL_INNER_X + (dist_km / dist_max) * PROFIL_INNER_W
        py = PROFIL_INNER_Y + PROFIL_INNER_H - ((alt - alt_min) / alt_span) * PROFIL_INNER_H
        return px, py

    profil_points_str = " ".join(
        f"{profil_xy(p['dist_km'], p['alt'])[0]:.1f},{profil_xy(p['dist_km'], p['alt'])[1]:.1f}"
        for p in profil_pts
    ) if profil_pts else ""

    # ── Tracé GPS polyline ───────────────────────────────────────────────────
    trace_points_str = ""
    if trace_pts:
        pts = [to_svg_xy(p["lat"], p["lon"]) for p in trace_pts]
        trace_points_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    # ── OSM géométries → SVG paths ───────────────────────────────────────────
    def osm_paths(coords_list_of_lists):
        paths = []
        for coords in coords_list_of_lists:
            if not coords:
                continue
            pts_svg = []
            for x, y in coords:
                bx0, by0, bx1, by1 = bbox_m
                sx = CARTE_X + (x - bx0) / (bx1 - bx0) * CARTE_W
                sy = CARTE_Y + CARTE_H - (y - by0) / (by1 - by0) * CARTE_H
                pts_svg.append(f"{sx:.1f},{sy:.1f}")
            paths.append("M " + " L ".join(pts_svg))
        return paths

    # ── Encoches dossard ────────────────────────────────────────────────────
    enc = mm(8)  # longueur encoche
    dx1 = DOS_X
    dy1 = DOS_Y
    dx2 = DOS_X + dos_w_px
    dy2 = DOS_Y + dos_h_px

    # Coin haut-gauche : /
    enc_hg = f'<line x1="{dx1:.1f}" y1="{dy1+enc:.1f}" x2="{dx1+enc:.1f}" y2="{dy1:.1f}" stroke="black" stroke-width="1.5"/>'
    # Coin haut-droit : \
    enc_hd = f'<line x1="{dx2-enc:.1f}" y1="{dy1:.1f}" x2="{dx2:.1f}" y2="{dy1+enc:.1f}" stroke="black" stroke-width="1.5"/>'
    # Coin bas-gauche : \
    enc_bg = f'<line x1="{dx1:.1f}" y1="{dy2-enc:.1f}" x2="{dx1+enc:.1f}" y2="{dy2:.1f}" stroke="black" stroke-width="1.5"/>'
    # Coin bas-droit : /
    enc_bd = f'<line x1="{dx2-enc:.1f}" y1="{dy2:.1f}" x2="{dx2:.1f}" y2="{dy2-enc:.1f}" stroke="black" stroke-width="1.5"/>'

    # ── Stats 4 cases ────────────────────────────────────────────────────────
    cell_w = COL_RIGHT_W / 2
    cell_h = STATS_H / 2

    def stat_cell(col, row, label, valeur, unit=""):
        cx = STATS_X + col * cell_w
        cy = STATS_Y + row * cell_h
        label_y = cy + mm(4)
        val_y = cy + cell_h * 0.62
        unit_y = cy + cell_h * 0.82
        return f"""
    <rect x="{cx:.1f}" y="{cy:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" stroke="black" stroke-width="0.8" fill="none"/>
    <text x="{cx + cell_w/2:.1f}" y="{label_y:.1f}" text-anchor="middle" fill="black" font-family="Georgia, serif" font-size="{mm(3):.1f}" letter-spacing="1.5">{label}</text>
    <text x="{cx + cell_w/2:.1f}" y="{val_y:.1f}" text-anchor="middle" fill="{couleur2}" font-family="'Palatino Linotype', Palatino, Georgia, serif" font-size="{mm(7):.1f}" font-weight="bold">{valeur}</text>
    <text x="{cx + cell_w/2:.1f}" y="{unit_y:.1f}" text-anchor="middle" fill="{couleur2}" font-family="Georgia, serif" font-size="{mm(2.8):.1f}" font-style="italic">{unit}</text>"""

    stats_svg = ""
    stats_svg += stat_cell(0, 0, "DISTANCE", f"{distance:.1f}", "km")
    stats_svg += stat_cell(1, 0, "DÉNIVELÉ +", f"{d_plus:,}".replace(",", " "), "m")
    stats_svg += stat_cell(0, 1, "TEMPS", temps, "")
    stats_svg += stat_cell(1, 1, "CLASSEMENT", classement, "")

    # ── Annotations profil (points marquants) ───────────────────────────────
    annotations_svg = ""
    if points_marquants:
        for pt in points_marquants:
            d = pt.get("dist_km", 0)
            a = pt.get("alt", alt_min)
            nom_pt = pt.get("nom", "")
            type_pt = pt.get("type", "")
            px, py = profil_xy(d, a)
            ligne2 = f"{type_pt} · " if type_pt else ""
            annotations_svg += f"""
    <line x1="{px:.1f}" y1="{py:.1f}" x2="{px:.1f}" y2="{PROFIL_INNER_Y - mm(2):.1f}" stroke="{couleur2}" stroke-width="0.7" stroke-dasharray="2,2"/>
    <text x="{px:.1f}" y="{PROFIL_INNER_Y - mm(3.5):.1f}" text-anchor="middle" fill="{couleur2}" font-family="Georgia, serif" font-size="{mm(2.5):.1f}" font-style="italic">{nom_pt}</text>
    <text x="{px:.1f}" y="{PROFIL_INNER_Y - mm(6.5):.1f}" text-anchor="middle" fill="{couleur2}" font-family="Georgia, serif" font-size="{mm(2.2):.1f}">{ligne2}km {d:.1f} · {a:.0f}m</text>"""

    # ── OSM SVG strings ──────────────────────────────────────────────────────
    osm_routes_svg = ""
    for rtype, rdata in (osm_data.get("routes") or {}).items():
        paths = osm_paths(rdata["coords"])
        lw = rdata["largeur"]
        for path in paths:
            osm_routes_svg += f'<path d="{path}" stroke="{couleur1}" stroke-width="{lw:.2f}" fill="none" opacity="0.7"/>\n'

    osm_chemins_svg = ""
    for ctype, cdata in (osm_data.get("chemins") or {}).items():
        paths = osm_paths(cdata["coords"])
        lw = cdata["largeur"]
        dash = ' stroke-dasharray="3,3"' if cdata.get("dash") else ""
        for path in paths:
            osm_chemins_svg += f'<path d="{path}" stroke="{couleur1}" stroke-width="{lw:.2f}" fill="none" opacity="0.6"{dash}/>\n'

    osm_eau_svg = ""
    for coords in (osm_data.get("eau_polygones") or []):
        paths = osm_paths([coords])
        for path in paths:
            # Hachures style crayonné
            osm_eau_svg += f'<path d="{path}" stroke="{couleur1}" stroke-width="1.0" fill="none" opacity="0.8"/>\n'
    for coords in (osm_data.get("eau_lignes") or []):
        paths = osm_paths([coords])
        for path in paths:
            osm_eau_svg += f'<path d="{path}" stroke="{couleur1}" stroke-width="0.8" fill="none" opacity="0.7"/>\n'

    # ── Titre font-size adaptatif ────────────────────────────────────────────
    titre_fs = min(mm(9), INNER_W / max(len(nom), 1) * 1.5)
    sous_titre_fs = min(mm(4.5), INNER_W / max(len(sous_titre or nom), 1) * 1.2)

    # ── Graduations profil ───────────────────────────────────────────────────
    n_grad = min(10, int(dist_max))
    grad_svg = ""
    for i in range(n_grad + 1):
        d_km = dist_max * i / n_grad
        gx, _ = profil_xy(d_km, alt_min)
        gy_base = PROFIL_INNER_Y + PROFIL_INNER_H
        grad_svg += f'<line x1="{gx:.1f}" y1="{gy_base:.1f}" x2="{gx:.1f}" y2="{gy_base + mm(1.5):.1f}" stroke="black" stroke-width="0.6"/>'
        grad_svg += f'<text x="{gx:.1f}" y="{gy_base + mm(3.5):.1f}" text-anchor="middle" fill="black" font-family="Georgia, serif" font-size="{mm(2.2):.1f}">{d_km:.0f}</text>'

    alt_label_x = PROFIL_INNER_X - mm(2)
    grad_svg += f'<text x="{alt_label_x:.1f}" y="{PROFIL_INNER_Y:.1f}" text-anchor="end" fill="black" font-family="Georgia, serif" font-size="{mm(2.2):.1f}">{alt_max:.0f}m</text>'
    grad_svg += f'<text x="{alt_label_x:.1f}" y="{PROFIL_INNER_Y + PROFIL_INNER_H:.1f}" text-anchor="end" fill="black" font-family="Georgia, serif" font-size="{mm(2.2):.1f}">{alt_min:.0f}m</text>'
    grad_svg += f'<text x="{PROFIL_INNER_X + PROFIL_INNER_W/2:.1f}" y="{PROFIL_INNER_Y + PROFIL_INNER_H + mm(6):.1f}" text-anchor="middle" fill="black" font-family="Georgia, serif" font-size="{mm(2.2):.1f}" letter-spacing="2">km</text>'

    # ═══════════════════════════════════════════════════════════════════════
    # ASSEMBLAGE SVG
    # ═══════════════════════════════════════════════════════════════════════
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {W:.1f} {H:.1f}"
     width="{w_mm}mm" height="{h_mm}mm">

  <!-- AFFICHE : {nom} | Format {format_key} | {w_mm}×{h_mm}mm -->
  <!--
    CALQUES CRICUT :
    - calque-noir  : structure, titres, stats labels, encoches
    - calque-vert  : carte OSM + tracé GPS + profil
    - calque-rouge : valeurs stats + annotations profil
  -->

  <!-- ═══════════ CALQUE NOIR ═══════════ -->
  <g id="calque-noir" stroke="black" fill="none">

    <!-- Bordure double -->
    <rect x="{MARGE:.1f}" y="{MARGE:.1f}" width="{INNER_W:.1f}" height="{INNER_H:.1f}" stroke-width="2.2" fill="none"/>
    <rect x="{MARGE+mm(1.5):.1f}" y="{MARGE+mm(1.5):.1f}" width="{INNER_W-mm(3):.1f}" height="{INNER_H-mm(3):.1f}" stroke-width="0.5" fill="none"/>

    <!-- Titre -->
    <text x="{W/2:.1f}" y="{MARGE + TITRE_H*0.45:.1f}" text-anchor="middle" fill="black" stroke="none"
          font-family="'Palatino Linotype', Palatino, Georgia, serif"
          font-size="{titre_fs:.1f}" font-weight="bold" letter-spacing="3">
      {nom.upper()}
    </text>
    <text x="{W/2:.1f}" y="{MARGE + TITRE_H*0.72:.1f}" text-anchor="middle" fill="black" stroke="none"
          font-family="Georgia, serif" font-size="{sous_titre_fs:.1f}" font-style="italic" letter-spacing="4">
      {sous_titre}
    </text>

    <!-- Ligne séparatrice titre -->
    <line x1="{MARGE+mm(3):.1f}" y1="{MARGE+TITRE_H*0.84:.1f}" x2="{W-MARGE-mm(3):.1f}" y2="{MARGE+TITRE_H*0.84:.1f}" stroke-width="0.8"/>
    <line x1="{MARGE+mm(3):.1f}" y1="{MARGE+TITRE_H*0.88:.1f}" x2="{W-MARGE-mm(3):.1f}" y2="{MARGE+TITRE_H*0.88:.1f}" stroke-width="0.3"/>

    <!-- Date et lieu -->
    <text x="{MARGE+mm(4):.1f}" y="{MARGE+TITRE_H*0.97:.1f}" fill="black" stroke="none"
          font-family="Georgia, serif" font-size="{mm(3):.1f}" letter-spacing="1.5">
      {date.upper()}  ·  {lieu}
    </text>

    <!-- Séparateur vertical gauche/droite -->
    <line x1="{COL_RIGHT_X:.1f}" y1="{MAIN_Y:.1f}" x2="{COL_RIGHT_X:.1f}" y2="{MAIN_Y + MAIN_H * 0.50:.1f}" stroke-width="0.6" stroke-dasharray="3,3"/>

    <!-- Séparateur horizontal carte/profil -->
    <line x1="{MARGE:.1f}" y1="{PROFIL_Y:.1f}" x2="{W-MARGE:.1f}" y2="{PROFIL_Y:.1f}" stroke-width="0.8"/>
    <line x1="{MARGE:.1f}" y1="{PROFIL_Y+mm(0.8):.1f}" x2="{W-MARGE:.1f}" y2="{PROFIL_Y+mm(0.8):.1f}" stroke-width="0.3"/>

    <!-- Cadre carte -->
    <rect x="{CARTE_X:.1f}" y="{CARTE_Y:.1f}" width="{CARTE_W:.1f}" height="{CARTE_H:.1f}" stroke-width="0.6" fill="none"/>

    <!-- Label PROFIL ALTIMÉTRIQUE -->
    <text x="{W/2:.1f}" y="{PROFIL_Y + mm(5):.1f}" text-anchor="middle" fill="black" stroke="none"
          font-family="Georgia, serif" font-size="{mm(2.5):.1f}" letter-spacing="4">
      PROFIL ALTIMÉTRIQUE
    </text>

    <!-- Cadre profil -->
    <rect x="{PROFIL_INNER_X:.1f}" y="{PROFIL_INNER_Y:.1f}" width="{PROFIL_INNER_W:.1f}" height="{PROFIL_INNER_H:.1f}" stroke-width="0.5" fill="none"/>

    <!-- Ligne de base profil -->
    <line x1="{PROFIL_INNER_X:.1f}" y1="{PROFIL_INNER_Y+PROFIL_INNER_H:.1f}"
          x2="{PROFIL_INNER_X+PROFIL_INNER_W:.1f}" y2="{PROFIL_INNER_Y+PROFIL_INNER_H:.1f}" stroke-width="0.8"/>

    <!-- Graduations -->
    {grad_svg}

    <!-- Stats 4 cases (cadres seulement) -->
    {stats_svg}

    <!-- Label CARTE -->
    <text x="{CARTE_X + CARTE_W/2:.1f}" y="{CARTE_Y + CARTE_H + mm(3.5):.1f}" text-anchor="middle" fill="black" stroke="none"
          font-family="Georgia, serif" font-size="{mm(2.2):.1f}" letter-spacing="3" font-style="italic">
      TRACÉ · CARTE TOPOGRAPHIQUE
    </text>

    <!-- Dossard label -->
    <text x="{DOS_X + dos_w_px/2:.1f}" y="{DOS_Y - mm(2):.1f}" text-anchor="middle" fill="black" stroke="none"
          font-family="Georgia, serif" font-size="{mm(2.5):.1f}" letter-spacing="3">
      DOSSARD
    </text>

    <!-- Rectangle dossard -->
    <rect x="{DOS_X:.1f}" y="{DOS_Y:.1f}" width="{dos_w_px:.1f}" height="{dos_h_px:.1f}" stroke-width="0.8" fill="none"/>

    <!-- Encoches dossard (à 45°) -->
    {enc_hg}
    {enc_hd}
    {enc_bg}
    {enc_bd}

  </g>

  <!-- ═══════════ CALQUE VERT ═══════════ -->
  <g id="calque-vert" stroke="{couleur1}" fill="none">

    <!-- Clip carte -->
    <defs>
      <clipPath id="clip-carte">
        <rect x="{CARTE_X:.1f}" y="{CARTE_Y:.1f}" width="{CARTE_W:.1f}" height="{CARTE_H:.1f}"/>
      </clipPath>
      <clipPath id="clip-profil">
        <rect x="{PROFIL_INNER_X:.1f}" y="{PROFIL_INNER_Y:.1f}" width="{PROFIL_INNER_W:.1f}" height="{PROFIL_INNER_H:.1f}"/>
      </clipPath>
    </defs>

    <g clip-path="url(#clip-carte)">
      <!-- Eau -->
      {osm_eau_svg}
      <!-- Routes -->
      {osm_routes_svg}
      <!-- Chemins / sentiers -->
      {osm_chemins_svg}
      <!-- Tracé GPS -->
      {'<polyline points="' + trace_points_str + f'" stroke="{couleur1}" stroke-width="2.5" fill="none"/>' if trace_points_str else ''}
      <!-- Point départ -->
      {''.join([f'<circle cx="{to_svg_xy(trace_pts[0]["lat"], trace_pts[0]["lon"])[0]:.1f}" cy="{to_svg_xy(trace_pts[0]["lat"], trace_pts[0]["lon"])[1]:.1f}" r="4" stroke="{couleur1}" stroke-width="1.5" fill="none"/>' if trace_pts else ''])}
    </g>

    <!-- Profil altimétrique -->
    <g clip-path="url(#clip-profil)">
      {'<polyline points="' + profil_points_str + f'" stroke="{couleur1}" stroke-width="1.8" fill="none"/>' if profil_points_str else ''}
    </g>

  </g>

  <!-- ═══════════ CALQUE ROUGE ═══════════ -->
  <g id="calque-rouge" stroke="{couleur2}" fill="none">

    <!-- Annotations profil (au-dessus de la courbe) -->
    {annotations_svg}

  </g>

</svg>"""

    return svg
