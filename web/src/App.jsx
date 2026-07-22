import { useState } from 'react'
import { useStore } from './store.jsx'
import AnchorsStage from './components/AnchorsStage.jsx'
import KeyframesStage from './components/KeyframesStage.jsx'
import ShotsStage from './components/ShotsStage.jsx'
import MasterStage from './components/MasterStage.jsx'

const STAGES = [
  { id: 'anchors', label: 'Personajes / Sets' },
  { id: 'keyframes', label: 'Keyframes' },
  { id: 'shots', label: 'Shots' },
  { id: 'master', label: 'Master' },
]

export default function App() {
  const { project, toRegen, ready, toast } = useStore()
  const [stage, setStage] = useState('shots')
  const stale = toRegen.stale?.length || 0
  const pending = toRegen.pending?.length || 0

  return (
    <div className="app">
      <header className="header">
        <div className="brand">Video Pipeline <small>· {project?.name || '…'}</small></div>
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
        <button className="go" disabled={!ready.ready} onClick={() => setStage('master')}
                title={ready.ready ? 'Listo para armar el master' : 'Faltan tomas aprobadas o hay STALE'}>
          GO · Master
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
        {stage === 'master' && <MasterStage />}
      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
