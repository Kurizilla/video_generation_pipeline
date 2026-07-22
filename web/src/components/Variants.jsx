import { outUrl } from '../api'

// Grilla de variantes generadas (imagen o video), cada una aceptable. items = [{path,note}] o [path].
export default function Variants({ items, kind, onAccept }) {
  if (!items || !items.length) return <div className="muted">— sin variantes generadas —</div>
  return (
    <div className="variants">
      {items.map((v, i) => {
        const path = typeof v === 'string' ? v : v.path
        const note = typeof v === 'object' ? v.note || '' : ''
        return (
          <div className="v" key={i}>
            {kind === 'video'
              ? <video src={outUrl(path)} controls loop />
              : <img src={outUrl(path)} alt="" />}
            {note && <div className="muted">{note}</div>}
            <button className="pri" style={{ width: '100%', marginTop: 4 }} onClick={() => onAccept(path)}>✔ aceptar</button>
          </div>
        )
      })}
    </div>
  )
}
