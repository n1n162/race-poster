# Race Poster · Générateur d'affiche de course

Crée des affiches SVG de tes courses trail/running, optimisées pour le tracé au **stylo Cricut**.

## Stack

| Partie | Techno | Hébergement |
|--------|--------|-------------|
| Frontend | React + Vite | **Vercel** |
| Backend | FastAPI + Python | **Render.com** (gratuit) |

---

## Structure

```
race-poster/
├── frontend/          → React app (Vercel)
│   ├── src/
│   │   ├── App.jsx
│   │   └── index.css
│   ├── vite.config.js
│   └── package.json
├── backend/           → FastAPI (Render.com)
│   ├── main.py
│   ├── gpx_parser.py
│   ├── osm_fetcher.py
│   ├── svg_builder.py
│   ├── requirements.txt
│   └── render.yaml
└── vercel.json
```

---

## Déploiement

### 1. Créer le repo GitHub

```bash
git init
git add .
git commit -m "init race-poster"
git remote add origin https://github.com/TON_USER/race-poster.git
git push -u origin main
```

### 2. Déployer le backend sur Render.com

1. Aller sur [render.com](https://render.com) → **New → Web Service**
2. Connecter le repo GitHub
3. **Root Directory** : `backend`
4. **Build Command** : `pip install -r requirements.txt`
5. **Start Command** : `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. **Plan** : Free
7. Cliquer **Create Web Service**
8. Copier l'URL générée (ex: `https://race-poster-api.onrender.com`)

### 3. Déployer le frontend sur Vercel

1. Aller sur [vercel.com](https://vercel.com) → **New Project**
2. Importer le repo GitHub
3. **Framework Preset** : Vite
4. **Root Directory** : `frontend`
5. **Ajouter la variable d'environnement** :
   - Nom : `VITE_API_URL`
   - Valeur : `https://race-poster-api.onrender.com` (URL Render)
6. Cliquer **Deploy**

---

## Fonctionnement

```
Utilisateur
  │
  ├─ Upload .gpx → /parse-gpx → stats instantanées
  │
  ├─ Remplit le formulaire (nom, date, lieu, temps, classement, dossard, format…)
  │
  └─ Clique "Générer" → /generate
       │
       ├─ Télécharge les données OSM (routes, sentiers, eau) ~1-2 min
       │
       └─ Génère le SVG final → téléchargement
```

## Calques SVG Cricut

Le SVG produit contient **3 calques** :

| ID | Stylo | Contenu |
|----|-------|---------|
| `calque-noir` | Stylo 1 (noir) | Cadres, titres, axes, encoches dossard |
| `calque-vert` | Stylo 2 (vert) | Carte OSM + tracé GPS + profil altimétrique |
| `calque-rouge` | Stylo 3 (rouge) | Valeurs stats + annotations profil |

Dans **Cricut Design Space** :
1. Importer le SVG
2. Les calques apparaissent séparément
3. Affecter un stylo à chaque calque
4. Lancer le tracé

## Formats supportés

| Format | Dimensions | Orientation Cricut |
|--------|------------|-------------------|
| 15×20 cm | 150×200 mm | Portrait |
| 20×30 cm | 300×200 mm | Paysage |
| A4 | 297×210 mm | Paysage |
| 30×40 cm | 400×300 mm | Paysage |

Tous dans les limites Cricut : **60×30 cm**.

## Dossard

L'utilisateur saisit la taille réelle de son dossard (largeur × hauteur en mm).
L'affiche prévoit un espace avec **4 encoches à 45°** aux coins pour glisser le dossard physique.

- Coins haut : `/` et `\`
- Coins bas : `\` et `/`

---

## Développement local

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (autre terminal)
cd frontend
npm install
cp .env.example .env.local   # éditer si besoin
npm run dev
```

Frontend : http://localhost:3000  
API docs : http://localhost:8000/docs
