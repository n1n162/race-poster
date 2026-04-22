from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import uuid
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

from gpx_parser import parse_gpx
from osm_fetcher import fetch_osm_geometries, PRESETS
from svg_builder import build_svg

app = FastAPI(title="Race Poster API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=2)

# Stockage en mémoire des jobs (pour usage léger famille/amis)
jobs: dict = {}


# ── Modèles ──────────────────────────────────────────────────────────────────

class PointMarquant(BaseModel):
    dist_km: float
    alt: float
    nom: str
    type: Optional[str] = ""

class GenerateRequest(BaseModel):
    # Données GPX (renvoyées par /parse-gpx)
    gpx_token: str

    # Infos saisies par l'utilisateur
    nom: str
    sous_titre: Optional[str] = ""
    date: Optional[str] = ""
    lieu: Optional[str] = ""
    temps: Optional[str] = ""
    classement: Optional[str] = ""

    # Dossard
    dossard_largeur_mm: float = 210
    dossard_hauteur_mm: float = 148

    # Format cadre
    format_key: str = "30x40"   # "15x20" | "20x30" | "a4" | "30x40"

    # Couleurs stylos
    couleur_vert: str = "#1a7a1a"
    couleur_rouge: str = "#cc1a00"

    # Niveau de détail OSM
    osm_preset: str = "trail"    # "trail" | "standard" | "detaille"
    osm_custom: Optional[dict] = None

    # Points marquants (optionnels, saisis manuellement)
    points_marquants: Optional[List[PointMarquant]] = None


# ── Stockage temporaire GPX parsé ────────────────────────────────────────────
gpx_cache: dict = {}


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "Race Poster API OK"}


@app.post("/parse-gpx")
async def parse_gpx_route(file: UploadFile = File(...)):
    """
    Étape 1 : Upload et parsing du GPX.
    Retourne les stats de la course + un token pour la génération.
    """
    if not file.filename.lower().endswith(".gpx"):
        raise HTTPException(400, "Fichier .gpx requis")

    content = await file.read()
    try:
        data = parse_gpx(content)
    except Exception as e:
        raise HTTPException(422, f"Erreur parsing GPX : {str(e)}")

    token = str(uuid.uuid4())
    gpx_cache[token] = data

    return {
        "token": token,
        "nom_gpx": data.get("nom_gpx"),
        "total_distance_km": data["total_distance_km"],
        "d_plus": data["d_plus"],
        "d_minus": data["d_minus"],
        "alt_min": data["alt_min"],
        "alt_max": data["alt_max"],
        "nb_points": data["nb_points_total"],
        "profil": data["profil"],   # pour prévisualisation profil côté frontend
    }


@app.post("/generate")
async def generate_poster(req: GenerateRequest, background_tasks: BackgroundTasks):
    """
    Étape 2 : Lance la génération complète (OSM + SVG).
    Retourne un job_id pour polling.
    """
    gpx_data = gpx_cache.get(req.gpx_token)
    if not gpx_data:
        raise HTTPException(404, "Token GPX invalide ou expiré. Re-uploadez le fichier.")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "progress": 0, "svg": None, "error": None}

    background_tasks.add_task(_run_generation, job_id, gpx_data, req)
    return {"job_id": job_id}


async def _run_generation(job_id: str, gpx_data: dict, req: GenerateRequest):
    try:
        jobs[job_id]["status"] = "osm"
        jobs[job_id]["progress"] = 10

        # OSM en thread (osmnx bloquant)
        loop = asyncio.get_event_loop()
        osm_cfg = req.osm_custom if req.osm_custom else req.osm_preset
        osm_data = await loop.run_in_executor(
            executor,
            fetch_osm_geometries,
            gpx_data["bbox"],
            osm_cfg,
            1.5
        )

        jobs[job_id]["status"] = "svg"
        jobs[job_id]["progress"] = 80

        # Fusion données race
        race_data = {**gpx_data}
        race_data["nom"] = req.nom
        race_data["sous_titre"] = req.sous_titre or ""
        race_data["date"] = req.date or ""
        race_data["lieu"] = req.lieu or ""
        race_data["temps"] = req.temps or ""
        race_data["classement"] = req.classement or ""

        points_marquants = [p.dict() for p in req.points_marquants] if req.points_marquants else []

        svg = build_svg(
            race_data=race_data,
            osm_data=osm_data,
            format_key=req.format_key,
            couleur1=req.couleur_vert,
            couleur2=req.couleur_rouge,
            dossard_w_mm=req.dossard_largeur_mm,
            dossard_h_mm=req.dossard_hauteur_mm,
            points_marquants=points_marquants,
        )

        jobs[job_id]["status"] = "done"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["svg"] = svg

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.get("/job/{job_id}")
def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job introuvable")
    return {
        "status": job["status"],
        "progress": job["progress"],
        "error": job["error"],
        "has_svg": job["svg"] is not None,
    }


@app.get("/job/{job_id}/svg")
def get_job_svg(job_id: str):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(404, "SVG non disponible")
    return Response(
        content=job["svg"],
        media_type="image/svg+xml",
        headers={"Content-Disposition": "attachment; filename=affiche_course.svg"}
    )
