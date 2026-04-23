import { useState, useCallback, useRef } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const FORMATS = [
  { key: '15x20', label: '15×20 cm', desc: 'petit cadre portrait' },
  { key: '20x30', label: '20×30 cm', desc: 'cadre paysage' },
  { key: 'a4',    label: 'A4 · 21×29.7', desc: 'format standard' },
  { key: '30x40', label: '30×40 cm', desc: 'grand cadre' },
]

const OSM_PRESETS = [
  { key: 'trail',    label: '🏃 Trail',    desc: 'Sentiers + eau' },
  { key: 'standard', label: '🗺️ Standard', desc: 'Routes + sentiers + eau' },
  { key: 'detaille', label: '🔍 Détaillé', desc: 'Tout afficher' },
]

const OSM_ROUTES = [
  { key: 'primary',       label: 'Routes principales' },
  { key: 'secondary',     label: 'Routes secondaires' },
  { key: 'tertiary',      label: 'Routes tertiaires' },
  { key: 'residential',   label: 'Rues résidentielles' },
  { key: 'unclassified',  label: 'Voies non classées' },
]

const OSM_CHEMINS = [
  { key: 'track',     label: 'Pistes / tracks' },
  { key: 'path',      label: 'Sentiers' },
  { key: 'footway',   label: 'Chemins piétons' },
  { key: 'bridleway', label: 'Chemins cavaliers' },
  { key: 'cycleway',  label: 'Pistes cyclables' },
  { key: 'steps',     label: 'Escaliers' },
]

const DEFAULT_OSM_CUSTOM = {
  routes: ['primary', 'secondary'],
  chemins: ['track', 'path', 'footway'],
  eau: true,
}

function StatBadge({ val, label }) {
  return (
    <div className="gpx-stat">
      <div className="val">{val}</div>
      <div className="lbl">{label}</div>
    </div>
  )
}

function Spinner() {
  return <span style={{ display: 'inline-block', animation: 'pulse 1s infinite' }}>⏳</span>
}

export default function App() {
  // ── État GPX ──
  const [gpxFile, setGpxFile] = useState(null)
  const [gpxStats, setGpxStats] = useState(null)
  const [gpxToken, setGpxToken] = useState(null)
  const [gpxLoading, setGpxLoading] = useState(false)
  const [gpxError, setGpxError] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  // ── Formulaire race ──
  const [nom, setNom] = useState('')
  const [sousTitre, setSousTitre] = useState('')
  const [date, setDate] = useState('')
  const [lieu, setLieu] = useState('')
  const [temps, setTemps] = useState('')
  const [classement, setClassement] = useState('')

  // ── Dossard ──
  const [dosW, setDosW] = useState(210)
  const [dosH, setDosH] = useState(148)

  // ── Format ──
  const [format, setFormat] = useState('30x40')

  // ── Couleurs ──
  const [coulNoir, setCoulNoir] = useState('#111111')
  const [coulVert, setCoulVert] = useState('#1a7a1a')
  const [coulRouge, setCoulRouge] = useState('#cc1a00')

  // ── OSM ──
  const [osmPreset, setOsmPreset] = useState('trail')
  const [osmAdvanced, setOsmAdvanced] = useState(false)
  const [osmCustom, setOsmCustom] = useState(DEFAULT_OSM_CUSTOM)

  // ── Points marquants ──
  const [points, setPoints] = useState([])

  // ── Génération ──
  const [jobId, setJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState(null)
  const [jobProgress, setJobProgress] = useState(0)
  const [svgUrl, setSvgUrl] = useState(null)
  const [svgContent, setSvgContent] = useState(null)
  const pollRef = useRef(null)

  // ─────────────────────────────────────────────────────────────
  // Upload GPX
  // ─────────────────────────────────────────────────────────────
  const handleGpxFile = useCallback(async (file) => {
    if (!file || !file.name.endsWith('.gpx')) {
      setGpxError('Fichier .gpx requis')
      return
    }
    setGpxFile(file)
    setGpxError(null)
    setGpxLoading(true)
    setSvgUrl(null)
    setSvgContent(null)
    setJobStatus(null)

    const fd = new FormData()
    fd.append('file', file)

    try {
      const res = await fetch(`${API}/parse-gpx`, { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Erreur parsing GPX')
      setGpxStats(data)
      setGpxToken(data.token)
      // Toujours mettre à jour le nom depuis le GPX (nouveau fichier = nouveau nom)
      if (data.nom_gpx) setNom(data.nom_gpx)
      // Pré-remplir les points marquants extraits du GPX
      if (data.points_marquants && data.points_marquants.length > 0) {
        setPoints(data.points_marquants.map(p => ({
          dist_km: String(p.dist_km),
          alt: String(p.alt),
          nom: p.nom || '',
          type: p.type || '',
          source: p.source || 'auto',
        })))
      } else {
        setPoints([])
      }
    } catch (e) {
      setGpxError(e.message)
    } finally {
      setGpxLoading(false)
    }
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    handleGpxFile(file)
  }, [handleGpxFile])

  // ─────────────────────────────────────────────────────────────
  // OSM custom toggles
  // ─────────────────────────────────────────────────────────────
  const toggleOsmRoutes = (key) => {
    setOsmCustom(prev => {
      const routes = prev.routes.includes(key)
        ? prev.routes.filter(r => r !== key)
        : [...prev.routes, key]
      return { ...prev, routes }
    })
  }

  const toggleOsmChemins = (key) => {
    setOsmCustom(prev => {
      const chemins = prev.chemins.includes(key)
        ? prev.chemins.filter(c => c !== key)
        : [...prev.chemins, key]
      return { ...prev, chemins }
    })
  }

  // ─────────────────────────────────────────────────────────────
  // Points marquants
  // ─────────────────────────────────────────────────────────────
  const addPoint = () => setPoints(p => [...p, { dist_km: '', alt: '', nom: '', type: '' }])
  const removePoint = (i) => setPoints(p => p.filter((_, j) => j !== i))
  const updatePoint = (i, field, val) => {
    setPoints(p => p.map((pt, j) => j === i ? { ...pt, [field]: val } : pt))
  }

  // ─────────────────────────────────────────────────────────────
  // Génération
  // ─────────────────────────────────────────────────────────────
  const startGeneration = async () => {
    if (!gpxToken) return

    setSvgUrl(null)
    setSvgContent(null)
    setJobStatus('pending')
    setJobProgress(0)

    const body = {
      gpx_token: gpxToken,
      nom, sous_titre: sousTitre, date, lieu, temps, classement,
      dossard_largeur_mm: parseFloat(dosW),
      dossard_hauteur_mm: parseFloat(dosH),
      format_key: format,
      couleur_trace: coulVert,
      couleur_stats: coulRouge,
      osm_preset: osmAdvanced ? 'custom' : osmPreset,
      osm_custom: osmAdvanced ? osmCustom : null,
      points_marquants: points
        .filter(p => p.dist_km !== '' && p.alt !== '')
        .map(p => ({
          dist_km: parseFloat(p.dist_km),
          alt: parseFloat(p.alt),
          nom: p.nom,
          type: p.type,
        })),
    }

    try {
      const res = await fetch(`${API}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Erreur génération')
      setJobId(data.job_id)
      pollJob(data.job_id)
    } catch (e) {
      setJobStatus('error')
      console.error(e)
    }
  }

  const pollJob = (id) => {
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API}/job/${id}`)
        const data = await res.json()
        setJobStatus(data.status)
        setJobProgress(data.progress)

        if (data.status === 'done') {
          clearInterval(pollRef.current)
          // Récupère le SVG
          const svgRes = await fetch(`${API}/job/${id}/svg`)
          const svgText = await svgRes.text()
          setSvgContent(svgText)
          const blob = new Blob([svgText], { type: 'image/svg+xml' })
          setSvgUrl(URL.createObjectURL(blob))
        }

        if (data.status === 'error') {
          clearInterval(pollRef.current)
        }
      } catch (e) {
        clearInterval(pollRef.current)
        setJobStatus('error')
      }
    }, 2000)
  }

  // ─────────────────────────────────────────────────────────────
  // Vérification dossard
  // ─────────────────────────────────────────────────────────────
  const formatDims = FORMATS.find(f => f.key === format)
  const [fw, fh] = formatDims?.key === 'a4'
    ? [297, 210]
    : formatDims?.label.match(/(\d+)×(\d+)/)?.slice(1).map(Number) || [400, 300]

  const dossTropGrand = dosW > fw * 0.38 || dosH > fh * 0.55

  // ─────────────────────────────────────────────────────────────
  // Labels état génération
  // ─────────────────────────────────────────────────────────────
  const statusLabels = {
    pending: 'Initialisation…',
    osm: '🗺️ Téléchargement des données cartographiques OSM… (peut prendre 1-2 min)',
    svg: '🎨 Génération du SVG…',
    done: '✅ Affiche générée !',
    error: '❌ Une erreur est survenue',
  }

  const canGenerate = gpxToken && nom && !gpxLoading

  return (
    <div className="app">
      <header className="app-header">
        <h1>Race Poster</h1>
        <span>Générateur d'affiche de course · Cricut &amp; SVG</span>
      </header>

      <div className="app-body">

        {/* ══ PANNEAU FORMULAIRE ══ */}
        <aside className="panel">

          {/* GPX Upload */}
          <div className="section">
            <div className="section-title">1 · Fichier GPX</div>

            <div
              className={`upload-zone ${gpxFile ? 'loaded' : ''} ${dragOver ? 'drag-over' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
            >
              <input
                type="file"
                accept=".gpx"
                onChange={(e) => handleGpxFile(e.target.files[0])}
              />
              <span className="upload-icon">{gpxLoading ? '⏳' : gpxFile ? '✅' : '📁'}</span>
              <p>{gpxLoading
                ? 'Analyse du GPX…'
                : gpxFile
                  ? gpxFile.name
                  : 'Glisser le fichier .gpx ici ou cliquer'
              }</p>
            </div>

            {gpxError && <div className="alert">{gpxError}</div>}

            {gpxStats && (
              <div className="gpx-stats fade-in">
                <StatBadge val={`${gpxStats.total_distance_km} km`} label="Distance" />
                <StatBadge val={`${gpxStats.d_plus} m`} label="Dénivelé +" />
                <StatBadge val={`${gpxStats.alt_min}–${gpxStats.alt_max} m`} label="Alt." />
              </div>
            )}
          </div>

          {/* Infos course */}
          <div className="section">
            <div className="section-title">2 · Informations course</div>

            <div className="field">
              <label>Nom de la course *</label>
              <input value={nom} onChange={e => setNom(e.target.value)} placeholder="Trail du Lac de Paladru" />
            </div>

            <div className="field">
              <label>Sous-titre</label>
              <input value={sousTitre} onChange={e => setSousTitre(e.target.value)} placeholder="Les Hauts du Lac" />
            </div>

            <div className="field-row">
              <div className="field">
                <label>Date</label>
                <input value={date} onChange={e => setDate(e.target.value)} placeholder="12 avril 2025" />
              </div>
              <div className="field">
                <label>Lieu</label>
                <input value={lieu} onChange={e => setLieu(e.target.value)} placeholder="Charavines, Isère" />
              </div>
            </div>

            <div className="field-row">
              <div className="field">
                <label>Temps réalisé</label>
                <input value={temps} onChange={e => setTemps(e.target.value)} placeholder="4h12'38&quot;" />
              </div>
              <div className="field">
                <label>Classement</label>
                <input value={classement} onChange={e => setClassement(e.target.value)} placeholder="47e / 312" />
              </div>
            </div>
          </div>

          {/* Dossard */}
          <div className="section">
            <div className="section-title">3 · Dossard</div>
            <div className="field-row">
              <div className="field">
                <label>Largeur (mm)</label>
                <input type="number" value={dosW} onChange={e => setDosW(e.target.value)} min="50" max="300" />
              </div>
              <div className="field">
                <label>Hauteur (mm)</label>
                <input type="number" value={dosH} onChange={e => setDosH(e.target.value)} min="50" max="300" />
              </div>
            </div>
            {dossTropGrand && (
              <div className="alert">
                ⚠️ Le dossard ({dosW}×{dosH} mm) est trop grand pour ce format d'affiche. Il sera réduit automatiquement.
              </div>
            )}
          </div>

          {/* Format cadre */}
          <div className="section">
            <div className="section-title">4 · Format d'affiche</div>
            <div className="field">
              <label>Format cadre</label>
              <select value={format} onChange={e => setFormat(e.target.value)}>
                {FORMATS.map(f => (
                  <option key={f.key} value={f.key}>{f.label} — {f.desc}</option>
                ))}
              </select>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text2)' }}>
              Tous les formats sont dans les limites Cricut 60×30 cm
            </p>
          </div>

          {/* Couleurs stylos */}
          <div className="section">
            <div className="section-title">5 · Couleurs stylos</div>
            <div className="color-row">
              <div className="color-field">
                <label>⬛ Stylo 1 — Noir</label>
                <input type="color" value={coulNoir} onChange={e => setCoulNoir(e.target.value)} />
              </div>
              <div className="color-field">
                <label>🟢 Tracé + Profil</label>
                <input type="color" value={coulVert} onChange={e => setCoulVert(e.target.value)} />
              </div>
              <div className="color-field">
                <label>🔴 Stats + Annotations</label>
                <input type="color" value={coulRouge} onChange={e => setCoulRouge(e.target.value)} />
              </div>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text2)' }}>
              Routes = noir · Sentiers = marron · Eau = bleu (couleurs fixes dans le SVG)
            </p>
          </div>

          {/* Niveau de détail OSM */}
          <div className="section">
            <div className="section-title">6 · Carte OSM</div>

            <div className="preset-tabs">
              {OSM_PRESETS.map(p => (
                <button
                  key={p.key}
                  className={`preset-tab ${osmPreset === p.key && !osmAdvanced ? 'active' : ''}`}
                  onClick={() => { setOsmPreset(p.key); setOsmAdvanced(false) }}
                  title={p.desc}
                >
                  {p.label}
                </button>
              ))}
            </div>

            <button
              className={`preset-tab ${osmAdvanced ? 'active' : ''}`}
              style={{ width: '100%', textAlign: 'left', padding: '8px 12px' }}
              onClick={() => setOsmAdvanced(v => !v)}
            >
              ⚙️ Mode avancé {osmAdvanced ? '▲' : '▼'}
            </button>

            {osmAdvanced && (
              <div className="osm-advanced fade-in">
                <p style={{ fontSize: '0.75rem', color: 'var(--text2)', marginBottom: 4 }}>Routes</p>
                {OSM_ROUTES.map(r => (
                  <label key={r.key} className="osm-toggle">
                    <input
                      type="checkbox"
                      checked={osmCustom.routes.includes(r.key)}
                      onChange={() => toggleOsmRoutes(r.key)}
                    />
                    <span>{r.label}</span>
                  </label>
                ))}
                <p style={{ fontSize: '0.75rem', color: 'var(--text2)', marginTop: 8, marginBottom: 4 }}>Chemins & sentiers</p>
                {OSM_CHEMINS.map(c => (
                  <label key={c.key} className="osm-toggle">
                    <input
                      type="checkbox"
                      checked={osmCustom.chemins.includes(c.key)}
                      onChange={() => toggleOsmChemins(c.key)}
                    />
                    <span>{c.label}</span>
                  </label>
                ))}
                <label className="osm-toggle" style={{ marginTop: 8 }}>
                  <input
                    type="checkbox"
                    checked={osmCustom.eau}
                    onChange={() => setOsmCustom(prev => ({ ...prev, eau: !prev.eau }))}
                  />
                  <span>Rivières, lacs, plans d'eau</span>
                </label>
              </div>
            )}
          </div>

          {/* Points marquants */}
          <div className="section">
            <div className="section-title">7 · Points marquants (optionnel)</div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text2)' }}>
              ⛰ auto-détectés depuis le GPX · 📍 waypoints nommés du GPX · modifiables
            </p>

            <div className="points-list">
              {points.map((pt, i) => (
                <div key={i} className="point-item">
                  <input
                    placeholder="Nom"
                    value={pt.nom}
                    onChange={e => updatePoint(i, 'nom', e.target.value)}
                  />
                  <input
                    placeholder="Type (col…)"
                    value={pt.type}
                    onChange={e => updatePoint(i, 'type', e.target.value)}
                  />
                  <input
                    placeholder="km"
                    type="number"
                    value={pt.dist_km}
                    onChange={e => updatePoint(i, 'dist_km', e.target.value)}
                  />
                  <input
                    placeholder="alt m"
                    type="number"
                    value={pt.alt}
                    onChange={e => updatePoint(i, 'alt', e.target.value)}
                  />
                  <span style={{fontSize:'0.65rem', color: pt.source === 'gpx' ? 'var(--accent3)' : 'var(--text2)', minWidth:'28px', textAlign:'center'}} title={pt.source === 'gpx' ? 'Waypoint GPX' : 'Sommet auto-détecté'}>
                    {pt.source === 'gpx' ? '📍' : '⛰'}
                  </span>
                  <button className="btn-remove" onClick={() => removePoint(i)}>✕</button>
                </div>
              ))}
            </div>

            <button className="btn-add-point" onClick={addPoint}>+ Ajouter un point</button>
          </div>

          {/* Bouton générer */}
          <div className="section">
            <button
              className="btn-generate"
              onClick={startGeneration}
              disabled={!canGenerate || (jobStatus && jobStatus !== 'done' && jobStatus !== 'error')}
            >
              {jobStatus === 'osm' || jobStatus === 'svg' || jobStatus === 'pending'
                ? '⏳ Génération en cours…'
                : '⚡ Générer l\'affiche SVG'}
            </button>

            {jobStatus && jobStatus !== 'done' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${jobProgress}%` }} />
                </div>
                <p className="progress-label">{statusLabels[jobStatus] || jobStatus}</p>
              </div>
            )}

            {jobStatus === 'done' && svgUrl && (
              <a href={svgUrl} download="affiche_course.svg" className="btn-download" style={{ textAlign: 'center' }}>
                ⬇️ Télécharger le SVG
              </a>
            )}
          </div>

        </aside>

        {/* ══ PANNEAU PRÉVISUALISATION ══ */}
        <main className="preview-panel">
          <div style={{
            fontFamily: 'var(--font-title)',
            fontSize: '0.75rem',
            letterSpacing: '0.15em',
            color: 'var(--text2)',
            textTransform: 'uppercase',
            alignSelf: 'flex-start',
          }}>
            Prévisualisation
          </div>

          {!svgContent && !jobStatus && (
            <div className="preview-placeholder">
              Remplissez le formulaire et cliquez sur<br/>
              <strong>Générer l'affiche SVG</strong><br/><br/>
              La génération prend 1 à 2 minutes<br/>
              (téléchargement des données cartographiques)
            </div>
          )}

          {jobStatus && jobStatus !== 'done' && jobStatus !== 'error' && (
            <div className="preview-placeholder pulsing">
              {statusLabels[jobStatus]}
            </div>
          )}

          {jobStatus === 'error' && (
            <div className="alert" style={{ maxWidth: 500 }}>
              ❌ Erreur lors de la génération. Vérifiez que le backend est accessible et réessayez.
            </div>
          )}

          {svgContent && (
            <div className="preview-svg-container fade-in">
              <div dangerouslySetInnerHTML={{ __html: svgContent }} />
            </div>
          )}

          {svgContent && (
            <div style={{ fontSize: '0.78rem', color: 'var(--text2)', textAlign: 'center' }}>
              Le SVG contient <strong style={{ color: 'var(--accent)' }}>3 calques séparés</strong> (noir / vert / rouge).<br/>
              Dans Cricut Design Space : importer → séparer les calques → affecter un stylo à chacun.
            </div>
          )}
        </main>

      </div>
    </div>
  )
}
