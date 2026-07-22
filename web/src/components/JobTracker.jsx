import { useState } from 'react'
import { useStore } from '../store.jsx'

// Panel flotante (esquina inferior izquierda) con la cola de generaciones: qué se mandó y qué ya llegó.
export default function JobTracker() {
  const { jobs, clearJobs } = useStore()
  const [open, setOpen] = useState(true)
  if (!jobs.length) return null

  const active = jobs.filter((j) => !j.done).length
  const anyDone = jobs.some((j) => j.done)

  const icon = (j) => (j.errors?.length ? '⚠' : j.done ? '✓' : '⏳')
  const kindIcon = (k) => (k === 'vid' ? '🎬' : '🖼')

  return (
    <div className="jobtracker">
      <div className="jt-head" onClick={() => setOpen((o) => !o)}>
        <span>{active ? `⏳ Generando (${active})` : '✓ Cola de generación'}</span>
        <span className="spacer" />
        {anyDone && <button className="jt-clear" onClick={(e) => { e.stopPropagation(); clearJobs() }}>limpiar</button>}
        <button className="jt-min">{open ? '▾' : '▴'}</button>
      </div>
      {open && (
        <div className="jt-body">
          {jobs.map((j) => {
            const pct = j.total ? Math.round((j.done_count / j.total) * 100) : 0
            return (
              <div className="jt-row" key={j.jid}>
                <div className="jt-line">
                  <span className="jt-ico">{icon(j)}</span>
                  <span className="jt-label">{kindIcon(j.kind)} {j.label}</span>
                  <span className="spacer" />
                  <span className="jt-count">{j.done_count}/{j.total}</span>
                </div>
                <div className="jt-bar"><div className="jt-fill" style={{ width: (j.done ? 100 : pct) + '%' }} /></div>
                {j.errors?.length ? <div className="jt-err">⚠ {j.errors.join(' · ')}</div> : null}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
