import { useEffect, useState } from 'react'
import { useStore } from '../store.jsx'
import ShotPanel from './ShotPanel.jsx'

// Etapa SHOTS: lista de tomas (con estado) → panel de regen de video a la derecha.
export default function ShotsStage() {
  const { tomas } = useStore()
  const [sel, setSel] = useState(null)
  useEffect(() => { if (!sel && tomas.length) setSel(tomas[0].key) }, [tomas, sel])

  return (
    <div className="work">
      <div className="list">
        <div className="lbl">Tomas ({tomas.length})</div>
        {tomas.map((t) => (
          <div key={t.key} className={`item ${sel === t.key ? 'active' : ''}`} onClick={() => setSel(t.key)}>
            <span>toma{String(t.n).padStart(2, '0')} {t.model?.includes('kling') ? '· kling' : ''}</span>
            <span className={`st ${t.video_status}`}>{t.video_status}</span>
          </div>
        ))}
      </div>
      <div className="detail">{sel ? <ShotPanel tkey={sel} /> : <div className="muted">Elegí una toma.</div>}</div>
    </div>
  )
}
