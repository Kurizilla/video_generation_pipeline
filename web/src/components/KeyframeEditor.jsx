import { useEffect, useRef, useState } from 'react'
import { api, outUrl, pollJob } from '../api'
import { useStore } from '../store.jsx'
import { fileToDataUrl, pasteImage } from '../lib/refs'
import MaskCanvas from './MaskCanvas.jsx'
import Variants from './Variants.jsx'

export default function KeyframeEditor({ stem }) {
  const { refresh, flash } = useStore()
  const [meta, setMeta] = useState(null)
  const [deps, setDeps] = useState(null)
  const [mode, setMode] = useState('A')
  const [comment, setComment] = useState('')
  const [instruction, setInstruction] = useState('')
  const [hifi, setHifi] = useState(true)
  const [refs, setRefs] = useState([])
  const [nvar, setNvar] = useState(2)
  const [variants, setVariants] = useState([])
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const maskRef = useRef(null)

  const load = async () => {
    setMeta(await api.kfMeta(stem)); setDeps(await api.depsFor(stem))
    setVariants((await api.kfVariants(stem)).variants); setRefs([]); setComment(''); setInstruction(''); setStatus('')
  }
  useEffect(() => { load() }, [stem])

  const addFiles = async (files) => { const urls = await Promise.all([...files].map(fileToDataUrl)); setRefs((r) => [...r, ...urls]) }
  const doPaste = async () => { const d = await pasteImage(); if (d) setRefs((r) => [...r, d]); else flash('Sin imagen en el portapapeles') }

  const regen = async () => {
    const body = { stem, mode, num_variants: nvar, ref_images: refs }
    if (mode === 'A') { body.comment = comment; body.hifi = hifi }
    else {
      if (maskRef.current?.isEmpty()) { flash('Dibujá una máscara primero'); return }
      body.instruction = instruction; body.mask_png = maskRef.current.getMaskPng(); body.strength = 0.6
    }
    setBusy(true); setStatus('Encolando…')
    const r = await api.kfRegen(body)
    if (r.error) { setBusy(false); setStatus('Error: ' + r.error); return }
    if (r.dry) { setBusy(false); setStatus(`DRY (no gasta): ${r.model} ~$${r.est_cost_usd}`); return }
    await pollJob('kf', r.job_id, async (s) => {
      const errs = s.errors || []
      setStatus(`Generando ${s.variants?.length || 0}/${s.total}${errs.length ? ' · ⚠ ' + errs.join(' | ') : ''}${s.done ? ' · listo' : ''}`)
      setVariants((await api.kfVariants(stem)).variants)
    })
    setBusy(false)
  }

  const accept = async (variant_path) => {
    const r = await api.kfAccept({ stem, variant_path, note: mode === 'A' ? comment : instruction })
    if (r.ok) {
      const d = r.deps
      flash(`Keyframe aceptado. ${d.explain}` + (d.marked_stale?.length ? ` · STALE: ${d.marked_stale.join(', ')}` : ''))
      await refresh(); await load()
    }
  }
  const revert = async (v) => { const r = await api.kfRevert({ stem, v }); if (r.ok) { flash('Revertido a v' + v); await refresh(); await load() } }
  const uploadLocal = async (file) => {
    if (!file) return
    setStatus('Subiendo imagen local…')
    const r = await api.kfUpload(stem, file)
    if (r.ok) { const d = r.deps; flash(`Keyframe reemplazado (manual). ${d?.explain || ''}` + (d?.marked_stale?.length ? ` · STALE: ${d.marked_stale.join(', ')}` : '')); await refresh(); await load() }
    else setStatus('Error: ' + (r.error || 'upload'))
  }

  if (!meta) return <div className="muted">Cargando…</div>
  const img = outUrl(meta.file)

  return (
    <div>
      <div className="row">
        <h3 style={{ margin: 0 }}>{stem}</h3>
        {deps?.is_seam
          ? <span className="st stale">◆ EMPALME — alimenta tomas {deps.tomas.join(' y ')}</span>
          : <span className="muted">alimenta toma {deps?.tomas?.join(',')}</span>}
      </div>
      {meta.last_error?.length ? <div className="banner">⚠ Último intento con error: {meta.last_error.join(' | ')}</div> : null}

      <div className="tabs">
        <button className={mode === 'A' ? 'active' : ''} onClick={() => setMode('A')}>Modo A · Regen completa</button>
        <button className={mode === 'B' ? 'active' : ''} onClick={() => setMode('B')}>Modo B · Máscara</button>
      </div>

      {mode === 'A' ? (
        <>
          <img src={img} className="kfimg" alt={stem} />
          <div className="lbl">Comentario (se suma al prompt original)</div>
          <textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)}
                    placeholder="el niño de atrás debe ser un niño, como en la referencia" />
          <label className="row" style={{ marginTop: 4 }}><input type="checkbox" checked={hifi} onChange={(e) => setHifi(e.target.checked)} /> alta fidelidad (+$)</label>
        </>
      ) : (
        <>
          <MaskCanvas ref={maskRef} src={img} />
          <div className="lbl">Instrucción para la región enmascarada</div>
          <textarea rows={2} value={instruction} onChange={(e) => setInstruction(e.target.value)}
                    placeholder="corregí SOLO este extra: niño con guayabera, estilizado" />
        </>
      )}

      <div className="lbl">Referencias / recortes</div>
      <div className="refstrip">
        {refs.map((r, i) => <img key={i} src={r} title="quitar" onClick={() => setRefs((x) => x.filter((_, j) => j !== i))} />)}
      </div>
      <div className="row">
        <label className="pri" style={{ padding: '6px 12px', borderRadius: 8, cursor: 'pointer' }}>+ Subir<input type="file" accept="image/*" multiple hidden onChange={(e) => addFiles(e.target.files)} /></label>
        <button onClick={doPaste}>+ Pegar recorte</button>
        <span className="spacer" />
        <span className="muted">variantes</span><input type="number" min="1" max="3" value={nvar} onChange={(e) => setNvar(+e.target.value)} style={{ width: 56 }} />
        <button className="pri" disabled={busy} onClick={regen}>Generar</button>
      </div>
      <div className="muted" style={{ marginTop: 4 }}>{status}</div>

      <div className="lbl">Reemplazo manual (subí tu propia imagen)</div>
      <label className="pri" style={{ padding: '6px 12px', borderRadius: 8, cursor: 'pointer', display: 'inline-block' }}>
        ⬆ Reemplazar con imagen local
        <input type="file" accept="image/*" hidden onChange={(e) => uploadLocal(e.target.files[0])} />
      </label>
      <span className="muted" style={{ marginLeft: 8 }}>se versiona (revertible) y marca STALE los videos dependientes</span>

      <div className="lbl">Variantes generadas (histórico)</div>
      <Variants items={variants} kind="image" onAccept={accept} />

      <div className="lbl">Versiones</div>
      <div className="muted">
        {(meta.versions || []).map((v) => (
          <span key={v.v} style={{ marginRight: 10 }}>
            v{v.v} {v.v === meta.current ? '◀' : <button style={{ padding: '2px 8px' }} onClick={() => revert(v.v)}>revertir</button>}
          </span>
        ))}
      </div>
    </div>
  )
}
