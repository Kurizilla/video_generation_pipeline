import { useEffect, useRef, useState } from 'react'
import { api, outUrl, pollJob } from '../api'
import { useStore } from '../store.jsx'
import Variants from './Variants.jsx'

const MODELS = {
  seedance: 'bytedance/seedance-2.0/image-to-video',
  kling: 'fal-ai/kling-video/v3/pro/image-to-video',
}

export default function ShotPanel({ tkey }) {
  const { refresh, flash } = useStore()
  const [meta, setMeta] = useState(null)
  const [prompt, setPrompt] = useState('')
  const [comment, setComment] = useState('')
  const [engine, setEngine] = useState('seedance')
  const [dur, setDur] = useState(5)
  const [res, setRes] = useState('1080p')
  const [cfg, setCfg] = useState(0.5)
  const [nvar, setNvar] = useState(2)
  const [variants, setVariants] = useState([])
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)

  const tkeyRef = useRef(tkey); tkeyRef.current = tkey   // para que los polls en curso sepan si seguís en esta toma

  const load = async () => {
    const m = await api.vidMeta(tkey); setMeta(m)
    setPrompt(m.prompt || ''); setComment(''); setStatus(''); setBusy(false)   // reset al cambiar de toma
    setEngine((m.model || '').includes('kling') ? 'kling' : 'seedance')
    setDur(+(m.params?.duration || 5)); setRes(m.params?.resolution || '1080p')
    setVariants((await api.vidVariants(tkey)).variants)
  }
  useEffect(() => { load() }, [tkey])

  // Dispara y LIBERA: apenas queda encolado el job, se re-habilita el botón para poder mandar más tomas
  // en paralelo. El seguimiento vive en la cola global (esquina ↙); este panel solo refresca sus variantes.
  const regen = async () => {
    const myKey = tkey
    const overrides = { prompt, duration: String(dur), model: MODELS[engine] }
    if (engine === 'kling') overrides.cfg_scale = cfg; else overrides.resolution = res
    setBusy(true); setStatus('Encolando…')
    const r = await api.vidRegen({ key: myKey, comment, overrides, num_variants: nvar })
    setBusy(false)   // encolado (o error): el botón vuelve a estar disponible enseguida
    if (r.error) { setStatus('Error: ' + r.error); return }
    if (r.dry) { setStatus(`DRY (no gasta): ${r.model} ~$${r.est_cost_usd}`); return }
    if (myKey === tkeyRef.current) setStatus(`En cola: ${r.total} variante(s) · seguí el progreso en la cola ↙`)
    pollJob('vid', r.job_id, async (s) => {
      if (myKey !== tkeyRef.current) return   // cambiaste de toma: no piso tu vista actual
      const errs = s.errors || []
      setStatus(`Generando ${s.variants?.length || 0}/${s.total}${errs.length ? ' · ⚠ ' + errs.join(' | ') : ''}${s.done ? ' · listo' : ''}`)
      setVariants((await api.vidVariants(myKey)).variants)
    })
  }

  const accept = async (variant_path) => { const r = await api.vidAccept({ key: tkey, variant_path, note: comment }); if (r.ok) { flash('Video aprobado v' + r.current); await refresh(); await load() } }
  const setStatusVal = async (st) => { await api.vidSetStatus({ key: tkey, status: st }); flash('Video: ' + st); await refresh(); await load() }
  const revert = async (v) => { const r = await api.vidRevert({ key: tkey, v }); if (r.ok) { flash('Revertido a v' + v); await refresh(); await load() } }
  const uploadLocal = async (file) => {
    if (!file) return
    setStatus('Subiendo video local…')
    const r = await api.vidUpload(tkey, file)
    if (r.ok) { flash('Video reemplazado (manual) v' + r.current); await refresh(); await load() }
    else setStatus('Error: ' + (r.error || 'upload'))
  }

  if (!meta) return <div className="muted">Cargando…</div>
  const hasVideo = (meta.versions || []).length > 0

  return (
    <div>
      <div className="row">
        <h3 style={{ margin: 0 }}>{tkey}</h3>
        <span className={`st ${meta.status}`}>{meta.status}</span>
        {meta.content_blocked && <span className="muted">· Seedance rechaza esta toma (caras) → Kling</span>}
      </div>
      {meta.last_error?.length ? <div className="banner">⚠ Último intento con error: {meta.last_error.join(' | ')}</div> : null}

      <div className="row" style={{ alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1 }}>
          {hasVideo ? <video src={outUrl('shots_raw/' + tkey + '.mp4')} controls loop style={{ width: '100%', borderRadius: 8 }} />
                    : <div className="muted">(sin video — regenerá)</div>}
        </div>
        <div style={{ width: 160 }}>
          <div className="lbl">START / END (guardrails)</div>
          <img className="thumb" src={outUrl(meta.start_ref)} alt="start" style={{ marginBottom: 6 }} />
          <img className="thumb" src={outUrl(meta.end_ref)} alt="end" />
        </div>
      </div>

      <div className="lbl">Prompt de video (editable)</div>
      <textarea rows={4} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
      <div className="lbl">Comentario extra</div>
      <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="menos drift de cámara; mantené quieto al extra de la izquierda" />

      <div className="row" style={{ marginTop: 8, flexWrap: 'wrap' }}>
        <span className="muted">modelo</span>
        <select value={engine} onChange={(e) => setEngine(e.target.value)} style={{ width: 150 }}>
          <option value="seedance">Seedance 2.0</option>
          <option value="kling">Kling v3 pro</option>
        </select>
        <span className="muted">dur</span><input type="number" min="3" max="15" value={dur} onChange={(e) => setDur(+e.target.value)} style={{ width: 56 }} />
        {engine === 'seedance'
          ? (<><span className="muted">res</span><select value={res} onChange={(e) => setRes(e.target.value)} style={{ width: 90 }}><option>480p</option><option>720p</option><option>1080p</option><option>4k</option></select></>)
          : (<><span className="muted">cfg</span><input type="number" min="0" max="1" step="0.1" value={cfg} onChange={(e) => setCfg(+e.target.value)} style={{ width: 56 }} /></>)}
        <span className="muted">variantes</span><input type="number" min="1" max="3" value={nvar} onChange={(e) => setNvar(+e.target.value)} style={{ width: 56 }} />
        <button className="pri" disabled={busy} onClick={regen}>Regenerar video</button>
      </div>
      <div className="muted" style={{ marginTop: 4 }}>{status}</div>

      <div className="lbl">Reemplazo manual (subí tu propio video)</div>
      <label className="pri" style={{ padding: '6px 12px', borderRadius: 8, cursor: 'pointer', display: 'inline-block' }}>
        ⬆ Reemplazar con video local
        <input type="file" accept="video/*" hidden onChange={(e) => uploadLocal(e.target.files[0])} />
      </label>
      <span className="muted" style={{ marginLeft: 8 }}>se versiona (revertible) y queda aprobado</span>

      <div className="lbl">Variantes (histórico)</div>
      <Variants items={variants} kind="video" onAccept={accept} />

      <div className="row" style={{ marginTop: 8 }}>
        <button className="pri" onClick={() => setStatusVal('approved')}>✔ Aprobar</button>
        <button className="bad" onClick={() => setStatusVal('rejected')}>✗ Rechazar</button>
        <span className="spacer" />
        <span className="muted">
          {(meta.versions || []).map((v) => (
            <span key={v.v} style={{ marginLeft: 8 }}>v{v.v}{v.v === meta.current ? '◀' : <button style={{ padding: '2px 8px' }} onClick={() => revert(v.v)}>rev</button>}</span>
          ))}
        </span>
      </div>
    </div>
  )
}
