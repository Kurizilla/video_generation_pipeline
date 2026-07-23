import { useEffect, useRef, useState } from 'react'
import { api, outUrl } from '../api'
import { useStore } from '../store.jsx'

const CHIP = { ready: 'st ok', stale: 'st stale', pending: 'st pending' }
const LABEL = { ready: 'listo', stale: 'STALE', pending: 'pendiente' }

// Espera a que un job (job_id) termine, sondeando; devuelve el result.
async function waitJob(jid, onTick) {
  while (true) {
    let s; try { s = await api.job(jid) } catch { await new Promise((r) => setTimeout(r, 2500)); continue }
    onTick?.(s)
    if (s.done || s.error) return s
    await new Promise((r) => setTimeout(r, 2500))
  }
}

function StepCard({ title, num, step, state, children, onRun, runLabel, busy, note }) {
  const s = state?.status || 'pending'
  return (
    <div className="card" style={{ marginBottom: 14 }}>
      <div className="row" style={{ alignItems: 'center' }}>
        <b>PASO {num} · {title}</b>
        <span className={CHIP[s]} style={{ marginLeft: 8 }}>{LABEL[s]}</span>
        <span className="spacer" />
        {onRun && <button className="pri" disabled={busy} onClick={onRun}>{busy ? '…' : runLabel}</button>}
      </div>
      {note && <div className="muted" style={{ marginTop: 4, color: s === 'stale' ? '#ffcf9e' : undefined }}>{note}</div>}
      {children}
    </div>
  )
}

function Versions({ step, versions, current, onRevert }) {
  if (!versions?.length) return null
  return (
    <div className="muted" style={{ marginTop: 6 }}>
      versiones: {versions.map((v) => (
        <span key={v.v} style={{ marginRight: 8 }}>
          v{v.v}{v.v === current ? '◀' : <button style={{ padding: '1px 7px' }} onClick={() => onRevert(step, v.v)}>rev</button>}
        </span>
      ))}
    </div>
  )
}

export default function PostProdStage() {
  const { flash } = useStore()
  const [st, setSt] = useState(null)
  const [busy, setBusy] = useState('')          // qué paso está corriendo
  const [voLines, setVoLines] = useState(null)  // [{n, text, t0, dur, cached}]
  const [voice, setVoice] = useState('')
  const [voEst, setVoEst] = useState(null)      // {to_synth, chars, est_cost_usd, paid}
  const [prose, setProse] = useState('')        // guion en prosa para distribuir con IA
  const [distributing, setDistributing] = useState(false)
  const [srt, setSrt] = useState('')
  const timer = useRef(null)

  const loadState = async () => { try { setSt(await api.postState()) } catch { /* API caída */ } }
  const loadVoPrep = async () => {
    const r = await api.postVoPrep({})
    if (r.error) { setVoLines([]); setVoEst(null); return }
    setVoLines(r.plan.map((p) => ({ ...p }))); setVoEst(r); if (!voice) setVoice(r.voice_id || '')
  }

  useEffect(() => {
    loadState(); loadVoPrep()
    timer.current = setInterval(loadState, 3000)
    return () => clearInterval(timer.current)
  }, [])

  // cargar el SRT actual cuando cambia la versión de subs
  useEffect(() => {
    const p = st?.subs?.artifact?.path
    if (!p) { setSrt(''); return }
    fetch(outUrl(p)).then((r) => r.text()).then(setSrt).catch(() => {})
  }, [st?.subs?.artifact?.path, st?.subs?.current])

  const runJob = async (label, fire, after) => {
    setBusy(label)
    const r = await fire()
    if (r.error) { setBusy(''); flash('Error: ' + r.error); return }
    if (r.gated) { setBusy(''); flash('Bloqueado: ' + r.reason); await loadState(); return }
    if (r.dry) { setBusy(''); flash(`DRY (no gastó): ${r.to_synth} línea(s) · ~$${r.est_cost_usd}. Poné el server en PAGA para generar la VO.`); return }
    if (!r.job_id) { setBusy(''); await loadState(); after?.(r); return }
    const done = await waitJob(r.job_id)
    setBusy('')
    const res = done.result || {}
    if (done.errors?.length || res.error) flash('Error: ' + (res.error || done.errors.join(' | ')))
    else if (res.gated) flash('Bloqueado: ' + res.reason)
    else if (res.dry) flash(`DRY (no gastó): ~$${res.est_cost_usd}. Poné el server en PAGA.`)
    else flash(`${label}: listo ✓`)
    await loadState(); after?.(res)
  }

  const revert = async (step, v) => { const r = await api.postRevert({ step, v }); if (r.ok) { flash(`${step} → v${v}`); await loadState() } }

  // IA: reparte la prosa en una línea por toma (según qué pasa y cuánto dura cada toma) y puebla las casillas
  const distribute = async () => {
    if (!prose.trim()) return
    setDistributing(true)
    const r = await api.postVoDistribute({ prose })
    setDistributing(false)
    if (r.error) { flash('Error: ' + r.error); return }
    setVoLines((ls) => (ls || []).map((l) => (r.lines[String(l.n)] != null ? { ...l, text: r.lines[String(l.n)], cached: false } : l)))
    flash('Guion distribuido por IA — revisá y ajustá antes de generar la VO')
  }

  if (!st) return <div className="muted">Cargando post-producción…</div>
  const A = (k) => st[k]?.artifact

  return (
    <div style={{ maxWidth: 860 }}>
      <h3 style={{ marginTop: 0 }}>Post-producción</h3>
      <p className="muted">Cuatro pasos independientes y reintentables. Cada uno versiona su salida; si un
        insumo aguas arriba cambia, el paso siguiente queda <b>STALE</b> y hay que rehacerlo.</p>

      {/* PASO 1 — UNIFICAR */}
      <StepCard num={1} title="Unificar videos" step="unify" state={st.unify} busy={busy === 'Unificar'}
        runLabel="Unificar videos" onRun={() => runJob('Unificar', () => api.postUnify())}
        note={st.unify.status === 'stale' ? 'Un shot cambió después de unificar — re-unificá.' : 'Concatena los shots aprobados en orden (cortes duros, respeta seams). Sin audio.'}>
        {A('unify') && <>
          <video src={outUrl(A('unify').path)} controls style={{ width: '100%', borderRadius: 8, marginTop: 8 }} />
          <div className="muted" style={{ marginTop: 4 }}>duración {A('unify').dur}s · {A('unify').cuts?.length} cortes</div>
        </>}
        <Versions step="unify" versions={st.unify.versions} current={st.unify.current} onRevert={revert} />
      </StepCard>

      {/* PASO 2 — VO */}
      <StepCard num={2} title="Voz en off" step="vo" state={st.vo} busy={busy === 'VO'}
        runLabel="Generar VO" onRun={() => runJob('VO', () => api.postVo({ lines: linesOverride(voLines), voice_id: voice }), loadVoPrep)}
        note={st.vo.status === 'stale' ? 'El video unificado cambió — regenerá la VO.' : 'Una línea por toma, sintetizada con ElevenLabs y timeada a cada toma. Editá el guion abajo.'}>
        {st.unify.status === 'pending'
          ? <div className="muted" style={{ marginTop: 8 }}>Unificá primero (paso 1): la VO se timea al video unificado.</div>
          : <>
            <div className="row" style={{ marginTop: 8 }}>
              <span className="muted">voz (ElevenLabs)</span>
              <input value={voice} onChange={(e) => setVoice(e.target.value)} style={{ width: 240 }} placeholder="voice_id" />
              <span className="spacer" />
              <button onClick={loadVoPrep} disabled={busy}>Estimar costo</button>
            </div>
            {voEst && <div className="muted" style={{ marginTop: 4 }}>
              {voEst.to_synth} línea(s) a sintetizar · {voEst.chars} chars · <b>~${voEst.est_cost_usd}</b>
              {' · '}{voEst.paid ? 'server en PAGA' : 'server en DRY (no gasta)'}
            </div>}

            <div className="lbl">Distribuir un guion en prosa con IA</div>
            <textarea rows={4} value={prose} onChange={(e) => setProse(e.target.value)}
              placeholder="Pegá acá la narración en prosa; la IA la reparte en una línea por toma según qué pasa y cuánto dura cada toma. Revisás y ajustás antes de generar la VO." />
            <div className="row" style={{ marginTop: 4 }}>
              <span className="muted">la IA usa título · acción · duración de cada toma (requiere key LLM + server en PAGA)</span>
              <span className="spacer" />
              <button className="pri" disabled={distributing || !prose.trim()} onClick={distribute}>
                {distributing ? 'Distribuyendo…' : '✦ Distribuir con IA'}</button>
            </div>

            <div className="lbl">Guion por toma (editable)</div>
            {(voLines || []).map((l, i) => (
              <div key={l.n} className="row" style={{ alignItems: 'flex-start', marginBottom: 4 }}>
                <span className="muted" style={{ width: 72, paddingTop: 8 }}>toma {String(l.n).padStart(2, '0')}<br /><small>{fmt(l.t0)}</small></span>
                <textarea rows={2} value={l.text}
                  onChange={(e) => setVoLines((ls) => ls.map((x, j) => j === i ? { ...x, text: e.target.value } : x))} />
                <span className="st" style={{ marginTop: 8 }}>{l.cached ? '♻ cache' : l.skip ? '—' : '$'}</span>
              </div>
            ))}
          </>}
        <Versions step="vo" versions={st.vo.versions} current={st.vo.current} onRevert={revert} />
      </StepCard>

      {/* PASO 3 — SUBTÍTULOS */}
      <StepCard num={3} title="Subtítulos" step="subs" state={st.subs} busy={busy === 'Subtítulos'}
        runLabel="Generar subtítulos" onRun={() => runJob('Subtítulos', () => api.postSubs())}
        note={st.subs.status === 'stale' ? 'La VO cambió — regenerá los subtítulos.' : 'Verbatim desde el script temporizado de la VO. Editables abajo.'}>
        {st.vo.status === 'pending'
          ? <div className="muted" style={{ marginTop: 8 }}>Generá la VO primero (paso 2).</div>
          : A('subs') && <>
            <textarea rows={8} value={srt} onChange={(e) => setSrt(e.target.value)} style={{ marginTop: 8, fontFamily: 'monospace', fontSize: 12 }} />
            <div className="row" style={{ marginTop: 4 }}>
              <a href={outUrl(A('subs').path)} download>descargar .srt</a>
              <span className="spacer" />
              <button onClick={async () => { const r = await api.postSubsEdit(srt); if (r.ok) { flash('Subtítulos guardados v' + r.v); await loadState() } }}>Guardar edición</button>
            </div>
          </>}
        <Versions step="subs" versions={st.subs.versions} current={st.subs.current} onRevert={revert} />
      </StepCard>

      {/* PASO 4 — MASTER */}
      <StepCard num={4} title="Armar final" step="master" state={st.master} busy={busy === 'Master'}
        runLabel="Armar final" onRun={st.master.can_build ? () => runJob('Master', () => api.postMaster({})) : null}
        note={st.master.can_build ? 'Une video unificado + VO + subtítulos (+música) en el master.'
          : 'Se habilita cuando los pasos 1–3 estén en «listo» y ninguno STALE.'}>
        {!st.master.can_build && <div className="muted" style={{ marginTop: 4 }}>
          Falta: {['unify', 'vo', 'subs'].filter((k) => st[k].status !== 'ready').map((k) => `${k} (${LABEL[st[k].status]})`).join(', ') || '—'}
        </div>}
        {A('master') && <video src={outUrl(A('master').path)} controls style={{ width: '100%', borderRadius: 8, marginTop: 8 }} />}
        <Versions step="master" versions={st.master.versions} current={st.master.current} onRevert={revert} />
      </StepCard>
    </div>
  )
}

const fmt = (s) => (s == null ? '' : `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`)
// {n: texto} solo con lo editado (para no pisar project.json salvo lo que tocaste)
const linesOverride = (ls) => (ls || []).reduce((o, l) => { o[l.n] = l.text; return o }, {})
