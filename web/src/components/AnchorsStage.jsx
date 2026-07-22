import { useState } from 'react'
import { useStore } from '../store.jsx'
import { api, outUrl } from '../api'

// Etapa PERSONAJES / SETS: previews de las hojas de anclaje + generar faltantes.
export default function AnchorsStage() {
  const { project, flash } = useStore()
  const [busy, setBusy] = useState(false)
  const ids = project?.anchors || []

  const generate = async (only) => {
    setBusy(true)
    const r = await api.runStage('anchors', only ? { only } : {})
    setBusy(false)
    flash(project?.paid ? 'Anchors: ' + JSON.stringify(r.result) : 'DRY: se generarían las faltantes (poné el server en PAGA para gastar)')
    setTimeout(() => window.location.reload(), 800) // refrescar previews
  }
  const upload = async (id, file) => {
    if (!file) return
    const r = await api.anchorUpload(id, file)
    if (r.ok) { flash(`Ancla "${id}" reemplazada (manual)`); setTimeout(() => window.location.reload(), 500) }
    else flash('Error al subir')
  }

  return (
    <div>
      <div className="row" style={{ marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>Personajes / Sets ({ids.length} anclas)</h3>
        <div className="spacer" />
        <button className="pri" disabled={busy} onClick={() => generate(null)}>Generar anclas faltantes</button>
      </div>
      <div className="grid">
        {ids.map((id) => (
          <div className="card" key={id}>
            <h4>{id}</h4>
            <img src={outUrl('anchors/' + id + '.png')} alt={id}
                 onError={(e) => { e.currentTarget.style.opacity = .15; e.currentTarget.alt = 'no generada'; }} />
            <button style={{ width: '100%', marginTop: 6 }} disabled={busy} onClick={() => generate([id])}>Regenerar</button>
            <label className="pri" style={{ display: 'block', textAlign: 'center', marginTop: 6, padding: '6px', borderRadius: 8, cursor: 'pointer' }}>
              ⬆ Reemplazar con imagen local
              <input type="file" accept="image/*" hidden onChange={(e) => upload(id, e.target.files[0])} />
            </label>
          </div>
        ))}
      </div>
      <p className="muted" style={{ marginTop: 10 }}>
        Las anclas son la base de consistencia (STYLE LOCK). Editarlas finamente se hace regenerando; los
        keyframes se anclan a ellas. En DRY no se gasta.
      </p>
    </div>
  )
}
