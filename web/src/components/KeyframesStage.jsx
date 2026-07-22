import { useEffect, useState } from 'react'
import { api } from '../api'
import KeyframeEditor from './KeyframeEditor.jsx'

// Etapa KEYFRAMES: lista seam-aware (stems) → editor A/B a la derecha.
export default function KeyframesStage() {
  const [graph, setGraph] = useState({})
  const [sel, setSel] = useState(null)

  useEffect(() => { api.graph().then((g) => { setGraph(g); setSel((s) => s || Object.keys(g)[0]) }) }, [])

  const stems = Object.keys(graph)
  return (
    <div className="work">
      <div className="list">
        <div className="lbl">Keyframes ({stems.length})</div>
        {stems.map((stem) => (
          <div key={stem} className={`item ${sel === stem ? 'active' : ''}`} onClick={() => setSel(stem)}>
            <span>{stem}</span>
            {graph[stem].is_seam && <span className="st stale" title={`empalme: tomas ${graph[stem].tomas.join(',')}`}>◆ seam</span>}
          </div>
        ))}
      </div>
      <div className="detail">
        {sel ? <KeyframeEditor stem={sel} /> : <div className="muted">Elegí un keyframe.</div>}
      </div>
    </div>
  )
}
