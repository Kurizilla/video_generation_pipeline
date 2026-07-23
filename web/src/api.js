// Cliente de la API del pipeline (pipeline.server). Base configurable por VITE_API_BASE.
export const API = import.meta.env.VITE_API_BASE || 'http://localhost:8788'

const asJson = (r) => r.json()
const get = (p) => fetch(API + p).then(asJson)
const post = (p, body) =>
  fetch(API + p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) }).then(asJson)
// multipart (uploads): nunca revienta — si el server devuelve error/no-JSON, resuelve a {error}
const postForm = async (p, form) => {
  let r
  try { r = await fetch(API + p, { method: 'POST', body: form }) }
  catch (e) { return { error: 'red: ' + (e?.message || e) } }
  const text = await r.text()
  try { return JSON.parse(text) }
  catch { return { error: `HTTP ${r.status}: ${(text || r.statusText).slice(0, 200)}` } }
}

// URL de un asset generado servido por el backend (/out/<ruta relativa a project.out>)
export const outUrl = (path) => `${API}/out/${path}?t=${Date.now()}`

export const api = {
  // --- multi-proyecto ---
  projects: () => get('/api/projects'),
  projectSelect: (name) => post('/api/projects/select', { name }),
  projectCreate: (body) => post('/api/projects/create', body),
  batchPlan: () => get('/api/batch/plan'),
  batchRun: () => post('/api/batch/run', {}),

  // --- lectura / estado ---
  project: () => get('/api/project'),
  tomas: () => get('/api/tomas'),
  toRegen: () => get('/api/deps/to-regen'),
  assemblyReady: () => get('/api/assembly-ready'),
  graph: () => get('/api/deps/graph'),
  depsFor: (stem) => get('/api/deps/for/' + stem),
  kfMeta: (stem) => get('/api/kf/' + stem),
  vidMeta: (key) => get('/api/vid/' + key),
  kfVariants: (stem) => get('/api/kf/variants/' + stem),
  vidVariants: (key) => get('/api/vid/variants/' + key),

  // --- etapas (disparo) ---
  runStage: (name, body) => post('/api/stage/' + name, body),
  assemble: (body) => post('/api/assemble', body),

  // --- edición keyframe (async job) ---
  kfRegen: (body) => post('/api/kf/regen', body),
  kfJob: (jid) => get('/api/kf/status/' + jid),
  kfAccept: (body) => post('/api/kf/accept', body),
  kfRevert: (body) => post('/api/kf/revert', body),

  // --- edición video (async job) ---
  vidRegen: (body) => post('/api/vid/regen', body),
  vidJob: (jid) => get('/api/vid/status/' + jid),
  vidAccept: (body) => post('/api/vid/accept', body),
  vidRevert: (body) => post('/api/vid/revert', body),
  vidSetStatus: (body) => post('/api/vid/set-status', body),

  // --- cola global de jobs (tracker) ---
  jobs: () => get('/api/jobs'),
  jobsClear: () => post('/api/jobs/clear'),
  job: (jid) => get('/api/job/' + jid),

  // --- post-producción: 4 pasos discretos ---
  postState: () => get('/api/post/state'),
  postUnify: () => post('/api/post/unify'),
  postVoPrep: (body) => post('/api/post/vo/prep', body),
  postVoDistribute: (body) => post('/api/post/vo/distribute', body),
  postVo: (body) => post('/api/post/vo', body),
  postSubs: () => post('/api/post/subs'),
  postSubsEdit: (content) => fetch(API + '/api/post/subs', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) }).then(asJson),
  postMaster: (body) => post('/api/post/master', body),
  postRevert: (body) => post('/api/post/revert', body),

  // --- reemplazo MANUAL por archivo local (upload) ---
  kfUpload: (stem, file) => { const f = new FormData(); f.append('stem', stem); f.append('file', file); return postForm('/api/kf/upload', f) },
  vidUpload: (key, file) => { const f = new FormData(); f.append('key', key); f.append('file', file); return postForm('/api/vid/upload', f) },
  anchorUpload: (id, file) => { const f = new FormData(); f.append('id', id); f.append('file', file); return postForm('/api/anchor/upload', f) },
}

// Hook util: sondea un job async (regen de imagen/video) hasta done, con callback por tick.
export async function pollJob(kind, jid, onTick, intervalMs = 3500) {
  const fetcher = kind === 'kf' ? api.kfJob : api.vidJob
  while (true) {
    let s
    try { s = await fetcher(jid) } catch { await sleep(intervalMs); continue }
    onTick(s)
    if (s.error || s.done) return s
    await sleep(intervalMs)
  }
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
