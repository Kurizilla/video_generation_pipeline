import { useState } from 'react'
import { api } from './api'
import { useStore } from './store.jsx'
import AnchorsStage from './components/AnchorsStage.jsx'
import KeyframesStage from './components/KeyframesStage.jsx'
import ShotsStage from './components/ShotsStage.jsx'
import PostProdStage from './components/PostProdStage.jsx'
import JobTracker from './components/JobTracker.jsx'

const STAGES = [
  { id: 'anchors', label: 'Personajes / Sets' },
  { id: 'keyframes', label: 'Keyframes' },
  { id: 'shots', label: 'Shots' },
  { id: 'post', label: 'Post-producción' },
]

export default function App() {
  const { project, projects, selectProject, loadProjects, toRegen, ready, toast } = useStore()
  const [stage, setStage] = useState('shots')
  const stale = toRegen.stale?.length || 0
  const pending = toRegen.pending?.length || 0

  const onPick = async (e) => {
    const v = e.target.value
    if (v === '__new__') {
      const name = window.prompt('Nombre del proyecto nuevo:')
      if (name) { const r = await api.projectCreate({ name }); if (r.error) alert(r.error); else { await loadProjects(); await selectProject(name) } }
      return
    }
    if (v && v !== project?.name) selectProject(v)
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">Video Pipeline</div>
        <select className="projsel" value={project?.name || ''} onChange={onPick} title="Proyecto activo">
          {!project && <option value="">…</option>}
          {projects.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}
          <option value="__new__">+ nuevo proyecto…</option>
        </select>
        <nav className="stepper">
          {STAGES.map((s) => (
            <div key={s.id}
                 className={`step ${s.id === stage ? 'active' : ''} ${s.id === 'shots' && stale > 0 ? 'warn' : ''}`}
                 onClick={() => setStage(s.id)}>
              <span className="dot" />{s.label}
            </div>
          ))}
        </nav>
        <div className="spacer" />
        <span className={`badge ${project?.paid ? 'paid' : 'dry'}`}>{project?.paid ? 'PAGA' : 'DRY'}</span>
        {stale > 0 && <span className="badge stale">{stale} stale</span>}
        {pending > 0 && <span className="badge">{pending} sin video</span>}
        <button className="go" onClick={() => setStage('post')}
                title="Post-producción: unificar → VO → subtítulos → master">
          GO · Post-producción
        </button>
      </header>

      <div className="body">
        {stale > 0 && (
          <div className="banner">
            <b>{stale} video(s) STALE</b> (un keyframe cambió después de generarse): {toRegen.stale.join(', ')}
            {' '}— regeneralos en la etapa <b>Shots</b> antes de armar el master.
          </div>
        )}
        {stage === 'anchors' && <AnchorsStage />}
        {stage === 'keyframes' && <KeyframesStage />}
        {stage === 'shots' && <ShotsStage />}
        {stage === 'post' && <PostProdStage />}
      </div>

      {toast && <div className="toast">{toast}</div>}
      <JobTracker />
    </div>
  )
}
