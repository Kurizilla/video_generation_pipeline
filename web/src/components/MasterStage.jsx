import { useState } from 'react'
import { api, outUrl } from '../api'
import { useStore } from '../store.jsx'

// Etapa MASTER ([GO]): gate (sin STALE + todas aprobadas) → unificación (concat + VO + subs + música).
export default function MasterStage() {
  const { ready, flash, refresh } = useStore()
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  const go = async () => {
    setBusy(true)
    const r = await api.assemble({})
    setBusy(false)
    if (r.gated) { flash('Gate: faltan aprobar / hay STALE'); return }
    if (r.dry) { flash('DRY: el master real requiere PAGA (VO). En DRY solo se planifica.'); return }
    if (r.error) { flash('Error: ' + r.error); return }
    setDone(true); flash('Master armado ✓'); refresh()
  }

  return (
    <div style={{ maxWidth: 900 }}>
      <h3>Master final (unificación → VO → subtítulos → pegado)</h3>
      {!ready.ready ? (
        <div className="banner">
          Todavía no se puede armar: {ready.stale?.length ? <b>STALE: {ready.stale.join(', ')}. </b> : null}
          {ready.pending?.length ? <b>Sin aprobar/video: {ready.pending.join(', ')}.</b> : null}
          {' '}Resolvé eso en Keyframes/Shots.
        </div>
      ) : (
        <div className="card">
          <p className="muted">Todas las tomas aprobadas y sin STALE. Al armar: concat de crudos (cortes duros,
            respeta seams) + VO por toma + subtítulos verbatim quemados + música opcional.</p>
          <button className="go" disabled={busy} onClick={go}>{busy ? 'Armando…' : 'GO · Armar master'}</button>
        </div>
      )}
      {(done || ready.ready) && (
        <div style={{ marginTop: 14 }}>
          <div className="lbl">master.mp4</div>
          <video src={outUrl('master.mp4')} controls style={{ width: '100%', borderRadius: 8 }}
                 onError={(e) => { e.currentTarget.style.display = 'none' }} />
        </div>
      )}
    </div>
  )
}
