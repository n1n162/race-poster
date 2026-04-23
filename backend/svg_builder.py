"""
svg_builder.py v2 — Génère le SVG final de l'affiche de course.

Calques Cricut :
  calque-noir    → Stylo noir   : structure, textes, cadres, encoches
  calque-routes  → Stylo noir   : routes
  calque-chemins → Stylo marron : chemins/sentiers
  calque-eau     → Stylo bleu   : rivières/lacs
  calque-trace   → Stylo vert   : tracé GPS + profil altimétrique
  calque-stats   → Stylo rouge  : valeurs stats + annotations profil

Correctifs v2 :
  - Couleurs séparées par type OSM (noir routes, marron chemins, bleu eau)
  - Stats en bandeau horizontal compact (une seule ligne sous le titre)
  - Profil : ratio hauteur/largeur réaliste (exagération ×5, non infini)
  - Dossard : occupe tout l'espace disponible dans la colonne droite
  - Date/lieu repositionnés à droite du titre
"""

import math

MM_TO_PX = 3.7795

FORMATS = {
    "15x20": (150, 200),
    "20x30": (300, 200),
    "a4":    (297, 210),
    "30x40": (400, 300),
}

COUL_ROUTES  = "#222222"
COUL_CHEMINS = "#7B4A1E"
COUL_EAU     = "#1a4fa0"


def mm(v): return v * MM_TO_PX


def latlon_to_mercator(lat, lon):
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
    y = y * 20037508.34 / 180
    return x, y


def build_svg(
    race_data: dict,
    osm_data: dict,
    format_key: str = "30x40",
    couleur_trace: str = "#1a7a1a",
    couleur_stats: str = "#cc1a00",
    dossard_w_mm: float = 210,
    dossard_h_mm: float = 148,
    points_marquants: list = None,
) -> str:

    w_mm, h_mm = FORMATS.get(format_key, (400, 300))
    W = mm(w_mm)
    H = mm(h_mm)

    MARGE    = mm(5)
    INNER_W  = W - 2 * MARGE
    INNER_H  = H - 2 * MARGE

    # ── Répartition verticale ────────────────────────────────────────────────
    TITRE_H  = INNER_H * 0.10
    STATS_H  = mm(10)
    PROFIL_H = INNER_H * 0.28
    MIDDLE_H = INNER_H - TITRE_H - STATS_H - PROFIL_H

    TITRE_Y  = MARGE
    STATS_Y  = MARGE + TITRE_H
    MIDDLE_Y = STATS_Y + STATS_H
    PROFIL_Y = MIDDLE_Y + MIDDLE_H

    # ── Colonnes middle ──────────────────────────────────────────────────────
    COL_LEFT_W  = INNER_W * 0.52
    COL_RIGHT_W = INNER_W * 0.48
    COL_RIGHT_X = MARGE + COL_LEFT_W

    CARTE_X = MARGE
    CARTE_Y = MIDDLE_Y
    CARTE_W = COL_LEFT_W
    CARTE_H = MIDDLE_H

    # ── Dossard : remplit la colonne droite ──────────────────────────────────
    dos_w_px = mm(dossard_w_mm)
    dos_h_px = mm(dossard_h_mm)
    max_dos_w = COL_RIGHT_W - mm(3)
    max_dos_h = MIDDLE_H - mm(6)
    scale = min(1.0, max_dos_w / dos_w_px, max_dos_h / dos_h_px)
    dos_w_px *= scale
    dos_h_px *= scale
    DOS_X = COL_RIGHT_X + (COL_RIGHT_W - dos_w_px) / 2
    DOS_Y = MIDDLE_Y + (MIDDLE_H - dos_h_px) / 2

    # ── Données race ─────────────────────────────────────────────────────────
    nom        = race_data.get("nom", "Trail")
    sous_titre = race_data.get("sous_titre", "")
    date       = race_data.get("date", "")
    lieu       = race_data.get("lieu", "")
    distance   = race_data.get("total_distance_km", 0)
    d_plus     = race_data.get("d_plus", 0)
    temps      = race_data.get("temps", "")
    classement = race_data.get("classement", "")
    profil_pts = race_data.get("profil", [])
    trace_pts  = race_data.get("trace", [])

    # ── Bounding box Mercator ─────────────────────────────────────────────────
    if trace_pts:
        merc   = [latlon_to_mercator(p["lat"], p["lon"]) for p in trace_pts]
        mx_min = min(p[0] for p in merc)
        mx_max = max(p[0] for p in merc)
        my_min = min(p[1] for p in merc)
        my_max = max(p[1] for p in merc)
        span_x = (mx_max - mx_min) or 1
        span_y = (my_max - my_min) or 1
        mg = 0.06
        bbox_m = (mx_min - span_x*mg, my_min - span_y*mg,
                  mx_max + span_x*mg, my_max + span_y*mg)
    else:
        bbox_m = (0, 0, 1, 1)

    bx0, by0, bx1, by1 = bbox_m

    def to_svg_xy(lat, lon):
        x, y = latlon_to_mercator(lat, lon)
        sx = CARTE_X + (x - bx0) / (bx1 - bx0) * CARTE_W
        sy = CARTE_Y + CARTE_H - (y - by0) / (by1 - by0) * CARTE_H
        return sx, sy

    def osm_paths(coords_list):
        paths = []
        for coords in coords_list:
            if not coords:
                continue
            pts = []
            for x, y in coords:
                sx = CARTE_X + (x - bx0) / (bx1 - bx0) * CARTE_W
                sy = CARTE_Y + CARTE_H - (y - by0) / (by1 - by0) * CARTE_H
                pts.append(f"{sx:.1f},{sy:.1f}")
            if pts:
                paths.append("M " + " L ".join(pts))
        return paths

    # ── Profil : ratio réaliste ───────────────────────────────────────────────
    PROFIL_INNER_X = MARGE + mm(10)
    PROFIL_INNER_W = INNER_W - mm(14)
    PROFIL_INNER_Y = PROFIL_Y + mm(11)
    PROFIL_INNER_H = PROFIL_H - mm(16)

    alt_vals = [p["alt"] for p in profil_pts] if profil_pts else [0, 1]
    alt_min  = min(alt_vals)
    alt_max  = max(alt_vals)
    dist_max = profil_pts[-1]["dist_km"] if profil_pts else 1
    dist_m   = dist_max * 1000
    dh_geo   = (alt_max - alt_min) or 1

    # Exagération verticale ×5, plafonnée à PROFIL_INNER_H
    ratio  = dh_geo / dist_m if dist_m > 0 else 0.05
    h_used = min(PROFIL_INNER_H, max(PROFIL_INNER_H * 0.25, PROFIL_INNER_W * ratio * 5))
    profil_offset_y = PROFIL_INNER_H - h_used
    alt_span = dh_geo

    def profil_xy(dist_km, alt):
        px = PROFIL_INNER_X + (dist_km / dist_max) * PROFIL_INNER_W
        py = (PROFIL_INNER_Y + profil_offset_y
              + h_used - ((alt - alt_min) / alt_span) * h_used)
        return px, py

    profil_points_str = " ".join(
        f"{profil_xy(p['dist_km'], p['alt'])[0]:.1f},{profil_xy(p['dist_km'], p['alt'])[1]:.1f}"
        for p in profil_pts
    ) if profil_pts else ""

    # ── Tracé GPS ─────────────────────────────────────────────────────────────
    trace_points_str = ""
    if trace_pts:
        pts = [to_svg_xy(p["lat"], p["lon"]) for p in trace_pts]
        trace_points_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    # ── Encoches dossard ─────────────────────────────────────────────────────
    enc  = mm(9)
    dx1, dy1 = DOS_X, DOS_Y
    dx2, dy2 = DOS_X + dos_w_px, DOS_Y + dos_h_px
    enc_hg = f'<line x1="{dx1:.1f}" y1="{dy1+enc:.1f}" x2="{dx1+enc:.1f}" y2="{dy1:.1f}" stroke="black" stroke-width="1.8"/>'
    enc_hd = f'<line x1="{dx2-enc:.1f}" y1="{dy1:.1f}" x2="{dx2:.1f}" y2="{dy1+enc:.1f}" stroke="black" stroke-width="1.8"/>'
    enc_bg = f'<line x1="{dx1:.1f}" y1="{dy2-enc:.1f}" x2="{dx1+enc:.1f}" y2="{dy2:.1f}" stroke="black" stroke-width="1.8"/>'
    enc_bd = f'<line x1="{dx2-enc:.1f}" y1="{dy2:.1f}" x2="{dx2:.1f}" y2="{dy2-enc:.1f}" stroke="black" stroke-width="1.8"/>'

    # ── Stats bandeau horizontal ──────────────────────────────────────────────
    cell_w   = INNER_W / 4
    fs_label = mm(2.1)
    fs_val   = mm(4.4)

    def stat_band(i, label, valeur, unit=""):
        cx  = MARGE + i * cell_w
        cy  = STATS_Y
        sep = (f'<line x1="{cx:.1f}" y1="{cy+mm(1.5):.1f}" x2="{cx:.1f}" y2="{cy+STATS_H-mm(1.5):.1f}" '
               f'stroke="black" stroke-width="0.4"/>') if i > 0 else ""
        val_txt = f"{valeur}{' ' + unit if unit else ''}"
        return f"""{sep}
    <text x="{cx + cell_w/2:.1f}" y="{cy + mm(3.2):.1f}" text-anchor="middle" fill="black" stroke="none"
          font-family="Georgia, serif" font-size="{fs_label:.1f}" letter-spacing="1">{label}</text>
    <text x="{cx + cell_w/2:.1f}" y="{cy + mm(8.0):.1f}" text-anchor="middle" fill="{couleur_stats}" stroke="none"
          font-family="'Palatino Linotype', Palatino, Georgia, serif" font-size="{fs_val:.1f}" font-weight="bold">{val_txt}</text>"""

    stats_svg  = stat_band(0, "DISTANCE",   f"{distance:.1f}", "km")
    stats_svg += stat_band(1, "DÉNIVELÉ +", f"{d_plus:,}".replace(",", " "), "m")
    stats_svg += stat_band(2, "TEMPS",       temps)
    stats_svg += stat_band(3, "CLASSEMENT",  classement)

    # ── Annotations profil ────────────────────────────────────────────────────
    annotations_svg = ""
    if points_marquants:
        for pt in points_marquants:
            d       = pt.get("dist_km", 0)
            a       = pt.get("alt", alt_min)
            nom_pt  = pt.get("nom", "")
            type_pt = pt.get("type", "")
            px, py  = profil_xy(d, a)
            ann_y   = PROFIL_INNER_Y + profil_offset_y - mm(1.5)
            ligne2  = f"{type_pt} · " if type_pt else ""
            annotations_svg += f"""
    <line x1="{px:.1f}" y1="{py:.1f}" x2="{px:.1f}" y2="{ann_y:.1f}"
          stroke="{couleur_stats}" stroke-width="0.7" stroke-dasharray="2,2"/>
    <text x="{px:.1f}" y="{ann_y - mm(0.8):.1f}" text-anchor="middle" fill="{couleur_stats}" stroke="none"
          font-family="Georgia, serif" font-size="{mm(2.4):.1f}" font-style="italic">{nom_pt}</text>
    <text x="{px:.1f}" y="{ann_y - mm(3.5):.1f}" text-anchor="middle" fill="{couleur_stats}" stroke="none"
          font-family="Georgia, serif" font-size="{mm(2.0):.1f}">{ligne2}km {d:.1f} · {a:.0f}m</text>"""

    # ── OSM SVG strings ───────────────────────────────────────────────────────
    osm_routes_svg = ""
    for rtype, rdata in (osm_data.get("routes") or {}).items():
        lw = rdata["largeur"]
        for path in osm_paths(rdata["coords"]):
            osm_routes_svg += f'<path d="{path}" stroke="{COUL_ROUTES}" stroke-width="{lw:.2f}" fill="none" opacity="0.75"/>\n'

    osm_chemins_svg = ""
    for ctype, cdata in (osm_data.get("chemins") or {}).items():
        lw   = cdata["largeur"]
        dash = ' stroke-dasharray="3,3"' if cdata.get("dash") else ""
        for path in osm_paths(cdata["coords"]):
            osm_chemins_svg += f'<path d="{path}" stroke="{COUL_CHEMINS}" stroke-width="{lw:.2f}" fill="none" opacity="0.85"{dash}/>\n'

    osm_eau_svg = ""
    for coords in (osm_data.get("eau_polygones") or []):
        for path in osm_paths([coords]):
            osm_eau_svg += f'<path d="{path}" stroke="{COUL_EAU}" stroke-width="1.0" fill="none" opacity="0.85"/>\n'
    for coords in (osm_data.get("eau_lignes") or []):
        for path in osm_paths([coords]):
            osm_eau_svg += f'<path d="{path}" stroke="{COUL_EAU}" stroke-width="0.9" fill="none" opacity="0.80"/>\n'

    # ── Typographie adaptative ────────────────────────────────────────────────
    titre_fs    = min(mm(8.5), INNER_W / max(len(nom), 1) * 1.4)
    ss_titre_fs = min(mm(3.8), INNER_W / max(len(sous_titre or " "), 1) * 1.1)

    # ── Graduations profil ────────────────────────────────────────────────────
    n_grad   = min(10, int(dist_max))
    grad_svg = ""
    gy_base  = PROFIL_INNER_Y + PROFIL_INNER_H

    for i in range(n_grad + 1):
        d_km   = dist_max * i / n_grad
        gx, _  = profil_xy(d_km, alt_min)
        grad_svg += (f'<line x1="{gx:.1f}" y1="{gy_base:.1f}" x2="{gx:.1f}" y2="{gy_base+mm(1.5):.1f}" '
                     f'stroke="black" stroke-width="0.6"/>')
        grad_svg += (f'<text x="{gx:.1f}" y="{gy_base+mm(3.5):.1f}" text-anchor="middle" fill="black" '
                     f'font-family="Georgia, serif" font-size="{mm(2.1):.1f}">{d_km:.0f}</text>')

    alt_lx    = PROFIL_INNER_X - mm(2)
    py_top, _ = profil_xy(0, alt_max)
    grad_svg += (f'<text x="{alt_lx:.1f}" y="{py_top:.1f}" text-anchor="end" fill="black" '
                 f'font-family="Georgia, serif" font-size="{mm(2.1):.1f}">{alt_max:.0f}m</text>')
    grad_svg += (f'<text x="{alt_lx:.1f}" y="{gy_base:.1f}" text-anchor="end" fill="black" '
                 f'font-family="Georgia, serif" font-size="{mm(2.1):.1f}">{alt_min:.0f}m</text>')
    grad_svg += (f'<text x="{PROFIL_INNER_X + PROFIL_INNER_W/2:.1f}" y="{gy_base+mm(6):.1f}" '
                 f'text-anchor="middle" fill="black" font-family="Georgia, serif" '
                 f'font-size="{mm(2.1):.1f}" letter-spacing="2">km</text>')

    # ── Point départ sur la carte ─────────────────────────────────────────────
    depart_svg = ""
    if trace_pts:
        sx, sy = to_svg_xy(trace_pts[0]["lat"], trace_pts[0]["lon"])
        r1, r2 = mm(2.2), mm(0.9)
        depart_svg = (f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{r1:.1f}" '
                      f'stroke="{couleur_trace}" stroke-width="1.5" fill="none"/>'
                      f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{r2:.1f}" '
                      f'stroke="{couleur_trace}" stroke-width="1" fill="none"/>')

    sep_stats_y = STATS_Y + STATS_H

    # ═══════════════════════════════════════════════════════════════════════
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {W:.1f} {H:.1f}"
     width="{w_mm}mm" height="{h_mm}mm">

  <!-- {nom} | {format_key} | {w_mm}x{h_mm}mm -->
  <defs>
    <clipPath id="clip-carte">
      <rect x="{CARTE_X:.1f}" y="{CARTE_Y:.1f}" width="{CARTE_W:.1f}" height="{CARTE_H:.1f}"/>
    </clipPath>
    <clipPath id="clip-profil">
      <rect x="{PROFIL_INNER_X:.1f}" y="{PROFIL_INNER_Y:.1f}" width="{PROFIL_INNER_W:.1f}" height="{PROFIL_INNER_H:.1f}"/>
    </clipPath>
  </defs>

  <!-- ═══ CALQUE NOIR ═══ -->
  <g id="calque-noir" stroke="black" fill="none">
    <rect x="{MARGE:.1f}" y="{MARGE:.1f}" width="{INNER_W:.1f}" height="{INNER_H:.1f}" stroke-width="2.0" fill="none"/>
    <rect x="{MARGE+mm(1.5):.1f}" y="{MARGE+mm(1.5):.1f}" width="{INNER_W-mm(3):.1f}" height="{INNER_H-mm(3):.1f}" stroke-width="0.4" fill="none"/>

    <text x="{W/2:.1f}" y="{TITRE_Y + TITRE_H*0.52:.1f}" text-anchor="middle" fill="black" stroke="none"
          font-family="'Palatino Linotype', Palatino, Georgia, serif"
          font-size="{titre_fs:.1f}" font-weight="bold" letter-spacing="3">{nom.upper()}</text>

    <text x="{MARGE+mm(4):.1f}" y="{TITRE_Y + TITRE_H*0.82:.1f}" text-anchor="start" fill="black" stroke="none"
          font-family="Georgia, serif" font-size="{ss_titre_fs:.1f}" font-style="italic" letter-spacing="4">{sous_titre}</text>

    <text x="{W-MARGE-mm(4):.1f}" y="{TITRE_Y + TITRE_H*0.82:.1f}" text-anchor="end" fill="black" stroke="none"
          font-family="Georgia, serif" font-size="{mm(2.5):.1f}" letter-spacing="1">{date}  ·  {lieu}</text>

    <line x1="{MARGE+mm(3):.1f}" y1="{TITRE_Y+TITRE_H*0.92:.1f}" x2="{W-MARGE-mm(3):.1f}" y2="{TITRE_Y+TITRE_H*0.92:.1f}" stroke-width="0.7"/>

    <line x1="{MARGE:.1f}" y1="{STATS_Y:.1f}" x2="{W-MARGE:.1f}" y2="{STATS_Y:.1f}" stroke-width="0.4"/>
    <line x1="{MARGE:.1f}" y1="{sep_stats_y:.1f}" x2="{W-MARGE:.1f}" y2="{sep_stats_y:.1f}" stroke-width="0.5"/>

    {stats_svg}

    <line x1="{COL_RIGHT_X:.1f}" y1="{MIDDLE_Y+mm(2):.1f}" x2="{COL_RIGHT_X:.1f}" y2="{MIDDLE_Y+MIDDLE_H-mm(2):.1f}" stroke-width="0.5" stroke-dasharray="4,3"/>
    <rect x="{CARTE_X:.1f}" y="{CARTE_Y:.1f}" width="{CARTE_W:.1f}" height="{CARTE_H:.1f}" stroke-width="0.5" fill="none"/>

    <line x1="{MARGE:.1f}" y1="{PROFIL_Y:.1f}" x2="{W-MARGE:.1f}" y2="{PROFIL_Y:.1f}" stroke-width="0.7"/>
    <line x1="{MARGE:.1f}" y1="{PROFIL_Y+mm(0.7):.1f}" x2="{W-MARGE:.1f}" y2="{PROFIL_Y+mm(0.7):.1f}" stroke-width="0.25"/>

    <text x="{W/2:.1f}" y="{PROFIL_Y+mm(5):.1f}" text-anchor="middle" fill="black" stroke="none"
          font-family="Georgia, serif" font-size="{mm(2.3):.1f}" letter-spacing="4">PROFIL ALTIMÉTRIQUE</text>

    <rect x="{PROFIL_INNER_X:.1f}" y="{PROFIL_INNER_Y:.1f}" width="{PROFIL_INNER_W:.1f}" height="{PROFIL_INNER_H:.1f}" stroke-width="0.4" fill="none"/>
    <line x1="{PROFIL_INNER_X:.1f}" y1="{PROFIL_INNER_Y+PROFIL_INNER_H:.1f}"
          x2="{PROFIL_INNER_X+PROFIL_INNER_W:.1f}" y2="{PROFIL_INNER_Y+PROFIL_INNER_H:.1f}" stroke-width="0.8"/>

    {grad_svg}

    <text x="{DOS_X+dos_w_px/2:.1f}" y="{DOS_Y-mm(2.5):.1f}" text-anchor="middle" fill="black" stroke="none"
          font-family="Georgia, serif" font-size="{mm(2.3):.1f}" letter-spacing="3">DOSSARD</text>
    <rect x="{DOS_X:.1f}" y="{DOS_Y:.1f}" width="{dos_w_px:.1f}" height="{dos_h_px:.1f}" stroke-width="0.8" fill="none"/>
    {enc_hg}
    {enc_hd}
    {enc_bg}
    {enc_bd}
  </g>

  <!-- ═══ CALQUE ROUTES (noir) ═══ -->
  <g id="calque-routes" clip-path="url(#clip-carte)">
    {osm_routes_svg}
  </g>

  <!-- ═══ CALQUE CHEMINS (marron #7B4A1E) ═══ -->
  <g id="calque-chemins" clip-path="url(#clip-carte)">
    {osm_chemins_svg}
  </g>

  <!-- ═══ CALQUE EAU (bleu #1a4fa0) ═══ -->
  <g id="calque-eau" clip-path="url(#clip-carte)">
    {osm_eau_svg}
  </g>

  <!-- ═══ CALQUE TRACE + PROFIL ═══ -->
  <g id="calque-trace" fill="none">
    <g clip-path="url(#clip-carte)">
      {'<polyline points="' + trace_points_str + f'" stroke="{couleur_trace}" stroke-width="2.5" fill="none"/>' if trace_points_str else ''}
      {depart_svg}
    </g>
    <g clip-path="url(#clip-profil)">
      {'<polyline points="' + profil_points_str + f'" stroke="{couleur_trace}" stroke-width="1.8" fill="none"/>' if profil_points_str else ''}
    </g>
  </g>

  <!-- ═══ CALQUE STATS + ANNOTATIONS (rouge) ═══ -->
  <g id="calque-stats" fill="none">
    {annotations_svg}
  </g>

</svg>"""

    return svg
