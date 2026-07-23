import { Fragment, useEffect, useState } from 'react'
import { api } from '../api'
import { useStore } from '../store.jsx'
import ShotPanel from './ShotPanel.jsx'

// Barra de inserción estilo PowerPoint: gap fino entre tomas; al pasar el mouse aparece un "+" verde.
function InsertBar({ pos, onAdd, busy }) {
  return (
    <div className="insbar" title={`Insertar toma nueva en la posición ${pos + 1}`}
         onClick={() => !busy && onAdd(pos)}>
      <span className="plus">＋</span>
    </div>
  )
}

// Etapa SHOTS: lista de tomas (con estado) + "+" verde entre ellas → panel de regen a la derecha.
export default function ShotsStage() {
  const { tomas, flash } = useStore()
  const [sel, setSel] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (!sel && tomas.length) setSel(tomas[0].key) }, [tomas, sel])

  const addAt = async (pos) => {
    if (!window.confirm(`¿Insertar una toma NUEVA en la posición ${pos + 1}? Crea 2 keyframes nuevos (que tenés que definir y generar) y el video.`)) return
    setBusy(true)
    const r = await api.tlAddToma({ after: pos })
    setBusy(false)
    if (r.error) { flash('Error: ' + r.error); return }
    flash(r.effect + ' — recargando…'); setTimeout(() => window.location.reload(), 1200)
  }

  return (
    <div className="work">
      <div className="list">
        <div className="lbl">Tomas ({tomas.length})</div>
        <InsertBar pos={0} onAdd={addAt} busy={busy} />
        {tomas.map((t, i) => (
          <Fragment key={t.key}>
            <div className={`item ${sel === t.key ? 'active' : ''}`} onClick={() => setSel(t.key)}>
              <span>toma{String(t.n).padStart(2, '0')} {t.model?.includes('kling') ? '· kling' : ''}</span>
              <span className={`st ${t.video_status}`}>{t.video_status}</span>
            </div>
            <InsertBar pos={i + 1} onAdd={addAt} busy={busy} />
          </Fragment>
        ))}
      </div>
      <div className="detail">{sel ? <ShotPanel tkey={sel} /> : <div className="muted">Elegí una toma.</div>}</div>
    </div>
  )
}
